# C6 Formal Attempt4 Observation-Only Evidence Package

## Scope and discovery

- Experiment: `exp_20260915_001_mdmt_mia_c6_pre_service_semantic_suppression`
- Formal run: `attempt4`
- Runtime commit: `905be37df4de1a5ad10d2758739eff21caca4ebe`
- Authorization SHA-256: `d9d9fccc22bcda92bb61c3d9ce6fee46e8bf104f3562b4c82f7a714277552bc3`
- Formal seal SHA-256: `ed7c531f70f58b1c5797bced2fb8883135b949ef0871fe38bc51dac63cbc1e6a`
- Author config: `/mnt/data/yzm/experiments/mdmt_mia_official/run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py`
- Detector checkpoint: `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth`
- Source: `summary_md/communication/c6_formal/_formal_runs/attempt4/C6_FORMAL_AGGREGATION.json`
- The review used only C6 communication/service evidence and runtime metadata. Tracking outcomes were not read.

## Artifact status

The Formal run ended `FORMAL_RUN_END / PASS`. All four cells are `VALID`; the aggregation, per-cell terminal records, and Formal seal were present and internally consistent. Independent recomputation reproduced each cell's three scientific quantities and both the Formal and baseline seals. No incomplete or failed Formal cell is included.

## Per-cell observations

| Cell | Role | Rate (bytes/s) | `B_avoided` | Treatment serviceable ID bytes | Baseline serviceable ID bytes | Delta | Runtime (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `pair_23__FIFO_strong` | primary efficacy | 16,649 | 7,299,121 | 0 | 3,221,174 | -3,221,174 | 1,459.491 |
| `pair_23__FIFO_mild` | stress control | 31,987 | 7,299,121 | 0 | 0 | 0 | 1,424.206 |
| `pair_44__FIFO_moderate` | low-opportunity control | 26,148 | 5,619,894 | 0 | 5,533,432 | -5,533,432 | 155.632 |
| `pair_66__FIFO_mild` | low-opportunity control | 31,987 | 5,784,574 | 0 | 5,543,264 | -5,543,264 | 141.402 |

Every observed treatment first-service ID-State decision was suppressed: `2097/2097`, `2097/2097`, `1077/1077`, and `897/897`, respectively. Treatment serviceable ID-State serviced bytes were therefore zero in every cell. This table contains one deterministic run per cell; there are no multi-seed estimates, variances, confidence intervals, or significance tests.

## Consistency checks

- Cell order, roles, service rates, baselines, metrics, and roots match the issued authorization.
- All cells use the same runtime commit, author configuration, and detector checkpoint.
- The recorded experimental seed is `unknown`; `PYTHONHASHSEED=0` is a runtime determinism setting and is not reported as an experiment seed.
- `B_avoided`, treatment serviceable bytes, and deltas were reproduced from the per-cell decision records and service ledgers.
- Every cell reports zero future reads, source bypass reads, published-history rewrites, feedback-chain mismatches, wire-roundtrip digest mismatches, and NumPy alias violations.

## Warnings and data issues

- The treatment trajectory contains no non-suppressed first-service ID-State decision in any cell.
- Suppressed decisions with an empty `packet_reason_flags` list number 1,021 for P23, 240 for P44, and 305 for P66.
- P44 and P66 `B_avoided` values exceed their frozen C5 descriptive opportunity references and therefore meet the preregistered forensic-review flag.
- The C5 opportunity references describe a different trajectory and are not treated here as upper bounds on the C6 treatment values.
- No tracking outcome was opened, aggregated, or interpreted.
