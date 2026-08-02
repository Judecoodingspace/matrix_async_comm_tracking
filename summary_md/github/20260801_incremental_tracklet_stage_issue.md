# exp_20260801_002: incremental local-tracklet update foundation

## Goal

Build and validate causal incremental local-tracklet messages. This foundation
stops before formal global delayed fusion so local tracking quality is not
confounded with the asynchronous association result.

## Checklist

- [x] Implement history-1 adapter and exact observation-level equivalence gate
- [x] Implement independent per-UAV bbox/OSNet local trackers and local ID namespaces
- [x] Define causal incremental tracklet message schema
- [x] Verify runtime code does not read GT personID
- [x] Audit local IDF1, tracklet purity, fragmentation, and overlap
- [x] Audit motion/covariance accumulation quality
- [x] Compare single-crop and causal pooled appearance quality
- [x] Prepare complete all-view OSNet cache and enforce coverage gate
- [x] Run smoke
- [ ] Run formal 0-999 (blocked until local-quality Gate 3 passes)
- [x] Complete seven-dimension smoke/blocker analysis

## Experiment card

`summary_md/experiments/2026-8-1/exp_20260801_002_matrix_incremental_tracklet_update_foundation.md`

## Output

`outputs/20260801_matrix_incremental_tracklet_update_foundation/`

## Decision target

Determine whether the local tracklet/message layer is reliable enough to enter
the next fixed-lag global tracklet-fusion experiment.

## Smoke result

Decision: `local_tracklet_quality_blocked`.

- History-1 mismatch: zero in all four legacy conditions.
- Embedding coverage: `25.59% -> 100%` after missing-crop extraction.
- bbox-only local IDF1/purity: `0.248077 / 0.329275`.
- bbox+OSNet local IDF1/purity: `0.073641 / 0.959313`.
- Interpretation: bbox-only merges identities; the current OSNet/motion gate
  creates pure but highly fragmented tracklets.

The next action is mobile-camera local tracking repair. Do not start global
tracklet fusion or the 0-999 foundation formal until Gate 3 is credible.
