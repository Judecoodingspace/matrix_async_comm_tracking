# exp_20260803_002 MDMT Asynchronous Incremental Tracklet Fusion

## Question

Under the same communication delay, does a causal incremental tracklet packet
with history provide more cross-view pedestrian identity continuity than a
history-length-1 observation packet?

## Scope

- MDMT person-only tracking
- Locked local baseline from `exp_20260803_001`
- Runtime messages contain no GT identity
- Delay reported in frames because MDMT has no reliable FPS metadata
- Support view does not read primary-view occlusion labels

## Planned Baselines

- `primary_only`
- `drop_delayed`
- `arrival_time_fusion`
- `history1_timestamped`
- `incremental_tracklet_timestamped`
- `fixed_lag_tracklet_update`
- `late_recovery_stitching`

## Gates

- [ ] Build a category-consistent person-only official cross-view GT subset
- [ ] Verify history-length-1 packet equivalence
- [ ] Add deterministic delay injection and frame-delay sweep
- [ ] Compare history 1 against incremental pooled tracklet state
- [ ] Separate online continuity from late recovery
- [ ] Complete smoke, Formal, and seven-dimension analysis

## Current Decision

`planned_current_stage`.

The local-tracklet readiness gate has passed. This experiment is the first
direct test of asynchronous tracklet-to-global-tracker fusion on MDMT.
