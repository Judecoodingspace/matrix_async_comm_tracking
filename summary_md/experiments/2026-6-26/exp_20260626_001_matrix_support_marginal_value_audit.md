# exp_20260626_001_matrix_support_marginal_value_audit

## Purpose

Audit whether delayed support observations have enough marginal identity value
to justify geometry-only risk-aware fusion under the current Stage A setup:
two-stage tracking, GT identity, reliable capture time, and noisy GT
world-coordinate support.

## Hypothesis

If support observations add little identity information because `personID` is
already the GT identity key, then coordinate noise cost should dominate and
geometry-only risk gates should remain below `drop_delayed`. In that case the
Stage A transition rule should stop requiring risk-aware IDF1 to exceed
`drop_delayed` and should instead treat Stage A as a harm-boundary result.

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frames: `0-199`
- Identity key: `personID`
- Position key: `positionID` as per-frame grid/location key
- Primary drone: `D1` / `drone_id=0`
- Support drones: `D2-D8`
- Delay profile: `fixed_2`
- Capture time: reliable; timestamp jitter disabled
- Pose/world-coordinate noise: `0.25m`, `0.50m`, `1.00m`
- Seed: `7`
- Baselines: `drop_delayed`, `timestamped_uncertain_fusion`
- Risk pipelines: `risk_aware_delayed_fusion`,
  `risk_aware_v2a_authority_cap`, `risk_aware_v2c_cap_plus_margin`
- Attribution categories: `helpful_support`, `harmful_accept`,
  `over_reject_or_underweight`, `neutral`
- Event subsets: `proximity`, `crossing_like`, `high_motion`,
  `support_only`, `normal`

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_support_marginal_value_audit.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 \
  --frame-end 199 \
  --delay-profiles fixed_2 \
  --pose-noise-levels 0.25 0.50 1.00 \
  --seed 7 \
  --output-dir outputs/20260626_matrix_support_marginal_value_audit
```

## Output

```text
outputs/20260626_matrix_support_marginal_value_audit/support_marginal_value_summary.csv
outputs/20260626_matrix_support_marginal_value_audit/support_marginal_value_by_event_subset.csv
outputs/20260626_matrix_support_marginal_value_audit/support_gate_outcome_breakdown.csv
outputs/20260626_matrix_support_marginal_value_audit/support_only_case_samples.csv
outputs/20260626_matrix_support_marginal_value_audit/stage_a_transition_decision.md
```

## Key Metrics

Decision:

```text
close_stage_a_boundary
```

V2C cap+margin summary:

| Pose noise | V2C IDF1 | Drop IDF1 | Uncertain IDF1 | V2C IDSW/1k | Helpful | Harmful | Weak/reject | Net |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.25 | 0.153250 | 0.352500 | 0.357500 | 227.125000 | 1113 | 1050 | 3209 | -3146 |
| 0.50 | 0.177625 | 0.352500 | 0.077125 | 204.375000 | 2673 | 853 | 3536 | -1716 |
| 1.00 | 0.286125 | 0.352500 | 0.039250 | 253.000000 | 3389 | 502 | 3640 | -753 |

Main comparison at `fixed_2 + pose_noise_0.50m`:

| Pipeline | IDF1 | IDSW/1k | Risk-Drop IDF1 | Risk-Uncertain IDF1 |
| --- | ---: | ---: | ---: | ---: |
| drop_delayed | 0.352500 | 253.000000 | 0.000000 | 0.275375 |
| timestamped_uncertain_fusion | 0.077125 | 354.875000 | -0.275375 | 0.000000 |
| risk_aware_delayed_fusion | 0.062125 | 431.875000 | -0.290375 | -0.015000 |
| risk_aware_v2a_authority_cap | 0.139750 | 247.250000 | -0.212750 | 0.062625 |
| risk_aware_v2c_cap_plus_margin | 0.177625 | 204.375000 | -0.174875 | 0.100500 |

Gate outcome summary:

| Pose noise | Pipeline | Accept rate | Candidate rejects | Margin rejects | Mean final weight | Primary confirmed rate |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 0.25 | risk_aware_v2c_cap_plus_margin | 0.660095 | 6303 | 9715 | 0.307282 | 0.790529 |
| 0.50 | risk_aware_v2c_cap_plus_margin | 0.535385 | 6338 | 15557 | 0.107077 | 0.731470 |
| 1.00 | risk_aware_v2c_cap_plus_margin | 0.310599 | 22382 | 10106 | 0.018271 | 0.667282 |

## Interpretation

V2C still has a real benefit over plain timestamped uncertain fusion at
`0.50m` and `1.00m`: it improves IDF1 and reduces IDSW. That benefit is not
large enough to beat `drop_delayed` IDF1 at any tested noisy level.

The row-level audit shows why. V2C finds useful support in many rows, but the
combined cost of harmful accepts and conservative reject/underweight behavior
is larger. Across all three noise levels, V2C has net
`helpful - harmful - weak/reject = -5615`.

## Decision

Accepted as a Stage A boundary result.

Close the current geometry-only Stage A condition. Do not continue scalar
threshold tuning that tries to make GT world-coordinate support beat
`drop_delayed`. Future work should either relax the Stage A method condition to
"better than plain uncertain while preserving oracle safety" or proceed to a
multi-cue/appearance-augmented design where support contributes information not
already supplied by GT identity.

## Next Actions

- [ ] Update the Stage A transition rule so `drop_delayed` is treated as a
  safety baseline, not a required IDF1 lower bound for geometry-only support.
- [ ] Design the next experiment around appearance-augmented support risk or
  identity/position update separation, not another v2 scalar-threshold sweep.
- [ ] Use Stage B/C as harm-boundary measurement stages unless a multi-cue
  mechanism is introduced.
