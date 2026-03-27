# ccevolve

Self-improving workflow plugin for Claude Code.

## Problem

Claude Code starts every session with a blank slate. Mistakes are repeated, good approaches are forgotten, and domain-specific knowledge isn't applied consistently. Manual rule maintenance doesn't scale.

## Solution

ccevolve provides the **framework** for continuous improvement:

- **Knowledge-First Flow** — search existing knowledge before starting work
- **Error Detection Hook** — detect recurring Bash errors and prompt rule creation
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

### PostToolUse Hook: Error Detector
Monitors Bash tool failures. When the same error pattern occurs 2+ times, prompts you to create a preventive rule or knowledge entry.

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

## License

MIT
