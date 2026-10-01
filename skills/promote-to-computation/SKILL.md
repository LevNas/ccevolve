---
name: promote-to-computation
description: Review the ccevolve ledger of recurring judgments (tool errors, permission prompts, advisor calls, review findings) and propose promoting the recurring ones from prose to computation — a hook, lint rule, test, gate or permission rule — and retiring prose a check now covers. Use during periodic review, at session wrap, or when the same failure or prompt keeps coming back.
license: MIT
allowed-tools: Bash, Read
---

# Promote to computation

Prose rules cost context every session and depend on the model reading them right. A judgment that gives the same answer for the same input can be a computation instead, which costs no context and does not drift. This skill turns the ledger into proposals; a human approves each one.

## Steps

1. Count the ledger from the repository root:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ledger_report.py" --days 30
   ```

   Add `--json` for structured output, `--kind tool_error` to focus, `--min-count N` to change the threshold (default 3).
2. For each candidate, ask: **given the same input, is the answer always the same?** If not (a design trade-off, a new situation, a value judgment), leave it to reasoning and say so.
3. If yes, draft the computed form, matched to the kind:
   - `tool_error` → a hook, lint rule, test or wrapper script that prevents it
   - `permission_prompt` → an `allow` / `ask` / `deny` rule, or a narrower command; never broaden to a family that runs arbitrary code (`bash *`, `python3 *`)
   - `review_finding` → a machine gate (lint, review gate entry, test)
   - `human_confirmation` → a fixed rule for when to ask; a standing authorization is written by the user, not by Claude
4. Name the prose it would retire (a line in CLAUDE.md, a rule file, an ADR paragraph). After the check is adopted, propose removing that prose from the always-loaded side and keeping only the reason, read on demand.
5. Present the proposals together. Do not apply any of them, and never write permission rules or settings yourself: changes that widen Claude's own permissions or instructions are the user's to make.
6. Advisor calls: if one session shows many calls (`advisor calls per session`), suggest starting such sessions with `--advisor` only when needed, or timing guidance in CLAUDE.md.

## Retiring

A check that never fires is also a candidate: propose deleting it with the evidence (no matching events over a long window). Keep the ledger window long enough (90 days or more) before calling a check dead.
