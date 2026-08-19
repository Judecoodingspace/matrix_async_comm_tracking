# ASCII 图解索引

这个目录专门存放用 ASCII 图解解释实验概念的 Markdown 文档。

目标不是替代实验报告，而是在从不同实验、路线图和论文之间切换时，快速恢复对核心机制的直觉理解。

## 当前阶段速记

```text
Stage A 几何门控        已关闭：作为 harm-boundary 结果保留
遮挡时间机制            fixed-lag 是当前最强简单机制；收益受 useful window 调节
时间-空间边界           0.10m support noise 仍有益，0.25m geometry-only 转为有害
身份维度                covariance + simulated identity 可补 0.25m 几何边界
最新质量边界            margin 离散区间 (0.040019, 0.056747]，依赖当前压力设置
当前结论                旧管线是 observation-to-track 机制，不是完整 MVMOT
下一步                  每架 UAV 独立维护并逐帧发送 incremental tracklet update
```

## 文档顺序

1. [时间轴和符号](01_time_axis_and_symbols.md)
2. [四种融合方式](02_fusion_timing_modes.md)
3. [遮挡、rho 和消息及时性](03_occlusion_rho_and_delay.md)
4. [成对反事实测量](04_paired_counterfactual.md)
5. [为什么同一 rho 桶内绝对 delay 仍然重要](05_same_rho_different_delay.md)
6. [时间边界模型](06_temporal_boundary_model.md)
7. [当前 Idea 逻辑主线](07_current_idea_mainline.md)
8. [OSNet 身份门控、外观模板与主视角重新关联](08_osnet_identity_gate_and_reacquisition.md)

## 通用符号

```text
f0, f1, f2       帧编号
0ms, 500ms       物理时间；MATRIX 2 FPS，所以 1 帧 = 500ms
P                primary UAV 的观测
S                support UAV 的观测
cap              capture time，观测产生的时刻
arr              arrival time，消息到达主 UAV 的时刻
pub              在线系统发布该帧结果
O                primary 被遮挡
x                primary 没有可用观测
```

## 读图原则

```text
capture time 决定消息属于哪个历史帧
arrival time 决定在线系统什么时候才知道这条消息
published output 一旦发布，在线系统默认不能回写
offline corrected 是上界，不代表在线可达到
```
