# OPEN_RESEARCH_DECISIONS

## Status

G1-G15b and RD-1 through RD-6 are `HUMAN-FROZEN`. RD-1 to RD-6 are recorded in
full in `EXPERIMENT_CONTRACT.md` Section 7A and encoded by the immutable
estimator config. They are not open decisions and must not be reinterpreted as
implementation defaults.

## Resolved Human Decisions

| Decision | Status | Governing location |
| --- | --- | --- |
| RD-1 — Decode, preprocessing, and SIFT | `HUMAN-FROZEN` | Contract §7A; immutable config |
| RD-2 — Matcher and correspondence policy | `HUMAN-FROZEN` | Contract §7A; immutable config |
| RD-3 — RANSAC, H normalization, hard failures | `HUMAN-FROZEN` | Contract §7A; immutable config |
| RD-4 — Two independent directions and denominator | `HUMAN-FROZEN` | Contract §7A; immutable config |
| RD-5 — 5x5 projection diagnostic construction | `HUMAN-FROZEN` | Contract §7A; immutable config |
| RD-6 — Determinism and repeat acceptance | `HUMAN-FROZEN` | Contract §7A; immutable config |

## RD-7 — G15c Geometry-Validity Gate

- Decision needed: final minimal validity rules for RANSAC consensus,
  reprojection/numerical consistency, and image-level projection plausibility.
- Required by: after an assertion-valid M5 raw ledger, before formal Pair-26/48
  geometry validation.
- Allowed evidence: immutable five-pair development-set geometry diagnostics
  only, used to identify clearly unreliable or degenerate regimes.
- Forbidden evidence: desired coverage, Pair 26/48, val, target/GT/tracker/
  candidate data, or Route-A outcomes.
- Current answer: `NEEDS_RESEARCH_DECISION_AFTER_M5`.

The following remain explicitly unfrozen: minimum inlier count/ratio,
acceptable reprojection error, rank/determinant/condition-number rules,
projection finite/inside/area/orientation rules, and cycle-consistency validity
thresholds.

## RD-8 — Later Pair-Level Geometry Readiness Rule

- Decision needed: how G15c-valid, full-denominator frame-direction evidence
  becomes a pair-level geometry readiness/coverage judgment for formal Pair
  26/48 validation.
- Required by: after G15c and before interpreting Pair-26/48 geometry coverage.
- Allowed evidence: a rule frozen before Pair-26/48 outcomes are viewed.
- Forbidden evidence: tuning to Pair-26/48 results or using candidate/tracking
  outcomes as geometry validity.
- Current answer: `NEEDS_RESEARCH_DECISION_BEFORE_FORMAL_INTERPRETATION`.

## Decision Boundary

```text
M0/M1: RD-1 to RD-6 already frozen
M2-M5: run unchanged estimator; do not create threshold-valid labels
After M5: human RD-7 / G15c
Before formal interpretation: human RD-8
```

No item in this file authorizes Pair-26/48 execution, Route-A MVE-1, tracker
changes, a learned/temporal geometry method, or a change to the frozen
five-pair manifest.
