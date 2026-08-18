# DECISION

Status: `RESEARCH_DECISIONS_RECORDED / SCIENTIFIC_DECISION_PENDING`

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

## Remaining Gate

Research-decision blocking is cleared, but the experiment is not implementation-
ready or Formal-ready. The next gate is the conditional R1 GT protocol gate:
exact official-test reproduction followed by non-test structural and cross-view
identity-semantics validation. Implementation and MVE remain unauthorized until
that lifecycle gate is completed and audited.

## Final Decision

Not available. Select one only after holdout confirmation:

```text
measurement_invalid
test_specific_or_not_replicated
delay_conditioned_but_onset_unresolved
mechanism_heterogeneous_across_splits
compensation_onset_validated
```
