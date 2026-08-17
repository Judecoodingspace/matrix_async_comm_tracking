# exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation

## Purpose

在不读取 official test 结果进行调参的前提下，验证 E023 的 d5 候选集合补偿是否能在
MDMT 非测试序列复现，并定位 d1-d5 内的出现区间。

## Hypothesis

ID-state delay 增加会先扩大 `S_delay` 与 `S_cf` 的差异；当 delay-only candidates
能够形成足够的 High-score Supplement write-in 时，`R_edge` 转为负、`C_comp`
转为正。替代解释是 E023 d5 仅为 test cohort 异质性。

## Setup

- Data: MDMT train/val, split policy pending R1/R2 approval.
- Detector: paper-aligned CARAFE, frozen `epoch_12.pth`.
- Tracker: ByteTrack + active packetized MIA.
- Delays: ID state `1,2,3,4,5` frames; pending R3 approval.
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

`PROPOSED / BLOCKED_PENDING_R1_R2_R3`

## Flowchart

`mermaid/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/onset_validation_flow.mmd`

