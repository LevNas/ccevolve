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

## Candidates from throwaway scripts

A script Claude writes again and again in temporary places (a sed copy of last time's, with new constants) is a step that wants to be a plugin script. The ledger does not see these; the transcripts do.

1. List the facts, with the output folder outside every git repository (the script refuses one inside: it copies script bodies out of the transcripts):

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/script_facts.py" --out <folder>
   ```

   The window is `--days N`, else `CCEVOLVE_TRANSCRIPT_DAYS`, else 60 days. Quote its first line in the report: it says how many days of transcripts there really were, on this machine only.
2. Group the scripts by purpose with one read-only subagent (Read, Grep, Glob). Give it `facts.json` and the `scripts/` folder, and ask for groups with their grounds: which scripts, and which lines show the shared purpose. Names alone are not grounds. The grouping is the subagent's; what to propose is yours.
3. Write the report yourself:
   - Take only groups created in two or more sessions, or run five or more times.
   - Deletion test: if this became one plugin script, would the complexity gather in one place, or only move?
   - Mark each **Strong**, **Worth exploring** or **Speculative**, and name where it would live (which plugin or repository).
   - Name the recorded failure it would fix: a knowledge-base entry (with ccmemo installed), an issue or a PR. A candidate with no such record stays **Speculative**. If every candidate is Speculative, say there is nothing to promote.
4. Stop at the report and let the user pick one, or none. Build nothing before that.

## Retiring

A check that never fires is also a candidate: propose deleting it with the evidence (no matching events over a long window). Keep the ledger window long enough (90 days or more) before calling a check dead.
