# exp_20260803_002 MDMT 异步增量 Tracklet 融合

## Purpose

验证在相同发送频率、相同单向量 embedding 预算和相同通信延迟下，带稳定 support local
track ID 与历史聚合外观的增量 tracklet 消息，是否比单帧消息更能维持主视角的在线全局
身份连续性。

## Hypotheses

- H1：同步增量 support 相对主视角同视角 ReID 存在额外性能空间。
- H2：相同单帧 payload 在 capture time 重放优于按 arrival time 融合。
- H3：稳定 local ID + pooled appearance 优于 history=1 单帧消息。
- H4：短延迟由 fixed-lag 覆盖，长延迟由 future-only recovery 补充。

## Setup

- Dataset：MDMT，val 阈值校准，official test 正式评价。
- Scope：person-only、GT bbox、排除 detector error。
- Local tracker：`bbox_sort`，`track_buffer=5`。
- Directions：`V1 -> V2` 与 `V2 -> V1` 双向主辅交换。
- Delay：`0,1,2,5,10,20,50` frames。
- Fixed lag：`5` frames。
- Appearance：冻结 OSNet cache；每包只传一个 float32 embedding。
- Runtime exclusions：GT identity、遮挡标签、world XY、未来帧。

## Pipelines

```text
primary_only
primary_reid_stitching
drop_delayed
arrival_time_fusion
history1_timestamped
incremental_tracklet_timestamped
fixed_lag_tracklet_update
late_recovery_stitching
```

`primary_reid_stitching` 是必要强基线，用于区分普通同视角长期 ReID 收益和跨视角
support 的真实增量。`history1_timestamped` 与 `arrival_time_fusion` 使用完全相同的 latest
embedding wire packet；`incremental_tracklet_timestamped` 改用稳定 support tracklet ID 和
pooled embedding。

## Implementation

```text
src/tracking/tracklet_packets.py
src/tracking/mdmt_global_tracklet_fusion.py
scripts/phase3_mdmt_async_incremental_tracklet_fusion.py
tests/test_mdmt_global_tracklet_fusion.py
```

全局融合状态分离保存 primary 与 support appearance gallery。capture-time replay 只能修改
internal corrected state 和未来输出，不能改写已经发布的 online global ID。每个
`sequence x direction x delay x pipeline` 独立 checkpoint，支持 `--resume` 和逐帧进度。

## Pilot Command

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/local-tracklet \
python scripts/phase3_mdmt_async_incremental_tracklet_fusion.py \
  --mode calibrate \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --view-directions 1:2 2:1 \
  --labels person \
  --delay-frames 0 1 2 5 10 20 50 \
  --lag-frames 5 \
  --local-config outputs/20260803_mdmt_local_tracklet_readiness_pilot/selected_config.json \
  --embedding-cache outputs/20260803_mdmt_local_tracklet_cache/osnet_x0_25_msmt17.npz \
  --seed 7 --progress-every 25 --resume \
  --output-dir outputs/20260803_mdmt_async_incremental_tracklet_fusion_pilot
```

## Formal Command

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/local-tracklet \
python scripts/phase3_mdmt_async_incremental_tracklet_fusion.py \
  --mode evaluate \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --view-directions 1:2 2:1 \
  --selected-config outputs/20260803_mdmt_async_incremental_tracklet_fusion_pilot/selected_config.json \
  --embedding-cache outputs/20260803_mdmt_local_tracklet_cache/osnet_x0_25_msmt17.npz \
  --official-mda-gt-root data/MDMT_official_mda_gt \
  --seed 7 --progress-every 25 --resume \
  --output-dir outputs/20260803_mdmt_async_incremental_tracklet_fusion
```

## Smoke Verification

单序列 val-22 双向、delay `0/2` 的真实数据 smoke 已完成。14 项实现级 measurement gate
全部通过；最终 wiring smoke 还验证了 `formal_allowed=false` 会随阈值 gate 正确锁定。
smoke 标记 `measurement_invalid` 仅因为 V1 主视角同视角 ReID 校准只有
1 个正样本，单序列无法达到 precision `>=0.95`。完整 val Pilot 将决定阈值 gate。

## Decision

`implemented_pilot_pending`

## Next Actions

- [ ] 用户终端执行完整 val Pilot。
- [ ] 仅当 `selected_config.json.formal_allowed=true` 时执行 official test Formal。
- [ ] Formal 后按七维框架填写分析报告并更新决策。
