# GPT Web Prompt: Next GT Protocol Investigation Gate

请直接使用以下提示词与 GPT 网页版讨论。讨论必须采用逐题问答方式，不要一次性给出完整方案。

---

你现在继续处理实验：

```text
exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation
```

GitHub 上下文：

```text
Repository: Judecoodingspace/matrix_async_comm_tracking
Branch: exp/20260803-002-mdmt-async-tracklet-fusion
Primary issue: https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/26
Primary PR to main: https://github.com/Judecoodingspace/matrix_async_comm_tracking/pull/25
Legacy stacked PR (background only): https://github.com/Judecoodingspace/matrix_async_comm_tracking/pull/22
```

开始讨论前，请读取该 branch 上的以下文件：

```text
AGENTS.md
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/EXEC_PLAN.md
summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/GT_PROTOCOL_GATE_ARTIFACT_SCHEMA.md
summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/GT_PROTOCOL_GATE_REPORT.md
summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/DECISION.md
scripts/prepare_mdmt_non_test_mda_gt.py
src/datasets/mdmt_mda_gt_protocol.py
tests/test_mdmt_non_test_mda_gt_protocol.py
```

## 已冻结的本轮事实

```text
G1 = PASS
- 88/88 XML 严格解析通过
- train/val/test XML 文件数 = 50/10/28
- parser issue = 0

G2 = FAIL
- official test 文件 = 28
- 精确匹配 = 5/28
- 不匹配 = 23/28
- official rows = 600,923
- source-derived rows = 601,270
- missing rows = 0
- extra rows = 347
- duplicate identity keys = 0
- 全部 88 个 XML 中 outside=1 box 数 = 0
- official-test eligible occluded box 数 = 158,301
- outside rule 无正样本见证

G3-G5 = NOT RUN / BLOCKED_BY_UNKNOWN
G6 = NOT RUN / BLOCKED_BY_UNKNOWN
G7 = GT_PROTOCOL_GATE_FAIL
```

边界条件：

```text
- 本轮没有运行 tracking、MIA 或 MVE。
- 不得根据 prediction、tracking 或 MVE outcome 修改 GT 转换规则。
- 不得直接继续 train/val GT、two-pair MVE、development、holdout、Formal 或 recovery。
- 347 行差异目前只能记为 observed extra rows，不能先验归因为 bbox 边界、类别、outside、插值或导出 bug。
- G2 记录的 converter SHA256 与 G7 最终 provenance 中的 converter SHA256 不同；protocol module 和 mapping-policy hash 一致。
- run B 只有空 generation record，没有生成文件和 G6 determinism report。
- Issue #26 原始正文描述的是执行前状态；应以 branch 最新 Gate report 和 Issue/PR 的最新结果更新为准。
```

## 本次讨论目标

只设计下一道“source annotation/export protocol investigation gate”，用于解释并验证官方 GT 与 XML 机械转换之间的 347 行差异，以及 outside 规则缺少正样本见证的问题。

本次讨论不设计 compensation-onset tracking 实验，不实现修复，也不授权 MVE。

需要逐项解决以下决策：

```text
D1. 哪些独立材料可以作为 official export/filter semantics 的权威证据？
D2. 如何在不读取 tracking outcome 的情况下，对 347 行 extra rows 做穷尽、可复核、非修复式分类？
D3. 如果全部自然 XML 都没有 outside=1，outside exclusion 规则应如何验证：官方导出器/规范证据、受控合成夹具，还是保持 UNKNOWN？
D4. converter hash 漂移和 run-B 空记录应如何进入新的 provenance/确定性硬门？
D5. 新 gate 的最小 PASS/FAIL/BLOCKED_BY_UNKNOWN 条件是什么？
D6. 若新 gate 通过，是否必须先单独重跑 G1-G2，并再次硬停止，再考虑 G3-G6？
```

## 强制问答协议

1. 必须逐题问答，一次只问一个决策问题，不得一次输出完整执行计划。
2. 每轮使用 `Q1`、`Q2` 等编号，并标明对应的 `D1-D6`。
3. 每个问题给出 2-3 个互斥选项、各自代价和你的推荐选项；同时允许我提供自定义答案。
4. 我回答后，先用一句话复述已冻结的答案，再继续下一题。
5. 每轮明确分开：`FACT`、`INFERENCE`、`UNKNOWN`、`PROPOSED DECISION`。
6. 不得把 347 行差异解释成已知机制；不得建议先跑 tracking/MVE 看结果。
7. 在我明确说“完成问答并生成计划”以前，不得输出最终 EXEC_PLAN、代码或运行命令。
8. 问答结束后，最终只输出：
   - 决策表；
   - 新 gate 的可证伪问题；
   - 输入证据与禁止证据；
   - 顺序 hard gates；
   - artifact schema；
   - PASS/FAIL/BLOCKED_BY_UNKNOWN 规则；
   - 明确仍未授权的 tracking/MVE 范围。

现在请先确认你已经读取 branch、Issue #26 和 PR #25 的最新内容，然后只提出 `Q1 / D1`：选择 official export/filter semantics 的权威证据链。不要提前回答 D2-D6。

---
