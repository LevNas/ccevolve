# ccevolve

Self-improving workflow plugin for Claude Code.

## Problem

Claude Code starts every session with a blank slate. Mistakes are repeated, good approaches are forgotten, and domain-specific knowledge isn't applied consistently. Manual rule maintenance doesn't scale.

## Solution

ccevolve provides the **framework** for continuous improvement:

- **Ledger of recurring judgments** — tool failures, permission prompts and advisor calls recorded as structured events, counted, and proposed for promotion from prose to computation (a hook, lint rule, test or permission rule)
- **Domain Rules Management** — organize rules in `.claude/rules/` to keep CLAUDE.md lean, written only after the user approves

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

### What the plugin does not ship
A Claude Code plugin can carry skills, agents, hooks, MCP and LSP servers, monitors, `bin/` executables and settings. It cannot carry a `CLAUDE.md` or rules that load into every session (see the [plugins reference](https://code.claude.com/docs/en/plugins-reference.md) and [memory](https://code.claude.com/docs/en/memory.md)). So ccevolve ships hooks and skills only.

Guidance you want read in every session (search the knowledge base before starting work, when to propose a rule) belongs in your repository's own `CLAUDE.md` or `.claude/rules/`. The ccharness plugin's scaffold writes these, if installed.

### Ledger hooks

Events go to `<project>/.claude/ledger/events.jsonl`, one JSON object per line (`ts`, `session_id`, `kind`, `key`, `id`, `detail`), with `kind` from a fixed list: `tool_error`, `permission_prompt`, `advisor_call`, and the reserved `review_finding`, `human_confirmation`. The project is `$CLAUDE_PROJECT_DIR`, so a session inside a worktree writes to the main checkout's ledger. Keys are normalized; command lines and tool output are never stored. Set `CCEVOLVE_LEDGER=0` to turn recording off. Decide per repository whether to commit `.claude/ledger/` or ignore it.

| Hook | Event | Records | Says |
|---|---|---|---|
| Error detector | `PostToolUseFailure` | `tool_error`, keyed by tool and normalized first error line | On the 2nd identical failure in a session, context for Claude asking for a fix that stops the recurrence, preferring a computed check |
| Permission observer | `PermissionRequest`, `PermissionDenied` | `permission_prompt`, keyed by tool and program name (`Bash:git`) | Nothing; returns no decision, so prompts are unchanged |
| Advisor counter | `Stop`, `SessionEnd` | `advisor_call`, one per advisor server-tool call in the transcript (a call written after the Stop hook started is caught by a short retry in advisor sessions, the next Stop, or SessionEnd) | A notice to you each time the session's count passes a multiple of `CCEVOLVE_ADVISOR_NOTIFY_AT` (default 3): the advisor re-reads the whole conversation uncached on every call |

The advisor counter reads the block shape the Claude API documents (`server_tool_use` named `advisor`), confirmed on a real Claude Code session (v2.1.284, Fable 5.1 advisor).

### Skill: `/promote-to-computation`
Runs `scripts/ledger_report.py` (counts by kind and key over a window, candidates seen at least N times, advisor calls per session) and drafts, for each recurring judgment that always has the same answer for the same input, the computed form and the prose it would retire. A human approves every proposal; the skill never writes permission rules or settings.

### Skill: `/evolve-rules`
Manages `.claude/rules/` directory:
- List existing rules
- Add/update/deprecate domain-specific rules
- Shows the file and the text first, and writes only after the user approves

## How It Works

```
Error, permission prompt or advisor call during work
    ↓
Hooks record it in the ledger (.claude/ledger/events.jsonl)
    ↓
Analyze the recurring ones (/promote-to-computation)
    ↓
Propose prevention in your repository:
  CLAUDE.md / .claude/rules/ / knowledge / a hook or check
    ↓
User approves → the change is written to your repository
    ↓
Later sessions read it from your repository, not from the plugin
```

## Relationship with ccmemo

| | ccmemo | ccevolve |
|---|---|---|
| **Focus** | Knowledge & task persistence | Behavior improvement workflow |
| **Writes to** | `.claude/knowledge/`, `.claude/tasks/` | `.claude/rules/` (`/evolve-rules`, after approval), `.claude/ledger/events.jsonl` |
| **Skills** | `/record-knowledge`, `/plan-task`, `/review-knowledge` | `/evolve-rules`, `/promote-to-computation` |
| **Hooks** | Context capture, compaction guard | Error detector, permission observer, advisor counter (ledger) |

They are complementary — ccmemo manages *what you know*, ccevolve manages *how you behave*.

## For Contributors

ccevolve follows the LevNas plugin conventions maintained in [claudecode-plugins/docs/development-guide.md](https://github.com/LevNas/claudecode-plugins/blob/main/docs/development-guide.md). Document placement and SKILL.md frontmatter rules are summarized below.

| Location | Purpose | Audience |
|----------|---------|----------|
| `README.md` | Plugin overview and usage | Users (humans) |
| `CLAUDE.md` | Notes for working on this repository; not loaded by the plugin | Contributors, Claude Code sessions in this repository |
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
