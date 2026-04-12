#!/usr/bin/env python3
"""Pytest configuration for Bot Builder tests.

Isolates tests from production bot_builder.db by using a test DB.
All tests import meta_bot/db via absolute paths from ROOT, so this conftest
must be loaded BEFORE those imports happen.
"""
import os
import sys
from pathlib import Path

# The actual bot-builder source lives in Projects/bot-builder/ (capital P).
# Test files are in projects/kai-bot-builder/tests/ (lowercase, git-tracked).
# Set up sys.path so tests can import from Projects/bot-builder.
BOT_BUILDER_ROOT = Path(__file__).resolve().parents[1]  # = projects/kai-bot-builder/
BOT_BUILDER_SOURCE = Path("/root/kai-system/Projects/bot-builder")

# Add kai-system root and bot-builder source to path (tests use these)
if "/root/kai-system" not in sys.path:
    sys.path.insert(0, "/root/kai-system")
if str(BOT_BUILDER_SOURCE) not in sys.path:
    sys.path.insert(0, str(BOT_BUILDER_SOURCE))

# Set test DB BEFORE any imports from db.py or meta_bot
TEST_DB_PATH = str(BOT_BUILDER_ROOT / "bot_builder.test.db")
os.environ["BOT_BUILDER_DB"] = TEST_DB_PATH

# Clean up test DB before each run to start fresh
import sqlite3
test_db = Path(TEST_DB_PATH)
if test_db.exists():
    test_db.unlink()

# Init test DB schema
conn = sqlite3.connect(TEST_DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=ON")
# Create minimal schema matching production
conn.executescript("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    bots_created INTEGER DEFAULT 0,
    subscription_until TEXT
);
CREATE TABLE IF NOT EXISTS bots (
    bot_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    description TEXT,
    bot_token_hash TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    stopped_at TEXT,
    deployed_at TEXT,
    subscription_until TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    event TEXT NOT NULL,
    payload TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    charge_id TEXT,
    months INTEGER DEFAULT 1,
    bot_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_events_event ON events(event);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
""")
conn.close()
