# exp_20260724_001_matrix_early_frame_online_proxy_readiness

## Purpose

验证 `exp_20260722_002` 得到的 `early_frame_gap_boundary` 能否转成在线可判断变量。核心问题不是继续证明 early-frame gap 存在，而是判断融合端能不能只用实时可获得 proxy 预测 support 是否还有正收益。

本轮不重新跑 tracker，复用：

```text
outputs/20260722_matrix_occlusion_temporal_boundary_expansion/
outputs/20260722_matrix_temporal_boundary_matched_diagnostics/
```

## Hypothesis

如果 online proxy readiness 成立，则 `M5_combined_online_proxy` 应在 group-CV 下明显优于 `M1_delay_only`：

```text
AUC improvement >= 0.05
F1 improvement >= 0.05
M5 recall >= 0.70
关键系数方向合理
```

其中 `rho_episode` 只作为 oracle-style 事后诊断，不作为在线模型输入。

## Setup

- Dataset: MATRIX `0-999`
- Primary UAV: D1
- Support UAVs: D2-D8
- Delay profiles: `fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10`
- Pose noise: none
- Timestamp jitter: none
- Seed: `7`
- Episode target: `positive_episode_gain = during_gain > 0.05`
- Frame target: `positive_frame_gain = frame_gain > 0`
- Frame-level model rows: deterministic balanced sample, default `4000`

Input tables:

```text
counterfactual_episode_gain.csv
temporal_boundary_frame_freshness.csv
```

## Implementation

New code:

```text
scripts/analyze_occlusion_online_proxy_readiness.py
tests/test_online_proxy_readiness.py
```

Output:

```text
outputs/20260724_matrix_early_frame_online_proxy_readiness/
```

Generated files:

```text
online_proxy_episode_dataset.csv
online_proxy_frame_dataset.csv
online_proxy_model_comparison.csv
online_proxy_group_cv.csv
online_proxy_error_diagnostics.csv
online_proxy_decision_summary.csv
online_proxy_decision.md
```

## Commands

Smoke:

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/analyze_occlusion_online_proxy_readiness.py \
  --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion \
  --matched-dir outputs/20260722_matrix_temporal_boundary_matched_diagnostics \
  --output-dir outputs/20260724_matrix_early_frame_online_proxy_readiness_smoke \
  --max-episode-rows 400 \
  --max-frame-rows 4000 \
  --seed 7
```

Formal:

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/analyze_occlusion_online_proxy_readiness.py \
  --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion \
  --matched-dir outputs/20260722_matrix_temporal_boundary_matched_diagnostics \
  --output-dir outputs/20260724_matrix_early_frame_online_proxy_readiness \
  --seed 7
```

## Formal Result

Decision:

```text
online_proxy_weak
```

Episode-level model comparison:

| Model | group-CV AUC | group-CV F1 | group-CV recall | group-CV RMSE |
| --- | ---: | ---: | ---: | ---: |
| `M1_delay_only` | 0.964606 | 0.813600 | 0.990263 | 0.363084 |
| `M2_episode_rho_oracle` | 0.858679 | 0.814726 | 0.991237 | 0.413217 |
| `M3_online_freshness` | 0.921871 | 0.830403 | 0.712756 | 0.307236 |
| `M4_early_occlusion_proxy` | 0.963873 | 0.848253 | 0.756573 | 0.276633 |
| `M5_combined_online_proxy` | 0.967811 | 0.889655 | 0.879260 | 0.273869 |

Readiness gate:

| Check | Result |
| --- | ---: |
| M5 vs M1 AUC improvement | 0.003205 |
| M5 vs M1 F1 improvement | 0.076055 |
| M5 recall | 0.879260 |
| Key coefficient signs reasonable | 1 |

Interpretation:

- Online proxy adds useful threshold/calibration signal: F1 improves from `0.813600` to `0.889655`.
- It does not yet add enough ranking/generalization signal: AUC improves only `0.003205`, below the `0.05` policy-readiness threshold.
- `rho_episode` performs worse than delay-only in group-CV AUC (`0.858679` vs `0.964606`), supporting the decision to keep it as post-hoc diagnostic, not online input.

Frame-level auxiliary result:

| Model | group-CV AUC | group-CV F1 | group-CV recall |
| --- | ---: | ---: | ---: |
| `M1_delay_only` | 0.830986 | 0.227325 | 0.146233 |
| `M3_online_freshness` | 0.940631 | 0.943566 | 0.983752 |
| `M5_combined_online_proxy` | 0.969113 | 0.943566 | 0.983752 |

Frame-level proxy is strong, but it is an auxiliary sampled diagnostic. The formal gate remains episode-level because the action decision must affect a support episode, not only one published frame.

## Verification

```bash
PYTHONPATH=src /usr/bin/python3 -m py_compile \
  scripts/analyze_occlusion_online_proxy_readiness.py \
  tests/test_online_proxy_readiness.py
```

```bash
PYTHONPATH=src python -m pytest tests/test_online_proxy_readiness.py -q
# 6 passed
```

```bash
PYTHONPATH=src python -m pytest tests/ -q
# 94 passed
```

## Decision

Do not proceed directly to policy learning. The next step should be a narrower threshold-calibration or action-readiness audit:

```text
delay-only already ranks episodes well;
online proxies improve F1 and frame-level prediction;
policy needs calibrated action thresholds, not a full RL jump yet.
```

GitHub tracking issue:

```text
https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/3
```
