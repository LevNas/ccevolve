#!/usr/bin/env python3
"""Stop hook: record advisor-tool calls in the ledger and flag heavy use once.

In Claude Code the advisor re-reads the whole conversation on every call and
that read is not cached, and there is no setting to cap the number of calls
(https://code.claude.com/docs/en/advisor). Guidance on when to call it is
prose; this hook is the counting side.

It scans the session transcript for advisor calls — assistant content blocks
`{"type": "server_tool_use", "name": "advisor", "id": ...}`, the shape the
Claude API documents for the advisor tool — and appends one `advisor_call`
event per call id not recorded yet. When the session's count crosses a
multiple of `CCEVOLVE_ADVISOR_NOTIFY_AT` (default 3), it shows the user one
`systemMessage`. It never blocks the stop.

The transcript is written asynchronously, so a call from the last turn may be
counted at the next stop. Fail-open: any error exits 0 without output.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import ledger  # noqa: E402

DEFAULT_NOTIFY_AT = 3


def advisor_call_ids(transcript_path: str) -> list:
    """Ids of advisor server-tool calls in the transcript, in order."""
    ids = []
    try:
        with open(transcript_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if '"advisor"' not in line:  # cheap pre-filter
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = entry.get("message") if isinstance(entry, dict) else None
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if (isinstance(block, dict) and block.get("type") == "server_tool_use"
                            and block.get("name") == "advisor" and block.get("id")):
                        ids.append(block["id"])
    except OSError:
        return []
    return ids


def notify_at(env) -> int:
    try:
        value = int(env.get("CCEVOLVE_ADVISOR_NOTIFY_AT", DEFAULT_NOTIFY_AT))
    except ValueError:
        return DEFAULT_NOTIFY_AT
    return value if value > 0 else DEFAULT_NOTIFY_AT


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(payload, dict) or not ledger.enabled():
        return
    transcript = payload.get("transcript_path") or ""
    session_id = payload.get("session_id") or ""
    if not transcript or not os.path.isfile(transcript):
        return

    path = ledger.ledger_path(payload.get("cwd") or os.getcwd())
    seen = ledger.recorded_ids(path, "advisor_call")
    new_ids = [i for i in advisor_call_ids(transcript) if i not in seen]
    if not new_ids:
        return

    before = ledger.count(path, "advisor_call", session_id=session_id)
    written = sum(ledger.append(path, session_id, "advisor_call", "advisor", event_id=i) for i in new_ids)
    after = before + written

    step = notify_at(os.environ)
    if after // step > before // step:
        print(json.dumps({"systemMessage": (
            f"[ccevolve] The advisor has been called {after} times in this session. "
            "Each call re-reads the whole conversation without caching. "
            "To stop for now: /advisor off (this saves to your user settings); "
            "to use it only per session, start with --advisor instead."
        )}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — a hook must never break a session
        pass
    sys.exit(0)
