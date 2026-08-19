# 实验契约（中文版）

## 实验身份

- 实验 ID：`exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`
- 状态：`R1-R3 已解决 / 契约修订已落盘 / 等待 GT 协议门`
- 父实验：E023 ID-delay candidate-set cascade Formal
- 输出目录：`outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/`

## 为什么不是直接做版本感知 Recovery

E023 只在 official test 的 `d1/d5` 上证明：

```text
d1：候选集合补偿不可辨识
d5：候选集合补偿成立
```

如果现在直接依据 test 结果选择 `d2/d3/d4` 或设计 delay gate，就会把 official
test 变成调参集。当前最小必要实验是先在非测试数据上回答：补偿从哪个延迟区间
开始出现，以及该现象是否能复现。版本感知 Recovery 是本实验通过后的下一份独立契约。

## 研究问题

> 在 Local Track、Homography 和 Supplement 及时，仅 ID state 延迟的条件下，
> E023 在五帧观察到的候选集合补偿是否能在非测试 MDMT 序列上复现？它首次变得
> 可辨识的延迟区间在哪里？

## 事实、推断与未知

### 已知事实

- E023 14-pair Formal 的 40 项测量门全部通过。
- ID-state delay 在 d1/d5 均降低 MDA，并明显增加 IDSW。
- `R_edge=Yec-Y10` 在 d1 跨 0，在 d5 显著小于 0。
- `C_comp` 在 d1 跨 0，在 d5 显著大于 0。
- `Yec` 是只输出 membership bit 的 oracle 诊断，不是方法上界。

### 当前推断

- d1 到 d5 之间可能存在候选集合补偿的出现边界。
- 延迟增加的 unmatched candidate 可能通过 High-score Supplement write-in
  形成部分补偿。

### 仍未知

- d5 结果是否只属于 official test cohort。
- d2/d3/d4 是否呈现稳定、单调的过渡。
- 哪些序列属性解释异质性。

## 冻结条件

```text
Detector / tracker：paper-aligned CARAFE + ByteTrack MIA
Local Track：timely
Homography：timely
ID delay：1, 2, 3, 4, 5 frames
Supplement：Y10/Yec timely；Y01/Y11 按现有 deadline 过期
seed：7
首帧初始化：保持同步 offline initialization
```

禁止新增 ReID、旧 bbox 插入、历史改写、重放、丢包、抖动或调度策略。

## 五个条件

| 条件 | ID state | Supplement | 候选集合 |
| --- | --- | --- | --- |
| `Y00` | 及时 | 及时 | 同步集合 |
| `Y10_d` | 延迟 d 帧 | 及时 | 实际 `S_delay` |
| `Y01` | 及时 | 过期 | 同步集合 |
| `Y11_d` | 延迟 d 帧 | 过期 | 实际 `S_delay` |
| `Yec_d` | 延迟 d 帧 | 及时 | oracle `S_cf` |

## 数据划分

official test 14 pairs 完全冻结，不再用于选择 delay。

批准并冻结：

```text
25 train pairs
  -> 15 development
  -> 10 train holdout

5 val pairs：22, 36, 46, 49, 72
  -> MDMT val holdout
```

先固定 25 个 train pair ID 的 canonical ordering，再用固定算法和 `seed=7`
一次性生成 15/10 划分；划分只能依赖 sequence identity、排序与 seed，并在读取
任何 tracking outcome 前冻结。5 个 val pairs 只提供跨 MDMT train/val split 的
方向一致性与 robustness evidence，不得称为 cross-dataset external validation。

## R1 非测试 MDA GT 协议

source annotation 是唯一权威。转换器只能做格式转换、预定义且确定性的 ID mapping
以及到 MDA representation 的机械投影；没有语义修复权限。禁止依据图像、tracking
result 或最终 MDA 修改身份，禁止人工修 ID 或 patch source annotation。

在用于 train/val 前，同一转换规则必须精确复现全部 official-test MDA GT：

```text
official_test_row_mismatch = 0
official_test_frame_mismatch = 0
official_test_id_mismatch = 0
```

任一不一致均 fail closed。train/val 还必须独立满足：

