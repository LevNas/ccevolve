#!/usr/bin/env python3
"""PostToolUse hook: detect recurring Bash errors and suggest self-improvement.

When a Bash command fails (exit code != 0), this hook tracks the error pattern.
If the same pattern occurs 2+ times in a session, it prompts Claude Code to
propose a rule or knowledge entry to prevent recurrence.

Error patterns are tracked in a temporary file per session under /tmp.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime


def get_tracker_path(cwd: str) -> str:
    """Return the path to the session error tracker file."""
    # Use cwd hash to separate trackers per project
    cwd_hash = hashlib.md5(cwd.encode()).hexdigest()[:8]
    return os.path.join("/tmp", f"ccevolve-errors-{cwd_hash}.jsonl")


def normalize_error(stderr: str) -> str:
    """Extract a normalized error pattern from stderr.

    Strips variable parts (paths, line numbers, timestamps) to group
    similar errors together.
    """
    if not stderr:
        return ""

    # Take first meaningful line
    for line in stderr.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip common noise
        if line.startswith(("+ ", "Warning:", "Note:", "Exit code")):
            continue
        # Normalize paths
        line = re.sub(r"/[^\s:]+", "<path>", line)
        # Normalize numbers
        line = re.sub(r"\b\d+\b", "<N>", line)
        return line[:120]

    return stderr[:120]


def load_error_counts(tracker_path: str) -> dict[str, int]:
    """Load error pattern counts from the tracker file."""
    counts: dict[str, int] = {}
    if not os.path.isfile(tracker_path):
        return counts

    try:
        with open(tracker_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    pattern = entry.get("pattern", "")
                    if pattern:
                        counts[pattern] = counts.get(pattern, 0) + 1
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass

    return counts


def append_error(tracker_path: str, pattern: str, command: str) -> None:
    """Append an error entry to the tracker file."""
    entry = {
        "pattern": pattern,
        "command": command[:200],
        "time": datetime.now().isoformat(),
    }
    try:
        with open(tracker_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        return

    tool_output = input_data.get("tool_output", "")
    tool_input = input_data.get("tool_input", {})
    cwd = input_data.get("cwd", os.getcwd())

    # Check for error exit code in output
    # Bash tool output includes "Exit code N" on failure
    if "Exit code" not in tool_output:
        return

    exit_match = re.search(r"Exit code (\d+)", tool_output)
    if not exit_match or exit_match.group(1) == "0":
        return

    command = tool_input.get("command", "")
    stderr = tool_output

    # Normalize the error pattern
    pattern = normalize_error(stderr)
    if not pattern:
        return

    tracker_path = get_tracker_path(cwd)

    # Load existing counts before appending
    counts = load_error_counts(tracker_path)
    previous_count = counts.get(pattern, 0)

    # Record the error
    append_error(tracker_path, pattern, command)

    # If this pattern has occurred before, suggest improvement
    if previous_count >= 1:
        total = previous_count + 1
        result = {
            "systemMessage": (
                f"[ccevolve] 同じエラーパターンが{total}回発生しています: "
                f"`{pattern[:80]}` — "
                "再発防止のため、以下のいずれかを提案してください:\n"
                "1. CLAUDE.md にルールを追加\n"
                "2. .claude/rules/ に領域別ルールを作成\n"
                "3. .claude/knowledge/entries/ にナレッジを記録"
            )
        }
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
