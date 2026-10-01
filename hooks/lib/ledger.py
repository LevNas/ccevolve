"""Append-only ledger of recurring judgments, shared by the ccevolve hooks.

One JSON object per line in `<project>/.claude/ledger/events.jsonl`:

    {"ts": ISO-8601, "session_id": str, "kind": KIND, "key": str, "id": str|null, "detail": {}}

`kind` comes from a fixed vocabulary so counts stay meaningful; `key` is the
thing being counted within a kind (an error pattern, a command family, ...).
`id` lets an observer skip events it has already recorded (for example an
advisor call's server tool-use id).

The ledger never stores command lines or tool output verbatim: observers put a
normalized key in it (a tool name plus the first word of a command, an error
pattern with paths and numbers replaced), so a secret typed into a command is
not copied here.

Location: `$CLAUDE_PROJECT_DIR` when set (it stays at the main checkout when a
session enters a worktree, so one project keeps one ledger), else the hook's
`cwd`. `CCEVOLVE_LEDGER=0` turns recording off. Every function is fail-open:
an unwritable or corrupt ledger never raises into a hook.
"""

import json
import os
from datetime import datetime, timezone

KINDS = (
    "advisor_call",        # the main model consulted the advisor tool
    "permission_prompt",   # Claude Code asked the user for permission, or auto mode denied
    "tool_error",          # a tool call failed
    "review_finding",      # reserved: a review reported a finding (category as key)
    "human_confirmation",  # reserved: the model asked the user to decide
)

LEDGER_RELPATH = os.path.join(".claude", "ledger", "events.jsonl")


def enabled(env=None) -> bool:
    env = os.environ if env is None else env
    return env.get("CCEVOLVE_LEDGER", "1").strip() != "0"


def ledger_path(cwd: str, env=None) -> str:
    env = os.environ if env is None else env
    root = env.get("CLAUDE_PROJECT_DIR") or cwd or os.getcwd()
    return os.path.join(root, LEDGER_RELPATH)


def append(path: str, session_id: str, kind: str, key: str, detail=None, event_id=None) -> bool:
    """Append one event. Returns True when written."""
    if kind not in KINDS or not key:
        return False
    event = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "session_id": session_id or "",
        "kind": kind,
        "key": key[:200],
        "id": event_id,
        "detail": detail or {},
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def read(path: str):
    """Yield events; skips lines that are not valid events."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("kind") in KINDS:
                    yield event
    except OSError:
        return


def count(path: str, kind: str, session_id=None, key=None) -> int:
    return sum(
        1 for e in read(path)
        if e["kind"] == kind
        and (session_id is None or e.get("session_id") == session_id)
        and (key is None or e.get("key") == key)
    )


def recorded_ids(path: str, kind: str) -> set:
    return {e["id"] for e in read(path) if e["kind"] == kind and e.get("id")}
