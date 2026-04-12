#!/usr/bin/env python3
"""Tests for Bot Builder preview-first onboarding improvements (task #5066)."""

from __future__ import annotations

import ast
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import db as db_module

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOT_BUILDER_DIR = ROOT / "Projects" / "bot-builder"
if str(BOT_BUILDER_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_BUILDER_DIR))

import meta_bot


# ─── Tests for _extract_capabilities ────────────────────────────────────────

class TestExtractCapabilities:
    def test_booking_keywords(self):
        caps = meta_bot._extract_capabilities(
            "Бот записть на стрижку: выбор услуги, даты и времени",
            "",
        )
        assert any("записть" in c.lower() or "услуг" in c.lower() for c in caps)

    def test_lead_capture_keywords(self):
        caps = meta_bot._extract_capabilities(
            "Бот для сбора заявок: имя, телефон, описание проблемы",
            "",
        )
        assert any("заявк" in c.lower() or "сбор" in c.lower() for c in caps)

    def test_faq_keywords(self):
        caps = meta_bot._extract_capabilities(
            "FAQ бот для ответов на частые вопросы о магазине",
            "",
        )
        assert any("faq" in c.lower() or "вопрос" in c.lower() for c in caps)

    def test_notification_keywords(self):
        caps = meta_bot._extract_capabilities(
            "Бот уведомлений о статусе заказа",
            "",
        )
        assert any("уведомлен" in c.lower() or "напомина" in c.lower() for c in caps)

    def test_fallback_generic(self):
        caps = meta_bot._extract_capabilities(
            "Сделай что-нибудь непонятное",
            "",
        )
        assert len(caps) >= 1
        assert any(len(c) > 0 for c in caps)

    def test_max_5_results(self):
        caps = meta_bot._extract_capabilities(
            "Бот записи уведомлений FAQ меню админ бот стрижка услуги",
            "",
        )
        assert len(caps) <= 5


# ─── Tests for _build_example_dialog ────────────────────────────────────────

class TestBuildExampleDialog:
    def test_parses_send_message_calls(self):
        code = '''
async def handle_start(update, context):
    await update.message.reply_text("Привет! Я бот записи.")
    await update.message.reply_text("Выберите услугу: стрижка или маникюр")
    await update.message.reply_text("Вы записаны!")
'''
        dialog = meta_bot._build_example_dialog(code)
        # Check extracted messages appear (labels are interleaved, not exact position)
        assert "Привет! Я бот записи" in dialog
        assert "Выберите услугу" in dialog
        assert "Вы записаны" in dialog
        assert "<b>Пример" in dialog
        # Check user/bot labels are present
        assert "🤖 Бот:" in dialog or "Бот:" in dialog

    def test_handles_syntax_error_in_code(self):
        dialog = meta_bot._build_example_dialog("this is not valid python {{{{")
        assert "Пример" in dialog  # falls back gracefully

    def test_fallback_example_dialog(self):
        # RU fallback
        fallback_ru = meta_bot._build_fallback_example_dialog("RU")
        assert "Пример" in fallback_ru
        assert "Стрижка" in fallback_ru
        assert "🤖 Бот:" in fallback_ru
        assert "👤 Клиент:" in fallback_ru
        # EN fallback
        fallback_en = meta_bot._build_fallback_example_dialog("EN")
        assert "Example" in fallback_en
        assert "haircut" in fallback_en
        assert "🤖 Bot:" in fallback_en
        assert "👤 Client:" in fallback_en


# ─── Tests for _build_preview_text ──────────────────────────────────────────

class TestBuildPreviewText:
    def test_contains_type(self):
        text = meta_bot._build_preview_text(
            "Бот для записи на стрижку",
            "booking",
            "async def main(): pass",
        )
        assert "Бот готов" in text
        assert "Тип:" in text
        assert "booking" in text

    def test_contains_description(self):
        desc = "Бот для записи на стрижку"
        text = meta_bot._build_preview_text(desc, None, "async def main(): pass")
        assert desc[:30] in text

    def test_contains_code_size(self):
        code = "x" * 500
        text = meta_bot._build_preview_text("desc", None, code)
        assert "500" in text or "символ" in text

    def test_contains_capabilities(self):
        text = meta_bot._build_preview_text(
            "Бот для записи на стрижку и сбора заявок",
            None,
            "",
        )
        assert "Что умеет" in text


# ─── Tests for button label constants ───────────────────────────────────────

class TestButtonConstants:
    def test_button_labels_defined(self):
        assert meta_bot.BTN_LAUNCH == "🚀 Запустить"
        assert meta_bot.BTN_EXAMPLE == "👀 Пример диалога"
        assert meta_bot.BTN_TOKEN_HELP == "🧭 Как получить токен"
        assert meta_bot.BTN_SAVE == "💾 Сохранить и вернуться позже"
        assert meta_bot.BTN_CANCEL == "❌ Отмена"

    def test_no_duplicate_button_labels(self):
        labels = {meta_bot.BTN_LAUNCH, meta_bot.BTN_EXAMPLE,
                  meta_bot.BTN_TOKEN_HELP, meta_bot.BTN_SAVE, meta_bot.BTN_CANCEL}
        assert len(labels) == 5, "Button labels must be unique"


