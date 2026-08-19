# exp_20260805_003 MDMT MIA 异步状态通道独立与级联审计

## Purpose

在已通过主动消息同步等价的 MIA-Net 上，分开延迟 `Local Track`、`Homography`、`ID state`
和 `Supplement`，定位异步通信的独立伤害与闭环级联，而不把四种语义混为一个总延迟。

## Frozen Setup

- Dataset: MDMT 14 个 official test pairs；CARAFE `epoch_12.pth` + 作者 ByteTrack。
- Reference: `exp_20260804_003_isolated_rerun/paper_aligned_mia`。
- Source: `packetized_async_deadline`，由通过 Gate B 的 `packetized_active_sync` 隔离复制。
- 首帧 XML GT 初始化保持同步；从第 1 帧开始双向固定延迟 `0/1/2/5/10` 帧。
- 不引入抖动、丢包、ReID、capture-time replay 或已发布 JSON 回写。

## Deadline Semantics

| Channel | Late-message action |
| --- | --- |
| Local Track | 本机仍发布当前轨迹；远端当帧消息未到则跳过跨视角步骤，不将旧 bbox 当当前目标。 |
| Homography | 使用同方向最近已到达的 H，并记录 `H_age_frames`。 |
| ID state | 将 ID 合并表达为单调版本化 remap 事件；只影响到达后仍存活的轨迹。 |
| Supplement | 当前帧有效；迟到即过期，禁止写入当前或历史输出。 |

## Conditions

Formal 共 27 条：同步 `d0`、四个单通道的 `d1/d2/d5/d10`、`H+ID`、`ID+Supplement`、
`H+ID+Supplement` 的 `d1/d5`，以及四个全通道延迟。Pilot 使用 pair 26/48，另重复
`all_channels_d5` 以检查确定性。

## Gates

- `d0` 检测缓存路径必须与冻结 reference 逐 JSON 相同。
- 禁止 GT identity、future read、source bypass、NumPy 引用共享和已发布历史回写。
- 单通道效应：至少两个非零延迟上 MDA 或 IDF1 损失 `>=0.02`，bootstrap 95% CI 不跨 0，
  且至少 `10/14` pairs 同方向；Supplement 可用 MOTA 损失 `>=0.01`。
- 级联：`combined_loss - max(single_channel_losses) >= 0.01`、CI 下界大于 0、至少 10 pair
  同方向，并由 H fallback、ID remap 或补全中介量恶化支撑。

## Commands

先生成隔离作者变体：

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking

PYTHONPATH=src python scripts/prepare_mdmt_mia_async_packet_variant.py \
  --source-root /mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_active_sync \
  --variant-root /mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_async_deadline \
  --copy-source
```

Pilot：

```bash
PYTHONPATH=src python scripts/phase3_mdmt_mia_async_state_channel_audit.py \
  --mode pilot \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --official-mda-gt-root data/MDMT_official_mda_gt \
  --async-source /mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_async_deadline \
  --reference-run-id exp_20260804_003_isolated_rerun \
  --delay-frames 0 1 2 5 10 --interaction-delays 1 5 \
  --seed 7 --progress-every 1 --resume \
  --output-dir outputs/20260805_mdmt_mia_async_state_channel_audit_pilot
```

Formal 仅在 Pilot decision 为 `pilot_ready_formal` 后运行，将 `--mode pilot` 改为 `formal`，
并将输出目录改为 `outputs/20260805_mdmt_mia_async_state_channel_audit`。

## Output

```text
outputs/20260805_mdmt_mia_async_state_channel_audit[_pilot]/
```

输出包含检测缓存审计、pair 级和聚合指标、延迟曲线、交互效应、packet action/outcome、
级联机制、GT frame coverage、measurement gate 和决策文档。

## Pilot Result

Pair 26/48 Pilot 已完成，测量门、`d0` JSON 等价和 `all_channels_d5` 重复确定性均通过，决策为
`pilot_ready_formal`。初步信号显示 ID state 对 IDSW/IDF1 最敏感，H 的直接影响较小，Supplement
主要影响 MDA；但只有 2 个 pair，不能据此宣布通道边界。

## Formal Result

14-pair Formal 已完成，测量门全部通过，决策为 `coupled_state_cascade_identified`。
Local Track 是最强的流程阻断通道：`all_channels` 在所有延迟下与 `local_only` 相同，因为
`skipped_local_deadline=5869` 使下游跨视角步骤无法执行。ID state 对 IDSW/IDF1 最敏感；
Supplement 主要影响 MDA。5 帧延迟下 `ID state + Supplement` 和 `H + ID state + Supplement`
的交互损失分别为 `0.064116` 和 `0.056203`，bootstrap CI 下界分别为 `0.022113` 和
`0.019310`，且同方向 pair 数为 `12/14` 和 `11/14`。

该结论不等于四个通道存在同等强度的联合协同：`all_channels` 的结果主要是 Local Track
的上游截止效应，而不是四通道交互项。详细分析见
`exp_20260805_003_mdmt_mia_async_state_channel_audit_analysis.md`。
