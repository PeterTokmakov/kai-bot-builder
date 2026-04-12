#!/usr/bin/env python3
"""Tests for orphan text fallback handler (task #5298)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOT_BUILDER_DIR = ROOT / "Projects" / "bot-builder"
if str(BOT_BUILDER_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_BUILDER_DIR))

import meta_bot


@pytest.fixture(autouse=True)
def record_event_spy(monkeypatch):
    """Prevent tests from writing to the production bot_builder.db."""
    recorded: list[tuple[str, dict]] = []
    monkeypatch.setattr(meta_bot, "record_event", lambda e, **kw: recorded.append((e, kw)))
    return recorded


@pytest.fixture
def generate_bot_code_spy(monkeypatch):
    """Stub out generate_bot_code so tests don't call the real API."""
    async def stub(description):
        return {"ok": True, "code": "# stub\nawait update.message.reply_text('hello')", "template": None}
    monkeypatch.setattr(meta_bot, "generate_bot_code", stub)
    return stub


@pytest.fixture
def validate_bot_harness_spy(monkeypatch):
    """Stub out validate_bot_harness."""
    def stub(name, code):
        return [
            {"check": "syntax", "passed": True, "detail": ""},
            {"check": "imports", "passed": True, "detail": ""},
            {"check": "handler_structure", "passed": True, "detail": ""},
            {"check": "no_credentials", "passed": True, "detail": ""},
            {"check": "no_bare_except", "passed": True, "detail": ""},
            {"check": "error_handling", "passed": True, "detail": ""},
            {"check": "no_html_injection", "passed": True, "detail": ""},
        ]
    monkeypatch.setattr(meta_bot, "validate_bot_harness", stub)
    return stub


