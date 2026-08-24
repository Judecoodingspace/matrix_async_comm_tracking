# RESULTS — RD-R1 Corrected Isolated Reproducibility Rerun

## Result status

`REPRODUCIBILITY_ACCEPTED_RAW_GEOMETRY_LEDGER / STOP_BEFORE_G15C`

This is an implementation-contract repair and isolated reproducibility result.
It is not a geometry-quality, G15c, Pair 26/48, val, or Route-A MVE result.

## Corrected attempt

- Attempt root: `outputs/20260823_mdmt_mia_independent_geometry_development/attempts/attempt_02_rng_placement_corrected/`
- Scientific estimator identity: `rd1-rd6-frozen-sift-flann-ransac-h` unchanged.
- Implementation revision: `v1-rng-placement-corrected`.
- Provider digest: `b8b65b881cc1627ff2e5f41f885f36473ebadf59f5e3f076240c9de1eee99a7d`.
- Manifest digest: `11f78f5252a5459007ca6c56c2b4eccec487b4a0e9a10c52b38e34a20dec3e8f`.
- Config digest: `c7b6b2cd30238c174295f2b367f70f5b8a062cae7737abd8aca9ab9ded66eb04`.

| Requirement | Result |
| --- | ---: |
| Full denominator | `5,460` |
| Unique ledger keys | `5,460` |
| `1_to_2` records | `2,730` |
| `2_to_1` records | `2,730` |
| Invalid record digests | `0` |
| Forbidden-scope recorded paths | `0` |
| Threshold status | `NOT_EVALUATED_PENDING_G15C` for all rows |

## Frozen repeat

The unchanged repeat subset was Pair 25, lexical frames `00000001.jpg` through
`00000010.jpg`, independently estimated in both directions.

```text
repeat_record_count = 20
mismatch_count = 0
REPRODUCIBILITY_ACCEPTANCE_PASS
```

No geometry-quality distribution, H availability, inlier ratio, reprojection
error, threshold candidate, coverage claim, or downstream tracking result is
reported by this result.

## Previous ledger disposition

The earlier 5,460-row ledger used provider digest
`34c0500b267e9d2eee00714a71f73a6451c3394878377a8cdbee30d434080723` and
failed the frozen repeat under an `IMPLEMENTATION_CONTRACT_VIOLATION`. It is
permanently `QUARANTINED_DIAGNOSTIC_ONLY / NOT_ADMISSIBLE_FOR_G15C`; it was not
merged with, resumed into, or used to patch the corrected ledger.

## Next boundary

The only established conclusion is that the corrected frozen estimator now has
an accepted raw diagnostic ledger. Human authorization is required before any
G15c decision or further validation.
