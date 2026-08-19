# exp_20260802_003 OC-SORT 运动模型与状态表达审计

状态：Pilot `0-199` 完成；Measurement Gate 全通过；Formal 禁止。

## Purpose

区分当前局部轨迹失败究竟来自 BoT-SORT 关联与生命周期、移动相机图像平面运动表达，
还是行人世界运动本身不满足常速度近似。

## Hypothesis

clean world-XY 三帧诊断显示常速度预测误差较小，而 GMC+CV 的图像候选召回高于 GMC
hold。预期世界运动不是首要瓶颈；OC-SORT 的 observation-centric recovery 可能改善局部
连续性，但只有通过完整 readiness gate 才允许 Formal。

## Setup

- 数据：MATRIX `0-199` Pilot，D1-D8，GT projected bbox + LoS
- 外观：冻结全视角 OSNet cache，threshold=`0.785027`
- GMC：复用/生成 `sparseOptFlow` 仿射缓存
- 参考：`botsort_gmc_osnet_hard_p01`
- 运动扫描：`delta_t={1,3}`、`inertia={0.1,0.2}`
- 固定：`track_buffer=5`、`match_thresh=0.8`、`proximity=0.1`
- 诊断上限：`oracle_world_xy_cv`，不参与部署 readiness 判定
- 运行时禁止：`person_id`、遮挡标签、world-XY 图像关联、未来帧

## Pipelines

```text
botsort_gmc_osnet_hard_p01
ocsort_no_gmc_noapp
deepocsort_gmc_noapp
deepocsort_gmc_osnet_soft_p01
deepocsort_gmc_osnet_hard_p01
oracle_world_xy_cv
```

OC-SORT 和 Deep OC-SORT 的无外观运动配置先按 IDF1、purity、fragmentation 排序；
之后只在胜出的 Deep OC-SORT 运动配置上比较 no-app、soft 和 hard veto。

## Pilot Command

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/deep-person-reid:.venvs/local-tracklet \
/usr/bin/python3 scripts/phase3_matrix_ocsort_motion_representation_audit.py \
  --mode calibrate \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 199 \
  --drone-ids 0 1 2 3 4 5 6 7 \
  --delta-ts 1 3 \
  --inertias 0.1 0.2 \
  --track-buffer 5 \
  --match-thresh 0.8 \
  --proximity-thresh 0.1 \
  --osnet-threshold 0.785027 \
  --progress-every 25 --resume \
  --output-dir outputs/20260802_matrix_ocsort_motion_representation_audit_pilot
```

## Decision Gates

Measurement gate 要求 BoT-SORT 参考误差 `<1e-6`，所有禁止读取、未来读取、确定性和
world-XY shuffle mismatch 均为 `0`。

完整 readiness：macro local IDF1 `>=0.80`、weighted purity `>=0.95`、最差视角
IDF1 `>=0.70`、遮挡 support coverage `>=0.90`。只有
`mobile_local_tracker_ready` 会在 `selected_config.json` 写入 `formal_allowed=1`。

其余决策为：`ocsort_partial_but_not_ready`、`association_lifecycle_bottleneck`、
`image_representation_bottleneck` 或 `world_motion_or_annotation_bottleneck`，均禁止 Formal。

## Outputs

```text
motion_representation_transition_metrics.csv
motion_representation_summary.csv
ocsort_config_selection.csv
ocsort_pipeline_metrics.csv
ocsort_quality_by_view.csv
ocsort_merge_fragmentation.csv
ocsort_occlusion_coverage.csv
ocsort_measurement_gate.csv
ocsort_decision.md
selected_config.json
checkpoints/
```

## Result

- world CV error p90=`0.269029m`，相对 hold 降低 `60.65%`。
- GMC+CV 的 IoU>=0.1 同人候选召回=`0.826277`。
- 最佳 image IDF1 来自 Deep OC-SORT soft：`0.337211`，但 purity 只有 `0.478666`。
- Deep OC-SORT hard purity=`0.968358`，但 IDF1=`0.096966`，fragmentation=`28142`。
- clean world-XY purity=`0.995616`、IDF1=`0.548384`；长于 5 帧的 LoS 间隔解释了
  多数碎片，说明当前 readiness 与局部生命周期/长期 ReID 混杂。

脚本原始 decision=`world_motion_or_annotation_bottleneck`。结构化分析将其收紧为
`readiness_gate_lifecycle_confounded`：运动诊断已经通过，当前不能把低 world-oracle
IDF1 直接归因给非线性运动或标注。详见 analysis report。

## Verification

```text
188 tests passed
py_compile passed
Pilot completed in the user terminal; Formal not launched
```

## Flowchart

`mermaid/exp_20260802_003_matrix_ocsort_motion_representation_audit/ocsort_motion_representation_flow.mmd`