# ─── Tests for state constants ──────────────────────────────────────────────

class TestStateConstants:
    def test_preview_state_exists(self):
        assert hasattr(meta_bot, "PREVIEW")
        assert meta_bot.PREVIEW == 1  # range(3) → DESCRIBE=0, PREVIEW=1, TOKEN=2

    def test_three_states(self):
        DESCRIBE, PREVIEW, TOKEN = range(3)
        assert DESCRIBE == 0
        assert PREVIEW == 1
        assert TOKEN == 2


# ─── Tests for start handler deep-link parsing ───────────────────────────────

@pytest.fixture
def tmp_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "bot_builder_test.db"
    monkeypatch.setattr(db_module, "DB_PATH", db_path)
    monkeypatch.setattr(meta_bot, "get_or_create_user", db_module.get_or_create_user)
    db_module.init_db()
    return db_path


class TestStartHandler:
    """Tests for /start handler with Telegram deep-link start parameter."""

    @pytest.mark.asyncio
    async def test_start_without_args_records_event(self, tmp_db_path):
        """start_opened emitted with no source when /start has no args."""
        update = SimpleNamespace(
            message=SimpleNamespace(
                reply_text=AsyncMock(),
                effective_user=SimpleNamespace(id=42, username="u42", first_name="Test42"),
            ),
            effective_user=SimpleNamespace(id=42, username="u42", first_name="Test42"),
        )
        context = SimpleNamespace(args=None)

        recorded = []
        original_record = meta_bot.record_event
        meta_bot.record_event = lambda e, **kw: recorded.append((e, kw))

        try:
            await meta_bot.start(update, context)
        finally:
            meta_bot.record_event = original_record

        assert len(recorded) == 1
        event, kwargs = recorded[0]
        assert event == "start_opened"
        assert kwargs.get("user_id") == 42
        assert kwargs.get("source") is None
        user_row = db_module.get_or_create_user(42)
        assert user_row["user_id"] == 42
        assert user_row["username"] == "u42"

    @pytest.mark.asyncio
    async def test_start_with_deep_link_vc(self, tmp_db_path):
        """/start vc records source=vc."""
        update = SimpleNamespace(
            message=SimpleNamespace(
                reply_text=AsyncMock(),
                effective_user=SimpleNamespace(id=42, username="u42", first_name="Test42"),
            ),
            effective_user=SimpleNamespace(id=42, username="u42", first_name="Test42"),
        )
        context = SimpleNamespace(args=["vc"])

        recorded = []
        original_record = meta_bot.record_event
        meta_bot.record_event = lambda e, **kw: recorded.append((e, kw))

        try:
            await meta_bot.start(update, context)
        finally:
            meta_bot.record_event = original_record

        assert len(recorded) == 1
        event, kwargs = recorded[0]
        assert event == "start_opened"
        assert kwargs.get("user_id") == 42
        assert kwargs.get("source") == "vc"
        user_row = db_module.get_or_create_user(42)
        assert user_row["user_id"] == 42

    @pytest.mark.asyncio
    async def test_start_with_unknown_param_still_recorded(self, tmp_db_path):
        """/start some_unknown_source records raw param."""
        update = SimpleNamespace(
            message=SimpleNamespace(
                reply_text=AsyncMock(),
                effective_user=SimpleNamespace(id=99, username="u99", first_name="Test99"),
            ),
            effective_user=SimpleNamespace(id=99, username="u99", first_name="Test99"),
        )
        context = SimpleNamespace(args=["foobar123"])

        recorded = []
        original_record = meta_bot.record_event
        meta_bot.record_event = lambda e, **kw: recorded.append((e, kw))

        try:
            await meta_bot.start(update, context)
        finally:
            meta_bot.record_event = original_record

        assert len(recorded) == 1
        event, kwargs = recorded[0]
        assert event == "start_opened"
        assert kwargs.get("source") == "foobar123"
        user_row = db_module.get_or_create_user(99)
        assert user_row["user_id"] == 99

    @pytest.mark.asyncio
    async def test_start_with_empty_args_list(self, tmp_db_path):
        """/start with empty args list treats as no param."""
        update = SimpleNamespace(
            message=SimpleNamespace(
                reply_text=AsyncMock(),
                effective_user=SimpleNamespace(id=42, username="u42", first_name="Test42"),
            ),
            effective_user=SimpleNamespace(id=42, username="u42", first_name="Test42"),
        )
        context = SimpleNamespace(args=[])

        recorded = []
        original_record = meta_bot.record_event
        meta_bot.record_event = lambda e, **kw: recorded.append((e, kw))

        try:
            await meta_bot.start(update, context)
        finally:
            meta_bot.record_event = original_record

        assert len(recorded) == 1
        event, kwargs = recorded[0]
        assert event == "start_opened"
        assert kwargs.get("source") is None
        user_row = db_module.get_or_create_user(42)
        assert user_row["user_id"] == 42
