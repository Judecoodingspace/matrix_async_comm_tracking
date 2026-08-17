# 实验契约（中文版）

## 实验身份

- 实验 ID：`exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`
- 状态：`拟定完成，等待 R1-R3 科研决策`
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

拟定使用：

```text
25 train pairs
  -> 15 development
  -> 10 train holdout

5 val pairs：22, 36, 46, 49, 72
  -> external holdout
```

划分只由 sequence ID 和 seed=7 决定，在读取性能结果前生成并冻结。

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
R_edge(d) < 0，95% CI 上界 < 0
C_comp(d) > 0，95% CI 下界 > 0
两个对比均至少 10/15 pair 同方向
delay-only candidates 确实产生 High-score write-in
```

## 执行规模

```text
MVE：2 pairs x 11 conditions = 22 pair-condition runs
Development：15 pairs x 17 conditions = 255 runs
Holdout：最多 15 pairs x 8 conditions = 120 runs
```

MVE 只验证代码、协议和因果门，不产生机制结论。

## 决策

- `compensation_onset_validated`：允许下一轮设计非 oracle、版本感知 Recovery。
- `test_specific_or_not_replicated`：不得围绕 E023 d5 构建方法。
- `delay_conditioned_but_onset_unresolved`：继续收集非测试数据，不设计硬 delay gate。
- `mechanism_heterogeneous_across_splits`：先解释 domain moderator。
- `measurement_invalid`：只修复测量边界并重新跑 MVE。

## 当前阻塞项

1. R1：是否批准从 raw annotation 构造 train/val MDA GT，前提是转换器严格复现全部 official test GT。
2. R2：是否批准 `15 train development + 10 train holdout + 5 val external holdout`。
3. R3：是否批准 `d1..d5` 与预注册的 earliest-onset 规则。

R1-R3 明确批准前，不进入 Terra，不实现代码，也不运行实验。

