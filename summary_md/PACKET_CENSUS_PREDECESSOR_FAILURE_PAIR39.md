# Packet Census predecessor failure — Pair 39

## Status

`PREDECESSOR_FORMAL_PACKET_CENSUS_INCOMPLETE`  
`PREDECESSOR_FORMAL_PACKET_CENSUS_INVALIDATED`

The predecessor formal run is historical only and must not contribute any
accepted artifacts to a successor aggregate.

## Frozen predecessor identity

- Execution baseline: `0e2880f1cd860ac1134dcbacb5f2fb94a2d1dda0`
- Formal output root: `outputs/packet_census_z0_train_all_3a071174_prediction_path_repair_78a05da/`
- Condition: Z0; population: the frozen 25-pair / 12,026-frame cohort.
- Previously completed pairs: `23, 25, 27, 28, 29, 30, 32`.

## FACT

- Pair 39 attempt 001 failed during an author run at frame 175 of 400 with
  `AttributeError: 'int' object has no attribute 'reshape'`.
- The call path was `supplement_MIA.py` →
  `supp_compute_transf_matrix(...)` in `demo/utils/trans_matrix.py`.
- In the low-local-match branch, `matching_pure.compute_matrics` returns the
  scalar sentinel `M = 0` when fewer than ten SIFT matches are available.
- The fallback then unconditionally calls `M.reshape(...)`, which is invalid
  for that scalar sentinel.

## INFERENCE

This is a caller-side homography-fallback type defect:
`PAIR39_AUTHOR_HOMOGRAPHY_FALLBACK_TYPE_DEFECT`.  Defining behavior for an
invalid current geometry candidate changes fallback semantics, so the failed
run cannot be retried in place.  A separately frozen successor is required.

## UNKNOWN

The upstream author documentation does not establish intended semantics for
the scalar no-match sentinel or for absent historical homography state.
No claim about geometry, tracking, communication, or workload behavior is
made by this report.

