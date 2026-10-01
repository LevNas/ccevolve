#!/usr/bin/env python3
"""PostToolUseFailure hook: record failed tool calls and flag a recurring pattern.

PostToolUse fires only after a tool succeeds; a failure fires
PostToolUseFailure, whose input carries the failure text in `error`
(https://code.claude.com/docs/en/hooks). Earlier versions listened on
PostToolUse and read a `tool_output` field that the event does not have, so
they never saw a failure.

Each failure becomes a `tool_error` event in the ledger, keyed by the tool name
and a normalized first error line (paths, numbers and long token-like strings
replaced). When the same key occurs a second time in the session, the hook adds
context for Claude asking it to propose a fix that stops the recurrence —
preferably a computed check (hook, lint rule, test) over more prose. User
interrupts are ignored. Fail-open: any error exits 0 without output.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import ledger  # noqa: E402


def normalize_error(text: str) -> str:
    """First meaningful line with variable parts replaced, up to 120 chars."""
    if not text:
        return ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("+ ", "Warning:", "Note:", "Exit code")):
            continue
        line = re.sub(r"/[^\s:]+", "<path>", line)
        line = re.sub(r"[A-Za-z0-9_\-+=/]{20,}", "<token>", line)
        line = re.sub(r"\b\d+\b", "<N>", line)
        return line[:120]
    first = text.strip().splitlines()[0] if text.strip() else ""
    return re.sub(r"\b\d+\b", "<N>", first)[:120]


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(payload, dict) or not ledger.enabled():
        return
    if payload.get("hook_event_name", "PostToolUseFailure") != "PostToolUseFailure":
        return
    if payload.get("is_interrupt"):
        return

    tool = payload.get("tool_name", "") or "unknown"
    pattern = normalize_error(str(payload.get("error", "")))
    if not pattern:
        return
    key = f"{tool}: {pattern}"
    session_id = payload.get("session_id") or ""
    path = ledger.ledger_path(payload.get("cwd") or os.getcwd())

    previous = ledger.count(path, "tool_error", session_id=session_id, key=key)
    ledger.append(path, session_id, "tool_error", key)
    if previous < 1:
        return

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUseFailure",
        "additionalContext": (
            f"[ccevolve] 同じ失敗が{previous + 1}回目です: `{key[:100]}` — "
            "再発を止める手を提案してください。入力が同じなら毎回同じ答えになる判断なら、"
            "文章のルールより計算（hook・lint・テスト・スクリプト）を優先します。"
            "文章にするなら .claude/rules/ か skill、知見ならナレッジに記録します。"
        ),
    }}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — a hook must never break a session
        pass
    sys.exit(0)
