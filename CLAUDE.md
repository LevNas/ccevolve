# ccevolve — notes for working on this repository

This file is not shipped with the plugin. Only sessions working inside this repository read it.

## Layout

- `hooks/` — hook scripts and `hooks.json`; `hooks/lib/ledger.py` is the shared ledger
- `skills/` — `evolve-rules`, `promote-to-computation`
- `scripts/` — `ledger_report.py` (read-only counts and candidates)
- `tests/` — `test_ccevolve.py` (runs the hooks as subprocesses against a throwaway project)

## Checks before a PR

The linter is `scripts/lint-skills.sh` in LevNas/claudecode-plugins. Run it from your clone of that repository and pass the path of this one:

```bash
python3 tests/test_ccevolve.py
bash <claudecode-plugins>/scripts/lint-skills.sh <path-to-ccevolve>
```

## Releasing

- When a PR changes hooks, skills or scripts, bump `version` in `.claude-plugin/plugin.json` in the same PR. The plugin cache is keyed by version, so without a bump the change does not reach users.
- Update `README.md` and `CHANGELOG.md` in the same PR as the change they describe.
