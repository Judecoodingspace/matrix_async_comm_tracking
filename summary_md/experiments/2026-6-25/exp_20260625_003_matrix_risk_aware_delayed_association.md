# exp_20260625_003_matrix_risk_aware_delayed_association

## Purpose

Test whether a minimal risk-aware delayed association gate can safely fuse
late support observations when capture time is reliable but support
world-coordinate observations have controlled pose/reprojection noise.

## Hypothesis

If delayed support observations are accepted, rejected, or downweighted using
a residual-to-uncertainty risk score, then risk-aware delayed fusion should
preserve the zero-noise timestamped oracle and outperform both drop-delayed
and plain timestamped uncertain fusion under moderate pose/world noise.

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frames: `0-199`
- Identity key: `personID`
- Position key: `positionID` as per-frame grid/location key
- Primary drone: `D1` / `drone_id=0`
- Support drones: `D2-D8`
- Delay profiles: `fixed_1`, `fixed_2`, `fixed_3`, `fixed_5`
- Capture time: reliable, no timestamp jitter in the main run
- Pose/world-coordinate noise: `0.00m`, `0.25m`, `0.50m`, `1.00m`
- Moderate stress rule: `fixed_2 + pose_noise_0.50m`
- Tracker: GT world-coordinate nearest-neighbor association
- Risk gate: `risk = residual_distance / sqrt(track_sigma^2 + obs_sigma^2)`
- Risk parameters: `track_sigma=0.25m`, `obs_sigma_floor=0.10m`,
  `gate=2.0`, `min_update_weight=0.10`
- Seed: `7`

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_risk_aware_delayed_association.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 \
  --frame-end 199 \
  --seed 7 \
  --output-dir outputs/20260625_matrix_risk_aware_delayed_association
```

## Output

```text
outputs/20260625_matrix_risk_aware_delayed_association/risk_aware_metrics.csv
outputs/20260625_matrix_risk_aware_delayed_association/risk_aware_event_subset_metrics.csv
outputs/20260625_matrix_risk_aware_delayed_association/risk_aware_gate_diagnostics.csv
outputs/20260625_matrix_risk_aware_delayed_association/risk_aware_gate_summary.csv
outputs/20260625_matrix_risk_aware_delayed_association/risk_aware_threshold_summary.csv
outputs/20260625_matrix_risk_aware_delayed_association/risk_aware_decision.md
```

## Key Metrics

Decision:

```text
risk_aware_needs_tuning
```

At `fixed_2`:

| Profile | Noise m | Risk IDF1 | Risk IDSW/1k | Plain IDF1 | Plain IDSW/1k | Drop IDF1 | Risk-Drop | Risk-Plain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| zero_pose_noise | 0.00 | 1.000000 | 0.000000 | 1.000000 | 0.000000 | 0.352500 | 0.647500 | 0.000000 |
| pose_noise_0.25m | 0.25 | 0.123125 | 279.750000 | 0.357500 | 42.500000 | 0.352500 | -0.229375 | -0.234375 |
| pose_noise_0.50m | 0.50 | 0.062125 | 431.875000 | 0.077125 | 354.875000 | 0.352500 | -0.290375 | -0.015000 |
| pose_noise_1.00m | 1.00 | 0.044125 | 548.625000 | 0.039250 | 557.250000 | 0.352500 | -0.308375 | 0.004875 |

Gate summary at `fixed_2`:

| Profile | Support Obs | Accept Rate | Mean Weight | Mean Risk |
| --- | ---: | ---: | ---: | ---: |
| pose_noise_0.25m | 47125 | 0.885008 | 0.566534 | 1.409938 |
| pose_noise_0.50m | 47125 | 0.930780 | 0.610448 | 1.106275 |
| pose_noise_1.00m | 47125 | 0.989899 | 0.818968 | 0.602157 |

## Interpretation

The v1 gate preserves the zero-noise oracle, so the implementation is safe in
the exact-coordinate case. Under moderate pose noise, however, it performs
worse than both drop-delayed and plain timestamped uncertain fusion. The gate
also accepts more observations as pose noise increases because the uncertainty
scale widens the gate. This confirms a design flaw discussed before the run:
uncertainty cannot only widen candidate gates; it must also reduce support
authority or require ambiguity-aware competition.

## Decision

Rejected as a ready method: do not move to Stage B with this v1 gate.

Accepted as a useful negative result: risk-aware delayed association remains
the right research direction, but this residual/scale gate plus exponential
weight is insufficient.

## Next Actions

- [ ] Tune or redesign the uncertainty policy so larger pose uncertainty does
  not automatically accept more support observations.
- [ ] Test a conservative two-stage gate: candidate gate plus uncertainty
  authority cap.
- [ ] Add ambiguity-aware competition using nearest-neighbor margin or
  event-risk tags before entering Stage B camera-projection experiments.
