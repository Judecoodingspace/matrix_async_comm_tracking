# exp_20260731_001_matrix_identity_cue_quality_boundary

GitHub tracking: [Issue #9](https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/9)

## Purpose

估计 simulated identity cue 的最低可用质量：真实 ReID/CNN embedding 至少需要达到多大的同人-异人平均相似度间隔，并采用什么 `identity_accept_threshold`，才能在 `fixed_2/fixed_3 + 0.25m` support world-coordinate noise 下复现身份线索收益。

## Hypothesis

随着 embedding observation noise 增大，同人相似度和同人-异人 margin 会降低。预计存在离散边界区间：边界以上至少一个 threshold 能在两个 delay 上同时提高 survival 并控制 IDSW；边界以下则不能稳定超过 drop-delayed。

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frame range: `0-999`
- Primary/support: D1 / D2-D8
- FPS: `2.0`
- Delay: `fixed_2`, `fixed_3`
- Lag: delay 对应的最小 eligible lag，即 `lag2`, `lag3`
- Support world-coordinate noise: `0.25m`
- Embedding dim: `128`
- View bias sigma: `0.08`
- Embedding noise sigma: `0.15 0.25 0.30 0.40 0.50 0.70`
- Identity threshold: `0.05 0.10 0.20 0.25 0.30`
- Seed: `7`
- Runtime association: geometry + covariance + embedding；不读取 GT `person_id`

## Threshold Calibration

全部 threshold 都先计算同人接受率和异人误接受率。使用 `same_accept_rate - 5 × different_accept_rate` 做不读取 tracking outcome 的初始校准，并要求 same accept rate 至少 `0.05`。随后对边界下侧 `noise=0.40/0.50` 补齐完整 tracking threshold grid，防止把校准策略失败误写成 cue quality 失败。

## Boundary Rule

每个 `(embedding margin, threshold)` 必须在 `1000ms` 和 `1500ms` 的 high useful-window episode 中同时满足：

```text
mean survival delta vs drop >= 0.05
mean window IDSW delta vs drop <= 0
```

另外报告 paired bootstrap 95% CI。边界输出为：

```text
(largest failing tested margin, minimum passing tested margin]
```

该区间是 MATRIX 与当前模拟生成器下的 calibrated target，不是通用 ReID 常数。

## Implementation

```text
scripts/phase2_matrix_identity_cue_quality_boundary.py
tests/test_matrix_identity_cue_quality_boundary.py
```

Runner 为每个 delay/noise/threshold 条件写独立 JSON checkpoint；重复运行默认跳过已完成条件，并用 manifest 防止不同配置混写。

## Commands

Smoke:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_identity_cue_quality_boundary.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 49 \
  --delay-profiles fixed_2 fixed_3 \
  --lag-frames 2 3 \
  --embedding-noise-sigmas 0.15 0.40 \
  --identity-thresholds 0.10 0.25 0.30 \
  --bootstrap-samples 200 \
  --seed 7 \
  --output-dir outputs/20260731_matrix_identity_cue_quality_boundary_smoke
```

Formal:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_identity_cue_quality_boundary.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --delay-profiles fixed_2 fixed_3 \
  --lag-frames 2 3 \
  --embedding-noise-sigmas 0.15 0.25 0.30 0.40 0.50 0.70 \
  --identity-thresholds 0.05 0.10 0.20 0.25 0.30 \
  --bootstrap-samples 1000 \
  --seed 7 \
  --output-dir outputs/20260731_matrix_identity_cue_quality_boundary
```

## Outputs

```text
identity_quality_pipeline_metrics.csv
identity_quality_episode_metrics.csv
identity_quality_embedding_summary.csv
identity_quality_threshold_operating_points.csv
identity_quality_boundary_cells.csv
identity_quality_boundary_summary.csv
identity_quality_mode_counts.csv
identity_quality_measurement_gate.csv
identity_quality_decision.md
checkpoints/*.json
run_manifest.json
```

## Measurement Gates

- Primary observations remain clean.
- Truth comes from clean observations.
- Runtime embedding lookup does not use `person_id`.
- All expected condition checkpoints exist.
- `noise_sigma=0.15, view_bias_sigma=0.08, threshold=0.25` reproduces the previous medium cue result within `1e-6`.

## Formal Result

```text
decision: quality_boundary_identified
measurement_valid: 1
condition checkpoints: 30 / 30
medium reference reproduction mismatches: 0
minimum passing tested margin: 0.056747 at threshold 0.20
largest fully-tested failing margin: 0.040019
boundary interval: (0.040019, 0.056747]
```

At the minimum passing level, worst-delay high-window survival delta is `+0.081453` and IDSW delta is `-0.489071`. Analysis: `exp_20260731_001_matrix_identity_cue_quality_boundary_analysis.md`.

## Status

Formal and structured analysis complete.
