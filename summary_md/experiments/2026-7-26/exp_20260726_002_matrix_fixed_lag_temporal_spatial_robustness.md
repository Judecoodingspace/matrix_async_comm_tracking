# exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness

GitHub tracking: [Issue #6](https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/6)

## Purpose

验证 fixed-lag OOSM update 在主 UAV 遮挡场景中加入 support world-coordinate noise 后是否仍能高于 `drop_delayed_sort`，并区分失败来自时间窗口不足、坐标噪声，还是二者共同作用。

## Hypothesis

在 `useful_window_fraction` 足够大的 episode 中，fixed-lag 在低噪声下仍应高于 drop-delayed；当 support world-coordinate noise 增大后，收益会从正转负，形成时间-空间联合边界。

## Setup

- Dataset: `MATRIX/MATRIX_30x30`
- Frame range: `0-999`
- FPS: `2.0`
- Primary UAV: D1 (`primary_drone_id=0`)
- Support UAVs: D2-D8 (`support_drone_ids=1..7`)
- Delay profiles: `fixed_0 fixed_1 fixed_2 fixed_3 fixed_5`
- Lag frames: `1 2 3 5`
- Support pose noise: `0.00 0.10 0.25 0.50m`
- Gate radius / distance threshold: `1.0m`
- Seed: `7`
- Primary observations: clean
- Truth observations: clean observations, separated from noisy support input

Implementation note: the formal run skipped noisy `fixed_0` sanity rows and noisy `arrival_time_sort` by default. This keeps the formal focused on the main decision matrix (`fixed_1/2/3/5 × noise × fixed-lag`) and avoids unbounded stale-track growth in noisy arrival-time fusion. `fixed_0 noise=0.00` and all `pose_noise=0.00` delayed rows reproduce prior formal results.

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_fixed_lag_temporal_spatial_robustness.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 \
  --lag-frames 1 2 3 5 \
  --pose-noise-levels 0.00 0.10 0.25 0.50 \
  --seed 7 \
  --output-dir outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness
```

## Output

```text
outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness/
```

Key files:

```text
fixed_lag_noise_pipeline_metrics.csv
fixed_lag_noise_episode_metrics.csv
fixed_lag_noise_useful_window_summary.csv
fixed_lag_noise_temporal_spatial_summary.csv
fixed_lag_noise_best_lag_by_condition.csv
fixed_lag_noise_failure_cases.csv
fixed_lag_noise_high_window_transition_summary.csv
fixed_lag_noise_measurement_gate.csv
fixed_lag_noise_decision.md
```

## Key Metrics

Measurement gates:

| Gate | Value |
| --- | ---: |
| measurement_valid | 1 |
| primary_only_noise_invariant_mismatch | 0 |
| drop_delayed_noise_invariant_mismatch | 0 |
| primary_perturbation_mismatches | 0 |
| pose0_prior_reproduction_mismatch | 0 |

High useful-window transition zone:

| Noise | Delay | Best lag | Occ IDF1 delta vs drop | Survival delta vs drop | Window IDSW delta vs drop |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00m | 1000ms | 2 | 0.818089 | 0.580660 | -11.666667 |
| 0.00m | 1500ms | 3 | 0.672047 | 0.425901 | -8.158470 |
| 0.10m | 1000ms | 2 | 0.107354 | 0.165227 | -3.852459 |
| 0.10m | 1500ms | 3 | 0.094543 | 0.132765 | -2.128415 |
| 0.25m | 1000ms | 2 | 0.017423 | -0.077936 | 2.289617 |
| 0.25m | 1500ms | 3 | 0.008199 | -0.078924 | 2.997268 |
| 0.50m | 1000ms | 2 | 0.000000 | -0.193784 | 5.199454 |
| 0.50m | 1500ms | 3 | 0.000000 | -0.173564 | 5.193989 |

## Interpretation

Fixed-lag 的 zero-noise 强收益被复现；0.10m support world-coordinate noise 下仍能保持正收益并降低 IDSW；到 0.25m 时，高 useful-window episode 的 survival delta 转负且 IDSW 高于 drop，说明失败不是因为没有足够时间窗口，而是坐标噪声已经污染了窗口内回放更新。

## Decision

`temporal_spatial_boundary_identified`

固定窗口机制仍有价值，但它不是空间噪声鲁棒的最终方法。下一步应进入 message-content / identity-cue ablation，验证是否需要引入身份线索、bbox/pose consistency 或噪声感知权威上限来保护 fixed-lag update。

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_fixed_lag_temporal_spatial_robustness.py -q
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src /usr/bin/python3 -m py_compile \
  src/tracking/matrix_reanchoring.py \
  scripts/phase2_matrix_fixed_lag_temporal_spatial_robustness.py
```

Result: `113 passed`.
