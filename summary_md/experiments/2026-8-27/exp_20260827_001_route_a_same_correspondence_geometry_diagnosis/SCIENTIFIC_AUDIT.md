# Scientific Audit

## Findings

No P0, P1, P2, or P3 finding remains before the development-only run.

The Homography and Fundamental Matrix inlier definitions are necessarily
model-specific. This is a frozen interpretation limitation, not an unrecorded
implementation difference: both receive identical float32 correspondence
arrays, with the same numeric RANSAC threshold, confidence, iteration budget,
and source images. Results cannot be interpreted as a calibrated model-choice
contest.

## Contract-to-code mapping

| Requirement | Evidence |
| --- | --- |
| One correspondence generation | `run_same_correspondence_probe()` calls extraction once; synthetic test instruments `SIFT_create` and observes one call. |
| Identical H/F inputs | Both results carry `input_correspondence_digest`; the runner aborts on mismatch and audits all rows. |
| Frozen H semantics | Existing solver parameters/diagnostics/normalization and G15c are reused; parity test matches the frozen provider. |
| F diagnostic only | Each F record declares `NOT_DEFINED_DIAGNOSTIC_ONLY`; no F classifier exists. |
| Full denominator | Frozen manifest has 2740 frames and 5480 frame-direction keys; finalization requires exact equality. |
| New train evidence | Manifest selected 23/27/28/30/32 before image reads; 45/29/51/69 and 26/48 are excluded. |
| Delta per unit | All rows contain `delta_inlier_ratio`, or JSON null plus `NOT_COMPARABLE`. |

## Runtime input trace

The runner accepts only a data root, frozen manifest/config, isolated output
root, and exact-provenance resume flag. It constructs input paths only under
`train/{1,2}/{23,27,28,30,32}-{1,2}/<frozen JPEG>`. Manifest frame counts and
filename-set digests are checked before decode. XML, GT, MDA GT, detector,
tracker, MIA, identity, Route-A state, prior/future frames, test, and val are
not accepted as runtime inputs or imported by the probe.

## Output/resume integrity

Attempt001 is isolated. Resume requires exact manifest/config/source digests and
Git commit, and validates record digests and unique keys. Completion requires a
5480-key ledger and a zero-mismatch 20-row deterministic repeat. No image,
descriptor, keypoint, or match cache is written.

## Verification

```text
python3 -m py_compile probe runner tests -> PASS
PYTHONPATH=. python3 -m pytest \
  tests/test_route_a_same_correspondence_geometry_diagnosis.py \
  tests/test_route_a_image_geometry_provider.py \
  tests/test_route_a_geometry_recovery_epoch.py -q
-> 15 passed
```

Frozen identities remain unchanged:

- provider SHA-256: `b8b65b881cc1627ff2e5f41f885f36473ebadf59f5e3f076240c9de1eee99a7d`
- estimator config SHA-256: `c7b6b2cd30238c174295f2b367f70f5b8a062cae7737abd8aca9ab9ded66eb04`

## Verdict

`SAFE_TO_RUN`
