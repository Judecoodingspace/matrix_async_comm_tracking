# exp_20260803_002 Pilot Analysis Report

> 状态：完整 MDMT val Pilot 已完成；official-test Formal 未运行，也未获授权。
> Pilot 的 14 项实现级 measurement gate 全部通过，但 3/6 个外观阈值无法达到
> precision >= 0.95，因此当前结论是 `calibration_blocked`，不能判定 H1-H4。

## 1. 假设对照

- H1 同步 support headroom：**未证实**。delay=0 时，增量 tracklet 相对
  `primary_reid_stitching` 的 gap survival delta 为 `0`，global IDF1 还从
  `0.963867` 降至 `0.942470`。
- H2 时间戳价值：**不可辨识**。`history1_timestamped` 与
  `arrival_time_fusion` 在所有 delay 上完全相同，因为 latest 阈值虽达到
  precision `1.0`，但两个方向 recall 只有 `0.000079/0.000119`，几乎没有
  support 消息真正产生有效关联。
- H3 增量 tracklet 价值：**不可判定**。两个方向的 pooled cue 都无法达到
  precision 门，当前回退阈值 `0.263346` 的 precision 仅 `0.014642`。
- H4 fixed-lag/late recovery：**不可判定**。所有 pipeline 的 17 个 gap 上
  survival 完全相同；长延迟增量重放只观察到更多 IDSW 和 fragmentation。

总体判决：`ambiguous_due_to_calibration_failure`。这不是 H3 已被否定，而是用于
检验 H3 的 pooled appearance gate 尚不可用。

## 2. 基线比较

| Pipeline / condition | Global IDF1 | IDSW | Fragmentation | Gap survival |
| --- | ---: | ---: | ---: | ---: |
| `primary_only` | 0.978587 | 50 | 38 | 0.000000 |
| `primary_reid_stitching` | 0.963867 | 48 | 36 | 0.117647 |
| `incremental`, delay 0-5 | 0.942470 | 48 | 36 | 0.117647 |
| `incremental`, delay 20 | 0.942438 | 51 | 38 | 0.117647 |
| `incremental`, delay 50 | 0.939839 | 62 | 50 | 0.117647 |

反直觉点：`primary_only` 的总体 IDF1 最高。同视角 ReID 恢复了 2/17 个长 gap，
但错误重连接使全局 IDF1 下降 `0.014720`。这说明“恢复更多 gap”和“全局身份更准”
不是同一个目标，必须同时约束 precision、IDSW 和 IDF1。

`drop_delayed` 在非零 delay 时精确等于 `primary_reid_stitching`，符合实现定义；
delay=0 时却降至 `0.942470`，原因是同步 pooled support 使用了失败后的低阈值。

## 3. 失败模式

### 外观校准失败

| Direction / cue | Precision | Recall | Gate |
| --- | ---: | ---: | --- |
| V1 primary, same-view | 1.000000 | 0.058824 | pass |
| V2 primary, same-view | 0.022989 | 1.000000 | fail |
| V1->V2 latest | 1.000000 | 0.000079 | nominal pass, ineffective |
| V2->V1 latest | 1.000000 | 0.000119 | nominal pass, ineffective |
| pooled, both directions | 0.014642 | 1.000000 | fail |

当不存在 precision>=0.95 的阈值时，当前阈值搜索选择“召回最高”的 fallback，实际
等价于接近全接受。它让增量管线产生大量错误跨视角绑定：full incremental 记录了
`2822` 次 `support_cross_match` 和 `730` 次 `primary_support_recovery`，但没有新增
任何 gap survival。

### 延迟下的污染累积

增量 full replay 在 delay 10/20/50 的 IDSW 为 `49/51/62`，fragmentation 为
`37/38/50`。退化随延迟增加，但由于 gate 本身无效，不能把这一曲线解释为异步
tracklet 的固有 harm boundary；它只是说明错误身份绑定经重放会被累积和放大。

### 评价与决策实现问题

- `global_measurement_gate.csv` 的 14 项全部通过，最终却统一输出
  `measurement_invalid`。阈值可校准性应与测量有效性分开报告。
- H1 代码对“AAS 提升”分支仍要求 gap-survival bootstrap CI 下界大于 0；当前并未
  对 AAS delta 单独 bootstrap，因此实现与实验卡中的二选一规则不完全一致。

