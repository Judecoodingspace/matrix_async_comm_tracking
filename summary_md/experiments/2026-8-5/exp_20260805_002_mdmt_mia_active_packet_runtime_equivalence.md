# exp_20260805_002 MDMT MIA 主动消息驱动同步等价验证

## Purpose

将 Gate A 的旁路消息审计升级为主动状态接口：四类 MIA 状态必须经过 JSON wire
roundtrip，并以解码后的独立对象继续驱动作者算法。该实验仍固定同步 `delay=0`；其目的是
排除“接口重构本身改变 MIA 状态闭环”的混淆，不能解释为通信性能实验。

## Frozen Reference

- Dataset: MDMT 14 个 official test pairs。
- Detector/tracker: CARAFE `epoch_12.pth` + 作者 ByteTrack。
- Reference: `paper_aligned_mia` 的 `exp_20260804_003_isolated_rerun` 输出。
- Initialization: 首帧 XML GT 初始化，仅标记为 offline initialization，不进入 packet。
- Timing: `capture_frame == arrival_frame`；无延迟、乱序、丢包或新 ReID。

## Active Boundaries

```text
ByteTrack local rows
  -> LocalTrackPacket -> decoded local rows
  -> H packet -> ID-state packets -> Supplement packets -> NMS
  -> explicit tracker feedback commit -> next-frame ByteTrack input
```

`IDStatePacket` 审计运行时 ID remap/old-unmatched 修复；`SupplementPacket` 审计新增或
改写的 runtime row。接口不携带 XML ID、official identity 或评价标签。

## Gates

- 解码数组与发送前对象无共享引用；active boundary 后下游变量只接收 decoded object。
- `source_bypass_read_count`、future-read、wire mismatch、alias、published-history rewrite 均为 `0`。
- 帧 `t` 发布的 tracker feedback digest 必须与帧 `t+1` 的 feedback input digest 一致。
- Pair 26 的五个单边界与组合路径逐 JSON 相等；Pair 48 检验稀少 H 点回退；14-pair Formal
  只运行组合路径。
- 所有比较视角的 SHA256、帧数、预测数、MOTA、IDF1、IDSW、MDA delta 必须完全相等。

## Commands

准备隔离变体：

```bash
PYTHONPATH=src python scripts/prepare_mdmt_mia_active_packet_variant.py \
  --source-root /mnt/data/yzm/experiments/mdmt_mia_official/variants/paper_aligned_mia \
  --variant-root /mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_active_sync \
  --copy-source
```

Pair-26 Pilot：

```bash
PYTHONPATH=src python scripts/phase3_mdmt_mia_active_packet_equivalence.py \
  --mode pilot \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --official-mda-gt-root data/MDMT_official_mda_gt \
  --active-source /mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_active_sync \
  --reference-run-id exp_20260804_003_isolated_rerun \
  --progress-every 25 --resume \
  --output-dir outputs/20260805_mdmt_mia_active_packet_runtime_equivalence_pilot
```

Pair-48 扩展只在 Pilot 的 `active_packet_equivalent` 后运行，将 `--mode pilot` 改为
`--mode pair48`；其通过后才运行 `--mode formal` 的 14-pair 组合路径。

## Output

```text
outputs/20260805_mdmt_mia_active_packet_runtime_equivalence[_pilot]/
```

包含 active JSON/metric equivalence、packet emission/consumption、state delta、feedback
chain、GT coverage、measurement gate 和 decision。

## Pilot Result

Pair-26 Pilot 已通过 `active_packet_equivalent`。六条条件的两视角 JSON SHA256 完全一致，
MOTA/IDF1/IDSW/MDA delta 全为 `0`。主动边界共完成 `2992` 次 packet emission/consumption，
反馈链 mismatch、共享引用、future read、source bypass 和 published-history rewrite 均为 `0`。

这只是 Pair-26 的边界验证，不是完整 Gate B；仍需 Pair-48 检验单应矩阵点数不足的回退，再做
14-pair Formal。

## Formal Result

Pair-48 组合路径通过，少于 5 个单应矩阵匹配点的回退未造成漂移。14-pair Formal 继续通过
全部 Gate：28 个视角 JSON SHA256 全等，MOTA、IDF1、IDSW、MDA delta 全为 `0`，主动 packet
往返共 `58718/58718`。反馈链 mismatch、共享引用、future read、source bypass 和
published-history rewrite 均为 `0`。

Formal 的同步指标与冻结 reference 完全相同：Overall MOTA `0.513848`、IDF1 `0.666922`、
IDSW `178.036`、MDA `0.383154`。Pair-55 view-1 仍有已知额外预测帧 `150`，但 GT frame coverage
为完整；该帧不改变等价结论。

## Decision

最终状态：`active_packet_equivalent`。Gate B 已通过，允许下一轮对
`Tracklet / H / ID state / Supplement` 分通道注入延迟。
