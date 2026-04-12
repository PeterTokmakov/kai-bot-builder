#!/usr/bin/env python3
"""Bot Builder Funnel Metrics — reusable cohort analysis.

Usage:
    python3 scripts/bot_builder_funnel_metrics.py [--days N] [--cohort-split TIMESTAMP]

Outputs:
    - Funnel table: stage → users → conversion rate
    - Pre/post-fix cohort split around FIX_TIMESTAMP (default: 2026-04-12 14:00 UTC)
    - Key conversion ratios: start→draft, draft→preview, preview→token, token→deploy
    - All-time, 7d, 30d windows

DB: BOT_BUILDER_DB env var (default: data/db/bot_builder.db)
"""

import os
import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

# ── CLI ────────────────────────────────────────────────────────────────────────

BOT_BUILDER_ROOT = Path(__file__).resolve().parents[2]  # projects/kai-bot-builder/
FIX_TIMESTAMP = "2026-04-12 14:00:00"  # orphan_text fix deployed

STAGES = [
    "start_opened",
    "draft_generated",
    "preview_shown",
    "token_step_opened",
    "example_dialog_opened",
    "botfather_help_opened",
    "token_submitted",
    "deploy_succeeded",
    "deploy_failed",
    "paywall_shown",
    "payment_succeeded",
]

KEY_RATIOS = [
    ("start → draft", "start_opened", "draft_generated"),
    ("draft → preview", "draft_generated", "preview_shown"),
    ("preview → token_step", "preview_shown", "token_step_opened"),
    ("preview → token_submit", "preview_shown", "token_submitted"),
    ("token → deploy", "token_submitted", "deploy_succeeded"),
    ("deploy → payment", "deploy_succeeded", "payment_succeeded"),
]


@dataclass
class CohortWindow:
    label: str
    start: str | None  # None = all-time start
    end: str | None
    stage_counts: dict[str, int]
    stage_users: dict[str, int]
    stage_users_unique: dict[str, int]  # distinct user_id per stage (correct funnel metric)
    orphan_text_count: int
    orphan_text_users: int


# ── DB helpers ─────────────────────────────────────────────────────────────────

