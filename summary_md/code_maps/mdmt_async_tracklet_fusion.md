# MDMT Async Tracklet Fusion Code Map

## Data Boundary

- `src/datasets/mdmt.py`: XML/official GT reconciliation plus strict and
  frame-consistent person evaluation masks. Identity fields remain offline.
- `src/datasets/mdmt_embeddings.py`: frozen OSNet cache keyed by
  `DetectionKey`, which contains no identity.

## Message Boundary

- `src/tracking/tracklet_packets.py`: `GlobalFusionPacket` is the deployed wire
  schema. It contains exactly one latest or pooled embedding.
- `global_fusion_packet_from_update()`: projects rich local state to history-1
  or incremental packets and applies delay.

## Fusion Core

- `src/tracking/mdmt_global_tracklet_fusion.py`:
  - `GlobalFusionState`: local/global mappings and separate appearance galleries.
  - `run_global_tracklet_fusion()`: arrival, full timestamped, fixed-lag and
    future-only recovery scheduling with immutable published IDs.
  - evaluation helpers: ID metrics, gap episodes, official AAS and cluster
    bootstrap.

## Experiment Orchestration

- `scripts/phase3_mdmt_async_incremental_tracklet_fusion.py`:
  - val-only threshold calibration;
  - official-test identity reconciliation;
  - bbox SORT local stream preparation;
  - condition-level checkpoint/resume and progress;
  - measurement gates, H1-H4 decisions and CSV assembly.

## Verification

- `tests/test_mdmt_global_tracklet_fusion.py`: packet fairness, no-GT runtime
  dependence, one-to-one matching, replay immutability, lag/recovery semantics,
  bidirectional symmetry, strict person masks and AAS formula.
