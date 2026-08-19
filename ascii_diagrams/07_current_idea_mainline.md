# 07 当前 Idea 逻辑主线

这份文档不是缩写版词典，而是从 `GLOSSARY.md` 中筛出真正支撑当前
MATRIX 异步多无人机跟踪主线的术语，并把它们连成一条可以讲给非本方向
研究者听的故事。

## 一句话版本

```text
当主无人机看不见人时，辅助无人机发来的旧消息仍可能救回身份；
但系统必须确认它来得还不算太晚、位置误差不会带偏轨迹、外观也确实像这个人，
才允许它回到一个有限的历史窗口中修正状态。
```

更专业地说：当前 idea 是在 LoS 遮挡下，对 delayed cross-view OOSM 做
`fixed-lag capture-time update`，并用 `geometry + covariance + identity`
共同控制迟到观测是否有资格写回轨迹状态。

## 1. 只保留这四组术语

### A. 描述问题：消息为什么“有用但来不及”

| 核心术语 | 生活化理解 | 在本项目中的准确含义 |
| --- | --- | --- |
| Primary / Support UAV | 一个店员现场值班，其他店员远程报信 | D1 是主要在线观测源，D2-D8 提供跨视角辅助观测 |
| Occlusion Episode | 现场店员暂时看不见顾客的一段时间 | primary 对目标无 LoS、但目标仍在全局 GT 中存在的连续帧段 |
| OOSM | 第 10 页的证据到第 12 页才送来 | capture time 早于当前处理时刻的乱序观测 |
| Capture / Arrival / Publish Time | 拍照、收到照片、提交报告是三个不同时间 | 观测属于 capture 帧，到 arrival 帧才可用；过去的 online output 在 publish 后不能改写 |
| Drop-delayed | 迟到情报一律不用 | 安全基线；避免污染，但遮挡时失去外部身份证据 |

### B. 解释失败：为什么不是“收到就融合”

| 核心术语 | 生活化理解 | 在本项目中的准确含义 |
| --- | --- | --- |
| Arrival-time Fusion | 把两分钟前的位置当成现在的位置 | 在消息到达帧直接融合旧 world-XY，会制造空间陈旧和误关联 |
| Causal Timestamped Replay | 把迟到证据放回原页，再重算后续几页 | 按 capture time 更新并重放 tracker；只能改善当前内部状态和未来输出 |
| Early-Frame Gap Boundary | 援军虽在事故结束前到，但最关键的头几分钟已错过 | 遮挡早期若没有及时 support，身份可能在后续消息到达前已经断开 |
| Support World-Coordinate Noise | 报信及时，但地图落点偏到了隔壁 | support 的位姿、标定或重投影误差在实验中由 world-XY 高斯噪声代理 |
| Temporal-Spatial Risk | 情报既旧又偏，两种误差叠加 | delay 造成的位置陈旧与坐标噪声共同逼近或越过关联门半径 |

### C. 当前机制：迟到消息怎样才允许“改病历”

| 核心术语 | 生活化理解 | 在本项目中的准确含义 |
| --- | --- | --- |
| Fixed-Lag OOSM Update | 医院只允许修改最近几页病历 | 只对 `delay <= lag` 的消息回到 capture time 附近更新并重放 |
| Useful Support Window | 救援队到场后还剩多少可救时间 | 消息到达后仍可影响多少遮挡期状态；`delay <= lag` 只是资格，不保证收益 |
| Covariance-Aware Update | 地图说自己可能偏 25 cm，就少给它一些决定权 | 根据 measurement uncertainty 降低 noisy support 对位置状态的更新权威 |
| Identity Gate | 地址有点偏时，再核对收件人照片 | 在几何候选中用 embedding similarity 拒绝身份不相符的 support |
| Same/Different Margin | 同一个人的照片要明显比不同人的更像 | `mean_same_similarity - mean_different_similarity`，是身份线索质量的离线解释量 |
| Identity Accept Threshold | 照片像到什么程度才放行 | runtime cosine similarity 的接受阈值；太松会误接，太严会拒绝有用 support |

### D. 判断证据：我们凭什么相信这个故事

| 核心术语 | 生活化理解 | 在本项目中的准确含义 |
| --- | --- | --- |
| Paired Counterfactual | 从同一存档复制两份，一份保留情报、一份删掉情报 | 从相同 episode 前状态分叉 Run A/B，隔离目标 support 的因果边际价值 |
| IDF1 / IDSW | 不只问“看见了几个人”，还问“姓名牌有没有一直戴对” | IDF1 衡量身份匹配质量，IDSW 统计轨迹身份切换 |
| Cue Quality Boundary | 照片至少清楚到什么程度才真的能认人 | 在指定 delay、噪声和阈值下，identity cue 从失败转为稳定有益的经验边界 |
| Candidate-Conditioned Calibration | 不和全城人比，只和附近候选人比 | 只在 geometry/covariance shortlist 内估计阈值，贴近 tracker 的真实竞争关系 |

