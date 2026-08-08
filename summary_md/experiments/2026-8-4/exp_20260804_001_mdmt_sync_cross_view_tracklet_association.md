# exp_20260804_001 MDMT 同步跨视角 Tracklet 关联可行性审计

## Purpose

在 `delay=0` 条件下，判断可靠 local tracklet 是否能通过在线候选约束和因果外观记忆，
产生超过主视角基线的跨视角身份增量。只有同步性能空间成立后，才恢复异步 delay sweep。

## Hypotheses

- H0：Oracle identity 能显著提升 gap survival 或 person AAS，证明 global fusion 与评价链有上限。
- H1：候选约束能在不使用 GT 的运行时把跨视角 precision 保持在 `0.95` 以上。
- H2：EMA、短窗口或接收端 gallery 能比 latest 和全历史 cumulative mean 提供更高 recall。
- H3：选中真实配置能把离线外观质量转化为同步 tracking 收益。

## Setup

- Dataset：MDMT，val 五序列 LOSO 校准；official test 仅在 Pilot 通过后评价。
- Scope：person-only、GT bbox、冻结 OSNet、本地 `bbox_sort buffer=5`。
- Directions：V1->V2、V2->V1。
- Delay：固定 `0`。
- Packet：每包一个 512-D embedding；gallery 只增加接收端状态，不增加通信向量数。
- Runtime exclusions：GT identity、world XY、遮挡标签和未来帧。

## Appearance And Candidate Audit

```text
latest / cumulative mean / EMA 0.9
window mean 3/5/10
receiver gallery max 5/10 / top3 of 10

all history / primary active / primary active or recent 5
```

每个方向用 leave-one-sequence-out 校准 threshold。无 precision `>=0.95` 的阈值时锁定
`1.000001` reject-all，不允许回退为低阈值全接受。

校准按“方向 × 外观方式 × 候选策略”独立写 checkpoint；`--resume` 会跳过已经完成的
LOSO 组合。gap bootstrap 先在 `(sequence_id, official_person_id)` 内汇总该身份的全部
gap，避免一个身份有多个 gap 时只保留最后一条。

## Pipelines

```text
primary_only
primary_reid_stitching
oracle_identity_sync
osnet_latest_all_history
osnet_cumulative_all_history
osnet_selected_sync
```

Oracle 是诊断分支，GT 读取独立计数；真实 pipeline 的 runtime GT reads 必须为 0。

## Pilot Command

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/local-tracklet \
python scripts/phase3_mdmt_sync_cross_view_tracklet_association.py \
  --mode calibrate \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --view-directions 1:2 2:1 \
  --labels person \
  --local-config outputs/20260803_mdmt_local_tracklet_readiness_pilot/selected_config.json \
  --embedding-cache outputs/20260803_mdmt_local_tracklet_cache/osnet_x0_25_msmt17.npz \
  --candidate-recent-frames 5 \
  --minimum-precision 0.95 --minimum-recall 0.10 \
  --seed 7 --progress-every 25 --resume \
  --output-dir outputs/20260804_mdmt_sync_cross_view_tracklet_association_pilot
```

## Formal Command

仅当 Pilot 的 `selected_config.json.formal_allowed=true` 时执行：

```bash
YOLO_CONFIG_DIR=/tmp \
PYTHONPATH=src:.venvs/local-tracklet \
python scripts/phase3_mdmt_sync_cross_view_tracklet_association.py \
  --mode evaluate \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --view-directions 1:2 2:1 \
  --selected-config outputs/20260804_mdmt_sync_cross_view_tracklet_association_pilot/selected_config.json \
  --embedding-cache outputs/20260803_mdmt_local_tracklet_cache/osnet_x0_25_msmt17.npz \
  --official-mda-gt-root data/MDMT_official_mda_gt \
  --seed 7 --progress-every 25 --resume \
  --output-dir outputs/20260804_mdmt_sync_cross_view_tracklet_association
```

## Decision

`implemented_pilot_pending`

Formal 需要同时满足：measurement valid、Oracle headroom、两个方向 appearance
precision/recall 门和真实同步 tracking transfer。

`candidate_constraint_required` 与 `tracklet_memory_required` 是通过后报告的机制标签，
不替代 `sync_cross_view_tracklet_association_ready` 这一 Formal 授权结论。

## Next Actions

- [ ] 用户手动运行完整 val Pilot。
- [ ] 分析 LOSO PR、候选策略、聚合方式与 Oracle headroom。
- [ ] 只有 `formal_allowed=true` 才运行 official-test Formal。
