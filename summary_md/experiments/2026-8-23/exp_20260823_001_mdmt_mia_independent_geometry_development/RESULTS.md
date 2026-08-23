# RESULTS — M2–M5 Raw Geometry Diagnostics

## Result status

`RAW_LEDGER_COMPLETE / REPRODUCIBILITY_ACCEPTANCE_FAIL / NOT_VALIDATED_FOR_M5_DECISION`

This result is limited to the frozen five-pair MDMT-train, image-only raw
diagnostic execution. It does not provide a geometry-validity threshold, Pair
26/48 validation, val result, or Route-A MVE result.

## Completed denominator and provenance

| Item | Result |
| --- | ---: |
| Frozen pair order | `45, 29, 51, 69, 25` |
| Frame-direction denominator | `5,460` |
| Unique ledger keys | `5,460` |
| `1_to_2` records | `2,730` |
| `2_to_1` records | `2,730` |
| Threshold status | `NOT_EVALUATED_PENDING_G15C` for every row |
| Manifest/config/provider digest cardinality | `1 / 1 / 1` |
| Invalid record digests | `0` |
| Recorded forbidden-scope image paths | `0` |

The raw JSONL ledger is retained locally as a diagnostic artifact. It is not
published as accepted evidence because the frozen repeat criterion failed.

## Frozen reproducibility check

The declared repeat subset is the first ten lexical frames of lexical first
selected Pair 25, in both independently estimated directions. The outcome was:

```text
REPRODUCIBILITY_ACCEPTANCE_FAIL
mismatch_count = 1
pair=25, frame=00000001.jpg, direction=1_to_2
```

The mismatched fields were `num_tentative_matches`, `num_unique_matches`,
`num_ransac_inliers`, `selected_correspondence_digest`,
`ransac_inlier_mask_digest`, `H_matrix`, `inlier_ratio`, and the three recorded
reprojection-error summaries.

## Boundary preserved

- no GT, XML, val, Pair 26/48, tracker, MIA runtime, target state, or Route-A
  MVE path was used by the provider;
- no G15c threshold was selected or applied;
- no numerical result is interpreted as geometry quality, coverage readiness,
  or tracking impact.

## Artifact pointers

- Full execution status: `M4_M5_EXECUTION_STATUS.md`
- Frozen contract: `EXPERIMENT_CONTRACT.md`
- Exact runner: `scripts/run_mdmt_independent_geometry_development.py`
- Image-only provider: `src/tracking/route_a_geometry/image_geometry_provider.py`
- Local raw output root (not versioned):
  `outputs/20260823_mdmt_mia_independent_geometry_development/`
