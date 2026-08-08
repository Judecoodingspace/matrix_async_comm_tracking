# exp_20260805_001 MDMT MIA 消息接口同步等价验证

## Purpose

将已经冻结且完成数值复现的同步 CARAFE + ByteTrack + MIA-Net 拆出可审计的消息边界，验证
这些边界在 `delay=0` 时不改变作者算法的逐帧输出。该实验是后续异步通信实验的 Gate A：若
消息接口本身改变了轨迹、单应矩阵、跨视角 ID 写回或补全顺序，任何延迟退化都不可归因于通信。

## Frozen Reference

- Dataset: MDMT 官方 14 个 test pairs。
- Detector/tracker: CARAFE `epoch_12.pth` + 作者 ByteTrack。
- Source: `paper_aligned_mia`；首帧 GT 初始化明确标记为 offline initialization。
- Reference output: `/mnt/data/yzm/experiments/mdmt_mia_official/outputs/exp_20260804_003_isolated_rerun/paper_aligned_mia/`。
- Synchronization: `capture_frame == arrival_frame`，未注入延迟、乱序、丢包或 ReID 替换。

前置同步复现门已关闭：pair-55 覆盖审计确认所有 GT 帧均被预测覆盖，view-1 的额外 frame 150
被单独报告；pair-26 两次作者运行 JSON 和 MDA/MOTA/IDF1/IDSW 均完全一致。

## Packet Boundaries

| Packet | Zero-delay content | Why it is needed later |
| --- | --- | --- |
| `LocalTrackPacket` | capture/arrival frame、view、融合前 tracker ID、track bbox/score、detector candidates、max ID | 延迟本地轨迹和低分检测补全依赖的候选框 |
| `HomographyPacket` | `H_AB`、`H_BA`、上一帧 H、匹配点数、估计模式 | 分离几何投影状态的延迟 |
| `IDStatePacket` | matched/confirmed IDs、两视角 max ID、重映射与旧 ID 修复状态 | 分离跨视角公共身份状态的延迟 |
| `SupplementPacket` | source/target view、映射 bbox、匹配检测框、IoU、low-score 标志、分配 ID | 分离检测补全的延迟 |

消息不包含 XML ID、官方跨视角 ID 或其他评价真值。每个零延迟消息均建立独立数组副本并完成
序列化审计；兼容路径仍保留作者 ByteTrack 的原始进程内 ID 写回引用，以免审计层改变作者的
历史状态反馈。真正替换为可延迟状态的运行时将在 Gate A 通过后逐通道实现。

## Execution Order

```text
two-view ByteTrack
  -> LocalTrackPacket
  -> homography estimation / HomographyPacket
  -> A-to-B ID allocation / IDStatePacket
  -> B-to-A ID allocation / IDStatePacket
  -> old-unmatched repair / IDStatePacket
  -> high-score then low-score supplementation / SupplementPacket
  -> NMS -> write IDs back to ByteTrack -> publish
```

## Measurement Gates

- Runtime GT identity reads, future reads: `0`.
- `capture_frame != arrival_frame` rows: `0`.
- Message serialization changes no values and creates no NumPy shared references.
- Pair-55 GT frame coverage remains complete; extra prediction frames are separately recorded.
- For every evaluated pair and both views: JSON SHA-256 equal, frame count equal, prediction count equal,
  and MOTA/IDF1/IDSW/MDA deltas are exactly `0`.

## Commands

Pair-26 Pilot:

```bash
PYTHONPATH=src python scripts/phase3_mdmt_mia_packet_interface_equivalence.py \
  --mode pilot \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --official-mda-gt-root data/MDMT_official_mda_gt \
  --packetized-source /mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_sync \
  --reference-run-id exp_20260804_003_isolated_rerun \
  --output-dir outputs/20260805_mdmt_mia_packet_interface_equivalence_pilot
```

Formal uses `--mode formal` with the same frozen source and output root
`outputs/20260805_mdmt_mia_packet_interface_equivalence/`.

## Current Result

Pair-26 and Pair-48 extensions both passed strict JSON and metric equivalence. The 14-pair Formal is running;
do not claim the experiment complete until every pair passes the same strict gate.

## Decision

Pending full formal. `packet_interface_equivalent` requires all 14 pairs and both views to be JSON-identical.
