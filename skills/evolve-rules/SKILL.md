---
name: evolve-rules
description: >-
  Manage domain-specific rules in .claude/rules/. List, add, update, or deprecate
  rules that guide Claude Code's behavior for specific products or domains
  (e.g., PowerShell validation, Linux distro checks). Use when listing rules to
  check coverage, adding or updating a rule, retiring an outdated one, or when a
  self-improvement proposal targets .claude/rules/.
license: MIT
allowed-tools: Read, Grep, Glob
---

# Evolve Rules

## Goal
Manage `.claude/rules/` — the domain-specific rule directory that keeps CLAUDE.md lean
while providing targeted guidance for specific products, platforms, or workflows.

## When to Use
- Adding a new rule after a self-improvement proposal
- Listing existing rules to check coverage
- Updating or deprecating an outdated rule

## Directory Structure

```
.claude/rules/
├── microsoft/
│   └── general.md         ← PowerShell validation, Azure CLI conventions
├── linux/
│   └── general.md         ← Distro confirmation, package manager rules
├── docker/
│   └── general.md         ← Build flags, image tagging conventions
└── ...
```

## Operations

### List Rules

1. Glob `.claude/rules/**/*.md` to find all rule files
2. For each file, read the first `#` heading and display as a summary table
3. Skip `CLAUDE.md` (some repositories keep an index there; it is not a rule)

### Add Rule

1. Determine the domain subdirectory (e.g., `microsoft/`, `linux/`, `docker/`)
2. Create `.claude/rules/<domain>/` if it doesn't exist (this also creates `.claude/rules/`; no separate setup step is needed)
3. Show the user which file you will create and its full content, and get the user's approval
4. Create `general.md` (or a more specific filename) with the approved content
5. Format:

```markdown
# Rule Title

## When
Describe when this rule applies.

## Rule
The specific rule or checklist to follow.

## Why
The reason this rule exists (incident, best practice, etc.).
```

### Update Rule

1. Read the existing rule file
2. Show the user the file and the change you will make, and get the user's approval
3. Apply the approved changes
4. If the rule is no longer relevant, explain why, get the user's approval, and add `**Status: deprecated**` at the top rather than deleting

## Approval

- Never add, update or deprecate a rule without the user's approval, including a rule from a self-improvement proposal
- This skill does not pre-approve `Edit` or `Write`. Unless the user's own settings (allow rules or auto mode) permit them, Claude Code asks the user before each write to a rule file. If they do permit them, the approval steps above are the only safeguard