下一步还会用到两个术语，但它们是“真实证据迁移”的实验控制，不是当前
算法的新部件：`GT-Box Real Appearance` 用 GT 框裁人、只测试真实外观
embedding；`Cross-Fitted Identity Threshold` 用一组身份定阈值、在另一组
身份上评价，避免用同一批人既调参又证明有效。

## 2. 先看清最基本的时间矛盾

MATRIX 当前按 2 FPS 使用，1 帧等于 500 ms。一条 support 消息可能在
`f10` 拍到目标，到 `f12` 才抵达：

```text
frame:       f10              f11              f12
             |----------------|----------------|
primary:     P                O                O
support:     S(cap) --------------------------> S(arr)
online:      publish(f10)     publish(f11)     publish(f12)

消息内容属于 f10；系统到 f12 才知道它。
f10/f11 的在线结果已经发布，不能因为后来知道答案而改写。
```

因此有三个不同的问题：

```text
消息有没有信息？              -> offline/timestamped 上界回答
消息什么时候到？              -> delay / arrival time 回答
消息到达后还能救多少在线状态？ -> lag + useful support window 回答
```

这也是为什么“最终收到了消息”不等于“消息对在线跟踪有用”。

## 3. Idea 是怎样被实验一步步逼出来的

```text
[问题]
Primary 在遮挡期看不见目标，Support 消息又会迟到
                         |
                         v
[最直接做法：Arrival-time Fusion]
把旧位置当成当前位置
                         |
                         v
[失败证据]
2 帧延迟已稳定有害；旧位置会把轨迹拉向错误候选
                         |
                         v
[第一次修正：按 Capture Time 处理]
把消息放回它真正属于的历史帧，再重放后续状态
                         |
              +----------+----------+
              |                     |
              v                     v
      离线结果很好             在线仍有 Early-Frame Gap
      说明消息有信息           过去输出已发布，晚到不能全救回
              |                     |
              +----------+----------+
                         v
[当前时间机制：Fixed-Lag OOSM]
只在有限历史窗口内回放，超过 lag 的旧消息不硬改历史
                         |
                         v
[第二个边界：Useful Support Window]
delay <= lag 只是入场资格；到达后还要剩下足够可影响的遮挡帧
                         |
                         v
[第三个边界：Temporal-Spatial Risk]
消息即使及时，world-XY 偏差达到 0.25m 时仍可能把状态写错
                         |
              +----------+----------+
              |                     |
              v                     v
       Covariance 降低权威       Identity Gate 核对身份
       “位置不准就少改”         “不像本人就不改”
              |                     |
              +----------+----------+
                         v
[当前联合结构]
Fixed-Lag + Geometry + Covariance + Identity
                         |
                         v
[最新边界]
模拟身份线索 margin=0.056747、threshold=0.20 可通过两档 delay；
margin=0.040019 在五个 threshold 下全部失败
                         |
                         v
[下一步]
运行已经实现的 GT-box 真实 appearance smoke/formal：
M3OT-GeM / OSNet frozen embedding
+ person-disjoint cross-fitting
+ geometry shortlist 内的 candidate-conditioned threshold calibration
```

## 4. 当前机制不是一个“大而全策略”，而是四道问题

一条 delayed support 到达时，可以用下面的流程理解：

```text
Delayed support observation arrives
                 |
                 v
    Q1: capture time 可靠吗？
        否 -> reject / 仅作诊断
        是
                 |
                 v
    Q2: delay <= fixed lag 吗？
        否 -> freeze published history；recovery-only 或 reject
        是
                 |
                 v
    回到 capture-time state，形成 geometry candidates
                 |
                 v
    Q3: 坐标残差和 covariance 允许吗？
        否 -> reject
        是 -> 不确定性越大，位置更新权威越低
                 |
                 v
    Q4: identity similarity >= threshold 吗？
        否 -> reject，避免“近但不是同一个人”
        是
                 |
                 v
    bounded update + replay to current state
                 |
                 v
    只影响尚未发布的当前/未来决策
```

这个流程中的四个维度各司其职：

```text
timestamp   : 这条消息属于什么时候？
fixed lag   : 系统还允许回头多远？
geometry + covariance: 位置是否合理，应该有多大更新权？
identity    : 它是不是这个人，而不只是离这个人近？
```

## 5. 证据链，而不是算法宣传词

