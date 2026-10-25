# Papers status

Status as of 2026-10-19. This repository holds more than one manuscript. Only one is current. Read this table before citing anything.

| Manuscript | Branch | File | Status | May be claimed | May not be claimed |
|---|---|---|---|---|---|
| **Reference Solutions That Fail Their Own Checks** (AgentDyn audit) | `audit/pivot-checks` (owner-label update in draft PR #165, branch `audit/owner-labels`) | `pivot-checks/MANUSCRIPT_SUBMISSION.md` | **Primary.** Being prepared for arXiv and TMLR. Not yet submitted. | At AgentDyn commit `5353cf7`, 20 of 28 AgentDyn-specific injection tasks ship a reference solution that fails the task's own security check, confirmed by executing the suite's check logic. Secondary results only as scoped in the manuscript. | Anything about the AdaptiGuard defense. Ranking reversals as a main result (they are secondary and mostly vanish under task-clustered inference). |
| **What Reached the Executor?** (AdaptiGuard negative result) | `main` | `docs/paper/negative_result/MANUSCRIPT_DRAFT_v1.md` (and `arxiv/`) | **Superseded, do not cite.** | Nothing, until the correction below is reviewed and applied. | The headline numbers 0.44->0.90 and 0.97->0.80. A PROPOSED correction (2026-10-15) states that in E1 the target model emitted no parseable tool call (0 of 488 predictions), so the "executed" record is the defense's deny log. See `docs/research/corrections/MANUSCRIPT_CORRECTIONS_DRAFT.md` on branch `docs/e1-b3-corrections` (commit `e8e9436`). The correction is not merged. |
| Confirmatory study (InjecAgent, defenses including SPOT_TOOL) | `phase3/confirmatory-protocol`, `analysis/confirmatory-results` | `docs/protocols/CONFIRMATORY_PROTOCOL_DRAFT_v0.1.md`, `docs/research/artifacts/confirmatory_results.json` | **In progress, unregistered.** The protocol says "FROZEN. NOT REGISTERED." Run R2 (`experiments/external/20261014T142921Z`) has manifest status `AUTH_MISMATCH`: the launcher's post-run cost check failed (`docs/protocols/DEVIATIONS.md`, D7, itself PROPOSED). | Nothing. | **No claim is made from this study, including the SPOT_TOOL results on llama and qwen.** |

## Older material

Everything else under `docs/paper/` (for example `dual_track/`, `workshop_vnext_fail/`, `phase1/`, `q1_findings/` and the numbered section files) is historical. It is kept for provenance and is not a current claim. `docs/paper/DUAL_TRACK_STATUS.md` and `docs/paper/CLAIMS_DUAL_TRACK.md` describe the earlier Track A / Track B results.

## Rules

- No number in any manuscript or frozen file was changed to write this page.
- The PROPOSED corrections are linked, not applied. Applying them needs the owner's review.
