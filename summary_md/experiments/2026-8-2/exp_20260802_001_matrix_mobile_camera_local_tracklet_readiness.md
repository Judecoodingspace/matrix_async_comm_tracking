# exp_20260802_001 MATRIX 移动相机局部 Tracklet Readiness

状态：Pilot `0-199` 完成但未通过 purity/readiness；当前 Formal 暂缓。

Pilot durable analysis：
`exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness_analysis.md`。

## Purpose

回答移动 UAV 上旧 local tracker 的失败主要来自生命周期过简、相机运动未补偿，
还是外观线索不足。该实验只选择可用的局部跟踪基础设施，不运行异步 global fusion。

## Hypothesis

成熟 BoT-SORT 生命周期配合稀疏光流 GMC，可降低移动相机造成的错误运动创新；冻结
OSNet 应进一步限制身份合并。只有 local IDF1、纯度和连续性同时过门，才允许进入
global tracklet fusion。

## Online/Offline Boundary

在线局部关联只读取：

```text
GT projected bbox（score=1.0）
当前及历史图像（仅 GMC）
冻结 OSNet embedding
BoT-SORT 历史状态
```

`person_id`、D1 遮挡标签和 world XY 不参与 local association。world XY 只在关联完成
后更新固定大小的增量 tracklet 摘要；GT 标签只在离线指标阶段读取。

## Pipelines

```text
current_bbox_sort
current_bbox_osnet
botsort_no_gmc_noapp
botsort_gmc_noapp
botsort_no_gmc_osnet
botsort_gmc_osnet
```

BoT-SORT 固定：OSNet cosine threshold `0.785027`、appearance EMA `0.9`、GMC
`sparseOptFlow`、downscale `2`。每架 UAV 使用独立 local ID namespace。

## Dependency And Cache Preflight

```bash
python -m pip install --target .venvs/local-tracklet "lap==0.5.12"

YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/deep-person-reid:.venvs/local-tracklet \
python -c "import lap, ultralytics; print(lap.__version__, ultralytics.__version__)"
```

Pilot 前先补齐 `0-999` 全视角缓存：

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/deep-person-reid:.venvs/local-tracklet \
/usr/bin/python3 scripts/prepare_matrix_local_tracklet_osnet_cache.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --drone-ids 0 1 2 3 4 5 6 7 \
  --output-cache outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_cache/osnet_x0_25_msmt17.npz \
  --torchreid-path .venvs/deep-person-reid \
  --osnet-checkpoint weights/osnet_x0_25_msmt17.pth \
  --device cuda:0 --progress-every 25 --resume
```

缓存覆盖率低于 `95%` 时实验硬失败。

## Pilot

Pilot 只用 `0-199` 在 `track_buffer={5,10}`、`match_thresh={0.7,0.8}` 中为每个
成熟变体锁定参数。优先保留 purity `>=0.95` 的配置，再按 IDF1、fragmentation、
buffer 依次排序。无配置过 purity 门时使用 IDF1/purity 调和平均值，但不宣布 ready。

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/deep-person-reid:.venvs/local-tracklet \
/usr/bin/python3 scripts/phase3_matrix_mobile_camera_local_tracklet_readiness.py \
  --mode calibrate \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 199 \
  --drone-ids 0 1 2 3 4 5 6 7 \
  --track-buffers 5 10 --match-thresholds 0.7 0.8 \
  --osnet-threshold 0.785027 \
  --progress-every 25 --resume \
  --output-dir outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_pilot
```

## Formal

Formal 加载 `180-199` 作为 warmup，只评价 `200-999`，并只读 Pilot 生成的配置。

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/deep-person-reid:.venvs/local-tracklet \
/usr/bin/python3 scripts/phase3_matrix_mobile_camera_local_tracklet_readiness.py \
  --mode evaluate \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 180 --eval-start 200 --frame-end 999 \
  --drone-ids 0 1 2 3 4 5 6 7 \
  --selected-config outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_pilot/selected_config.json \
  --progress-every 25 --resume \
  --output-dir outputs/20260802_matrix_mobile_camera_local_tracklet_readiness
```

## Gates

Measurement Gate：运行时 GT/遮挡/world-XY association/future read 均为 `0`，标签扰动
不改变预测，embedding coverage `>=0.95`，determinism mismatch `0`。

Readiness Gate 对 evaluation 的有效视角要求：

```text
macro local IDF1 >= 0.80
weighted purity >= 0.95
minimum per-view local IDF1 >= 0.70
D1 遮挡帧正确 active support tracklet coverage >= 0.90
```

## Outputs

```text
local_tracker_config_selection.csv
mobile_local_pipeline_metrics.csv
mobile_local_quality_by_view.csv
mobile_local_merge_fragmentation.csv
mobile_local_association_diagnostics.csv
mobile_local_gmc_audit.csv
mobile_local_occlusion_support_coverage.csv
mobile_local_message_manifest.csv
mobile_local_measurement_gate.csv
mobile_local_decision.md
checkpoints/
```

## Decision

`gmc_required`、`appearance_required`、`joint_gmc_appearance_required`、
`mobile_local_tracker_ready`、`local_tracklet_quality_still_blocked` 五选一。只有至少一个
成熟变体过门，下一轮才比较 history-1 observation packet 与 history>1 incremental
tracklet packet。

## Flowchart

外部流程图：
`mermaid/exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness/mobile_local_readiness_flow.mmd`。
