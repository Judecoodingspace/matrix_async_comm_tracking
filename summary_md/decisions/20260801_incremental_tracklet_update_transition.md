# Decision: Transition to Incremental Tracklet Update

Date: 2026-08-01

## Decision

The next research stage uses **incremental local-tracklet updates** as the
cross-UAV message unit. The completed observation-level experiments remain the
controlled mechanism baseline; they are not presented as a complete MVMOT
system.

## Scope Correction

Previous support messages formed a delayed stream of per-frame observations:

```text
world_xy + bbox + embedding + capture/arrival time
```

They did not include an independently maintained support local tracklet. The
new stage adds a causal per-UAV local tracker and sends its current tracklet
state every frame. It does not wait for a tracklet to terminate.

## Preserved Mechanisms

- capture-time alignment
- fixed-lag replay
- useful support window
- identity candidate gate
- covariance-aware position authority
- late-message recovery/stitching boundary

## New Variables

- local tracklet purity and fragmentation
- accumulated motion and covariance
- pooled appearance history
- local track age and miss count
- observation packet versus incremental tracklet packet

## Deferred

- detector errors
- camera-ray/reprojection geometry
- completed-tracklet batching
- Mamba/end-to-end training

These remain deferred until the incremental-tracklet foundation reproduces the
observation-level reference and passes no-GT-leakage checks.

