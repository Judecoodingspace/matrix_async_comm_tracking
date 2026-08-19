# exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation

GitHub tracking: [Issue #7](https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/7)

## Purpose

验证在 `fixed_2/fixed_3 + 0.25m` support world-coordinate noise 下，身份维度是否能补上 fixed-lag geometry-only update 的噪声边界。

## Hypothesis

如果 0.25m 边界主要来自 noisy support world-coordinate 的错误关联和过度位置更新，那么加入 simulated identity cue 与 covariance-aware update 后，应在 high useful-window episodes 中恢复 identity survival，并降低 window IDSW。

## Setup

- Dataset: `MATRIX/MATRIX_30x30`
- Frame range: `0-999`
- Primary UAV: D1 (`primary_drone_id=0`)
- Support UAVs: D2-D8 (`support_drone_ids=1..7`)
- FPS: `2.0`
- Delay profiles: `fixed_2`, `fixed_3`
- Lag frames: `2`, `3`
- Support pose/world-coordinate noise: `0.25m`
- Gate radius: `1.0m`
- Identity cue: simulated embedding, strengths `strong`, `medium`, `weak`
- Seed: `7`

## Pipelines

```text
primary_only_sort
drop_delayed_sort
fixed_lag_world_xy
fixed_lag_world_xy_covariance
fixed_lag_world_xy_identity_{strong,medium,weak}
fixed_lag_world_xy_covariance_identity_{strong,medium,weak}
```

`person_id` is only used to generate hidden simulated embedding prototypes and to evaluate episodes. Runtime association uses world geometry, covariance, and observation-keyed embeddings; it does not read `person_id` for association.

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_fixed_lag_simulated_identity_cue_ablation.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_2 fixed_3 \
  --lag-frames 2 3 \
  --pose-noise-m 0.25 \
  --identity-strengths strong medium weak \
  --seed 7 \
  --output-dir outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation
```

## Output

```text
outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation/
```

Key files:

```text
sim_identity_pipeline_metrics.csv
sim_identity_episode_metrics.csv
sim_identity_high_window_summary.csv
sim_identity_cue_quality_summary.csv
sim_identity_mode_counts.csv
sim_identity_measurement_gate.csv
sim_identity_decision.md
```

## Key Metrics

High useful-window episodes, delta relative to `drop_delayed_sort`:

| Delay | Pipeline | Survival Delta | Window IDSW Delta | Positive Fraction |
| ---: | --- | ---: | ---: | ---: |
| 1000ms | `fixed_lag_world_xy` | -0.077936 | 2.259563 | 0.267760 |
| 1000ms | `fixed_lag_world_xy_covariance` | -0.011726 | 0.426230 | 0.346995 |
| 1000ms | `fixed_lag_world_xy_identity_medium` | 0.144970 | -1.193989 | 0.631148 |
| 1000ms | `fixed_lag_world_xy_covariance_identity_medium` | 0.289408 | -4.327869 | 0.792350 |
| 1500ms | `fixed_lag_world_xy` | -0.078924 | 2.915301 | 0.213115 |
| 1500ms | `fixed_lag_world_xy_covariance` | -0.034936 | 1.693989 | 0.286885 |
| 1500ms | `fixed_lag_world_xy_identity_medium` | 0.076321 | 1.393443 | 0.590164 |
| 1500ms | `fixed_lag_world_xy_covariance_identity_medium` | 0.167618 | -1.333333 | 0.729508 |

Aggregate occlusion IDF1:

| Delay | Drop | World XY | Covariance | Identity Medium | Covariance + Identity Medium |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1000ms | 0.052011 | 0.069434 | 0.092749 | 0.173969 | 0.279529 |
| 1500ms | 0.052011 | 0.060210 | 0.072636 | 0.164105 | 0.235204 |

Cue quality:

| Strength | Same Sim | Different Sim | Margin |
| --- | ---: | ---: | ---: |
| strong | 0.754159 | -0.008598 | 0.762758 |
| medium | 0.251248 | 0.004039 | 0.247209 |
| weak | 0.076330 | 0.006376 | 0.069954 |

## Interpretation

Decision: `identity_dimension_supported`.

The result supports the mechanism-level claim that identity information can compensate for the 0.25m geometry-noise boundary, but only when coupled with covariance-aware position authority control. Identity-only variants improve survival, yet at 1500ms they still keep window IDSW above drop-delayed. The best trade-off is `world_xy + covariance + simulated identity cue`.

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_matrix_simulated_identity_cue.py tests/test_matrix_reanchoring.py -q
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src /usr/bin/python3 -m py_compile \
  src/tracking/matrix_identity_cue.py \
  src/tracking/matrix_reanchoring.py \
  scripts/phase2_matrix_fixed_lag_simulated_identity_cue_ablation.py
```

Result:

```text
117 passed
```

## Decision

Accepted as a controlled Step 1 result. Proceed to a more realistic message-content ablation: keep the `world_xy + covariance + identity` mechanism, then replace simulated identity with a real appearance proxy or a calibrated noisy identity proxy before detector/ReID integration.

## Next Actions

- [ ] Add checkpoint/resume support to long formal runners.
- [ ] Design real or semi-real appearance message-content ablation: embedding-only, geometry-only, geometry+appearance, and geometry+appearance+covariance.
- [ ] Add identity cue quality sweep / threshold sweep to determine how much ReID separation is required to retain the 0.25m gain.
