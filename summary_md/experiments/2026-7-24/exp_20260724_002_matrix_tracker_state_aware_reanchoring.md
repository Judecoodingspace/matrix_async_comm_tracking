# exp_20260724_002_matrix_tracker_state_aware_reanchoring

GitHub tracking: [Issue #4](https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/4)

## Purpose

验证在主 UAV 遮挡、support 异步到达时，持续跟踪机制能否缓解此前发现的 early-frame gap harm。

本轮从“诊断异步通信为什么伤害跟踪”转向“用 tracker 机制缓解伤害”。方法仍保持在 MATRIX GT world-coordinate、zero-noise 条件下，不进入 detector/ReID 或 policy learning。

## Hypothesis

如果 tracker-state-aware delayed re-anchoring 有效，则应在 `fixed_2=1000ms` 和 `fixed_3=1500ms` 过渡区同时满足：

```text
相对 drop_delayed_sort: occlusion IDF1 +0.05，IDSW 不明显增加
相对 arrival_time_sort: IDSW 明显下降
相对 fixed_lag / recovery-only: 有更好 IDF1/IDSW/reacquisition trade-off
```

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frame range: `0-999`
- Primary UAV: D1 (`0`)
- Support UAVs: D2-D8 (`1 2 3 4 5 6 7`)
- FPS: `2.0`
- Delay profiles: `fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10`
- Lag windows: `1 2 3 5`
- State-aware lag: `3`
- Pose noise: none
- Timestamp jitter: none
- Seed: `7`
- Tracker: BEV/SORT-style world-coordinate tracker

## Implementation

New code:

```text
src/tracking/matrix_reanchoring.py
scripts/phase2_matrix_tracker_state_aware_reanchoring.py
tests/test_matrix_reanchoring.py
```

Output:

```text
outputs/20260724_matrix_tracker_state_aware_reanchoring/
```

Generated files:

```text
reanchoring_pipeline_metrics.csv
reanchoring_episode_metrics.csv
reanchoring_transition_zone_metrics.csv
reanchoring_track_state_diagnostics.csv
reanchoring_mode_counts.csv
reanchoring_fragmentation_metrics.csv
reanchoring_case_samples.csv
reanchoring_decision.md
```

## Commands

Smoke:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_tracker_state_aware_reanchoring.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 49 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_2 fixed_3 \
  --lag-frames 1 2 3 \
  --seed 7 \
  --output-dir outputs/20260724_matrix_tracker_state_aware_reanchoring_smoke
```

Formal:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_tracker_state_aware_reanchoring.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10 \
  --lag-frames 1 2 3 5 \
  --seed 7 \
  --output-dir outputs/20260724_matrix_tracker_state_aware_reanchoring
```

## Formal Result

Decision:

```text
fixed_lag_sufficient
```

Transition-zone metrics:

| delay | pipeline | occlusion IDF1 | occlusion IDSW | identity survival | mean fragmentation |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1000ms | `drop_delayed_sort` | 0.052011 | 5084 | 0.355588 | 13.368564 |
| 1000ms | `arrival_time_sort` | 0.155521 | 3988 | 0.441935 | 9.959350 |
| 1000ms | `fixed_lag_oosm_lag2` | 0.870100 | 829 | 0.931527 | 1.260163 |
| 1000ms | `state_aware_reanchoring` | 0.870100 | 829 | 0.931527 | 1.260163 |
| 1500ms | `drop_delayed_sort` | 0.052011 | 5084 | 0.355588 | 13.368564 |
| 1500ms | `arrival_time_sort` | 0.179477 | 3931 | 0.472494 | 10.010840 |
| 1500ms | `fixed_lag_oosm_lag3` | 0.724058 | 2101 | 0.778026 | 3.818428 |
| 1500ms | `state_aware_reanchoring` | 0.724058 | 2101 | 0.778026 | 3.818428 |

Interpretation:

- Fixed-lag OOSM update is a strong mitigation mechanism in the transition zone.
- Current `state_aware_reanchoring` does not beat the best matching fixed-lag ablation; it ties `lag2` at 1000ms and `lag3` at 1500ms.
- Recovery-only stitching is not sufficient in the current world-coordinate-only setup.
- Long-delay behavior confirms the need for a bounded window: at 2500ms, `fixed_lag_oosm_lag5` remains useful (`0.516013` occlusion IDF1), while state-aware with lag3 drops to `0.078017`.

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_matrix_reanchoring.py -q
# 6 passed
```

```bash
PYTHONPATH=src python -m pytest tests/ -q
# 100 passed
```

```bash
PYTHONPATH=src /usr/bin/python3 -m py_compile \
  src/tracking/matrix_reanchoring.py \
  scripts/phase2_matrix_tracker_state_aware_reanchoring.py \
  tests/test_matrix_reanchoring.py
```

## Decision

本轮不应宣称“state-aware reanchoring 已经胜出”。更准确的结论是：

```text
固定窗口 delayed update 是当前最强、最简单、最可解释的缓解机制。
状态感知规则当前没有提供超过固定窗口的额外收益。
```

下一步应先围绕 fixed-lag OOSM 做收紧实验：加入 pose/world-coordinate noise，测试窗口大小、速度位移和 gate radius 的关系，再决定是否需要更复杂的 state-aware decision rule。
