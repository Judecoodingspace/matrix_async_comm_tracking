# exp_20260722_002_matrix_temporal_boundary_matched_diagnostics

## Purpose

承接 `exp_20260722_001` 的 `0-999` formal 输出，修正 temporal boundary 的判定逻辑，并用 matched diagnostics 解释为什么同一 `rho_bucket` 内绝对延迟仍然支配 `during_gain`。

本轮不重新跑 tracker，只分析已有输出：

```text
outputs/20260722_matrix_occlusion_temporal_boundary_expansion/
```

## Hypothesis

旧 gate 把 `delay-rho cell` 数量作为硬门槛，导致 `2214` 条有效 episode rows 仍被判定为 sparse。更合理的判据应该是：

- 模型稳定性：`M4_delay_coverage_interaction` 是否稳定优于 `M1_delay_only`
- matched diagnostics：同一 `rho_bucket` 下的 delay 差异、同一 delay 下的 coverage 差异、early-frame support 到达率和 spillover 是否给出一致解释

预期结果不是直接进入 policy learning，而是得到更可信的 temporal boundary 机制解释。

## Setup

- Dataset: MATRIX `0-999`
- Input directory: `outputs/20260722_matrix_occlusion_temporal_boundary_expansion/`
- Output directory: `outputs/20260722_matrix_temporal_boundary_matched_diagnostics/`
- Primary UAV: D1
- Support UAVs: D2-D8
- Delay profiles: `fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10`
- FPS: `2.0`, one frame = 500 ms
- Pose noise: none
- Timestamp jitter: none
- Seed: `7`

Input tables:

```text
counterfactual_episode_gain.csv
temporal_boundary_frame_freshness.csv
temporal_boundary_model_comparison.csv
replay_reproduction_audit.csv
```

## Implementation

New code:

```text
scripts/analyze_occlusion_temporal_boundary_matched.py
tests/test_temporal_boundary_matched.py
```

New outputs:

```text
matched_rho_delay_diagnostics.csv
matched_delay_coverage_diagnostics.csv
early_frame_gain_profile.csv
spillover_gain_diagnostics.csv
boundary_gate_refined_model_stability.csv
boundary_gate_refined_decision.md
```

## Smoke Command

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/analyze_occlusion_temporal_boundary_matched.py \
  --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion \
  --output-dir outputs/20260722_matrix_temporal_boundary_matched_diagnostics_smoke \
  --max-rows 2000 \
  --seed 7
```

## Formal Command

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/analyze_occlusion_temporal_boundary_matched.py \
  --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion \
  --output-dir outputs/20260722_matrix_temporal_boundary_matched_diagnostics \
  --seed 7
```

## Decision Rules

### Gate 1: Measurement Validity

Required:

```text
Run A reproduction mismatches = 0
mask mismatch rows = 0
no-effective-support nonzero gain rows = 0
```

### Gate 2: Model Stability

Required:

```text
M4 group-CV RMSE improves over M1 by >= 10%
M4 R2 improves over M1 by >= 0.05
M4 delay_x_coverage coefficient bootstrap CI does not cross 0
```

Sparse groups are reported as extrapolation risk, not as a hard failure.

### Gate 3: Matched Diagnostics

Decision options:

- `joint_boundary_supported`: M4 stable and matched diagnostics support delay plus coverage jointly.
- `absolute_delay_boundary`: coverage adds little and delay-only is sufficient.
- `early_frame_gap_boundary`: dominant loss is early online frames missing usable support.
- `boundary_still_inconclusive`: model and matched diagnostics disagree.

## Formal Result

Decision:

```text
early_frame_gap_boundary
```

Key checks:

| Check | Result |
| --- | ---: |
| Run A reproduction mismatches | 0 |
| Mask mismatch rows | 0 |
| No-effective-support nonzero gain rows | 0 |
| M1 group-CV RMSE | 0.416513 |
| M4 group-CV RMSE | 0.277068 |
| Group-CV RMSE improvement | 0.334791 |
| M1 R2 | 0.458015 |
| M4 R2 | 0.758755 |
| R2 improvement | 0.300740 |
| delay_x_coverage CI | [-0.959284, -0.846348] |

Matched diagnostic facts:

| Diagnostic | Result |
| --- | ---: |
| Same-rho monotonic delay signal | pass, `[0,0.25)` |
| Same-delay coverage modulation | fail |
| Max same-delay coverage gain spread | 0.005815 |
| Early arrival-rate drop, 500ms to 1000ms | 0.166439 |
| Early frame-gain drop, 500ms to 1000ms | 0.704866 |
| Spillover-sensitive boundary | pass |

Within the same `rho_bucket=[0,0.25)`, `during_gain` drops from `0.915576` at 500ms to `0.146273` at 1000ms, `0.023258` at 1500ms, and `0.008351` at 2500ms. This confirms that episode-level `rho` is too coarse: the key failure is whether support reaches the early online publish frames soon enough.

## Verification

```bash
PYTHONPATH=src /usr/bin/python3 -m py_compile \
  scripts/analyze_occlusion_temporal_boundary_matched.py
```

```bash
PYTHONPATH=src python -m pytest tests/test_temporal_boundary_matched.py -q
# 7 passed
```

```bash
PYTHONPATH=src python -m pytest tests/ -q
# 88 passed
```

## Decision

Accepted as the refined temporal-boundary diagnostic for `exp_20260722_001`.

Do not use strict cell count as the main boundary gate. The next method question should focus on online proxies for early-frame availability and, after that, add pose/world-coordinate noise to test whether spatial staleness introduces a third boundary dimension.

GitHub tracking issue:

```text
https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/2
```
