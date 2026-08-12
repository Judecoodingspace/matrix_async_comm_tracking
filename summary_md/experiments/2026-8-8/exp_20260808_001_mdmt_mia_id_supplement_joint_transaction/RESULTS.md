# RESULTS

Status: `NO EXPERIMENT RUN - V2 STATIC RE-AUDIT PASSED`

## Experiment ID

`exp_20260808_001_mdmt_mia_id_supplement_joint_transaction`

The filename is historical. ADR-20260809-R4 suspended the joint-transaction
hypothesis. The active experiment is the R5/R6 ID-delay candidate-membership
cascade mechanism audit.

## Implementation Provenance

- Base commit recorded by Contract: `09281aa`
- Implementation commit: `PENDING`
- Evaluation commit: `PENDING`
- Rejected source variant: `packetized_id_supplement_cascade` (v1)
- Current source variant: `packetized_id_supplement_cascade_v2`
- Variant manifest: `/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v2/cascade_edge_manifest.json`

## Static Verification

### OBSERVATION

- Focused cascade tests: passed.
- Full repository regression: passed; no existing test failure.
- Generated v2 source: structural audit passed for every registered boundary.
- Generated changed files: Python AST/compile checks passed.
- Generated file SHA256 values equal the v2 manifest.
- No MVE or Formal condition was executed.

### INTERPRETATION

The implementation is eligible for a separately authorized MVE. Static
verification is not evidence for or against the scientific hypothesis.

## Active Conditions

```text
Y00: ID timely  + Supplement timely + synchronous membership
Y10: ID delayed + Supplement timely + S_delay
Y01: ID timely  + Supplement expired
Y11: ID delayed + Supplement expired
Yec: ID delayed + Supplement timely + oracle S_cf membership only
```

Y10 and Yec both compute the same read-only shadow diagnostics. Only Yec may
consume `S_cf` as High-score membership. Low-score receives no oracle input.

## Mandatory MVE Gates

- Y00 equals the frozen synchronous reference JSON.
- One complete pre-branch capture/consume per non-initial frame.
- No missing, stale, double, wrong-frame or non-conserved snapshot.
- No runtime GT, future read, NumPy alias, feedback mismatch or published rewrite.
- Shadow export is membership-only and actual branch inputs remain unchanged.
- Y10/Yec 各自 run 内的 actual/shadow candidate 使用 pre-branch row key；状态分叉后禁止跨 run 复用该 key。
- Logging ON/OFF predictions and async state traces are byte-identical.
- Shadow ON/OFF Y10 predictions and async state traces are byte-identical.
- Packet emission equals packet consumption plus expiry.
- Resume fingerprint matches variant, conditions, pairs, seed and reference.

## Missing Evidence

- MVE measurement gate: `NOT RUN`
- MVE R5d process trace: `NOT RUN`
- MVE decision: `NOT RUN`
- Formal 14-pair metrics and bootstrap: `NOT RUN`
- Scientific decision: `PENDING`

Formal is code-gated by `--mve-evidence-dir` and cannot proceed from static
verification alone.
