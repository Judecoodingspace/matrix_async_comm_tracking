# exp_20260803_002 Analysis Template

> 状态：等待完整 val Pilot 与 official test Formal。本文件不得用 smoke 的单序列结果替代正式结论。

## 1. 假设对照

- H1 同步 support headroom：待填。
- H2 capture-time 时间戳价值：待填。
- H3 增量 tracklet 相对单帧消息价值：待填。
- H4 fixed-lag 与 late recovery 部署机制：待填。

## 2. 基线比较

待从 `global_pipeline_metrics.csv`、`global_fusion_contrasts.csv` 和
`official_person_aas.csv` 填写。

## 3. 失败模式

按 direction、delay、gap length、support coverage 和类别一致性子集分析。

## 4. 上限分析

先检查 delay=0 的 `incremental_tracklet_timestamped` 是否超过
`primary_reid_stitching`；若无同步性能空间，不解释异步方法优劣。

## 5. 泛化信号

比较双向结果、strict person 与 frame-consistent person 子集，并报告 MDMT 无可靠 FPS
导致的 frame-delay 外推限制。

## 6. 与历史对照

连接 MATRIX observation-level harm boundary、MDMT local readiness，以及本轮
history=1 与 history>1 的信息单位变化。

## 7. 下一步建议

按 P0/P1/P2 填写，并明确是否允许进入 detector robustness 或通信字节预算消融。

## Flowchart

参考：`mermaid/exp_20260803_002_mdmt_async_incremental_tracklet_fusion/fusion_flow.mmd`。
