# exp_20260625_002_matrix_time_pose_uncertainty

## Purpose

Test whether ideal timestamped/capture-time fusion remains reliable when
capture timestamps and pose/world-coordinate projections are imperfect.

## Hypothesis

Small timestamp jitter and pose/world-coordinate noise should preserve most of
the timestamped fusion advantage, but moderate uncertainty may push delayed
support observations back below the drop-delayed safety baseline. If moderate
uncertainty fails, the next method direction should become uncertainty-aware
delayed association rather than only timestamp-aware buffering.

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frames: `0-199`
- Identity key: `personID`
- Position key: `positionID` as per-frame grid/location key
- Primary drone: `D1` / `drone_id=0`
- Support drones: `D2-D8`
- Delay profiles: `fixed_1`, `fixed_2`, `fixed_3`, `fixed_5`
- Timestamp jitter: `none`, `jitter_pm1`, `jitter_pm2`
- Support world-XY noise: `0.00m`, `0.25m`, `0.50m`, `1.00m`
- Moderate stress rule: `fixed_2` with `jitter_pm1_noise_0.50m`
- Tracker: GT world-coordinate nearest-neighbor association
- Distance threshold: `1.0`
- Seed: `7`

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_time_pose_uncertainty.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 \
  --frame-end 199 \
  --seed 7 \
  --output-dir outputs/20260625_matrix_time_pose_uncertainty
```

## Output

```text
outputs/20260625_matrix_time_pose_uncertainty/uncertainty_metrics.csv
outputs/20260625_matrix_time_pose_uncertainty/uncertainty_event_subset_metrics.csv
outputs/20260625_matrix_time_pose_uncertainty/uncertainty_threshold_summary.csv
outputs/20260625_matrix_time_pose_uncertainty/time_pose_uncertainty_decision.md
```

## Key Metrics

Decision:

```text
needs_uncertainty_aware_association
```

At `fixed_2`:

| Profile | Jitter | Noise m | IDF1 | IDSW/1k GT | Drop IDF1 | Ideal gap | IDSW below drop |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| zero_uncertainty | none | 0.00 | 1.000000 | 0.000000 | 0.352500 | 0.000000 | 1 |
| jitter_pm1_noise_0.00m | jitter_pm1 | 0.00 | 0.131625 | 203.375000 | 0.352500 | 0.868375 | 1 |
| jitter_none_noise_0.25m | none | 0.25 | 0.316000 | 43.250000 | 0.352500 | 0.684000 | 1 |
| jitter_none_noise_0.50m | none | 0.50 | 0.081250 | 343.375000 | 0.352500 | 0.918750 | 0 |
| jitter_pm1_noise_0.50m | jitter_pm1 | 0.50 | 0.066875 | 408.875000 | 0.352500 | 0.933125 | 0 |
| jitter_pm2_noise_0.50m | jitter_pm2 | 0.50 | 0.053625 | 457.500000 | 0.352500 | 0.946375 | 0 |

At `fixed_1`, the same qualitative pattern appears:

| Profile | IDF1 | IDSW/1k GT | Drop IDF1 | Ideal gap |
| --- | ---: | ---: | ---: | ---: |
| zero_uncertainty | 1.000000 | 0.000000 | 0.352500 | 0.000000 |
| jitter_pm1_noise_0.00m | 0.132625 | 222.250000 | 0.352500 | 0.867375 |
| jitter_none_noise_0.25m | 0.394750 | 31.875000 | 0.352500 | 0.605250 |
| jitter_pm1_noise_0.50m | 0.062500 | 400.625000 | 0.352500 | 0.937500 |

## Interpretation

Zero uncertainty exactly matches ideal timestamped fusion, so the new pipeline
is wired correctly. Once coarse frame-level timestamp jitter or 0.50m support
world-coordinate noise is introduced, timestamped uncertain fusion falls below
drop-delayed at `fixed_2`. Even `jitter_pm1` without pose noise causes a large
IDF1 drop, showing severe sensitivity to capture-time labeling error.

This means the paper should not stop at "put delayed observations into a
capture-time buffer." The next mechanism must reason about timestamp/pose
uncertainty before trusting a late support observation.

## Decision

Accepted: timestamped fusion is not robust under the tested moderate
time/pose uncertainty.

Promote the next method direction from plain timestamp-aware OOSM fusion to
uncertainty-aware delayed association.

## Next Actions

- [ ] Implement uncertainty-aware gating: reject or downweight late support
  observations when timestamp/pose uncertainty makes the association unsafe.
- [ ] Replace coarse frame-level jitter with a finer sub-frame or equivalent
  spatial-error model if the next experiment needs realistic sensor timing.
- [ ] Keep zero-uncertainty timestamped fusion, drop-delayed, and arrival-time
  fusion as required baselines.
