# DECISION — M2–M5 Reproducibility Stop

## Decision

`STOP_FOR_HUMAN_REPRODUCIBILITY_DECISION`

The M2–M5 raw diagnostic ledger reached its full frozen denominator, but the
predeclared exact-repeat acceptance criterion failed. Under RD-6, the current
provider/configuration is not accepted as reproducible M4/M5 evidence.

## Consequences

- Do not use this ledger to freeze G15c thresholds.
- Do not run Pair 26/48, val, or Route-A MVE-1 from this result.
- Do not tune the ratio test, RANSAC, support, projection, or threshold values.
- Do not silently replace exact repeat with a weaker criterion.

## Required next research decision

Human review must decide whether the observed mismatch is classified as an
implementation defect or environment-level nondeterminism, and—only if a new
decision is approved—define a new reproducibility protocol/configuration under
a new experiment stage or decision version. The current raw ledger remains
diagnostic-only pending that decision.
