# exp_20260802_004: local-tracklet lifecycle-stratified readiness

## Goal

Separate active visible-run local tracking quality from long-gap termination,
reacquisition, and global-stitching demand.

## Status

- [x] Implement analysis-only runner
- [x] Add segmentation and long-gap tests
- [x] Run the `0-199`, D1-D8 audit
- [x] Write the seven-dimension analysis
- [ ] Compare a public mobile-camera/UAV tracker with the corrected active-run gate
- [ ] Implement the minimum asynchronous global-stitching audit

## Decision

`readiness_metric_recalibrated_local_tracker_still_blocked`

Clean world-XY active-run IDF1 reaches `0.935778`, confirming that the previous
full-sequence readiness gate was long-gap confounded. No image tracker passes
active-run readiness. All 537 long gaps have complete support-view coverage,
providing clear headroom for a separate global-stitching experiment.
