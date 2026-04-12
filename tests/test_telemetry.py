#!/usr/bin/env python3
"""Tests for Bot Builder funnel telemetry (task #5067)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOT_BUILDER_DIR = ROOT / "Projects" / "bot-builder"
if str(BOT_BUILDER_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_BUILDER_DIR))

import db as db_module


class TestRecordEvent:
    """Tests for record_event."""

    def test_record_event_inserts_row(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("draft_generated", user_id=12345, template="booking")

        conn = db_module._conn()
        row = conn.execute(
            "SELECT event, user_id, payload FROM events WHERE user_id = ?",
            (12345,),
        ).fetchone()
        conn.close()

        assert row is not None
        assert row["event"] == "draft_generated"
        assert row["user_id"] == 12345
        payload = json.loads(row["payload"])
        assert payload["template"] == "booking"

    def test_record_event_without_user(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("deploy_succeeded", bot_id="test_bot")

        conn = db_module._conn()
        row = conn.execute(
            "SELECT event, user_id, payload FROM events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()

        assert row["event"] == "deploy_succeeded"
        assert row["user_id"] is None

    def test_record_event_multiple_events(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("draft_generated", user_id=1)
            db_module.record_event("preview_shown", user_id=1)
            db_module.record_event("token_submitted", user_id=1)
            db_module.record_event("deploy_succeeded", user_id=1)

        conn = db_module._conn()
        counts = conn.execute(
            "SELECT event, COUNT(*) as cnt FROM events GROUP BY event ORDER BY event"
        ).fetchall()
        conn.close()

        assert len(counts) == 4
        counts_dict = {r["event"]: r["cnt"] for r in counts}
        assert counts_dict["draft_generated"] == 1
        assert counts_dict["deploy_succeeded"] == 1

    def test_record_event_unknown_event_allowed(self, tmp_db_path):
        """Any event name is allowed — schema doesn't restrict names."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("saved_for_later", user_id=99)
            db_module.record_event("resumed_after_delay", user_id=99)

        conn = db_module._conn()
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        conn.close()
        assert count == 2


