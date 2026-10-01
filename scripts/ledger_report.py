#!/usr/bin/env python3
"""Count ledger events and list promotion candidates.

Usage: ledger_report.py [--project DIR] [--days N] [--kind KIND] [--min-count N] [--json]

Reads `<project>/.claude/ledger/events.jsonl` (see hooks/lib/ledger.py), counts
events by kind and key over the last N days, and lists keys seen at least
--min-count times as candidates for promotion from prose to computation.
Advisor calls are reported per session instead, since their cost is per
session. Read-only; prints nothing about events older than the window.
"""

import argparse
import collections
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hooks"))
from lib import ledger  # noqa: E402

HINTS = {
    "tool_error": "a check that prevents it (hook, lint rule, test, wrapper script)",
    "permission_prompt": "a permission rule (allow, ask or deny) or a narrower command",
    "review_finding": "a machine gate (lint, review-gates entry, test)",
    "human_confirmation": "a standing authorization the user writes, or a fixed rule for when to ask",
}


def parse_ts(value: str):
    try:
        ts = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def report(path: str, days: int, kind=None, min_count: int = 3) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    counts = collections.Counter()
    advisor_by_session = collections.Counter()
    for e in ledger.read(path):
        ts = parse_ts(e.get("ts"))
        if ts is None or ts < since or (kind and e["kind"] != kind):
            continue
        counts[(e["kind"], e.get("key", ""))] += 1
        if e["kind"] == "advisor_call":
            advisor_by_session[e.get("session_id", "")] += 1
    candidates = [
        {"kind": k, "key": key, "count": n, "promote_to": HINTS[k]}
        for (k, key), n in counts.most_common()
        if k in HINTS and n >= min_count
    ]
    by_kind = collections.Counter()
    for (k, _), n in counts.items():
        by_kind[k] += n
    return {
        "ledger": path,
        "days": days,
        "by_kind": dict(by_kind),
        "candidates": candidates,
        "advisor_calls_per_session": dict(advisor_by_session.most_common()),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--kind", choices=ledger.KINDS)
    ap.add_argument("--min-count", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    path = os.path.join(os.path.abspath(args.project), ledger.LEDGER_RELPATH)
    result = report(path, args.days, args.kind, args.min_count)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    print(f"ledger: {path} (last {args.days} days)")
    if not result["by_kind"]:
        print("no events")
        return 0
    for k, n in sorted(result["by_kind"].items()):
        print(f"  {k:<20} {n:>6}")
    if result["advisor_calls_per_session"]:
        print("advisor calls per session:")
        for session, n in result["advisor_calls_per_session"].items():
            print(f"  {session[:12] or '?':<12} {n:>4}")
    print(f"promotion candidates (seen >= {args.min_count} times):")
    if not result["candidates"]:
        print("  none")
    for c in result["candidates"]:
        print(f"  [{c['kind']}] x{c['count']}  {c['key']}\n      -> {c['promote_to']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
