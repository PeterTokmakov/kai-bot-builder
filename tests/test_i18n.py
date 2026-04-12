#!/usr/bin/env python3
"""Tests for EN/RU runtime language selection (task #5444)."""

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


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_update(user_id=42, text="test", language_code="ru"):
    """Create a minimal mock Update with language support."""
    return SimpleNamespace(
        message=SimpleNamespace(
            text=text,
            reply_text=AsyncMock(),
            effective_user=SimpleNamespace(
                id=user_id, username="test", first_name="Test", language_code=language_code
            ),
        ),
        effective_user=SimpleNamespace(
            id=user_id, username="test", first_name="Test", language_code=language_code
        ),
    )


def make_context(**kwargs):
    ctx = SimpleNamespace(user_data=kwargs.get("user_data", {}))
    ctx.chat_data = kwargs.get("chat_data", {})
    return ctx


# ─── Locale detection ─────────────────────────────────────────────────────────

class TestGetLocale:
    def test_ru_user_returns_ru(self):
        update = make_update(language_code="ru")
        assert meta_bot._get_locale(update) == "RU"

    def test_en_user_returns_en(self):
        update = make_update(language_code="en")
        assert meta_bot._get_locale(update) == "EN"

    def test_no_language_code_returns_en(self):
        update = make_update(language_code=None)
        assert meta_bot._get_locale(update) == "EN"

    def test_unknown_lang_returns_en(self):
        update = make_update(language_code="fr")
        assert meta_bot._get_locale(update) == "EN"

    def test_uk_returns_en(self):
        update = make_update(language_code="uk")
        assert meta_bot._get_locale(update) == "EN"


# ─── Pricing display ──────────────────────────────────────────────────────────

class TestPricingDisplay:
    def test_ru_returns_rub(self):
        assert meta_bot._pricing_display("RU") == "990₽/мес"

    def test_en_returns_usd(self):
        assert meta_bot._pricing_display("EN") == "$10/mo"

    def test_unknown_defaults_to_en(self):
        assert meta_bot._pricing_display("XX") == "$10/mo"


# ─── Text layer completeness ─────────────────────────────────────────────────

class TestTextLayerCompleteness:
    """Verify every locale has all required keys."""

    REQUIRED_KEYS = [
        "start_title", "start_prompt", "desc_too_short", "generating", "timeout",
        "gen_error", "validation_error", "preview_title", "preview_choose",
        "launch_excellent", "launch_token_ask", "token_help_title", "token_help_steps",
        "token_ask_in_token_state", "save_title", "save_body", "save_nothing",
        "invalid_token", "paywall_limit_exhausted", "paywall_pre_limit",
        "paywall_last_free_deployed", "paywall_one_left", "success_bots_left",
        "deploying", "deploy_failed", "subscribe_cta_label",
        "invoice_title", "invoice_desc", "invoice_label", "payment_success",
        "help_title", "help_body", "share_text", "cancel",
        "mybots_empty", "mybots_title", "stop_usage", "stop_not_found", "stopped",
        "delete_usage", "delete_not_found", "deleted",
        "orphan_too_short", "resume_no_draft", "internal_error",
        "example_label", "example_bot_label", "example_client_label", "example_fallback",
        "cap_booking", "cap_lead", "cap_faq", "cap_notification",
        "cap_catalog", "cap_admin", "cap_interaction", "cap_salon", "cap_generic",
        "template_custom",
    ]

    def test_ru_has_all_keys(self):
        missing = [k for k in self.REQUIRED_KEYS if k not in meta_bot.TEXTS["RU"]]
        assert not missing, f"Missing RU keys: {missing}"

    def test_en_has_all_keys(self):
        missing = [k for k in self.REQUIRED_KEYS if k not in meta_bot.TEXTS["EN"]]
        assert not missing, f"Missing EN keys: {missing}"

    def test_no_duplicate_keys(self):
        for locale, texts in meta_bot.TEXTS.items():
            keys = list(texts.keys())
            assert len(keys) == len(set(keys)), f"Duplicate keys in {locale}"


# ─── Start handler locale ────────────────────────────────────────────────────

class TestStartHandlerLocale:
    """Verify start() uses correct locale for user-facing text."""

    @pytest.mark.asyncio
    async def test_ru_start_text(self, monkeypatch):
        update = make_update(language_code="ru", text="")
        context = SimpleNamespace(args=[])

        recorded = []
        monkeypatch.setattr(meta_bot, "record_event", lambda e, **kw: recorded.append(e))
        monkeypatch.setattr(meta_bot, "get_or_create_user", lambda *a, **kw: {})

        await meta_bot.start(update, context)

        reply_text = update.message.reply_text.await_args_list[0][0][0]
        assert "Bot Builder" in reply_text
        assert "бесплатно" in reply_text
        assert "990₽" in reply_text  # RU price display

    @pytest.mark.asyncio
    async def test_en_start_text(self, monkeypatch):
        update = make_update(language_code="en", text="")
        context = SimpleNamespace(args=[])

        recorded = []
        monkeypatch.setattr(meta_bot, "record_event", lambda e, **kw: recorded.append(e))
        monkeypatch.setattr(meta_bot, "get_or_create_user", lambda *a, **kw: {})

        await meta_bot.start(update, context)

        reply_text = update.message.reply_text.await_args_list[0][0][0]
        assert "Bot Builder" in reply_text
        assert "free" in reply_text.lower()
        assert "$10" in reply_text  # EN price display


