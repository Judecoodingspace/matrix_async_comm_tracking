# M4–M5 Execution Status

## Current status

`RD-R1_REPAIR_VALIDATED / REPRODUCIBILITY_ACCEPTED_RAW_GEOMETRY_LEDGER / STOP_BEFORE_G15C`

## Previous attempt

- Status: `QUARANTINED_DIAGNOSTIC_ONLY`.
- Reason: `IMPLEMENTATION_CONTRACT_VIOLATION` — the only RNG reset occurred
  after SIFT/FLANN/correspondence filtering instead of at directional-call
  start.
- Provider digest: `34c0500b267e9d2eee00714a71f73a6451c3394878377a8cdbee30d434080723`.
- Old repeat verdict: `REPRODUCIBILITY_ACCEPTANCE_FAIL`.
- G15c admissible: `NO`.
- Merged with corrected ledger: `NO`.

## Corrected isolated attempt

- Attempt: `attempt_02_rng_placement_corrected`.
- New provider digest: `b8b65b881cc1627ff2e5f41f885f36473ebadf59f5e3f076240c9de1eee99a7d`.
- Same manifest digest and estimator config digest as the prior attempt.
- Full denominator: `5,460`; unique rows: `5,460`.
- Directions: `1_to_2=2,730`, `2_to_1=2,730`.
- Recorded firewall audit: `PASS` (zero forbidden-scope image paths).
- Frozen repeat: Pair 25, first ten lexical frames, both directions;
  `20` units, `mismatch_count=0`, `REPRODUCIBILITY_ACCEPTANCE_PASS`.

## Stop boundary

The corrected ledger is accepted as raw diagnostic evidence only. G15c,
Pair 26/48, val, Route-A MVE-1, parameter tuning, matcher replacement, and
tolerance relaxation were not performed.
