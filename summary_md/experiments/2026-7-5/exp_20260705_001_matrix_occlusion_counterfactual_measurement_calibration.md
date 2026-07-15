# exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration

## Purpose

校准遮挡场景中的成对反事实测量框架，确认每个遮挡片段自己的支撑观测是否能被干净归因，而不是被回放重编号或跨片段状态继承混淆。

## Hypothesis

在不使用 `person_id` 修正 tracker 的前提下，Run A 保留目标遮挡支撑消息、Run B 只屏蔽目标遮挡支撑消息，可以得到可复现、无泄漏的支撑因果增益。预期短延迟下 gain 为正，较长延迟下 gain 衰减。

## Setup

- Device: server workspace, CPU run
- Detector: not used, GT world-coordinate observations
- ReID: not used
- Dataset: `MATRIX/MATRIX_30x30`
- Frame range: `0-199`
- Primary source: D1, `primary_drone_id=0`
- Support sources: D2-D8, `support_drone_ids=1 2 3 4 5 6 7`
- Delay distribution: `fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10`
- FPS: `2.0`, 1 frame = 500 ms
- Seed: `7`
- Tracker: `WorldNearestTracker`, distance threshold `1.0`
- Metrics: Run A reproduction mismatch, during gain, spillover gain, aggregate IDF1/IDSW, delay-rho cell coverage

## Command

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/phase2_matrix_occlusion_counterfactual_calibration.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 199 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10 \
  --min-episode-length 2 \
  --seed 7 \
  --workers 8 \
  --output-dir outputs/20260705_matrix_occlusion_counterfactual_measurement_calibration
```

## Output

```text
outputs/20260705_matrix_occlusion_counterfactual_measurement_calibration/
```

Files:

- `aggregate_pipeline_metrics.csv`
- `counterfactual_episode_gain.csv`
- `counterfactual_gain_by_cell.csv`
- `lineage_stability_audit.csv`
- `replay_reproduction_audit.csv`
- `counterfactual_decision.md`

## Key Metrics

| Delay | Causal occlusion IDF1 | Arrival occlusion IDF1 | Mean during gain | Gain direction |
| --- | ---: | ---: | ---: | --- |
| 0 ms | 1.000 | 1.000 | 0.908 | positive_stable |
| 500 ms | 0.990 | 0.990 | 0.910 | positive_stable |
| 1000 ms | 0.393 | 0.197 | 0.271 | positive_stable |
| 1500 ms | 0.301 | 0.229 | 0.049 | inconclusive |
| 2500 ms | 0.220 | 0.190 | 0.013 | inconclusive |
| 5000 ms | 0.184 | 0.149 | 0.001 | inconclusive |

Gate checks:

| Gate | Result |
| --- | ---: |
| Run A reproduction mismatches | 0 |
| Mask manifest mismatch rows | 0 |
| No-effective-support nonzero during-gain rows | 0 |
| Delay-rho cells with `n>=5` | 8 |
| Covered delay levels | 6 |
| Covered rho buckets | 3 |

## Interpretation

成对反事实测量框架通过：Run A 能逐帧复现 baseline，屏蔽消息范围一致，且没有使用真值身份修正轨迹号。短延迟支撑观测具有强因果收益；1000 ms 仍为稳定正收益但明显衰减；1500 ms 之后遮挡期间增益接近 0 或不稳定。

`rho<0.25` 内 gain 从 500 ms 的 `0.926` 降到 1000 ms 的 `0.275`，再降到 1500 ms 的 `0.050`，说明仅用遮挡比值不足以解释伤害边界，绝对延迟仍有独立作用。

## Decision

`measurement_valid_but_underdetermined`

测量框架可信，但 0-199 的 delay-rho cell 覆盖仍不足以拟合可发表的 harm boundary。下一步应扩展到 `0-999`，不是直接进入噪声或多信息维度门控。

## Verification

```bash
PYTHONPATH=src python -m pytest tests/ -q
# 80 passed

PYTHONPATH=src /usr/bin/python3 -m py_compile \
  src/tracking/matrix_occlusion.py \
  scripts/phase2_matrix_occlusion_counterfactual_calibration.py
# passed
```

## Next Actions

- [ ] 生成 MATRIX `200-999` 的 POM 和 `annotations_positions`。
- [ ] 用同一脚本扩展到 `0-999`，保留 `--workers 8` 或更高并行度。
- [ ] 在更密集 cell 覆盖下拟合 `gain ~ delay_ms + online_support_coverage_fraction + interaction`。
- [ ] 边界稳定后再加入 pose noise 和 `v*delay/gate_radius`。
