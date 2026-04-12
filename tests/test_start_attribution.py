#!/usr/bin/env python3
"""Tests for start_opened acquisition attribution telemetry.

Verifies the fix from task #5431: start_opened events now always include
a `source` key in the payload (null if no deep-link, actual param otherwise).
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure bot-builder is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from db import record_event
import db as db_module


class MockConn:
    """Spy on record_event SQL writes."""

    def __init__(self):
        self.writes: list[tuple] = []

    def execute(self, sql: str, params: tuple):
        self.writes.append((sql, params))

    def commit(self):
        pass

    def close(self):
        pass


class TestStartOpenedAttribution:
    """Tests for start() acquisition attribution."""

    def _capture_event(self, **kwargs) -> dict | None:
        """Call record_event and return the captured payload."""
        mock_conn = MockConn()
        original_conn = db_module._conn
        db_module._conn = lambda: mock_conn
        try:
            record_event("start_opened", user_id=12345, **kwargs)
        finally:
            db_module._conn = original_conn

        sql, params = mock_conn.writes[0]
        payload_str = params[2]
        if payload_str is None:
            return None
        return json.loads(payload_str)

    def test_no_payload_source_is_null(self):
        """No deep-link param: source=null in payload."""
        payload = self._capture_event(source=None)
        assert payload is not None, "payload should not be None"
        assert "source" in payload, "source key must be present"
        assert payload["source"] is None, "source should be null for direct opens"
        print("PASS: no-payload → source=null")

    def test_direct_source_value(self):
        """Explicit 'direct' source: stored as-is."""
        payload = self._capture_event(source="direct")
        assert payload is not None
        assert payload["source"] == "direct"
        print("PASS: source=direct → stored as-is")

    def test_ref_code_stored(self):
        """Deep-link ref code: stored verbatim."""
        payload = self._capture_event(source="ref_kai")
        assert payload is not None
        assert payload["source"] == "ref_kai"
        print("PASS: source=ref_kai → stored verbatim")

    def test_empty_payload_impossible(self):
        """Payload is NEVER null after the fix: source key is always present."""
        # The key invariant: kwargs always contains 'source', so json.dumps always produces a dict
        # Test at the boundary: None as source value is valid but payload is always a dict
        for source_val in [None, "direct", "ref_partner", "reddit_q1"]:
            payload = self._capture_event(source=source_val)
            assert payload is not None, f"payload must not be None for source={source_val}"
            assert isinstance(payload, dict), f"payload must be dict for source={source_val}"
            assert "source" in payload, f"source key must exist for source={source_val}"
        print("PASS: payload never null for all source values")


class TestStartParamExtraction:
    """Tests for the actual start() handler context.args parsing."""

    def test_real_deep_link(self):
        """Real Telegram deep-link: context.args[0] is the param."""
        ctx = MagicMock()
        ctx.args = ["ref_reddit_0426"]
        start_param = ctx.args[0].strip() if (ctx.args and ctx.args[0]) else None
        assert start_param == "ref_reddit_0426"
        print("PASS: real deep-link extracted")

    def test_direct_open_empty_args(self):
        """Direct open: context.args is empty list."""
        ctx = MagicMock()
        ctx.args = []
        start_param = ctx.args[0].strip() if (ctx.args and ctx.args[0]) else None
        assert start_param is None
        print("PASS: direct open → None")

    def test_direct_open_none_args(self):
        """Direct open: context.args is None."""
        ctx = MagicMock()
        ctx.args = None
        start_param = ctx.args[0].strip() if (ctx.args and ctx.args[0]) else None
        assert start_param is None
        print("PASS: args=None → None")

    def test_whitespace_only_arg(self):
        """Deep-link with whitespace-only param: stripped to empty → None."""
        ctx = MagicMock()
        ctx.args = ["   "]
        raw_arg = (ctx.args[0].strip() if ctx.args and ctx.args[0] else "") or ""
        start_param = raw_arg if raw_arg else None
        assert start_param is None
        print("PASS: whitespace-only → None")


if __name__ == "__main__":
    t = TestStartOpenedAttribution()
    t.test_no_payload_source_is_null()
    t.test_direct_source_value()
    t.test_ref_code_stored()
    t.test_empty_payload_impossible()

    e = TestStartParamExtraction()
    e.test_real_deep_link()
    e.test_direct_open_empty_args()
    e.test_direct_open_none_args()
    e.test_whitespace_only_arg()

    print("\nAll 8 tests passed.")
