# DECISION — RD-R1 RNG Placement Repair

## Decision

`RNG_PLACEMENT_REPAIR_VALIDATED`

`REPRODUCIBILITY_ACCEPTED`

`STOP_BEFORE_G15C`

The authorised correction moved the sole per-direction RNG reset to the start
of the image-only provider call. The new, full, isolated ledger passed the
unchanged 20-unit frozen repeat acceptance rule.

## Consequences

- The corrected ledger is accepted only as a reproducible raw geometry
  diagnostic ledger.
- No G15c threshold is frozen or evaluated.
- Pair 26/48, val, and Route-A MVE-1 remain unrun and unauthorized.
- No estimator parameter, matcher, tolerance, pair, denominator, or repeat
  protocol was changed.
- The old ledger remains quarantined diagnostic-only and is not admissible for
  G15c.

## Required next action

Stop for a separate human research decision on whether and how to enter G15c.
