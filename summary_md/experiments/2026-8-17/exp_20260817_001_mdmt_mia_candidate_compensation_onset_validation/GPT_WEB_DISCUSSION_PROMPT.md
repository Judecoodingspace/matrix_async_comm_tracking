# GPT Web Discussion Prompt — Frozen 15-Pair Development Result

Copy the block below directly into GPT Web.  It is a compact, self-contained
discussion context, not a request to run code or alter the frozen protocol.

```text
你是一位严格的多目标跟踪 / 异步协同跟踪审稿人。请审查下面这份已经完成的
development-stage 科学分析，并给出“结论是否被证据支持、表述应如何收紧、holdout
前还需要预先冻结哪些分析规则”的建议。请不要建议事后改 threshold、删 pair、增删 delay、
更换 bootstrap，或根据 development 结果重写 protocol。

研究问题
========
我们研究 MDMT 双视角异步 MIA 跟踪中：ID-state 延迟是否会损害 cross-view MDA，以及由
delay-only candidate 触发的及时 Supplement 是否能产生可测的补偿。当前是非测试 train
development cohort；评估协议是独立定义的
MDMT_SOURCE_ANNOTATION_MDA_V1，不等同于 official-test GT/export。

设计与冻结规则
==============
- cohort：15 个预冻结 train development pairs：
  [53,66,30,74,76,63,39,78,44,32,58,23,65,42,54]
- delays：d1,d2,d3,d4,d5；每 pair 17 个条件，共 255/255 accepted。
- Y01 是预测工件 parity 已验证的 singleton physical Y01_d1，按冻结定义复用于各正 delay。
- 对每个 delay、以 pair 为统计单位：
  D_ID(d)   = Y00 - Y10_d
  R_edge(d) = Yec_d - Y10_d
  C_comp(d) = (Y10_d - Y11_d) - (Y00 - Y01)
- 95% CI：pair bootstrap，10,000 resamples，numpy default_rng(7)。
- 通过规则：
  A: R_edge CI upper < 0
  B: C_comp CI lower > 0
  C: >=10/15 pairs R_edge < 0
  D: >=10/15 pairs C_comp > 0
  E: 完整机制路径被观测到
  F: 完整路径出现在 >=10/15 pairs
- onset 定义为按 d1→d5 升序第一个通过 A--F 的 delay。

测量有效性边界
==============
- 255/255 attempts accepted；每个 attempt 的 runtime guards、Source-MDA real prediction path
  和 output integrity 已复核。
- Y00 与同 pair legacy synchronous reference 的双视角 prediction JSON 均严格 byte-identical。
- 没有删除 pair、没有事后加入 delay、没有修改 gate/threshold/bootstrap/Source-MDA。
- 10 train holdout pairs 和所有 val pairs 未运行、未读取；本次不宣称 official-export equivalence。

结果（mean [pair-bootstrap 95% CI]；方向 pair 数）
===================================================
D_ID：
d1 0.038865 [0.013510, 0.068979]，13+/2-/0
d2 0.043049 [0.014019, 0.077351]，13+/2-/0
d3 0.115834 [0.073748, 0.161281]，15+/0-/0
d4 0.072246 [0.041204, 0.108280]，14+/1-/0
d5 0.064563 [0.036649, 0.095340]，14+/1-/0

R_edge：
d1 -0.002876 [-0.007376, -0.000351]，12-/0+/3= 
d2 -0.007222 [-0.017674, -0.000056]，12-/2+/1=
d3 -0.014530 [-0.034537, -0.001371]，13-/1+/1=
d4 -0.021710 [-0.041631, -0.005933]，12-/2+/1=
d5 -0.011313 [-0.024810, +0.000285]，12-/2+/1=  （仅 Gate A 失败）

C_comp：
d1 +0.025731 [+0.001577, +0.057355]，10+/4-/1=
d2 +0.033549 [+0.008272, +0.066311]，12+/2-/1=
d3 +0.061353 [+0.029050, +0.098691]，14+/1-/0
d4 +0.050662 [+0.021138, +0.086038]，13+/2-/0
d5 +0.041479 [+0.017755, +0.067870]，14+/1-/0

机制可观测性
============
完整路径定义为：delayed ID -> delay-only candidate (S_delay=1,S_cf=0) -> 同帧 timely
Supplement consumption -> actual High-score bbox write-in。
该完整路径在 d1--d5 的所有 15/15 pairs 都出现；pooled complete-path event counts 分别为：
d1=471，d2=1,675，d3=4,545，d4=2,440，d5=1,911。

冻结的 development 结论
========================
- d1--d4 通过 A--F；d5 只因 R_edge CI 上界略越过 0 而失败 A。
- 因此 earliest reliable onset 按预注册升序规则锁定为 d1。
- 结论类别：DEVELOPMENT_FULL_REPLICATION；下一步仅能是单独授权的 locked d1 holdout confirmation。
- 重要限制：d1 的中位 R_edge=-0.000245、C_comp=+0.000395，且效应异质性明显：Pair74 约占
  d1 |R_edge| 总量的 75.9%，Pair39 约占 d1 |C_comp| 总量的 47.0%。这些 pair 没有被删除。
- 这不是单调 delay-response claim，也不证明 deployable policy、官方 GT 等价或因果机制已最终定论。

请按以下结构回答：
1. 证据最强、可安全写入论文的 3--5 条 claim；
2. 必须明确降级或避免的 claim；
3. 对 d1 onset 选择与 d5 failure 的统计解释是否严谨；
4. 异质性（Pair74 / Pair39）最可能对可解释性造成什么风险；
5. holdout 前应锁定的最小分析计划（只提出预先指定的检查，不重开 development 决策）；
6. 以苛刻 reviewer 视角给出最多 5 条主要质疑及可用回应。

请区分 FACT、INFERENCE、UNKNOWN；不要把 Source-MDA-v1 称为 official GT，也不要把
development result 当作 holdout confirmation。
```

## Evidence links

- Scientific analysis: `FROZEN_15_PAIR_DEVELOPMENT_SCIENTIFIC_ANALYSIS.md`
- Measurement-validity audit: `POST_DEVELOPMENT_EXECUTION_MEASUREMENT_VALIDITY_AUDIT.md`
- Analysis implementation: `scripts/analyze_mdmt_mia_onset_development.py`
- Analysis manifest: `outputs/20260906_mdmt_mia_frozen_15_pair_development_analysis_v1/DEVELOPMENT_ANALYSIS_MANIFEST.json`