## 4. 上限分析

- 本地 tracking 不是当前瓶颈：上一轮 MDMT person-only Formal 的 local IDF1 为
  `0.997229`。
- 当前主视角 online IDF1 已高达 `0.978587`，同步 support 的可提升空间很小，且
  任何错误 stitching 都容易让总体 IDF1 下降。
- 17 个 val gap 中，support coverage 均值为 `0.7793`；delay 0-10 时全部消息都能在
  primary reacquisition 前到达。因此当前缺失的不是消息时机，而是可靠的跨视角身份
  证据及其候选约束。

## 5. 泛化信号

1. 稳定 local track ID 和历史长度本身不会产生身份信息；如果 pooled appearance 不可
   分，history>1 只会稳定地传播错误关联。
2. 高 precision、近零 recall 的门控在安全性上近似“丢弃 support”，不能作为
   cross-view cue 有效的证据。
3. 在强 primary baseline 下，应先证明同步 support 的净增量，再研究 delay、重放和
   recovery；否则异步比较没有可识别的有效信号。

## 6. 与历史对照

- 与 MATRIX simulated identity 一致：身份线索只有在候选质量达到边界后才可能帮助
  delayed update。
- 与 MATRIX real OSNet 结果一致：冻结 OSNet 在大视角差异下只能提供有限、方向不对称
  的身份信息。
- 与 MDMT local readiness 不矛盾：本地 bbox SORT 很强，只证明单视角 active-run
  tracklet 可靠，不证明跨视角 embedding 可分。

本轮把瓶颈从“本地轨迹生成”进一步收紧为“跨视角候选与外观校准”。

## 7. 下一步建议

### P0：修复校准和决策语义

- 无 precision 合格阈值时使用 reject-all sentinel，不得回退到全接受阈值。
- 分开输出 `measurement_valid`、`calibration_feasible` 和 `formal_allowed`。
- 为 AAS delta 实现独立的 identity-cluster bootstrap，修正 H1 判据。
- 成功标准：14 项 measurement gate 仍全通过；失败 cue 不再触发任何 runtime match；
  H1 的 gap-survival 与 AAS 两条路径各使用自己的 CI。

### P0：做 candidate-conditioned appearance audit

- 分方向报告 latest/pooled 的 same/different similarity 分布、PR 曲线、最大可达 recall，
  并限制到 runtime 真正可见的 global candidates，而不是只给一个阈值结果。
- 比较平均池化、近期窗口池化和小型 gallery max/Top-k 聚合，判断全历史平均是否因姿态
  混合而破坏身份分离。
- 成功标准：至少一种 tracklet appearance 在 precision>=0.95 时 recall 达到可用水平
  （建议先要求 >=0.10），并且两个方向均有信号。

### P1：同步最小验证后再跑 delay sweep

- 只运行 delay=0，比较 `primary_reid_stitching`、reject-all support、latest support 和
  修复后的 tracklet appearance。
- 只有同步 support 在 gap survival 或 bootstrap AAS 上显著优于 primary ReID，才恢复
 完整异步 Pilot；否则结论应为 `no_sync_support_headroom`。

### P2：若 OSNet 仍不可分，升级跨视角表示

- 比较跨相机 ReID 微调、camera-conditioned threshold 或 pose/时序约束。
- 不应通过降低 precision 门来强行获得 recall；本轮已经显示错误 support 会随 replay
  扩大 IDSW。

## Flowchart

```mermaid
flowchart LR
    A[14项实现检查通过] --> B{外观阈值可校准?}
    B -->|latest: 几乎零召回| C[近似丢弃 support]
    B -->|pooled: precision 1.46%| D[错误跨视角绑定]
    C --> E[H2 无法辨识]
    D --> F[IDSW 随延迟累积]
    E --> G[Formal 禁止]
    F --> G
    G --> H[先修校准与候选外观]
```

设计图：`mermaid/exp_20260803_002_mdmt_async_incremental_tracklet_fusion/fusion_flow.mmd`。

## 补充说明

- 本次命令的 mode 是 `calibrate`，输出目录以 `_pilot` 结尾，因此不是 Formal。
- 当前 `selected_config.json.formal_allowed=false`，不得执行 official-test 命令。
- Git 元数据在当前执行环境不可见，本次仅更新文件系统中的研究记录。
