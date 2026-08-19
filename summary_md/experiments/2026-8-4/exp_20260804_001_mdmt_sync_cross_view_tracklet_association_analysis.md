# exp_20260804_001 Analysis Template

> 状态：代码和测试完成，等待完整 val Pilot。不得用 Oracle 结果代替真实 OSNet 结论。

## 1. 假设对照

- H0 Oracle 同步性能空间：待填。
- H1 候选约束的 precision/recall：待填。
- H2 tracklet 外观记忆价值：待填。
- H3 真实同步 tracking transfer：待填。

## 2. 基线比较

比较 `primary_only`、`primary_reid_stitching`、Oracle、latest、cumulative 和选中配置。

## 3. 失败模式

按方向、候选策略、聚合方式、gap length 和 support coverage 分析。

## 4. 上限分析

先检查 Oracle 是否超过 best primary baseline；Oracle 失败时不解释 embedding 优劣。

## 5. 泛化信号

报告单向量通信约束下，候选约束和接收端状态量各自的贡献。

## 6. 与历史对照

连接上一轮 latest 近零 recall、cumulative precision `0.014642` 和本轮 reject-all 修复。

## 7. 下一步建议

明确是否允许 official-test Formal、恢复 delay sweep或进入跨相机 ReID 微调。

## Flowchart

参考：`mermaid/exp_20260804_001_mdmt_sync_cross_view_tracklet_association/sync_feasibility_flow.mmd`。

