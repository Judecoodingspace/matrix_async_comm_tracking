# exp_20260622_001_matrix_async_pose_gt

## Purpose

Test whether timestamp-aware pose/world-coordinate fusion improves
multi-UAV multi-object identity tracking under controlled communication delay
on MATRIX.

## Hypothesis

Delayed support observations fused at arrival time will corrupt identity
association when the world position is stale. Fusing delayed observations at
their capture time should preserve identity tracking.

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frames: `0-49`
- Identity key: `personID`
- Position key: `positionID` as per-frame grid/location key
- Primary drone: `D1` / `drone_id=0`
- Support drones: `D2-D8`
- Inputs: GT world coordinates and generated MATRIX annotations/POMs
- Delay profiles: `fixed_0`, `fixed_1`, `fixed_3`, `fixed_5`, `fixed_10`, `uniform_1_10`
- Seed: `7`
- Tracker: GT world-coordinate nearest-neighbor association
- Distance threshold: `1.0`
- Metrics: IDF1, IDSW, MOTA, world XY MAE/RMSE, latency

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_async_pose_gt.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 \
  --frame-end 49 \
  --seed 7 \
  --output-dir outputs/20260622_matrix_async_pose_gt
```

## Output

```text
outputs/20260622_matrix_async_pose_gt/phase1_matrix_async_pose_metrics.csv
outputs/20260622_matrix_async_pose_gt/phase1_delay_breakdown.csv
outputs/20260622_matrix_async_pose_gt/phase1_decision.md
```

## Key Metrics

| Delay | Pipeline | IDF1 | IDSW | MOTA | World XY MAE | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| fixed_0 | Sync oracle | 1.000000 | 0 | 1.000000 | 0.000001 | no delay |
| fixed_0 | Arrival-time fusion | 1.000000 | 0 | 1.000000 | 0.000001 | no delay |
| fixed_0 | Timestamped pose fusion | 1.000000 | 0 | 1.000000 | 0.000001 | no delay |
| fixed_1 | Drop delayed | 0.846000 | 251 | 0.874500 | 0.449551 | D1 only support after drop |
| fixed_1 | Arrival-time fusion | 0.994500 | 11 | 0.994500 | 0.091759 | small delay mostly tolerable |
| fixed_1 | Timestamped pose fusion | 1.000000 | 0 | 1.000000 | 0.000001 | accepted |
| fixed_3 | Arrival-time fusion | 0.372500 | 480 | 0.760000 | 0.186475 | stale support corrupts IDs |
| fixed_3 | Timestamped pose fusion | 1.000000 | 0 | 1.000000 | 0.000001 | accepted |
| fixed_5 | Arrival-time fusion | 0.324500 | 495 | 0.752500 | 0.228228 | stale support corrupts IDs |
| fixed_5 | Timestamped pose fusion | 1.000000 | 0 | 1.000000 | 0.000001 | accepted |
| fixed_10 | Arrival-time fusion | 0.353500 | 514 | 0.743000 | 0.302121 | stale support corrupts IDs |
| fixed_10 | Timestamped pose fusion | 1.000000 | 0 | 1.000000 | 0.000001 | accepted |
| uniform_1_10 | Arrival-time fusion | 0.162000 | 870 | 0.565000 | 0.093031 | worst ID stability |
| uniform_1_10 | Timestamped pose fusion | 1.000000 | 0 | 1.000000 | 0.000001 | accepted |

## Interpretation

The first MATRIX GT/world-coordinate experiment strongly supports the
timestamped pose-fusion hypothesis. Arrival-time fusion is safe at zero delay
and mostly tolerable at one frame, but delays of three or more frames create
large identity degradation. Timestamped pose fusion remains perfect in this GT
setup because support observations are associated at the correct capture-time
world state.

Drop-delayed equals the primary-only baseline after nonzero support delay and
is better than arrival-time fusion for delay profiles `fixed_3`, `fixed_5`,
`fixed_10`, and `uniform_1_10`. This means stale support can be worse than no
support unless capture-time pose/time metadata are used.

`arrival_time_exp_decay` currently matches arrival-time fusion because this GT
prototype records the decay baseline but does not yet apply weighted state
updates.

## Decision

Accepted.

Proceed with MATRIX asynchronous pose/world-coordinate tracking. The next run
should expand the timestep range or add stress profiles before adding
detector/ReID noise.

## Next Actions

- [ ] Generate annotations/POMs for the next frame range if expanding beyond
  `0-49`.
- [ ] Add a weighted arrival-time exp-decay state update or remove it from the
  next GT comparison if not needed.
- [ ] Add crossing/occlusion subset diagnostics for delay-sensitive events.
- [ ] Only after GT stress tests, add detector/ReID noise.
