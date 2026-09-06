# Logical Experiment Activity Timeline

This timeline separates an **EXPERIMENT_ID** (the immutable experiment root)
from an **ACTIVITY_DATE** (a design, protocol, implementation, execution, or
analysis event).  It is evidence navigation, not a replacement for the
referenced contract, manifest, report, or commit.

## Key lineage timeline

| Activity date | Experiment ID | Activity | Authority / primary evidence |
| --- | --- | --- | --- |
| 2026-06-16 | `exp_20260616_001`, `exp_20260616_002` | M3OT OOSM Backfill and event-gated follow-up establish rejected historical direction. | [INDEX](../experiments/INDEX.md) rows for both experiments |
| 2026-06-21 to 2026-08-01 | MATRIX mechanism line | Dataset readiness, delay/uncertainty, counterfactual, fixed-lag, and identity-cue investigations establish the prior observation-level evidence chain. | [INDEX](../experiments/INDEX.md) and linked analysis cards |
| 2026-08-02 | MDMT adapter/readiness transition | Dataset-neutral local-tracklet adapter makes paired MDMT evaluation feasible. | `exp_20260802_005` card in [INDEX](../experiments/INDEX.md) |
| 2026-08-03 | MDMT local tracking | Person local-tracklet readiness completes; async incremental fusion calibration remains blocked. | `exp_20260803_001` and `002` Index rows |
| 2026-08-04 to 2026-08-05 | MDMT MIA execution authority | Author synchronous reproduction, active packet-runtime exact equivalence, and channel audit establish the synchronous/packetized lineage. | `exp_20260804_003`, `exp_20260805_002`, `exp_20260805_003` Index rows |
| 2026-08-08 / 2026-08-13 | `exp_20260808_001_mdmt_mia_id_supplement_cascade` | E023 formal analysis: delay-conditioned candidate/Supplement mechanism evidence on 14 official test pairs. | [`FORMAL_ANALYSIS_REPORT.md`](../experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md) |
| 2026-08-17 | `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation` | Experiment root/design created for non-test compensation-onset validation. | commit `469f065`; `EXPERIMENT_CONTRACT.md` |
| 2026-08-18 | same EID | Frozen onset decisions and GT-protocol execution plan recorded. | commits `c5fd943`, `fec3422` |
| 2026-08-19 | same EID | Historical official-export gate fails closed; Route-B Source-MDA remains separately scoped. | commit `292d5cd`; `GT_PROTOCOL_GATE` evidence |
| 2026-09-04 | same EID | Source-MDA-v1 fresh source-protocol preflight, Y01 parity authority, composed MVE implementation, and execution-plan evidence completed. | commits `639dd62`, `2f5dd64`, `68dd12a`, `25c2713` and reports in the immutable EID root |
| 2026-09-05 | same EID | Pair53/66 MVE execution/measurement validity and frozen 15-pair development package are completed; cache-seed repair is retained as failed historical evidence. | commits `afb167b`, `657372a`, `69496bd`, `7e18f76`; post-MVE/development validity reports |
| 2026-09-06 | same EID | Single-batch frozen 15-pair development analysis completes: d1--d4 pass A--F; frozen ascending rule selects earliest onset `d1`; d5 fails Gate A only. | commit `6c57e15`; `FROZEN_15_PAIR_DEVELOPMENT_SCIENTIFIC_ANALYSIS.md` |
| 2026-09-06 | same EID | Non-authoritative GPT Web discussion prompt recorded; it does not change scientific execution provenance. | commit `3fb7edd`; `GPT_WEB_DISCUSSION_PROMPT.md` |
| 2026-09-03 onward | `packet_census_z0_train_all_hfallback_v1` | Accepted Homography-fallback successor packet census completes; earlier predecessor census remains historical invalid. | [`PACKET_CENSUS_RUN_REPORT.md`](../PACKET_CENSUS_RUN_REPORT.md) |

## Current onset experiment state

```text
EXPERIMENT_ID = exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation
EXPERIMENT_START_DATE = 2026-08-17
LATEST_SCIENTIFIC_ACTIVITY_DATE = 2026-09-06

DEVELOPMENT_EXECUTION = COMPLETE (255/255 accepted)
DEVELOPMENT_ANALYSIS = COMPLETE
EARLIEST_FROZEN_ONSET = d1
HOLDOUT_CONFIRMATION = NOT_RUN
PAPER_READINESS = NEEDS_HOLDOUT
```

The latest activity date does not create a new experiment and does not alter
the experiment-root directory date.  The next scientifically meaningful action
remains separately authorized locked `d1` holdout confirmation; this timeline
does not authorize that action.
