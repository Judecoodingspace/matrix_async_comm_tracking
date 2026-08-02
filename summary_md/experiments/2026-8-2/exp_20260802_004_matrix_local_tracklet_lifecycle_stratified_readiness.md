# exp_20260802_004 局部轨迹生命周期分层就绪审计

状态：analysis-only formal 完成；Measurement Gate 全通过；global fusion 仍禁止。

## Purpose

将局部 tracker 的责任拆成：

```text
active visible run:
  local purity / IDSW / segment IDF1 / 短时 fragmentation

long gap:
  tracklet termination / reacquisition / global stitching demand
```

避免用一个全序列 local IDF1 同时要求短时跟踪和长期 ReID。

## Setup

- 输入：`exp_20260802_003` Pilot 的 12 条管线逐检测 prediction 和逐轨迹 message
- 数据范围：MATRIX `0-199`，D1-D8
- 短时 gap：最多 `5` 个缺失帧
- 长 gap：缺失帧 `>5`
- FPS：`2.0`
- 外观诊断：冻结 OSNet，threshold=`0.785027`
- GT identity/跨视角可见性只用于离线分段和评价
- 不重新运行 tracker，不改写任何 local ID

GT run 与 predicted track 都在 measurement gap 超过 5 帧时切段。长 gap 单独检查原
local ID 是否存活、重新捕获延迟、其他 UAV 的 support bridge，以及真实同人 OSNet
特征是否通过阈值。

## Command

```bash
PYTHONPATH=src:scripts:.venvs/local-tracklet \
/usr/bin/python3 scripts/analyze_matrix_local_tracklet_lifecycle_stratified.py \
  --input-dir outputs/20260802_matrix_ocsort_motion_representation_audit_pilot \
  --embedding-cache outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_cache/osnet_x0_25_msmt17.npz \
  --short-gap-frames 5 --fps 2.0 \
  --identity-threshold 0.785027 \
  --progress-every 1 \
  --output-dir outputs/20260802_matrix_local_tracklet_lifecycle_stratified_readiness
```

## Result

- Measurement Gate 全通过：12 条管线 sensor keys 一致，`537` 个长 gap，embedding
  coverage=`1.0`。
- clean world-XY：全序列 IDF1 `0.548384`，active-run IDF1 `0.935778`，purity
  `0.995616`。旧 readiness 确实被长 gap 混杂。
- 最佳 image active-run 仍为 Deep OC-SORT soft：IDF1 `0.373450`，purity
  `0.433254`，不就绪。
- BoT-SORT hard active-run IDF1 `0.248246`、purity `0.948805`，仍严重碎片化。
- `537/537` 长 gap 的全部 gap frames 中，目标都至少被另一 UAV 看见；support bridge
  availability/coverage 均为 `1.0`。
- 几乎所有方法在长 gap 后创建新 local ID；这是 global stitching demand，不再计入
  active-run fragmentation。
- OSNet true-pair appearance threshold pass rate=`0.664804`，说明 appearance-only
  stitching 仍不足。

Decision：`readiness_metric_recalibrated_local_tracker_still_blocked`。

## Outputs

`outputs/20260802_matrix_local_tracklet_lifecycle_stratified_readiness/`

```text
active_run_manifest.csv
active_run_case_metrics.csv
active_run_quality_by_view.csv
active_run_pipeline_metrics.csv
long_gap_manifest.csv
long_gap_event_metrics.csv
long_gap_pipeline_summary.csv
lifecycle_stratified_measurement_gate.csv
lifecycle_stratified_decision.md
```

## Flowchart

`mermaid/exp_20260802_004_matrix_local_tracklet_lifecycle_stratified_readiness/lifecycle_stratified_flow.mmd`