def _conn(db_path: str | None = None) -> sqlite3.Connection:
    if db_path is None:
        db_path = os.environ.get(
            "BOT_BUILDER_DB",
            "/root/kai-system/Projects/bot-builder/bot_builder.db",
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def stage_counts(conn: sqlite3.Connection, start: str | None = None, end: str | None = None) -> dict[str, int]:
    """Count events per stage in the given window."""
    where = _where_clause(start, end)
    sql = f"SELECT event, COUNT(*) as n FROM events {where} GROUP BY event"
    rows = conn.execute(sql).fetchall()
    return {r["event"]: r["n"] for r in rows}


def stage_users(conn: sqlite3.Connection, start: str | None = None, end: str | None = None) -> dict[str, int]:
    """Count DISTINCT users per stage in the given window."""
    where = _where_clause(start, end)
    sql = f"SELECT event, COUNT(DISTINCT user_id) as n FROM events {where} GROUP BY event"
    rows = conn.execute(sql).fetchall()
    return {r["event"]: r["n"] for r in rows}


def orphan_counts(conn: sqlite3.Connection, start: str | None = None, end: str | None = None) -> tuple[int, int]:
    """Return (event_count, distinct_user_count) for orphan_text in window."""
    where = _where_clause(start, end)
    rows = conn.execute(
        f"SELECT COUNT(*) as n, COUNT(DISTINCT user_id) as u "
        f"FROM events {where} AND event = 'orphan_text'"
    ).fetchall()
    return (rows[0]["n"] or 0, rows[0]["u"] or 0)


def funnel_users(conn: sqlite3.Connection, start: str | None = None, end: str | None = None) -> dict[str, set[int]]:
    """Return {event: set(user_ids)} for all users who hit each stage."""
    where = _where_clause(start, end)
    sql = f"SELECT event, user_id FROM events {where}"
    rows = conn.execute(sql).fetchall()
    result: dict[str, set[int]] = defaultdict(set)
    for r in rows:
        if r["user_id"] is not None:
            result[r["event"]].add(r["user_id"])
    return result


def funnel_users_unique(conn: sqlite3.Connection, start: str | None = None, end: str | None = None) -> dict[str, int]:
    """Return {event: distinct user count} — the correct funnel metric.

    Raw event counts are inflated by repeat presses (e.g. a user pressing
    LAUNCH 5 times = 5 token_step_opened events). This measures unique
    users who reached each stage at least once.
    """
    where = _where_clause(start, end)
    sql = f"SELECT event, COUNT(DISTINCT user_id) as n FROM events {where} GROUP BY event"
    rows = conn.execute(sql).fetchall()
    return {r["event"]: r["n"] for r in rows}


def _where_clause(start: str | None, end: str | None) -> str:
    clauses = []
    if start:
        clauses.append(f"created_at >= '{start}'")
    if end:
        clauses.append(f"created_at <= '{end}'")
    if not clauses:
        return ""
    return "WHERE " + " AND ".join(clauses)


# ── Report generation ──────────────────────────────────────────────────────────

def build_report(conn: sqlite3.Connection, fix_ts: str, days: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    # Time windows
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    window_7d_start = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
                      .timestamp() - days * 86400)
    window_7d_start_str = datetime.fromtimestamp(window_7d_start, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    windows: list[dict] = [
        {"label": "all-time", "start": None, "end": now_str},
        {"label": f"last-{days}d", "start": window_7d_start_str, "end": now_str},
        {"label": "pre-fix", "start": None, "end": fix_ts},
        {"label": "post-fix", "start": fix_ts, "end": now_str},
    ]

    cohorts: list[CohortWindow] = []
    for w in windows:
        sc = stage_counts(conn, w["start"], w["end"])
        su = stage_users(conn, w["start"], w["end"])
        suu = funnel_users_unique(conn, w["start"], w["end"])
        ot_n, ot_u = orphan_counts(conn, w["start"], w["end"])
        cohorts.append(CohortWindow(
            label=w["label"],
            start=w["start"],
            end=w["end"],
            stage_counts=sc,
            stage_users=su,
            stage_users_unique=suu,
            orphan_text_count=ot_n,
            orphan_text_users=ot_u,
        ))

    return {
        "queried_at": now,
        "fix_timestamp": fix_ts,
        "cohorts": [asdict(c) for c in cohorts],
        "stages": STAGES,
        "key_ratios": KEY_RATIOS,
    }


def print_report(report: dict) -> None:
    print(f"\n{'='*70}")
    print("Bot Builder Funnel Metrics")
    print(f"{'='*70}")
    print(f"Queried at: {report['queried_at']}")
    print(f"Fix deployed: {report['fix_timestamp']}")
    print()

    for cohort in report["cohorts"]:
        label = cohort["label"]
        start = cohort["start"] or "beginning"
        end = cohort["end"] or "now"
        print(f"{'─'*70}")
        print(f"  [{label.upper()}]  {start} → {end}")
        print(f"{'─'*70}")

        sc = cohort["stage_counts"]
        su = cohort["stage_users"]

        total_events = sum(sc.values())
        print(f"  Total events: {total_events}")
        print()

        print(f"  {'Stage':<30} {'Events':>8}  {'Users':>6}  {'Uniq.users':>10}  {'%of_start':>10}")
        print(f"  {'─'*70}")

        start_n = sc.get("start_opened", 0)
        draft_n = sc.get("draft_generated", 0)
        start_u = su.get("start_opened", 0)

        for stage in report["stages"]:
            n = sc.get(stage, 0)
            u = su.get(stage, 0)
            uu = cohort["stage_users_unique"].get(stage, 0)
            pct_start = (uu / start_u * 100) if start_u > 0 else 0
            pct_draft = (uu / uu * 100) if uu > 0 else 0  # noqa: F541

            # Highlight funnel-critical stages
            marker = ""
            if stage == "token_step_opened":
                marker = " ← key fix target"
            elif stage == "orphan_text":
                marker = " ← bug indicator"
            elif stage == "deploy_succeeded":
                marker = " ← success"

            pct_start_s = f"{pct_start:>9.1f}%" if start_u > 0 else "         -"
            pct_draft_s = f"{pct_draft:>9.1f}%" if uu > 0 else "         -"

            print(f"  {stage:<30} {n:>8}  {u:>6}  {uu:>10}  {pct_start_s}")

        print()
        print(f"  Orphan text events: {cohort['orphan_text_count']}  "
              f"users: {cohort['orphan_text_users']}")
        print()

        # Key ratios
        if draft_n > 0:
            print(f"  Key conversion ratios:")
            for ratio_label, num_event, den_event in report["key_ratios"]:
                num = sc.get(num_event, 0)
                den = sc.get(den_event, 0) if den_event else start_n
                if den_event in sc:
                    denom = sc.get(den_event)
                else:
                    denom = start_n if num_event == "start_opened" else draft_n
                pct = (num / denom * 100) if denom > 0 else 0
                print(f"    {ratio_label:<25} {num:>4} / {denom:<4} = {pct:>5.1f}%")

        print()

    # ── Pre/post comparison ──────────────────────────────────────────────────
    print(f"{'='*70}")
    print("  PRE vs POST FIX comparison")
    print(f"{'='*70}")

    pre = next(c for c in report["cohorts"] if c["label"] == "pre-fix")
    post = next(c for c in report["cohorts"] if c["label"] == "post-fix")

    # Scale post to pre period length for fair comparison
    print(f"  {'Stage':<30} {'Pre':>8}  {'Post':>8}  {'Δ':>6}")
    print(f"  {'─'*56}")

    for stage in report["stages"]:
        pre_n = pre["stage_counts"].get(stage, 0)
        post_n = post["stage_counts"].get(stage, 0)
        delta = post_n - pre_n
        delta_s = f"{delta:>+6}" if delta != 0 else "     0"
        print(f"  {stage:<30} {pre_n:>8}  {post_n:>8}  {delta_s}")

    print()
    print(f"  Orphan text: pre={pre['orphan_text_count']} → post={post['orphan_text_count']}")
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    parser = argparse.ArgumentParser(description="Bot Builder Funnel Metrics")
    parser.add_argument("--days", type=int, default=30, help="Window in days (default: 30)")
    parser.add_argument("--cohort-split", default=FIX_TIMESTAMP,
                        help="Cohort split timestamp (default: 2026-04-12 14:00:00)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of table")
    parser.add_argument("--db", help="Path to bot_builder.db (overrides BOT_BUILDER_DB)")
    args = parser.parse_args()

    db_path = args.db or os.environ.get("BOT_BUILDER_DB")
    conn = _conn(db_path)

    report = build_report(conn, args.cohort_split, args.days)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)

    # Exit with non-zero if post-fix has orphan_text events (bug still occurring)
    post = next(c for c in report["cohorts"] if c["label"] == "post-fix")
    if post["orphan_text_count"] > 0:
        print(f"\n⚠️  WARNING: {post['orphan_text_count']} orphan_text events in POST-FIX window. Bug still occurring.")
        sys.exit(1)
    sys.exit(0)
