# exp_20260802_002 MATRIX BoT-SORT 候选门修复

状态：Pilot `0-199` 已完成；Readiness Gate 未通过，Formal 未启动。

## Purpose

验证上一轮 BoT-SORT 失败能否通过最小候选机制修复：固定 GMC，放宽几何候选门，
并比较标准软外观代价与 OSNet 硬身份拒绝。

## Setup

- 数据：MATRIX `0-199`，D1-D8，GT projected bbox + LoS，score=`1.0`
- Tracker：Ultralytics BoT-SORT `8.4.113`
- GMC：复用上一轮 `sparseOptFlow` 审计缓存
- 外观：冻结 OSNet，cosine threshold=`0.785027`
- 固定参数：`track_buffer=5`、`match_thresh=0.8`
- 自变量：`proximity_thresh={0.1,0.3,0.5}`、`appearance={soft,hard_veto}`
- 禁止输入：运行时 `person_id`、D1 遮挡标签、world XY association、未来帧

硬身份拒绝只允许同时满足以下条件的匹配：

```text
GMC 后 IoU >= proximity_thresh
AND OSNet cosine similarity >= 0.785027
```

## Command

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/deep-person-reid:.venvs/local-tracklet \
/usr/bin/python3 scripts/phase3_matrix_botsort_candidate_gate_repair.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 199 \
  --drone-ids 0 1 2 3 4 5 6 7 \
  --proximity-thresholds 0.1 0.3 0.5 \
  --appearance-modes soft hard_veto \
  --track-buffer 5 --match-thresh 0.8 \
  --osnet-threshold 0.785027 \
  --progress-every 25 --resume \
  --output-dir outputs/20260802_matrix_botsort_candidate_gate_repair_pilot
```

## Gates

Measurement Gate：embedding coverage `>=0.95`，运行时禁止字段读取、未来读取和
determinism mismatch 均为 `0`。

Readiness Gate：macro local IDF1 `>=0.80`、weighted purity `>=0.95`、最差视角
IDF1 `>=0.70`、遮挡支撑覆盖 `>=0.90`。

## Result

Measurement Gate 全通过。最佳折中为 `IoU>=0.1 + hard veto`：IDF1 `0.137546`、
purity `0.946417`、最差视角 IDF1 `0.116761`、覆盖 `0.997379`。重点条件
`IoU>=0.3 + hard veto` 虽有 purity `0.973078`，但 IDF1 只有 `0.077409`。

最终决策：`hard_veto_tradeoff_only`，`formal_allowed=0`。下一步比较 OC-SORT 或
移动相机/UAV 专用 tracker，不继续微调 BoT-SORT proximity。

## Outputs

`outputs/20260802_matrix_botsort_candidate_gate_repair_pilot/`

## Flowchart

`mermaid/exp_20260802_002_matrix_botsort_candidate_gate_repair/candidate_gate_repair_flow.mmd`
