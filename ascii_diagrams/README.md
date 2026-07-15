# ASCII 图解索引

这个目录专门存放用 ASCII 图解解释实验概念的 Markdown 文档。

目标不是替代实验报告，而是在从不同实验、路线图和论文之间切换时，快速恢复对核心机制的直觉理解。

## 当前阶段速记

```text
Stage A 几何门控        已关闭：作为 harm-boundary 结果保留
遮挡场景支撑价值        当前主线：D1 被遮挡时，support 是否真的维持身份
成对反事实测量          已通过 0-199 校准：测量有效，但边界欠定
下一步                  扩展到 0-999，判断 delay 与遮挡相对时机的联合边界
```

## 文档顺序

1. [时间轴和符号](01_time_axis_and_symbols.md)
2. [四种融合方式](02_fusion_timing_modes.md)
3. [遮挡、rho 和消息及时性](03_occlusion_rho_and_delay.md)
4. [成对反事实测量](04_paired_counterfactual.md)
5. [为什么同一 rho 桶内绝对 delay 仍然重要](05_same_rho_different_delay.md)

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
