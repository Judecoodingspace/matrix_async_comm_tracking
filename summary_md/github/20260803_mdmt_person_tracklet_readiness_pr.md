## Summary

- add the identity/position separation and incremental-tracklet foundation
- add MATRIX mobile-camera local-tracklet diagnostics and lifecycle-stratified analysis
- add dataset-neutral tracklet packets and the MDMT adapter
- import and audit the official paired MDA GT protocol
- complete the MDMT person-only local-tracklet Pilot and locked official-test Formal

## Formal Decision

`person_local_tracklet_ready`

On `124824` visible person detections and `912` active runs, `bbox_sort` reaches:

- IDF1: `0.997229`
- purity: `0.997500`
- IDSW: `22`
- fragmentation: `20`

All measurement gates pass. Generated outputs, datasets, caches, and model
weights remain ignored.

## Verification

```text
208 passed in 2.31s
```

## GitHub Tracking

- completed experiment issues: #13 through #19
- current-stage issue: #20

The next stage is MDMT person-only asynchronous incremental-tracklet fusion.
