# Glossary

Canonical project glossary: [GLOSSARY.md](GLOSSARY.md)

This lowercase file exists so references to `glossary.md` still land on the
project terminology. The full living glossary is maintained in `GLOSSARY.md`.

## 异步位姿通信实验术语澄清

### 1. "不携带 capture-time / capture-pose 信息"是什么意思？

这不是说 UAV 之间没有传世界坐标，而是说融合端没有把世界坐标和"它属于哪一时刻、哪一相机位姿"绑定使用。

错误用法：

```text
第 10 帧 D2 观测到 person 7 的 world_xyz
消息第 15 帧才到
融合端把这条第 10 帧观测直接和第 15 帧轨迹状态匹配
```

正确用法：

```text
第 10 帧 D2 观测到 person 7 的 world_xyz
消息第 15 帧才到
融合端知道 capture_time=10，并用第 10 帧的世界状态/位姿语境做关联
```

位姿/世界坐标信息解决"空间在哪里"，`capture_time` 解决"这个空间信息属于什么时候"。异步通信实验要同时关注这两者。

### 2. 三种方法的区别

| 方法 | 延迟观测怎么处理 | 直觉 | 当前实验结果 |
| --- | --- | --- | --- |
| `timestamped_pose_fusion` | 按 `capture_time` / 捕获时刻位姿对齐后融合 | 迟到照片插回正确页 | IDF1 `1.000000`, IDSW `0` |
| `arrival_time_fusion` | 到达后直接按当前帧状态融合 | 迟到照片当成刚拍的 | 延迟 3 帧后明显崩溃 |
| `drop_delayed` | 延迟的辅助 UAV 观测不用 | 过期消息直接丢掉 | 非零延迟下等同 D1-only |

### 3. `fixed_1`、`fixed_3`、`uniform_1_10` 是什么？

它们是 delay profile：

- `fixed_1`：辅助 UAV 观测固定晚 1 帧到达。
- `fixed_3`：辅助 UAV 观测固定晚 3 帧到达。
- `uniform_1_10`：每条辅助 UAV 观测随机晚 1 到 10 帧到达。

主 UAV D1 在当前实验中不加延迟，作为主轨迹来源。

### 4. `arrival_time_exp_decay` 和 `arrival_time_fusion` 的区别

理论区别：

- `arrival_time_fusion`：延迟观测到达后直接按当前时刻融合，权重不变。
- `arrival_time_exp_decay`：仍然在到达时刻融合，但延迟越大，观测权重越小。典型形式是 `weight = exp(-λ * delay)`。

当前实验局限：

`exp_20260622_001_matrix_async_pose_gt` 的 GT prototype 还没有把这个权重真正用于轨迹状态更新，所以 `arrival_time_exp_decay` 只是记录了 baseline 名字，数值结果与 `arrival_time_fusion` 一致。下一步要么实现加权状态更新，要么从下一张表里移除这个占位 baseline。

### 5. 为什么必须使用 `capture_time / capture_pose`？

多目标跟踪的核心不是"有没有一个近似位置"，而是"这个位置应该更新哪一条身份轨迹"。

当人群移动或交叉时，第 10 帧 person A 的位置，到了第 15 帧可能已经被 person B 占据。如果第 10 帧观测在第 15 帧才到，并且直接按第 15 帧状态关联，它就可能把 A 的信息更新到 B 的轨迹上，造成 ID switch。此时这条支持观测不是帮助系统，而是在污染系统。

当前实验结果体现了这一点：

- `drop_delayed`：IDF1 `0.846000`，IDSW `251`
- `arrival_time_fusion fixed_3`：IDF1 `0.372500`，IDSW `480`
- `arrival_time_fusion uniform_1_10`：IDF1 `0.162000`，IDSW `870`
- `timestamped_pose_fusion`：IDF1 `1.000000`，IDSW `0`

结论：延迟跨无人机观测只有在携带并使用 capture-time / capture-pose 语境时才是可靠支持信息；否则它可能比不用更危险。