| 实验转折 | 关键结果 | 它改变了什么认识 |
| --- | --- | --- |
| M3OT broad Backfill | IDF1 `0.5566`，低于 Drop `0.6556` | Backfill 不是天然正确的最终方法 |
| MATRIX arrival vs timestamped | 2 帧 arrival-time 开始稳定有害；理想 timestamped 可保持正确 | 时间归属是必要信息 |
| Causal occlusion audit | 500 ms 接近上界，1000 ms 明显下跌 | 在线 publish 约束形成早期帧缺口 |
| Fixed-lag re-anchoring | 1000/1500 ms 明显优于 drop；复杂 state-aware 首版只打平 | 固定短窗口已是强而简单的机制 |
| Useful-window audit | eligible bucket 的 survival delta spread 为 `0.382940` | `delay <= lag` 不能单独预测收益 |
| Spatial-noise audit | 0.10m 仍有益，0.25m survival delta 转负 | 时间正确仍不够，位置也必须可靠 |
| Simulated identity ablation | covariance + identity 在 0.25m 下恢复正收益并降低 IDSW | 身份维度能补几何边界 |
| Cue-quality boundary | 通过/失败 margin 区间为 `(0.040019, 0.056747]` | “用了 ReID”不够，必须量化线索质量和阈值 |

## 6. 哪些词暂时不要放在主线中心

下面这些词仍可保留在完整词典中，但不应主导当前 idea 介绍：

```text
Broad Backfill:
  是已被 M3OT 实验否定的早期假设，不是当前默认方法。

Fuse-at-current + Exp Decay:
  是早期必要基线，用来证明简单衰减可能胜过 broad Backfill；
  它不是当前 MATRIX 遮挡主线。

Risk-aware v1 / v2a / v2b / v2c:
  是几何门控演化史。Stage A 已作为 harm boundary 关闭，
  适合解释为什么要加入 identity，不适合包装成当前最终算法。

Tracker-State-Aware Re-anchoring:
  第一版只与最佳 fixed-lag 打平。可作为后续扩展，
  目前没有证据取代更简单的 fixed-lag baseline。

Online Policy Learning:
  当前 episode-level online proxy 增量太弱，尚不足以支撑复杂策略学习。
```

## 7. 当前可以说与不可以说的结论

可以说：

```text
1. 异步 support 的身份信息是有价值的，但价值受在线到达时机限制。
2. 有界 fixed-lag capture-time update 是当前最强且简单的时间缓解机制。
3. delay <= lag 只决定资格；有效窗口和空间噪声共同决定是否有益。
4. covariance-only 不足以解决身份歧义；身份线索可补 0.25m 几何噪声边界。
5. 身份线索存在可测质量边界，且阈值应在几何候选内校准。
6. 真实 embedding runner 已实现，但 smoke/formal 尚未运行，不能提前宣称迁移成功。
```

不可以说：

```text
1. Backfill 普遍优于丢弃迟到消息。
2. 只要按时间戳回放，所有延迟消息都会有益。
3. `(0.040019, 0.056747]` 是适用于所有 ReID 模型和数据集的通用常数。
4. 当前模拟 embedding 已证明真实跨无人机 appearance 一定可用。
5. 当前已有必要性去设计完整自适应通信或 policy-learning 系统。
```

## 8. 适合论文开场的生活化表述

```text
多无人机协同跟踪像多人接力看守同一批行人：主无人机被建筑遮挡时，
其他无人机的消息能帮它接住身份；问题是这些消息常常迟到。

迟到消息不能直接当成当前位置，也不能因为带了时间戳就无条件写回历史。
我们目前发现，系统需要把消息放回一个有限的历史窗口，同时检查三件事：
它是否还来得及影响后续跟踪、它报告的位置有多可信、它看到的是否真是同一个人。

实验因此把问题从“要不要回填旧消息”，逐步收敛成：
在多大的时间窗口、空间误差和身份线索质量下，迟到观测仍能安全地维持身份连续性？
```

## 9. 继续阅读

建议按下面顺序看已有图解：

1. [时间轴和符号](01_time_axis_and_symbols.md)
2. [四种融合方式](02_fusion_timing_modes.md)
3. [遮挡、rho 和消息及时性](03_occlusion_rho_and_delay.md)
4. [成对反事实测量](04_paired_counterfactual.md)
5. [为什么同一 rho 桶内绝对 delay 仍然重要](05_same_rho_different_delay.md)
6. [时间边界模型](06_temporal_boundary_model.md)
7. 完整定义和交叉引用见 [`GLOSSARY.md`](../GLOSSARY.md)

对应的下一轮实验卡是
[`exp_20260731_002_matrix_real_embedding_quality_transfer`](../summary_md/experiments/2026-7-31/exp_20260731_002_matrix_real_embedding_quality_transfer.md)：
实现已经完成，当前等待手工 CUDA smoke 和 `0-999` formal。
