# exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation

## Purpose

在不读取 official test 结果进行调参的前提下，验证 E023 的 d5 候选集合补偿是否能在
MDMT 非测试序列复现，并定位 d1-d5 内的出现区间。

## Hypothesis

ID-state delay 增加会先扩大 `S_delay` 与 `S_cf` 的差异；当 delay-only candidates
能够形成足够的 High-score Supplement write-in 时，`R_edge` 转为负、`C_comp`
转为正。替代解释是 E023 d5 仅为 test cohort 异质性。

## Setup

- Data: MDMT train/val; approved frozen policy is 15 train development, 10
  train holdout and 5 separately reported MDMT val holdout pairs.
- Detector: paper-aligned CARAFE, frozen `epoch_12.pth`.
- Tracker: ByteTrack + active packetized MIA.
- Delays: ID state `1,2,3,4,5` frames; select the earliest delay passing the
  frozen Gate A-F onset rule.
- Local Track/Homography: timely.
- Supplement: timely or existing nonzero-delay expiry.
- Seed: `7`.
- Primary metric: MDA.
- Secondary: MOTA, IDF1, IDSW and R5d process traces.

## Output

```text
outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/
```

## Current Decision

`RESEARCH_DECISIONS_RESOLVED / CONTRACT_AMENDED /
BLOCKED_PENDING_GT_PROTOCOL_GATE`

- R1: `APPROVED / RESOLVED_CONDITIONAL`.
- R2: `APPROVED / RESOLVED`.
- R3: `APPROVED / RESOLVED_WITH_CONTRACT_AMENDMENT`.
- Amendment: actual delay-only candidate -> High-score Supplement write-in must
  occur in at least `10/15` development pairs.
- Implementation and MVE are not yet authorized.

## Flowchart

`mermaid/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/onset_validation_flow.mmd`
