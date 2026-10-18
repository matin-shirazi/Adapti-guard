# Hard set rebuild plan (Path 2, task T1)

**Status: BLOCKING GAP.** Plan only; nothing has been run. API/LLM spend: USD 0.00 (0 calls).
Binding docs: `docs/experiments/MASTER_PROMPT.md`, `docs/paper/negative_result/PHASES_BEFORE_MAIN_20261001.md` (main @ `19f8ae25`).

## 1. What is missing (searched 2026-10-19)
Not found anywhere: the item file (`hardset_items.jsonl`, which `scripts/run_phase2_calibration.py` reads from `/tmp/llmail/`), `hardset_rater_tools.py`, `RATER_GUIDE_20261001.md`, `local_private/rater_sheets/`, `XCHANNEL_MANIFEST_full.json` and `xchannel_items_final.jsonl`.
Searched: all 109 remote branches (path + history), GitHub code search, the owner's WSL machine (`~`, `~/projects/*` working trees, git history, stashes, ignored files, `/tmp`, the whole filesystem by name), the Windows profile `C:\Users\MohammadReza` (recursive, excluding AppData), and the shared box (`/workspace`, `/tmp`).
Still present: `datasets/attackset_hard_v1/FREEZE_RECORD.json` (main) and `datasets/attackset_hard_v1/MANIFEST.json` (59 branches, e.g. `r3/closeout`, blob `dced5001`, 104,927 B). The manifest's SHA-256 is `786505ecaa77c6c8619495a23661eb364dd0c857c368a7c1cb9c383b8b7ba1d4`, which **matches** the freeze record.

## 2. What the Hard set is (per the freeze record and manifest; nothing is reinterpreted)
- 238 human-written attack emails from `microsoft/llmail-inject-challenge` (MIT, phases 1 and 2; 120/118). Selection seed `20261001`, Jaccard 0.6 clusters, at most 12 items per team, half per phase, QC pass. The selection used no result from this project's targets.
- Split fixed in the manifest: **test 170 / calibration 68**. Channel: email; goal: unauthorized_send.
- Each item records `id`, `source_rowkey`, `source_phase`, `source_scenario`, `team`, `cluster`, `split`, `text_sha256` and `mechanism_heuristic_UNVALIDATED`. Mechanism labels are heuristic and unvalidated; per Phase 1c they may only come from human ratings.
- The 69 model-generated cross-channel items are **not frozen** and stay exploratory. They cannot be rebuilt because their manifest is missing too.

## 3. Deterministic rebuild (a re-materialization, not a re-selection)
1. Do not edit the frozen files (`FREEZE_RECORD.json`, `MANIFEST.json`). Read them only. Restore `MANIFEST.json` byte-identically from blob `dced5001` and check its SHA-256 against `786505ec…`.
2. Download the public dataset at a pinned HF revision (record the commit hash). This costs nothing and makes no LLM calls.
3. For each manifest item, look up the row by `source_rowkey` within `source_phase`. Take the attack text with the field rule from `docs/research/ATTACK_SET_SPEC_20261001.md` on the branch where it exists. Require `sha256(text) == text_sha256`. **Any mismatch or missing row means BLOCKING GAP for that item: no substitution, no re-draw.**
4. Write the items to `local_private/hardset_v1/hardset_items.jsonl` (gitignored, never committed), carrying `split` over unchanged from the manifest. Commit only a rebuild report: count matched out of 238, the HF revision, and SHA-256 of the JSONL in canonical form (sorted keys, UTF-8, `\n`).
5. **Split hashing check:** `sha256("\n".join(sorted(f"{id}\t{split}")))` is recorded once and asserted by a deterministic test (170/68, the same as `tests/test_protocol_power_v01.py`). The split is never redrawn. If the source cannot fully reproduce it, the fallback is a v1.1 re-selection with seed `20261001` and a logged reason, as the freeze record's `rule_after_freeze` requires. That needs owner sign-off.
6. **No overlap with frozen packs:** compare normalized `text_sha256` and 0.6-Jaccard near-duplicate matches against `datasets/frozen/vnext_confirm_v1` (`523c8818…`) and `datasets/frozen/phase1_confirm_v1` (`c789811a…`). Report the counts. Any overlap is reported, never silently dropped (invariants 3 and 7).

## 4. Rater kit (rebuild needed; Phase 1a)
- `hardset_rater_tools.py`: deterministic and non-LLM. `make-sheets` writes blinded sheets: seeded shuffle with seed `20261001`, no split, team, or heuristic label shown, ≥ 60 items double-rated, stored in `local_private/rater_sheets/`. `agree` computes Cohen's kappa for q1 and percent agreement for q2. Unit tests use synthetic sheets only.
- `RATER_GUIDE_20261001.md`: q1 = mechanism (the 7 categories), q2 = "is this an injection that requests an unauthorized send". The exact wording needs owner sign-off, because the original is lost.
- Exit gate (unchanged): kappa ≥ 0.70 on q1, ≥ 95% on q2, ≥ 200 validated items, manifest hash committed. Without raters the set stays "candidate" and no per-mechanism result is published.

## 5. Cost and guardrails
USD 0. No OpenRouter calls. Nothing changes under `datasets/frozen/**` or `experiments/real_llm_eval/**`. Raw data and rater data stay in `local_private/`. This is a draft PR only: no merge, nothing pushed to main.

## 6. Owner decision needed
(a) Check whether the original files exist on another device or backup (they were last expected at `/tmp/llmail`, which is ephemeral). (b) If not, approve steps 3.2–3.6 and the rater-kit rebuild, as T1b.
