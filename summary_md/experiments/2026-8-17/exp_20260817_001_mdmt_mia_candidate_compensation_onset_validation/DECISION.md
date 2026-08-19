# DECISION

Status: `GT_PROTOCOL_GATE_FAIL / SCIENTIFIC_DECISION_PENDING`

## Current Planning Decision

The minimum discriminating next experiment is non-test compensation-onset
validation. Direct implementation of version-aware recovery is deferred.

## Resolved Research Decisions

| ID | Final status | Decision and rationale |
| --- | --- | --- |
| R1 | `APPROVED / RESOLVED_CONDITIONAL` | Non-test MDA GT may be constructed mechanically from authoritative raw annotations only after exact official-test row/frame/ID reproduction and separate non-test integrity and identity-semantics gates. The converter has no semantic repair authority. |
| R2 | `APPROVED / RESOLVED` | Freeze 15 train development and 10 train holdout pairs from canonical pair ordering with a fixed algorithm and seed 7 before reading outcomes; separately retain all 5 val pairs as cross-MDMT-split robustness evidence. |
| R3 | `APPROVED / RESOLVED_WITH_CONTRACT_AMENDMENT` | Freeze d1-d5 and select the earliest delay passing all onset gates; do not optimize compensation magnitude or revisit the delay after holdout. |

## Contract Amendment

The mechanism gate is strengthened from pooled nonzero High-score write-in to:

```text
actual delay-only candidate -> timely Supplement consumption
-> High-score Supplement bbox write-in
in at least 10/15 development pairs
```

Mechanism recurrence does not replace the causal MDA contrasts `R_edge` and
`C_comp`.

## GT Protocol Gate Execution (2026-08-19)

G1 passed, but G2 failed strict official-test equivalence: only 5 of 28 files
matched; the mechanically derived source rows contained 347 extra rows and the
official test sources contain no `outside=1` witness. Therefore G3-G6 were not
run and G7 is `GT_PROTOCOL_GATE_FAIL`. This is fail-closed: no non-test GT,
MIA/tracking run, MVE, development selection, holdout, Formal, or recovery
implementation is authorized.

See `GT_PROTOCOL_GATE_REPORT.md` and `GT_PROTOCOL_GATE_ARTIFACT_SCHEMA.md`.

## Remaining Gate

Research-decision blocking is cleared, but the failed conditional R1 GT protocol
gate blocks implementation and MVE. The only admissible next work is a new,
approved source-annotation/export protocol investigation; it must resolve the
347 extra rows and the missing outside-rule witness before the lifecycle gate
can be restarted.

## Final Decision

Not available. Select one only after holdout confirmation:

```text
measurement_invalid
test_specific_or_not_replicated
delay_conditioned_but_onset_unresolved
mechanism_heterogeneous_across_splits
compensation_onset_validated
```
