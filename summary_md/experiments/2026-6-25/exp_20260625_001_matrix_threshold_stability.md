# exp_20260625_001_matrix_threshold_stability

## Purpose

Validate whether the `fixed_2` critical delay threshold found on MATRIX frames
`0-49` is stable across longer and shifted frame windows.

## Hypothesis

Arrival-time fusion should become harmful at a repeatable short delay, expected
near `2-3` frames. If the threshold varies, earlier thresholds should align
with higher proximity/crossing-like/high-motion event coverage. Timestamped
pose fusion should remain at the GT/sync-oracle upper bound.

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frames: `0-199`
- Windows: `0-49`, `50-99`, `100-149`, `150-199`, `0-99`, `100-199`, `0-199`
- Identity key: `personID`
- Position key: `positionID` as per-frame grid/location key
- Primary drone: `D1` / `drone_id=0`
- Support drones: `D2-D8`
- Inputs: GT world coordinates and generated MATRIX annotations/POMs
- Delay profiles: `fixed_0` through `fixed_10`
- Seed: `7`
- Tracker: GT world-coordinate nearest-neighbor association
- Distance threshold: `1.0`
- Event proximity radius: `2.0`
- Metrics: `T_main`, `T_drop5`, `T_idsw_rate`, event coverage, timestamped sanity

## Commands

Generate missing derived files for frames `50-199`:

```bash
cd MATRIX/MATRIX_30x30
MPLCONFIGDIR=/tmp /usr/bin/python3 -c "from generatePOM import generate_POM; from generateAnnotation import annotate; max_timestep=200; [ (generate_POM(t), annotate(t, max_timestep)) for t in range(50, max_timestep) ]"
```

Run the stability experiment:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_threshold_stability.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-end 199 \
  --seed 7 \
  --output-dir outputs/20260625_matrix_threshold_stability
```

## Output

```text
outputs/20260625_matrix_threshold_stability/window_threshold_scan.csv
outputs/20260625_matrix_threshold_stability/window_event_coverage.csv
outputs/20260625_matrix_threshold_stability/threshold_stability_summary.csv
outputs/20260625_matrix_threshold_stability/threshold_stability_decision.md
```

## Key Metrics

| Window | T_main | T_drop5 | T_idsw_rate | Timestamped sanity |
| --- | ---: | ---: | ---: | ---: |
| 0-49 | 2 | 2 | 2 | 1 |
| 50-99 | 2 | 2 | 2 | 1 |
| 100-149 | 2 | 2 | 2 | 1 |
| 150-199 | 2 | 2 | 2 | 1 |
| 0-99 | 2 | 2 | 2 | 1 |
| 100-199 | 2 | 2 | 2 | 1 |
| 0-199 | 2 | 2 | 2 | 1 |

Event coverage:

| Window | Event risk | Proximity | Crossing-like | High-motion | Support-only |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0-49 | 0.454833 | 0.705500 | 0.409000 | 0.250000 | 0.123500 |
| 50-99 | 0.501000 | 0.782500 | 0.470500 | 0.250000 | 0.340500 |
| 100-149 | 0.482000 | 0.757000 | 0.439000 | 0.250000 | 0.123500 |
| 150-199 | 0.482500 | 0.780000 | 0.417500 | 0.250000 | 0.175500 |
| 0-199 | 0.482333 | 0.756250 | 0.440750 | 0.250000 | 0.190750 |

Aggregate `0-199` snapshot:

| Delay | Arrival IDF1 | Arrival IDSW/1k GT | Drop IDF1 | Drop IDSW/1k GT | Timestamped IDF1 | Timestamped IDSW |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_0 | 1.000000 | 0.000000 | 1.000000 | 0.000000 | 1.000000 | 0 |
| fixed_1 | 0.998000 | 2.625000 | 0.352500 | 253.000000 | 1.000000 | 0 |
| fixed_2 | 0.052875 | 617.625000 | 0.352500 | 253.000000 | 1.000000 | 0 |
| fixed_3 | 0.108000 | 346.875000 | 0.352500 | 253.000000 | 1.000000 | 0 |

## Interpretation

The threshold is stable under this window design. All seven windows have
`T_main=2`, `T_drop5=2`, and `T_idsw_rate=2`, and timestamped pose fusion passes
the sanity check in every window. The event-risk correlation with `T_main` is
zero because `T_main` has no variation to explain.

The result strengthens the previous conclusion: under MATRIX GT/world-coordinate
tracking, one-frame stale support remains useful, but two-frame stale support
is already harmful when fused at arrival time. Timestamped pose fusion remains
the correct upper-bound mechanism before adding pose/timestamp uncertainty.

## Decision

Accepted: stable.

Use `2` frames as the first measured harmful-delay threshold on MATRIX
`0-199` under the current GT world-coordinate tracker and fixed-delay profiles.

## Next Actions

- [ ] Add timestamp jitter / pose interpolation noise on `0-199`, using
  proximity and crossing-like rows as primary stress subsets.
- [ ] Keep drop-delayed and timestamped fusion as required baselines.
- [ ] Do not design adaptive fusion until capture-time correction remains
  robust under non-ideal timestamp/pose conditions.
