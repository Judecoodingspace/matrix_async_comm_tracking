# exp_20260625_004_matrix_risk_aware_v2_ablation

## Purpose

Test which risk-aware delayed association component explains the failure of
v1 under reliable capture time and controlled pose/reprojection noise:
authority cap, ambiguity margin, or both.

## Hypothesis

If v1 failed because uncertainty only widened the candidate gate, then adding
an authority cap and/or ambiguity margin should preserve zero-noise oracle
behavior and improve IDF1/IDSW under moderate pose noise.

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frames: `0-199`
- Identity key: `personID`
- Position key: `positionID` as per-frame grid/location key
- Primary drone: `D1` / `drone_id=0`
- Support drones: `D2-D8`
- Delay profiles: `fixed_1`, `fixed_2`, `fixed_3`, `fixed_5`
- Capture time: reliable; timestamp jitter disabled
- Pose/world-coordinate noise: `0.00m`, `0.25m`, `0.50m`, `1.00m`
- Moderate stress rule: `fixed_2 + pose_noise_0.50m`
- Risk defaults: `track_sigma=0.25m`, `obs_sigma_floor=0.10m`,
  `gate=2.0`, `sigma_ref=0.25m`, `absolute_gate_cap=1.0m`,
  `margin_threshold=0.50m`
- V1 min update weight: `0.10`
- V2 min update weight: `0.05`
- Seed: `7`

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_risk_aware_v2_ablation.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 \
  --frame-end 199 \
  --seed 7 \
  --output-dir outputs/20260625_matrix_risk_aware_v2_ablation
```

## Output

```text
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_metrics.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_event_subset_metrics.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_gate_diagnostics.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_gate_summary.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_ablation_summary.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_decision.md
```

## Key Metrics

Decision:

```text
risk_v2_needs_redesign
```

At `fixed_2 + pose_noise_0.50m`:

| Pipeline | Zero pass | Moderate pass | IDF1 | IDSW/1k | Risk-Drop | Risk-Plain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| risk_aware_delayed_fusion | 1 | 0 | 0.062125 | 431.875000 | -0.290375 | -0.015000 |
| risk_aware_v2a_authority_cap | 1 | 0 | 0.139750 | 247.250000 | -0.212750 | 0.062625 |
| risk_aware_v2b_ambiguity_margin | 1 | 0 | 0.071750 | 339.000000 | -0.280750 | -0.005375 |
| risk_aware_v2c_cap_plus_margin | 1 | 0 | 0.177625 | 204.375000 | -0.174875 | 0.100500 |

Gate summary at `fixed_2 + pose_noise_0.50m`:

| Pipeline | Accept Rate | Candidate Rejects | Margin Rejects | Mean Final Weight |
| --- | ---: | ---: | ---: | ---: |
| v1 | 0.930780 | 3262 | 0 | 0.610448 |
| v2a authority cap | 0.873570 | 5958 | 0 | 0.174714 |
| v2b ambiguity margin | 0.413687 | 5093 | 22537 | 0.304160 |
| v2c cap plus margin | 0.535385 | 6338 | 15557 | 0.107077 |

## Interpretation

All risk-aware variants preserve the zero-noise oracle. Authority cap is the
main useful component: v2a improves over v1 and plain uncertain fusion, while
v2b alone has only minor benefit. Combining cap plus margin gives the best
result: IDF1 `0.177625`, IDSW rate `204.375`, and IDSW below drop-delayed.
However, v2c still does not beat drop-delayed IDF1 `0.352500`, so Stage A is
not complete.

## Decision

Partially supported, not accepted as final Stage A method.

Do not move to Stage B yet. The next method should keep authority cap and
ambiguity control, but address missing identity evidence or support-only
failure where conservative gating cannot recover IDF1.

## Next Actions

- [ ] Analyze why v2c lowers IDSW but remains below drop-delayed IDF1.
- [ ] Add a support-only handling rule or candidate persistence mechanism.
- [ ] Consider separating identity update and position update, so uncertain
  support can help recall without rewriting identity state too aggressively.
