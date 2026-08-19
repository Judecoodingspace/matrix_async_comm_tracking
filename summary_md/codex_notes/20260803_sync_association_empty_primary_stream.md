# exp_20260804_001 Pilot 中断诊断

## 现象

同步跨视角 Tracklet 关联 Pilot 在跟踪阶段报错：

```text
ValueError: min() arg is an empty sequence
```

位置是 `phase3_mdmt_sync_cross_view_tracklet_association.py` 对
`primary_packets` 计算起止帧。

## 根因

验证集序列 `49` 的 V1 XML 只包含 `bicycle` 和 `car`，person-only 过滤后有
0 条有效主视角检测；V2 仍有 1890 条 person 检测。因此方向 `V1->V2` 在该序列
没有可定义的 primary stream，不能计算 `min(primary_packets)`。

这不是 Oracle 关联失败，也不是 OSNet 阈值失败，而是空主流未被 CLI 显式处理。

## 已保存进度

- LOSO 校准检查点已经保存。
- 序列 `22、36、46` 的两方向、6 条 pipeline 已完成，共 36 个 tracking checkpoint。
- 还缺少序列 `49` 的有效方向 `V2->V1` 6 条条件，以及序列 `72` 两方向 12 条条件。
- `49: V1->V2` 的 6 条条件应记录为 `skipped_no_primary_person`，不应伪造指标。

## 重跑要求

需要先为 `primary_packets == []` 增加显式跳过和审计记录，再使用原 Pilot 命令加
`--resume`。校准和已完成的 36 条 tracking 条件可以复用，不需要从头计算。

在最终汇总前，报告两个方向各自的有效序列数，并禁止把空主流方向计入性能均值。
