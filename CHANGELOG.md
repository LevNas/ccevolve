# Changelog

## 0.2.3

- **Advisor counter waits for the turn's last message instead of guessing from mtime.** Second live check (two advisor calls in one turn): the message holding the second call was written in one go when the ~36 s consult ended, a few milliseconds after Stop hooks started, and nothing was written during the consult, so the transcript's mtime was 36 s old and 0.2.2 decided it was not being written. In advisor sessions the Stop hook now waits until the transcript's last assistant text ends like the Stop input's `last_assistant_message` (polls every 0.1 s, at most 2 s; 0.5 s when that field is empty). The message is usually already there, so nothing is waited. Sessions without the advisor never wait.
- A `server_tool_use` advisor call without a matching `advisor_tool_result` (seen once live, an interrupted consult) counts as one attempt.
- Test: 37 checks, including the live shape (old mtime, last message landing after the hook started).

## 0.2.2

- **Advisor counter retry**: 0.2.1 retried only when the first read found nothing new. In a session where an earlier call had been missed at its own Stop, the next Stop found that older call as new, skipped the retry, and missed the call of the current turn again. The retry now runs in every advisor session whose transcript changed under 2 s ago, whatever the first read found. Sessions without the advisor still never wait. Test: 36 checks.

## 0.2.1

Fixes from the first live check with `claude --advisor fable` (Opus 5.5 main, Fable 5.1 advisor).

- **Advisor counter missed the call at the Stop of the same turn.** The transcript is written asynchronously: the turn's last assistant message, which held the advisor call, landed about 50 ms after Stop hooks started, so the hook read a transcript without it (the next Stop would have counted it; a session that ended there never would). Now the same script also runs on `SessionEnd` (records only, no notice), and in a session that has already used the advisor, when nothing new is found and the transcript changed under 2 s ago, the Stop hook waits 0.5 s once and reads again. Sessions without the advisor never wait.
- **Permission key for compound commands**: `printf msg > f && git add . && git commit -F f` was keyed `Bash:printf`; harmless programs (`printf`, `echo`, `true`, `sleep`, `test`, `pwd`, `date` …) are now skipped when another program is present, so it is `Bash:git`.
- Confirmed live: the transcript stores the call as `server_tool_use` named `advisor` and the result as `advisor_tool_result` with an `advisor_redacted_result` (encrypted) body, as the parser assumed; `PostToolUseFailure` and `PermissionRequest` events reached the ledger.
- `tests/test_ccevolve.py`: 35 checks (late write caught by retry, no wait without the advisor, SessionEnd records without notice, compound-command keys).

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
