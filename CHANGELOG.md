# Changelog

## 0.2.0

Ledger of recurring judgments and promotion from prose to computation (#3).

- **Ledger** (`hooks/lib/ledger.py`): append-only `<project>/.claude/ledger/events.jsonl` with a fixed `kind` vocabulary (`tool_error`, `permission_prompt`, `advisor_call`; `review_finding` and `human_confirmation` reserved). Keys are normalized; command lines and tool output are never stored. `$CLAUDE_PROJECT_DIR` picks the project, so worktree sessions share the main checkout's ledger. `CCEVOLVE_LEDGER=0` turns it off. Fail-open.
- **Advisor counter** (`Stop`): records each advisor server-tool call found in the transcript once, and notifies the user each time the session's count passes a multiple of `CCEVOLVE_ADVISOR_NOTIFY_AT` (default 3). Claude Code has no setting to cap advisor calls, and each call re-reads the conversation uncached. The parser follows the Claude API's documented block shape and is not yet checked against a real session with the advisor on.
- **Permission observer** (`PermissionRequest`, `PermissionDenied`): records prompts keyed by tool and program name (`Bash:git`); for compound commands the first real program after `cd` / `pushd` (`cd repo && git push` → `Bash:git`). Returns no decision.
- **Skill `/promote-to-computation`** and `scripts/ledger_report.py`: counts by kind and key over a window, candidates seen at least N times, advisor calls per session; the skill drafts the computed form and the prose it would retire, for human approval. It never writes permission rules or settings.
- `tests/test_ccevolve.py`: 29 checks.

### Fixed

- The error detector never saw a failure: it was registered on `PostToolUse`, which fires only after a tool succeeds, and read a `tool_output` field. It now listens on `PostToolUseFailure` and reads `error`, skips interrupts, records to the ledger instead of a shared `/tmp` file that was never cleared, masks token-like strings (20+ characters containing a digit) in the key, and returns its nudge as `additionalContext` for Claude (a `systemMessage` is shown to the user). The nudge now prefers a computed check over more prose.

## 0.1.0

- Knowledge-First Flow, error detection hook, `/evolve-rules` skill.
