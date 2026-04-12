#!/usr/bin/env python3
"""Regression tests for Bot Builder timeout/error handling."""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
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

import generator
import meta_bot


class DummyMessage:
    def __init__(self, text: str):
        self.text = text
        self.reply_text = AsyncMock()


class DummyUpdate:
    def __init__(self, text: str):
        self.message = DummyMessage(text)
        self.effective_message = self.message
        self.effective_user = SimpleNamespace(id=123, username="user", first_name="Test", language_code="ru")
        self.effective_chat = SimpleNamespace(id=456)


class DummyContext:
    def __init__(self):
        self.user_data = {}
        self.error = None


def test_generate_bot_code_returns_structured_timeout_error(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout", 0))

    monkeypatch.setattr(generator.subprocess, "run", fake_run)

    result = asyncio.run(generator.generate_bot_code("Сделай бота для записи на маникюр"))

    assert result["ok"] is False
    assert result["error_type"] == "timeout"
    assert result["code"] == ""
    assert "слишком долго" in result["error"]


def test_generate_bot_code_success_path_still_returns_ok(monkeypatch):
    payload = {"ok": True, "text": "from telegram.ext import Application\nBOT_TOKEN = 'x'\napp = Application.builder().token(BOT_TOKEN).build()\napp.run_polling()"}

    def fake_run(*args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(generator.subprocess, "run", fake_run)

    result = asyncio.run(generator.generate_bot_code("Сделай простого FAQ бота"))

    assert result["ok"] is True
    assert result["error"] is None
    assert result["error_type"] is None
    assert "Application.builder" in result["code"]


def test_generator_system_prompt_documents_english_fallback():
    assert "fallback to English" in generator.SYSTEM_PROMPT
    assert "fallback to Russian" not in generator.SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_receive_description_shows_timeout_retry_message(monkeypatch):
    update = DummyUpdate("Сделай бота для записи на маникюр с уведомлениями и каталогом услуг")
    context = DummyContext()

    async def _fake_generate(description):
        return {
            "ok": False,
            "error_type": "timeout",
            "error": "Генерация заняла слишком долго (> 120 сек).",
            "code": "",
            "template": None,
        }

    monkeypatch.setattr(
        meta_bot,
        "generate_bot_code",
        _fake_generate,
    )

    state = await meta_bot.receive_description(update, context)

    assert state == meta_bot.DESCRIBE
    assert context.user_data["description"].startswith("Сделай бота")
    calls = update.message.reply_text.await_args_list
    assert len(calls) == 2
    assert "Генерирую бота" in calls[0].args[0]
    assert "Генерация заняла слишком долго" in calls[1].args[0]
    assert "Выберите действие ниже или отправьте новое описание" in calls[1].args[0]


@pytest.mark.asyncio
async def test_handle_application_error_replies_and_clears_context(caplog):
    update = DummyUpdate("test")
    context = DummyContext()
    context.user_data["description"] = "pending"
    context.error = RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="bot-builder"):
        await meta_bot.handle_application_error(update, context)

    assert context.user_data == {}
    update.message.reply_text.assert_awaited_once()
    assert "внутренняя ошибка" in update.message.reply_text.await_args.args[0].lower()
    assert "update_info" in caplog.text
    assert "text_len" in caplog.text
    assert "text_hash" in caplog.text
    assert "chat_id" in caplog.text
    assert "user_id" in caplog.text
    assert "'test'" not in caplog.text


def test_safe_update_info_uses_metadata_not_raw_text():
    update = DummyUpdate("секретный текст")

    info = meta_bot._safe_update_info(update)

    assert info["user_id"] == 123
    assert info["chat_id"] == 456
    assert info["text_len"] == len("секретный текст")
    assert len(info["text_hash"]) == 8
    assert "text" not in info


def test_main_runs_polling_with_drop_pending_updates(monkeypatch):
    polling_kwargs = {}

    class FakeApplication:
        def run_polling(self, **kwargs):
            polling_kwargs.update(kwargs)

    monkeypatch.setattr(meta_bot, "BOT_TOKEN", "123:abc")
    monkeypatch.setattr(meta_bot, "build_application", lambda: FakeApplication())

    meta_bot.main()

    assert polling_kwargs == {"drop_pending_updates": True}


def test_build_application_registers_error_handler(monkeypatch):
    added_error_handlers = []

    class FakeApplication:
        def add_handler(self, handler):
            return None

        def add_error_handler(self, handler):
            added_error_handlers.append(handler)

    class FakeBuilder:
        def token(self, token):
            return self

        def build(self):
            return FakeApplication()

    class FakeApplicationFactory:
        @staticmethod
        def builder():
            return FakeBuilder()

    monkeypatch.setattr(meta_bot, "Application", FakeApplicationFactory)

    app = meta_bot.build_application()

    assert app is not None
    assert added_error_handlers == [meta_bot.handle_application_error]
