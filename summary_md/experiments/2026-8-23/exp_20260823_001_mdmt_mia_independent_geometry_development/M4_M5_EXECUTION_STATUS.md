# M4–M5 Execution Status

## Status

`STOPPED_REPRODUCIBILITY_ACCEPTANCE_FAIL`

This is not a geometry-quality or Route-A result.  No G15c threshold was
proposed, frozen, or applied; Pair 26/48, val, and Route-A MVE-1 remain
unexecuted.

## Completed raw-ledger checks

- The authorized-run ledger contains exactly `5,460` unique
  `(pair_id, frame_name, direction)` records: Pair 45=`800`, Pair 29=`1400`,
  Pair 51=`860`, Pair 69=`1400`, Pair 25=`1000`.
- Direction counts are `2,730` for `1_to_2` and `2,730` for `2_to_1`.
- Every record has `NOT_EVALUATED_PENDING_G15C`; one manifest digest, one
  config digest, and one provider-code digest are present.
- All record digests validate.  All recorded image paths remain under the
  frozen train-pair scope; the ledger has zero paths containing val, test, GT,
  XML, Pair 26, or Pair 48 components.

## Reproducibility stop

The frozen repeat subset is Pair 25, frames `00000001.jpg` through
`00000010.jpg`, both directions.  Its comparison verdict was
`REPRODUCIBILITY_ACCEPTANCE_FAIL` with one mismatch:

```text
pair=25, frame=00000001.jpg, direction=1_to_2
fields=num_tentative_matches, num_unique_matches, num_ransac_inliers,
selected_correspondence_digest, ransac_inlier_mask_digest, H_matrix,
inlier_ratio, reprojection_error_mean, reprojection_error_median,
reprojection_error_p95
```

Per RD-6, this mismatch requires stopping without parameter tuning or a
threshold decision.  The raw ledger is retained as a diagnostic artifact only,
not as a reproducibility-accepted M4/M5 evidence package.

## Execution-isolation note

An earlier tool-launched process continued after its initiating window ended.
Its complete same-config output was isolated under `attempts/`; it is not
merged with the authorized-run ledger above.  Stale summaries produced by that
process were also isolated before the final reproducibility check.

## Next required action

Human review of the reproducibility failure and a separate authorization are
required before any rerun or estimator/environment change.
