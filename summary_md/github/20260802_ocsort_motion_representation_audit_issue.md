# exp_20260802_003: OC-SORT motion representation audit

## Goal

Audit whether MATRIX local-tracklet failure is caused by BoT-SORT association,
mobile-camera image representation, or non-linear world motion.

## Scope

- [x] Add OC-SORT/Deep OC-SORT local-tracklet adapter
- [x] Add clean world-XY and image-plane motion diagnostics
- [x] Add resumable Pilot/Formal CLI with terminal progress
- [x] Add tests and experiment records
- [x] Run `0-199` Pilot
- [x] Analyze gates and update durable conclusion
- [ ] Run Formal only when `formal_allowed=1`

## Gate

Formal is blocked unless an image tracker reaches IDF1 `0.80`, purity `0.95`,
minimum-view IDF1 `0.70`, and occlusion support coverage `0.90`.

Pilot result: `formal_allowed=0`. Motion linearity and GMC+CV candidate recall
pass, but image trackers retain a merge-versus-fragmentation trade-off. The
clean-world diagnostic also shows that the current IDF1 gate is confounded by
local track termination across gaps longer than `track_buffer=5`. Next split
active-run continuity from long-gap reacquisition/stitching.

Labels: `experiment`, `analysis`
