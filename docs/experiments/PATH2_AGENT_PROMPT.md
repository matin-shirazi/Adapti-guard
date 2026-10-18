# Path 2 agent prompt

Read docs/experiments/MASTER_PROMPT.md and
docs/paper/negative_result/PHASES_BEFORE_MAIN_20261001.md only; they bind you.
Goal: Path 2, i.e. confirmatory evidence for the negative-result manuscript.

Facts not elsewhere in the repo (2026-10-19):
- The Hard set, hardset_rater_tools.py, RATER_GUIDE and rater sheets are on no
  branch; they are likely on the owner's machine.
- OpenRouter key limit is USD 1 (needs 3). About USD 2.04 of budget remains.

Extra rules: API=0 unless the owner approves a run and its cap. Never commit
local_private/. Missing data means "BLOCKING GAP", then stop.

Tasks (one at a time, each on its own branch with a draft PR):
- T1 Get the Hard set files from the owner; commit manifest + split + tools with
  SHA-256. If not found: a 1-page rebuild plan, then stop.
- T2 Deterministic checks + pytest: uniqueness, no overlap with frozen packs,
  hashed split.
- T3 Blind sheets generator, 2-page rater guide, kappa tool + test.
- T4 Phase 2 manifests with USD caps and a no-API dry run; ask owner to approve.
- T5 OSF preregistration draft.
- T6 After runs: update section 6.6 via scripts/assemble_manuscript.py, run the
  ledger test.

Report to owner in Persian, max 5 lines: done / blocked / his next action / USD spent.
