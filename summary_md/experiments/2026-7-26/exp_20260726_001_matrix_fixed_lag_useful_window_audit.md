# exp_20260726_001_matrix_fixed_lag_useful_window_audit

GitHub tracking: [Issue #5](https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/5)

## Purpose

澄清 fixed-lag 的收益条件：它是否只由 `delay <= lag` 决定，还是还会被遮挡长度和 support 到达后剩余的有效支撑窗口调节。

本轮是 analysis-only，复用已有 `0-999` formal 输出，不重新跑 tracker。

## Hypothesis

如果 `delay <= lag` 只是可用资格而不是收益保证，则在 eligible episode 中，不同 `useful_window_fraction` bucket 的 identity survival gain 应有明显差异。

## Setup

- Input reanchoring: `outputs/20260724_matrix_tracker_state_aware_reanchoring/`
- Input temporal boundary: `outputs/20260722_matrix_occlusion_temporal_boundary_expansion/`
- Frame range inherited: MATRIX `0-999`
- Pose noise: none
- Timestamp jitter: none
- Pipelines analyzed: `fixed_lag_oosm_lag1/2/3/5`
- Baseline alignment: same `(delay_profile, person_id, start_frame, end_frame)` against `drop_delayed_sort`

New script:

```text
scripts/analyze_matrix_fixed_lag_useful_window.py
```

Output:

```text
outputs/20260726_matrix_fixed_lag_useful_window_audit/
```

## Derived Variables

```text
lag_eligible = delay_frames <= lag_frames
lag_headroom_frames = lag_frames - delay_frames
remaining_after_first_arrival_frames = max(episode_length - delay_frames, 0)
useful_window_fraction = remaining_after_first_arrival_frames / episode_length
effective_fixed_lag_window_fraction =
  useful_window_fraction if lag_eligible else 0
```

## Commands

Smoke:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/analyze_matrix_fixed_lag_useful_window.py \
  --reanchoring-dir outputs/20260724_matrix_tracker_state_aware_reanchoring \
  --temporal-boundary-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion \
  --output-dir outputs/20260726_matrix_fixed_lag_useful_window_audit_smoke \
  --max-rows 2000
```

Formal:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/analyze_matrix_fixed_lag_useful_window.py \
  --reanchoring-dir outputs/20260724_matrix_tracker_state_aware_reanchoring \
  --temporal-boundary-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion \
  --output-dir outputs/20260726_matrix_fixed_lag_useful_window_audit
```

## Formal Result

Decision:

```text
useful_window_modulated_fixed_lag
```

Key metrics:

| Condition | Value |
| --- | ---: |
| fixed-lag episode rows | 8856 |
| eligible useful-window buckets with n>=5 | 3 |
| survival delta spread across eligible useful-window buckets | 0.382940 |
| high-minus-low survival delta | 0.382940 |
| larger-lag penalty detected | 0 |
| state-aware 2500ms IDF1 | 0.078017 |
| fixed-lag lag5 2500ms IDF1 | 0.516013 |

Eligible useful-window evidence:

| useful window bucket | n | mean survival delta vs drop | mean IDSW delta vs drop |
| --- | ---: | ---: | ---: |
| `[0,0.25)` | 18 | 0.000000 | 0.055556 |
| `[0.5,0.75)` | 164 | 0.203212 | -3.195122 |
| `[0.75,1]` | 4984 | 0.382940 | -7.745586 |

Interpretation:

```text
delay <= lag 是 fixed-lag update 的资格条件，不是收益保证。
fixed-lag 的收益仍由遮挡长度、到达时机和剩余可影响窗口调节。
```

## Output Files

```text
fixed_lag_useful_window_episode_metrics.csv
fixed_lag_delay_length_summary.csv
fixed_lag_useful_window_summary.csv
fixed_lag_eligibility_vs_gain.csv
fixed_lag_best_lag_by_condition.csv
fixed_lag_failure_cases.csv
fixed_lag_decision_summary.csv
fixed_lag_useful_window_decision.md
```

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_fixed_lag_useful_window.py -q
# 6 passed
```

```bash
PYTHONPATH=src /usr/bin/python3 -m py_compile \
  scripts/analyze_matrix_fixed_lag_useful_window.py
```

## Decision

本轮修正了上一轮 fixed-lag 结果的解释边界：

```text
fixed-lag 是强缓解机制；
但其收益应按 useful support window 分层报告；
不能写成“只要 support 在 lag 内到达就一定有 gain”。
```

下一步可以进入 fixed-lag + pose/world-coordinate noise，但必须保留 useful-window 分层，否则噪声实验会把时间窗口效应和空间误差效应混在一起。
