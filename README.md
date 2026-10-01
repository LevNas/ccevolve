# ccevolve

Self-improving workflow plugin for Claude Code.

## Problem

Claude Code starts every session with a blank slate. Mistakes are repeated, good approaches are forgotten, and domain-specific knowledge isn't applied consistently. Manual rule maintenance doesn't scale.

## Solution

ccevolve provides the **framework** for continuous improvement:

- **Knowledge-First Flow** — search existing knowledge before starting work
- **Ledger of recurring judgments** — tool failures, permission prompts and advisor calls recorded as structured events, counted, and proposed for promotion from prose to computation (a hook, lint rule, test or permission rule)
- **Domain Rules Management** — organize rules in `.claude/rules/` to keep CLAUDE.md lean
- **Feedback Recording** — persist user corrections and validated approaches

The plugin provides the *mechanism*. Concrete rules and knowledge accumulate in **your project**, not in the plugin.

## Install

```bash
# Add marketplace (if not already added)
/plugin marketplace add LevNas/claudecode-plugins

# Install for all projects
/plugin install ccevolve@levnas-plugins --scope user

# Or install for current project only
/plugin install ccevolve@levnas-plugins --scope project
```

## What You Get

### Plugin CLAUDE.md (auto-loaded)
Defines the self-improvement workflow:
- When and how to search knowledge
- When to propose new rules
- Where to record different types of improvements

### Ledger hooks

Events go to `<project>/.claude/ledger/events.jsonl`, one JSON object per line (`ts`, `session_id`, `kind`, `key`, `id`, `detail`), with `kind` from a fixed list: `tool_error`, `permission_prompt`, `advisor_call`, and the reserved `review_finding`, `human_confirmation`. The project is `$CLAUDE_PROJECT_DIR`, so a session inside a worktree writes to the main checkout's ledger. Keys are normalized; command lines and tool output are never stored. Set `CCEVOLVE_LEDGER=0` to turn recording off. Decide per repository whether to commit `.claude/ledger/` or ignore it.

| Hook | Event | Records | Says |
|---|---|---|---|
| Error detector | `PostToolUseFailure` | `tool_error`, keyed by tool and normalized first error line | On the 2nd identical failure in a session, context for Claude asking for a fix that stops the recurrence, preferring a computed check |
| Permission observer | `PermissionRequest`, `PermissionDenied` | `permission_prompt`, keyed by tool and program name (`Bash:git`) | Nothing; returns no decision, so prompts are unchanged |
| Advisor counter | `Stop` | `advisor_call`, one per advisor server-tool call in the transcript | A notice to you each time the session's count passes a multiple of `CCEVOLVE_ADVISOR_NOTIFY_AT` (default 3): the advisor re-reads the whole conversation uncached on every call |

The advisor counter reads the block shape the Claude API documents (`server_tool_use` named `advisor`); it has not yet been checked against a real Claude Code session with the advisor on.

### Skill: `/promote-to-computation`
Runs `scripts/ledger_report.py` (counts by kind and key over a window, candidates seen at least N times, advisor calls per session) and drafts, for each recurring judgment that always has the same answer for the same input, the computed form and the prose it would retire. A human approves every proposal; the skill never writes permission rules or settings.

### Skill: `/evolve-rules`
Manages `.claude/rules/` directory:
- `init` — set up the rules directory with conventions
- List existing rules
- Add/update domain-specific rules

## How It Works

```
Error or inefficiency during work
    ↓
Analyze root cause
    ↓
Propose prevention (CLAUDE.md / .claude/rules/ / knowledge / memory)
    ↓
User approves → persist the improvement
    ↓
Next session auto-applies it
```

## Relationship with ccmemo

| | ccmemo | ccevolve |
|---|---|---|
| **Focus** | Knowledge & task persistence | Behavior improvement workflow |
| **Writes to** | `.claude/knowledge/`, `.claude/tasks/` | `CLAUDE.md`, `.claude/rules/`, `memory/` |
| **Skills** | `/record-knowledge`, `/plan-task`, `/review-knowledge` | `/evolve-rules` |
| **Hooks** | Context capture, compaction guard | Error detection |

They are complementary — ccmemo manages *what you know*, ccevolve manages *how you behave*.

## For Contributors

ccevolve follows the LevNas plugin conventions maintained in [claudecode-plugins/docs/development-guide.md](https://github.com/LevNas/claudecode-plugins/blob/main/docs/development-guide.md). Document placement and SKILL.md frontmatter rules are summarized below.

| Location | Purpose | Audience |
|----------|---------|----------|
| `README.md` | Plugin overview and usage | Users (humans) |
| `CLAUDE.md` | Auto-loaded workflow definition | Claude Code |
| `skills/<name>/SKILL.md` | Skill definition with required frontmatter (`name`/`description`/`license`/`allowed-tools`) | Claude Code |
| `skills/<name>/references/` | Runtime reference resources | Claude Code |
| `docs/` | Developer/operator internal docs | Contributors (humans) |
| `hooks/` | Hook implementations and `hooks.json`; `hooks/lib/ledger.py` is the shared ledger | Claude Code |
| `scripts/` | `ledger_report.py` (read-only counts and candidates) | Claude Code, humans |
| `tests/` | `python3 tests/test_ccevolve.py` (hooks run as subprocesses against a throwaway project) | Contributors |

Run the tests and the central linter from claudecode-plugins before sending a PR:

```bash
bash ~/src/github.com/LevNas/claudecode-plugins/scripts/lint-skills.sh ~/src/github.com/LevNas/ccevolve
```

## License

MIT