class TestOrphanTextFallback:
    """Tests for _orphan_text_fallback handler."""

    @pytest.mark.asyncio
    async def test_orphan_text_gets_reply(self, record_event_spy):
        """Unmatched plain text should always get a helpful reply."""
        reply_calls = []
        update = SimpleNamespace(
            message=SimpleNamespace(
                text="Привет как дела",
                reply_text=AsyncMock(side_effect=lambda *a, **kw: reply_calls.append((a, kw))),
                effective_user=SimpleNamespace(id=7777, language_code="ru"),
            ),
            effective_user=SimpleNamespace(id=7777, language_code="ru"),
        )
        context = SimpleNamespace(user_data={})

        await meta_bot._orphan_text_fallback(update, context)

        assert len(reply_calls) == 1
        text = reply_calls[0][0][0]
        # Either /start redirect for cmd messages, or "describe more" for short text
        assert "символ" in text or "/start" in text or "подробнее" in text.lower()
        assert len(record_event_spy) == 1

    @pytest.mark.asyncio
    async def test_orphan_text_records_event(self, record_event_spy, generate_bot_code_spy, validate_bot_harness_spy):
        """Orphan text should emit a telemetry event with safe metadata."""
        update = SimpleNamespace(
            message=SimpleNamespace(
                text="Просто текст без контекста",
                reply_text=AsyncMock(),
                effective_user=SimpleNamespace(id=8888, language_code="ru"),
            ),
            effective_user=SimpleNamespace(id=8888),
        )
        context = SimpleNamespace(user_data={})

        await meta_bot._orphan_text_fallback(update, context)

        assert len(record_event_spy) >= 1
        event, kwargs = record_event_spy[0]
        assert event == "orphan_text"
        assert kwargs.get("user_id") == 8888
        assert "text_len" in kwargs
        assert "text_hash" in kwargs
        assert kwargs["text_len"] == len("Просто текст без контекста")

    @pytest.mark.asyncio
    async def test_orphan_text_hash_is_truncated_safe(self, record_event_spy, generate_bot_code_spy, validate_bot_harness_spy):
        """Hash is 8 hex chars — no raw text exposed."""
        update = SimpleNamespace(
            message=SimpleNamespace(
                text="Привет мир это длинный тест который не должен попасть в логи",
                reply_text=AsyncMock(),
                effective_user=SimpleNamespace(id=9999, language_code="ru"),
            ),
            effective_user=SimpleNamespace(id=9999, language_code="ru"),
        )
        context = SimpleNamespace(user_data={})

        await meta_bot._orphan_text_fallback(update, context)

        assert len(record_event_spy) >= 1
        event, kwargs = record_event_spy[0]
        assert event == "orphan_text"
        assert len(kwargs["text_hash"]) == 8
        assert all(c in "0123456789abcdef" for c in kwargs["text_hash"])
        assert "text" not in kwargs
        assert "content" not in kwargs

    @pytest.mark.asyncio
    async def test_orphan_text_does_not_leak_full_content(self, record_event_spy, generate_bot_code_spy, validate_bot_harness_spy):
        """Telemetry records length and hash, not raw content."""
        long_text = "x" * 300
        update = SimpleNamespace(
            message=SimpleNamespace(
                text=long_text,
                reply_text=AsyncMock(),
                effective_user=SimpleNamespace(id=9999, language_code="ru"),
            ),
            effective_user=SimpleNamespace(id=9999, language_code="ru"),
        )
        context = SimpleNamespace(user_data={})

        await meta_bot._orphan_text_fallback(update, context)

        assert len(record_event_spy) >= 1
        event, kwargs = record_event_spy[0]
        assert event == "orphan_text"
        assert kwargs["text_len"] == 300
        assert len(kwargs["text_hash"]) == 8
        assert "text" not in kwargs

    @pytest.mark.asyncio
    async def test_short_text_guides_to_longer_description(self, record_event_spy):
        """Text shorter than MIN_DESCRIPTION should get helpful guidance."""
        reply_texts = []
        update = SimpleNamespace(
            message=SimpleNamespace(
                text="привет",
                reply_text=AsyncMock(side_effect=lambda t, **_: reply_texts.append(t)),
                effective_user=SimpleNamespace(id=2222, language_code="ru"),
            ),
            effective_user=SimpleNamespace(id=2222, language_code="ru"),
        )
        context = SimpleNamespace()

        await meta_bot._orphan_text_fallback(update, context)

        assert len(reply_texts) == 1
        text = reply_texts[0]
        assert "20" in text or "символ" in text.lower()
        assert len(record_event_spy) == 1

    @pytest.mark.asyncio
    async def test_long_orphan_text_treated_as_new_description(self, generate_bot_code_spy, validate_bot_harness_spy):
        """Orphan text >= 20 chars should trigger new bot description flow."""
        reply_texts = []
        update = SimpleNamespace(
            message=SimpleNamespace(
                text="Бот для записи на стрижку — выбор услуги, даты и времени",
                reply_text=AsyncMock(side_effect=lambda t, **_: reply_texts.append(t)),
                effective_user=SimpleNamespace(id=5555, language_code="ru"),
            ),
            effective_user=SimpleNamespace(id=5555, language_code="ru"),
        )
        context = SimpleNamespace(user_data={})

        await meta_bot._orphan_text_fallback(update, context)

        # Should have received generation message, not /start redirect
        assert any("Генерирую" in t or "Готово" in t or "Бот готов" in t for t in reply_texts)

    @pytest.mark.asyncio
    async def test_orphan_text_reply_guides_user(self, record_event_spy):
        """Fallback reply should guide user toward providing a valid description."""
        reply_texts = []
        update = SimpleNamespace(
            message=SimpleNamespace(
                text="что-то непонятное",
                reply_text=AsyncMock(side_effect=lambda t, **_: reply_texts.append(t)),
                effective_user=SimpleNamespace(id=1111, language_code="ru"),
            ),
            effective_user=SimpleNamespace(id=1111, language_code="ru"),
        )
        context = SimpleNamespace()

        await meta_bot._orphan_text_fallback(update, context)

        assert len(reply_texts) == 1
        text = reply_texts[0]
        # Short text < 20 chars gets a "describe more" reply, not /start
        assert "символ" in text.lower() or "20" in text or "подробнее" in text.lower()
        assert len(record_event_spy) == 1
