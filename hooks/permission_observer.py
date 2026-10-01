#!/usr/bin/env python3
"""PermissionRequest / PermissionDenied hook: count permission prompts in the ledger.

Records one `permission_prompt` event each time Claude Code is about to ask
the user for permission (PermissionRequest) or auto mode denies a call
(PermissionDenied). The ledger then shows which prompts recur — the input for
deciding what to allow, ask or deny by rule instead of by hand each time.

Privacy: the key is the tool name plus, for Bash, only the first word of the
command (`Bash:git`, `Bash:curl`, `WebFetch`). The full command line is never
stored, because commands can carry secrets.

This hook returns no decision, so the user still sees the prompt as before.
Fail-open: any error exits 0 without output.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import ledger  # noqa: E402


NAVIGATION = {"cd", "pushd", "popd"}
# Programs that never need a permission of their own: in a compound command the
# prompt is about something else (`printf msg > f && git commit -F f` is a git
# prompt). Used only when another program is present.
HARMLESS = {"printf", "echo", "true", "false", ":", "sleep", "test", "[", "pwd", "date"}


def _program(segment: str) -> str:
    """Program name of one command segment, skipping VAR=value assignments and '('."""
    words = [w for w in segment.replace("(", " ").split()
             if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", w)]
    first = os.path.basename(words[0]) if words else ""
    return re.sub(r"[^A-Za-z0-9._+-]", "", first)[:40]


def prompt_key(tool_name: str, tool_input) -> str:
    if tool_name == "Bash" and isinstance(tool_input, dict):
        command = str(tool_input.get("command", "")).strip()
        # Key on the first significant program: `cd dir && git push` and
        # `printf msg > f && git commit -F f` are git prompts.
        programs = [p for p in (_program(s) for s in re.split(r"&&|\|\||;", command)) if p]
        real = [p for p in programs if p not in NAVIGATION]
        significant = [p for p in real if p not in HARMLESS]
        first = (significant or real or programs or [""])[0]
        return f"Bash:{first}" if first else "Bash"
    return tool_name or "unknown"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return
    if not isinstance(payload, dict) or not ledger.enabled():
        return
    event = payload.get("hook_event_name", "")
    outcome = {"PermissionRequest": "asked", "PermissionDenied": "auto_denied"}.get(event)
    if not outcome:
        return
    ledger.append(
        ledger.ledger_path(payload.get("cwd") or os.getcwd()),
        payload.get("session_id") or "",
        "permission_prompt",
        prompt_key(payload.get("tool_name", ""), payload.get("tool_input")),
        detail={"outcome": outcome, "mode": payload.get("permission_mode", "")},
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 — a hook must never break a session
        pass
    sys.exit(0)
