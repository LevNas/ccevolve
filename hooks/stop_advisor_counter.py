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

The transcript is written asynchronously. On a live session the turn's last
assistant message — the one holding the advisor call — was written in one go
when the advisor's ~36 s consult ended, a few milliseconds after Stop hooks
started; nothing was written during the consult, so the file's mtime was old
and cannot tell "still being written". Three measures cover it:

- in a session that has used the advisor, the Stop hook waits until the
  transcript's last assistant text ends like the Stop input's
  `last_assistant_message` (polling every `POLL_S`, at most `MAX_WAIT_S`; a
  fixed `FALLBACK_WAIT_S` when that field is empty), then reads. Usually the
  message is already there and nothing is waited. Sessions without the advisor
  never wait;
- the next Stop reads the transcript again (ids already recorded are skipped);
- the same script also runs on SessionEnd, so a call in the final turn of a
  session is still recorded (no notice is shown there).

A call is counted from its `server_tool_use` block; a call without a matching
`advisor_tool_result` (an interrupted consult) still counts as one attempt.

Fail-open: any error exits 0 without output.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import ledger  # noqa: E402

DEFAULT_NOTIFY_AT = 3
MAX_WAIT_S = 2.0
POLL_S = 0.1
FALLBACK_WAIT_S = 0.5
TAIL_BYTES = 256 * 1024
MATCH_CHARS = 60


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


def last_assistant_text(transcript_path: str) -> str:
    """Text of the last assistant text block in the transcript's tail, or ""."""
    try:
        with open(transcript_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - TAIL_BYTES))
            lines = f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            if any(t.strip() for t in texts):
                return "".join(texts)
    return ""


def wait_for_last_message(transcript_path: str, expected: str) -> bool:
    """Wait until the transcript's last assistant text ends like `expected`."""
    want = (expected or "").strip()[-MATCH_CHARS:]
    if not want:
        time.sleep(FALLBACK_WAIT_S)
        return False
    deadline = time.monotonic() + MAX_WAIT_S
    while True:
        if last_assistant_text(transcript_path).strip().endswith(want):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(POLL_S)


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
    all_ids = advisor_call_ids(transcript)
    if all_ids and payload.get("hook_event_name") != "SessionEnd":
        # An advisor session: the turn's last message may not be written yet.
        # Wait for it, then read again, whatever the first read found.
        wait_for_last_message(transcript, payload.get("last_assistant_message") or "")
        all_ids = advisor_call_ids(transcript)
    new_ids = [i for i in all_ids if i not in seen]
    if not new_ids:
        return

    before = ledger.count(path, "advisor_call", session_id=session_id)
    written = sum(ledger.append(path, session_id, "advisor_call", "advisor", event_id=i) for i in new_ids)
    after = before + written

    if payload.get("hook_event_name") == "SessionEnd":
        return  # the session is ending; record only
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