# ─── Preview text locale ──────────────────────────────────────────────────────

class TestPreviewTextLocale:
    def test_ru_preview(self):
        text = meta_bot._build_preview_text(
            "Бот для записи на стрижку", "booking", "async def main(): pass", locale="RU"
        )
        assert "Бот готов" in text or "✨" in text
        assert "Что умеет" in text
        assert "990₽" not in text  # preview doesn't show pricing

    def test_en_preview(self):
        text = meta_bot._build_preview_text(
            "Haircut booking bot", "booking", "async def main(): pass", locale="EN"
        )
        assert "ready" in text.lower() or "✨" in text
        assert "What it can do" in text


# ─── Example dialog locale ────────────────────────────────────────────────────

class TestExampleDialogLocale:
    def test_ru_fallback(self):
        text = meta_bot._build_example_dialog("not valid python", locale="RU")
        assert "Пример" in text
        assert "Стрижка" in text

    def test_en_fallback(self):
        text = meta_bot._build_example_dialog("not valid python", locale="EN")
        assert "Example" in text
        assert "haircut" in text.lower()


# ─── Capabilities locale ─────────────────────────────────────────────────────

class TestCapabilitiesLocale:
    def test_ru_capabilities(self):
        caps = meta_bot._extract_capabilities(
            "Бот записи на стрижку", "", locale="RU"
        )
        assert any("запись" in c.lower() or "услуг" in c.lower() for c in caps)

    def test_en_capabilities(self):
        caps = meta_bot._extract_capabilities(
            "Haircut booking bot", "", locale="EN"
        )
        assert any("booking" in c.lower() or "service" in c.lower() for c in caps)


# ─── Paywall pricing locale ───────────────────────────────────────────────────

class TestPaywallPricingLocale:
    @pytest.mark.asyncio
    async def test_subscribe_cta_ru(self):
        keyboard = meta_bot.make_subscribe_ctaKeyboard("RU")
        btn = keyboard.inline_keyboard[0][0]
        assert "Подписаться" in btn.text
        assert "990₽" in btn.text

    @pytest.mark.asyncio
    async def test_subscribe_cta_en(self):
        keyboard = meta_bot.make_subscribe_ctaKeyboard("EN")
        btn = keyboard.inline_keyboard[0][0]
        assert "Subscribe" in btn.text
        assert "$10" in btn.text


# ─── Help command locale ─────────────────────────────────────────────────────

class TestHelpCommandLocale:
    @pytest.mark.asyncio
    async def test_help_ru(self, monkeypatch):
        update = make_update(language_code="ru")
        monkeypatch.setattr(meta_bot, "record_event", lambda e, **kw: None)
        await meta_bot.help_cmd(update, SimpleNamespace())

        reply_text = update.message.reply_text.await_args_list[0][0][0]
        assert "бесплатно" in reply_text
        assert "990₽" in reply_text

    @pytest.mark.asyncio
    async def test_help_en(self, monkeypatch):
        update = make_update(language_code="en")
        monkeypatch.setattr(meta_bot, "record_event", lambda e, **kw: None)
        await meta_bot.help_cmd(update, SimpleNamespace())

        reply_text = update.message.reply_text.await_args_list[0][0][0]
        assert "free" in reply_text.lower()
        assert "$10" in reply_text


# ─── Share command locale ────────────────────────────────────────────────────

class TestShareCommandLocale:
    @pytest.mark.asyncio
    async def test_share_ru(self, monkeypatch):
        update = make_update(language_code="ru")
        monkeypatch.setattr(meta_bot, "record_event", lambda e, **kw: None)
        await meta_bot.share_cmd(update, SimpleNamespace())

        reply_text = update.message.reply_text.await_args_list[0][0][0]
        assert "бесплатно" in reply_text
        assert "990₽" in reply_text

    @pytest.mark.asyncio
    async def test_share_en(self, monkeypatch):
        update = make_update(language_code="en")
        monkeypatch.setattr(meta_bot, "record_event", lambda e, **kw: None)
        await meta_bot.share_cmd(update, SimpleNamespace())

        reply_text = update.message.reply_text.await_args_list[0][0][0]
        assert "free" in reply_text.lower()
        assert "$10" in reply_text


# ─── EN buttons don't match RU regex ────────────────────────────────────────

class TestButtonSeparation:
    """EN buttons must be distinct strings so regex filters separate them from RU."""

    def test_launch_buttons_different(self):
        assert meta_bot.BTN_LAUNCH != meta_bot.BTN_LAUNCH_EN

    def test_example_buttons_different(self):
        assert meta_bot.BTN_EXAMPLE != meta_bot.BTN_EXAMPLE_EN

    def test_token_help_buttons_different(self):
        assert meta_bot.BTN_TOKEN_HELP != meta_bot.BTN_TOKEN_HELP_EN

    def test_save_buttons_different(self):
        assert meta_bot.BTN_SAVE != meta_bot.BTN_SAVE_EN

    def test_cancel_buttons_different(self):
        assert meta_bot.BTN_CANCEL != meta_bot.BTN_CANCEL_EN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
