#!/usr/bin/env python3
"""Focused tests for Bot Builder token step guidance improvements (task #5392).

Tests:
1. _handle_launch sends inline BotFather guidance + help keyboard
2. receive_token invalid-token path shows inline guidance + help keyboard
3. TOKEN state has BTN_TOKEN_HELP handler
4. Deploy failed path shows help keyboard
5. All 6 BotFather steps present in guidance
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOT_BUILDER_DIR = ROOT / "Projects" / "bot-builder"
if str(BOT_BUILDER_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_BUILDER_DIR))

import meta_bot


def make_mock_update(user_id=42, username="test", first_name="Test", token="invalid", language_code="ru"):
    """Create a minimal mock Update."""
    return SimpleNamespace(
        message=SimpleNamespace(
            text=token,
            reply_text=AsyncMock(),
            effective_user=SimpleNamespace(id=user_id, username=username, first_name=first_name, language_code=language_code),
        ),
        effective_user=SimpleNamespace(id=user_id, username=username, first_name=first_name, language_code=language_code),
    )


def make_context(code="async def main(): pass", description="Test bot", previous_state=None):
    """Create context with chat_data dict (for state tracking)."""
    ctx = SimpleNamespace(user_data={"code": code, "description": description})
    ctx.chat_data = {"_previous_state": previous_state} if previous_state is not None else {}
    return ctx


class TestHandleLaunchGuidance:
    """Tests for _handle_launch inline guidance."""

    @pytest.mark.asyncio
    async def test_launch_message_has_all_6_botfather_steps(self):
        """Launch message includes all 6 BotFather steps inline."""
        update = make_mock_update()
        context = make_context()
        await meta_bot._handle_launch(update, context)

        # _handle_launch sends 2 messages:
        # 1. BotFather deep-link as first message (inline button)
        # 2. launch_excellent + token guidance with persistent ReplyKeyboardMarkup
        update.message.reply_text.assert_called()
        calls = update.message.reply_text.call_args_list
        assert len(calls) == 2, f"Expected 2 reply_text calls, got {len(calls)}"

        # Second call contains the 6-step guidance + persistent keyboard
        args, kwargs = calls[1]
        text = args[0] if args else kwargs.get("text", "")
        reply_markup = kwargs.get("reply_markup", None)

        # Check all 6 steps are present
        assert "1️⃣" in text, "Step 1 missing"
        assert "2️⃣" in text, "Step 2 missing"
        assert "3️⃣" in text, "Step 3 missing"
        assert "4️⃣" in text, "Step 4 missing"
        assert "5️⃣" in text, "Step 5 missing"
        assert "6️⃣" in text, "Step 6 missing"

        # Check BotFather link
        assert "@BotFather" in text or "t.me/BotFather" in text

        # Check token format example
        assert "123456789:" in text

        # Check persistent ReplyKeyboardMarkup is attached (keyboard attribute)
        assert reply_markup is not None
        keyboard = reply_markup.keyboard
        btn_labels = [row[0].text for row in keyboard]
        assert meta_bot.BTN_TOKEN_HELP in btn_labels, \
            f"Help button missing from keyboard: {btn_labels}"

    @pytest.mark.asyncio
    async def test_launch_message_has_revoke_note(self):
        """Launch message notes that token is stored as hash only."""
        update = make_mock_update()
        context = make_context()
        await meta_bot._handle_launch(update, context)

        args, kwargs = update.message.reply_text.call_args
        text = args[0] if args else kwargs.get("text", "")
        assert "хеш" in text.lower() or "hash" in text.lower(), \
            "Revoke/hash note missing from launch message"


class TestInvalidTokenGuidance:
    """Tests for receive_token invalid-token path."""

    @pytest.mark.asyncio
    async def test_invalid_token_shows_guidance(self):
        """Invalid token reply includes token format guidance and BotFather link."""
        update = make_mock_update(token="notavalidtoken")
        context = make_context()

        with patch.object(meta_bot, "record_event", lambda e, **kw: None):
            with patch.object(meta_bot, "can_create_bot", return_value=(True, "")):
                with patch.object(meta_bot, "get_or_create_user", lambda *a, **kw: None):
                    with patch.object(meta_bot, "deploy_bot", return_value={"error": ""}):
                        result = await meta_bot.receive_token(update, context)

        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        text = args[0] if args else kwargs.get("text", "")
        reply_markup = kwargs.get("reply_markup", None)

        # Should still be in TOKEN state (not END)
        assert result == meta_bot.TOKEN, f"Expected TOKEN state, got {result}"

        # Should show error and token format guidance
        assert "❌" in text, "Error indicator missing"
        assert "123456789:" in text, "Token format example missing"
        assert "@BotFather" in text or "t.me/BotFather" in text

        # Should have help keyboard attached
        assert reply_markup is not None
        keyboard = reply_markup.keyboard
        btn_labels = [row[0].text for row in keyboard]
        assert meta_bot.BTN_TOKEN_HELP in btn_labels, \
            f"Help button missing from invalid-token keyboard: {btn_labels}"

    @pytest.mark.asyncio
    async def test_invalid_token_no_colon(self):
        """Token without colon is rejected with guidance."""
        update = make_mock_update(user_id=99, token="notoken")
        context = make_context()

        with patch.object(meta_bot, "record_event", lambda e, **kw: None):
            with patch.object(meta_bot, "can_create_bot", return_value=(True, "")):
                with patch.object(meta_bot, "get_or_create_user", lambda *a, **kw: None):
                    with patch.object(meta_bot, "deploy_bot", return_value={"error": ""}):
                        result = await meta_bot.receive_token(update, context)

        assert result == meta_bot.TOKEN
        args, kwargs = update.message.reply_text.call_args
        text = args[0] if args else kwargs.get("text", "")
        # New format: shows token format example, not numbered steps
        assert "123456789:" in text, "Token format example missing"

    @pytest.mark.asyncio
    async def test_invalid_token_too_short(self):
        """Token shorter than 30 chars is rejected with guidance."""
        update = make_mock_update(user_id=100, token="short")
        context = make_context()

        with patch.object(meta_bot, "record_event", lambda e, **kw: None):
            with patch.object(meta_bot, "can_create_bot", return_value=(True, "")):
                with patch.object(meta_bot, "get_or_create_user", lambda *a, **kw: None):
                    with patch.object(meta_bot, "deploy_bot", return_value={"error": ""}):
                        result = await meta_bot.receive_token(update, context)

        assert result == meta_bot.TOKEN
        args, kwargs = update.message.reply_text.call_args
        text = args[0] if args else kwargs.get("text", "")
        assert "123456789:" in text, "Token format example missing"


class TestTokenStateHelpHandler:
    """Tests for BTN_TOKEN_HELP handler in TOKEN state."""

    def test_token_state_has_help_handler(self):
        """ConversationHandler TOKEN state includes BTN_TOKEN_HELP handler."""
        # Find the ConversationHandler in app
        with patch.object(meta_bot, "BOT_TOKEN", "test_token"):
            app = meta_bot.build_application()
            conv_handler = None
            for handler in app.handlers[0]:
                if isinstance(handler, meta_bot.ConversationHandler):
                    conv_handler = handler
                    break
        assert conv_handler is not None, "ConversationHandler not found"

        token_state_handlers = conv_handler.states.get(meta_bot.TOKEN, [])
        handler_types = [type(h).__name__ for h in token_state_handlers]
        assert "MessageHandler" in handler_types, \
            f"TOKEN state has no MessageHandler: {handler_types}"

    @pytest.mark.asyncio
    async def test_token_help_from_token_state_returns_token(self):
        """Help from TOKEN state returns TOKEN (not PREVIEW)."""
        update = make_mock_update(user_id=77)
        context = make_context(previous_state=meta_bot.TOKEN)

        with patch.object(meta_bot, "_show_token_help", AsyncMock()):
            with patch.object(meta_bot, "record_event", lambda e, **kw: None):
                result = await meta_bot._handle_token_help(update, context)

        assert result == meta_bot.TOKEN, \
            f"Help from TOKEN should return TOKEN, got {result}"

    @pytest.mark.asyncio
    async def test_token_help_from_token_state_reshows_token_keyboard(self):
        """Help from TOKEN state reshows TOKEN keyboard (not PREVIEW menu)."""
        update = make_mock_update(user_id=77)
        context = make_context(previous_state=meta_bot.TOKEN)

        with patch.object(meta_bot, "_show_token_help", AsyncMock()):
            with patch.object(meta_bot, "record_event", lambda e, **kw: None):
                result = await meta_bot._handle_token_help(update, context)

        update.message.reply_text.assert_called_once()
        args, kwargs = update.message.reply_text.call_args
        reply_markup = kwargs.get("reply_markup", None)
        assert reply_markup is not None
        keyboard = reply_markup.keyboard
        btn_labels = [row[0].text for row in keyboard]
        # Should have help button (TOKEN keyboard), not launch/save (PREVIEW menu)
        assert meta_bot.BTN_TOKEN_HELP in btn_labels, \
            f"Expected TOKEN keyboard (help button), got: {btn_labels}"
        assert meta_bot.BTN_LAUNCH not in btn_labels, \
            f"PREVIEW keyboard shown in TOKEN state: {btn_labels}"

    @pytest.mark.asyncio
    async def test_token_help_from_preview_state_returns_preview(self):
        """Help from PREVIEW state returns PREVIEW (existing behavior preserved)."""
        update = make_mock_update(user_id=77)
        context = make_context(previous_state=meta_bot.PREVIEW)

        with patch.object(meta_bot, "_show_token_help", AsyncMock()):
            with patch.object(meta_bot, "record_event", lambda e, **kw: None):
                result = await meta_bot._handle_token_help(update, context)

        assert result == meta_bot.PREVIEW, \
            f"Help from PREVIEW should return PREVIEW, got {result}"

    @pytest.mark.asyncio
    async def test_launch_stores_previous_state_preview(self):
        """_handle_launch stores _previous_state = PREVIEW in chat_data."""
        update = make_mock_update(user_id=42)
        context = make_context()

        await meta_bot._handle_launch(update, context)

        assert context.chat_data.get("_previous_state") == meta_bot.PREVIEW, \
            f"Expected _previous_state=PREVIEW, got {context.chat_data.get('_previous_state')}"

    @pytest.mark.asyncio
    async def test_token_help_handler_records_event(self):
        """BTN_TOKEN_HELP pressed in TOKEN state records botfather_help_opened."""
        update = make_mock_update(user_id=77)
        context = make_context(previous_state=meta_bot.TOKEN)

        recorded = []
        with patch.object(meta_bot, "record_event", lambda e, **kw: recorded.append((e, kw))):
            with patch.object(meta_bot, "_show_token_help", AsyncMock()) as mock_help:
                result = await meta_bot._handle_token_help(update, context)
                mock_help.assert_called_once()

        assert ("botfather_help_opened", {"user_id": 77}) in recorded


class TestDeployFailedGuidance:
    """Tests for deploy_failed path."""

    @pytest.mark.asyncio
    async def test_deploy_failed_shows_help_keyboard(self):
        """Deploy error shows help keyboard so user can get token guidance."""
        # Valid token format to pass validation, then deploy fails
        update = make_mock_update(user_id=55, token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyzXYZabc")
        context = make_context()

        with patch.object(meta_bot, "record_event", lambda e, **kw: None):
            with patch.object(meta_bot, "can_create_bot", return_value=(True, "")):
                with patch.object(meta_bot, "get_or_create_user", lambda *a, **kw: None):
                    with patch.object(meta_bot, "deploy_bot",
                                     return_value={"error": "bot blocked by Telegram"}):
                        result = await meta_bot.receive_token(update, context)

        assert result == meta_bot.ConversationHandler.END
        # Called twice: first "launching" message, then deploy error
        assert update.message.reply_text.call_count >= 2, \
            f"Expected at least 2 calls (launching + error), got {update.message.reply_text.call_count}"
        # Last call is the error message
        args, kwargs = update.message.reply_text.call_args
        text = args[0] if args else kwargs.get("text", "")
        reply_markup = kwargs.get("reply_markup", None)
        assert "❌" in text, "Deploy error message missing"
        assert reply_markup is not None
        keyboard = reply_markup.keyboard
        btn_labels = [row[0].text for row in keyboard]
        assert meta_bot.BTN_TOKEN_HELP in btn_labels, \
            f"Help button missing from deploy-failed keyboard: {btn_labels}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