```text
non_test_duplicate_identity_keys = 0
non_test_missing_source_rows = 0
frame_offset = 0
```

并单独审计跨视角同 ID 是否符合 train/val annotation convention。主结果使用完整、
未经人工修正的确定性 GT；class-consistent sensitivity 只作 robustness evidence。
若两者结论冲突，必须报告 measurement-validity 风险，不得选择性采用 sensitivity。

## 主要对比

```text
D_ID(d)    = Y00 - Y10_d
R_edge(d)  = Yec_d - Y10_d
M_delay(d) = Y10_d - Y11_d
M_sync     = Y00 - Y01
C_comp(d)  = M_delay(d) - M_sync
```

补偿起点要求同时满足：

```text
Gate A：R_edge(d) 的 pair-level bootstrap 95% CI 上界 < 0
Gate B：C_comp(d) 的 pair-level bootstrap 95% CI 下界 > 0
Gate C：至少 10/15 development pairs 的 R_edge(d) < 0
Gate D：至少 10/15 development pairs 的 C_comp(d) > 0
Gate E：实际出现 delayed ID -> delay-only candidate -> timely Supplement
        consumption -> High-score Supplement bbox write-in
Gate F：上述实际 write-in 路径至少出现在 10/15 development pairs
```

bootstrap 的统计单位必须是 pair，不能把 frame 或 candidate 当成独立样本。按
`d1 -> d2 -> d3 -> d4 -> d5` 顺序检查，`d*` 是最早通过 Gate A-F 的 delay，
不是 magnitude 最大或数值最漂亮的 delay。更早的少数 responder 和 moderator pattern
只能作为 descriptive / hypothesis-generating evidence。

若 d1-d5 均未通过，正式结论为：在预注册 d1-d5 范围内没有识别到可靠的
candidate-compensation onset；此时停止，不进入 holdout，不放宽门槛，也不在本实验
中扩展到 d6 以上。

## 执行规模

```text
MVE：2 pairs x 11 conditions = 22 pair-condition runs
Development：15 pairs x 17 conditions = 255 runs
Holdout：最多 15 pairs x 8 conditions = 120 runs
```

MVE 只验证代码、协议和因果门，不产生机制结论。

## 因果解释限制

- `Yec` 始终是 oracle membership-only causal diagnostic，不是可部署方法，也不是
  performance upper bound。
- `R_edge < 0` 不表示 ID-state delay 有益；delay 可能仍有直接伤害，而 candidate
  compensation 只抵消其中一部分。
- MDA 是 primary endpoint；MOTA、IDF1、IDSW 必须作为 secondary metrics 分开解释，
  不能由 MDA 补偿结果推导“overall tracking performance improves”。
- mechanism write-in 只证明路径活跃且可重复，性能因果证据仍由 `R_edge` 与
  `C_comp` 承担。
- 本实验只验证 non-test compensation onset，不授权 version-aware recovery 实现。

## 决策

- `compensation_onset_validated`：允许下一轮设计非 oracle、版本感知 Recovery。
- `test_specific_or_not_replicated`：不得围绕 E023 d5 构建方法。
- `delay_conditioned_but_onset_unresolved`：继续收集非测试数据，不设计硬 delay gate。
- `mechanism_heterogeneous_across_splits`：先解释 domain moderator。
- `measurement_invalid`：只修复测量边界并重新跑 MVE。

## 已解决的科研决策

1. R1：`APPROVED / RESOLVED_CONDITIONAL`。
2. R2：`APPROVED / RESOLVED`。
3. R3：`APPROVED / RESOLVED_WITH_CONTRACT_AMENDMENT`。

本轮契约修订是把机制门从 pooled nonzero write-in 收紧为：至少 `10/15`
development pairs 实际出现 delay-only candidate -> High-score Supplement write-in。

Research Decision blocker 已解除，但实验尚未 implementation-ready 或 Formal-ready。
下一道门是 R1 的 GT 协议门；在 official-test 精确复现和 non-test 结构/身份语义审计
完成前，不实现 MVE、不运行实验，也不进入 version-aware recovery。