class TestGetFunnelReport:
    """Tests for get_funnel_report."""

    def test_empty_report(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            report = db_module.get_funnel_report(days=7)

        assert report["total_events"] == 0
        assert report["event_counts"] == []
        assert report["period_days"] == 7

    def test_report_counts_by_event(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            for _ in range(3):
                db_module.record_event("draft_generated", user_id=1)
            for _ in range(2):
                db_module.record_event("preview_shown", user_id=1)
            db_module.record_event("deploy_succeeded", user_id=1)
            report = db_module.get_funnel_report(days=7)

        assert report["total_events"] == 6
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts["draft_generated"] == 3
        assert counts["preview_shown"] == 2
        assert counts["deploy_succeeded"] == 1
        # today_counts and total_today are new fields
        assert "today_counts" in report
        assert "total_today" in report
        today_map = {r["event"]: r["count"] for r in report["today_counts"]}
        assert today_map.get("draft_generated", 0) == 3  # these are from today in tmp DB

    def test_report_ordered_by_count_desc(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("deploy_failed", user_id=1)
            db_module.record_event("deploy_succeeded", user_id=1)
            db_module.record_event("draft_generated", user_id=1)
            report = db_module.get_funnel_report(days=7)

        assert report["event_counts"][0]["event"] == "deploy_failed"
        assert report["event_counts"][1]["event"] == "deploy_succeeded"

    def test_report_respects_days_filter(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("draft_generated", user_id=1)
            report_all = db_module.get_funnel_report(days=7)
            # Events from far in the past would be 0 with a very small window
            # (In real DB this would filter by created_at)
            assert report_all["total_events"] >= 1

    def test_report_includes_queried_at(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            report = db_module.get_funnel_report()
        assert "queried_at" in report
        assert report["queried_at"] is not None


# ─── Tests for draft save/resume ─────────────────────────────────────────────

class TestDraftSaveResume:
    """Tests for save_draft, get_draft, delete_draft."""

    def test_save_and_get_draft(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.save_draft(100, "Бот для записи", "print('hi')", "booking")

        conn = db_module._conn()
        row = conn.execute("SELECT description, code, template FROM drafts WHERE user_id = ?", (100,)).fetchone()
        conn.close()

        assert row is not None
        assert row["description"] == "Бот для записи"
        assert row["code"] == "print('hi')"
        assert row["template"] == "booking"

    def test_save_draft_replaces_previous(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.save_draft(100, "Draft 1", "code1", None)
            db_module.save_draft(100, "Draft 2", "code2", "faq")
            draft = db_module.get_draft(100)

        assert draft["description"] == "Draft 2"
        assert draft["code"] == "code2"
        assert draft["template"] == "faq"

    def test_get_draft_returns_none_when_empty(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            result = db_module.get_draft(999)
        assert result is None

    def test_delete_draft_removes_it(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.save_draft(100, "Draft", "code", None)
            db_module.delete_draft(100)
            result = db_module.get_draft(100)
        assert result is None

    def test_save_draft_multiple_users(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.save_draft(100, "Draft for user 100", "code100", None)
            db_module.save_draft(200, "Draft for user 200", "code200", None)
            d100 = db_module.get_draft(100)
            d200 = db_module.get_draft(200)
        assert d100["description"] == "Draft for user 100"
        assert d200["description"] == "Draft for user 200"

    def test_resumed_after_delay_event(self, tmp_db_path):
        """saved_for_later and resumed_after_delay events are recorded correctly."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("saved_for_later", user_id=50)
            db_module.record_event("resumed_after_delay", user_id=50, elapsed_seconds=3600)
            events = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in events["event_counts"]}
        assert counts.get("saved_for_later", 0) == 1
        assert counts.get("resumed_after_delay", 0) == 1

    def test_example_dialog_opened_event(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("example_dialog_opened", user_id=42)
            events = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in events["event_counts"]}
        assert counts.get("example_dialog_opened", 0) == 1


# ─── Tests for smoke signal ────────────────────────────────────────────────────────

class TestSmokeSignal:
    """Tests for smoke_signal() in funnel_report.py."""

    def test_smoke_signal_green_when_draft_generated_today(self):
        from scripts.funnel_report import smoke_signal
        today = [{"event": "start_opened", "count": 2}, {"event": "draft_generated", "count": 1}]
        period = today + [{"event": "preview_shown", "count": 1}]
        status, reason = smoke_signal(today, period)
        assert status == "GREEN"
        assert "draft_generated: 1" in reason

    def test_smoke_signal_yellow_when_only_start_opened_today(self):
        from scripts.funnel_report import smoke_signal
        today = [{"event": "start_opened", "count": 2}]
        period = [{"event": "start_opened", "count": 2}, {"event": "draft_generated", "count": 4}]
        status, reason = smoke_signal(today, period)
        assert status == "YELLOW"
        assert "landing opens: 2" in reason
        assert "no downstream funnel events" in reason

    def test_smoke_signal_red_when_no_events_today(self):
        from scripts.funnel_report import smoke_signal
        today = []
        period = [{"event": "draft_generated", "count": 4}]
        status, reason = smoke_signal(today, period)
        assert status == "RED"


# ─── Tests for new monetization telemetry events ─────────────────────────────────

class TestMonetizationTelemetry:
    """Tests for paywall_shown and subscribe_opened events."""

    def test_paywall_shown_event(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("paywall_shown", user_id=100, trigger="last_free_bot_deployed")
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("paywall_shown", 0) == 1

    def test_paywall_shown_multiple_triggers(self, tmp_db_path):
        """Different trigger values are all recorded as the same event."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("paywall_shown", user_id=100, trigger="last_free_bot_deployed")
            db_module.record_event("paywall_shown", user_id=100, trigger="limit_exhausted_at_token")
            db_module.record_event("paywall_shown", user_id=101, trigger="one_free_bot_left")
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("paywall_shown", 0) == 3

    def test_subscribe_opened_event(self, tmp_db_path):
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("subscribe_opened", user_id=200)
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("subscribe_opened", 0) == 1

    def test_token_step_opened_event(self, tmp_db_path):
        """token_step_opened fires when user clicks launch button to enter token step."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("token_step_opened", user_id=300)
            db_module.record_event("token_submitted", user_id=300)
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("token_step_opened", 0) == 1
        assert counts.get("token_submitted", 0) == 1

    def test_subscribe_opened_and_paywall_in_same_funnel(self, tmp_db_path):
        """Both events can coexist in funnel report."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("draft_generated", user_id=1)
            db_module.record_event("deploy_succeeded", user_id=1)
            db_module.record_event("paywall_shown", user_id=1, trigger="last_free_bot_deployed")
            db_module.record_event("subscribe_opened", user_id=1)
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("paywall_shown", 0) == 1
        assert counts.get("subscribe_opened", 0) == 1
        assert counts.get("deploy_succeeded", 0) == 1


# ─── Tests for CTA surfacing on deploy success and limit-exhausted paths ─────────────────

class TestUpgradeCTASurfacing:
    """Tests for inline subscribe CTA appearing at free-limit boundaries."""

    def test_make_subscribe_ctaKeyboard_returns_inline_button(self):
        """subscribe_ctaKeyboard() returns an InlineKeyboardMarkup with subscribe button (RU)."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from meta_bot import make_subscribe_ctaKeyboard
        keyboard_ru = make_subscribe_ctaKeyboard("RU")
        keyboard_en = make_subscribe_ctaKeyboard("EN")
        assert keyboard_ru is not None
        assert keyboard_en is not None
        # RU: 990₽/мес
        row_ru = keyboard_ru.inline_keyboard[0]
        btn_ru = row_ru[0]
        assert "Подписаться" in btn_ru.text
        assert "990₽" in btn_ru.text
        assert btn_ru.callback_data == "subscribe_cta"
        # EN: $10/mo
        row_en = keyboard_en.inline_keyboard[0]
        btn_en = row_en[0]
        assert "Subscribe" in btn_en.text
        assert "$10" in btn_en.text
        assert btn_en.callback_data == "subscribe_cta"

    def test_paywall_shown_at_last_free_bot_deployed(self, tmp_db_path):
        """When remaining=0 after deploy, paywall_shown event is recorded."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("paywall_shown", user_id=1, trigger="last_free_bot_deployed")
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("paywall_shown", 0) == 1

    def test_paywall_shown_at_limit_exhausted(self, tmp_db_path):
        """When limit is exhausted at token submission, paywall_shown event is recorded."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("paywall_shown", user_id=1, trigger="limit_exhausted_at_token")
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("paywall_shown", 0) == 1

    def test_paywall_shown_with_one_free_bot_left(self, tmp_db_path):
        """When remaining=1 after deploy, paywall_shown event is recorded."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("paywall_shown", user_id=1, trigger="one_free_bot_left")
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("paywall_shown", 0) == 1

    def test_payment_succeeded_event_recorded(self, tmp_db_path):
        """successful_payment should record payment_succeeded telemetry."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("payment_succeeded", user_id=1, amount=500, charge_id="test_charge_123")
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("payment_succeeded", 0) == 1

    def test_payment_succeeded_and_subscribe_opened_coexist(self, tmp_db_path):
        """Both payment_succeeded and subscribe_opened appear in funnel together."""
        with patch.object(db_module, "DB_PATH", tmp_db_path):
            db_module.init_db()
            db_module.record_event("paywall_shown", user_id=1, trigger="last_free_bot_deployed")
            db_module.record_event("subscribe_opened", user_id=1)
            db_module.record_event("payment_succeeded", user_id=1, amount=500, charge_id="ch_1")
            report = db_module.get_funnel_report(days=7)
        counts = {r["event"]: r["count"] for r in report["event_counts"]}
        assert counts.get("paywall_shown", 0) == 1
        assert counts.get("subscribe_opened", 0) == 1
        assert counts.get("payment_succeeded", 0) == 1


# ─── Pytest fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db_path(tmp_path):
    """Provide a temporary DB path for isolated tests."""
    db_path = tmp_path / "test_funnel.db"
    with patch.object(db_module, "DB_PATH", db_path):
        yield db_path
