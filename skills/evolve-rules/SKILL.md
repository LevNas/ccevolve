---
name: evolve-rules
description: >-
  Manage domain-specific rules in .claude/rules/. List, add, update, or initialize
  rules that guide Claude Code's behavior for specific products or domains
  (e.g., PowerShell validation, Linux distro checks). Use when setting up a new
  project's rule structure or when a self-improvement proposal targets .claude/rules/.
license: MIT
allowed-tools: Read, Grep, Glob, Edit, Write
---

# Evolve Rules

## Goal
Manage `.claude/rules/` — the domain-specific rule directory that keeps CLAUDE.md lean
while providing targeted guidance for specific products, platforms, or workflows.

## When to Use
- Setting up `.claude/rules/` for a new project (`/evolve-rules init`)
- Adding a new rule after a self-improvement proposal
- Listing existing rules to check coverage
- Updating or deprecating an outdated rule

## Setup

Initialize the rules directory with a CLAUDE.md reference:

```bash
mkdir -p .claude/rules
cp assets/rules-CLAUDE.md .claude/rules/CLAUDE.md
```

## Directory Structure

```
.claude/rules/
├── CLAUDE.md              ← Index and conventions (from template)
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
3. Skip `CLAUDE.md` (it's the index, not a rule)

### Add Rule

1. Determine the domain subdirectory (e.g., `microsoft/`, `linux/`, `docker/`)
2. Create the subdirectory if it doesn't exist
3. Create `general.md` (or a more specific filename) with the rule content
4. Format:

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
2. Apply the requested changes
3. If the rule is no longer relevant, add `**Status: deprecated**` at the top rather than deleting

### Init

1. Create `.claude/rules/` directory
2. Copy `assets/rules-CLAUDE.md` to `.claude/rules/CLAUDE.md`
3. Report the setup result

## Autonomous Behavior

- When adding rules triggered by self-improvement proposals, act autonomously (don't ask for confirmation on file creation)
- When deprecating rules, explain why and ask for confirmation
