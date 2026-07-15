# exp_20260623_001_matrix_delay_event_diagnostics

## Purpose

Find the critical communication-delay threshold where arrival-time fusion turns
from useful to harmful, then attribute IDF1/IDSW degradation to lightweight
event subsets.

## Hypothesis

Arrival-time fusion should be safe at very small delay but should become worse
than dropping delayed support after a measurable delay threshold. The IDSW
increase should concentrate in close-proximity/crossing-like and high-motion
person-frame subsets.

## Setup

- Dataset: MATRIX `MATRIX/MATRIX_30x30`
- Frames: `0-49`
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
- Metrics: IDF1, IDSW, MOTA-compatible run metrics, event-subset IDF1/IDSW

## Command

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_delay_event_diagnostics.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 \
  --frame-end 49 \
  --seed 7 \
  --output-dir outputs/20260623_matrix_delay_event_diagnostics
```

## Output

```text
outputs/20260623_matrix_delay_event_diagnostics/delay_threshold_scan.csv
outputs/20260623_matrix_delay_event_diagnostics/event_subset_metrics.csv
outputs/20260623_matrix_delay_event_diagnostics/per_person_frame_trace.csv
outputs/20260623_matrix_delay_event_diagnostics/critical_delay_decision.md
```

## Key Metrics

| Delay | Arrival IDF1 | Arrival IDSW | Drop-delayed IDF1 | Drop-delayed IDSW | Timestamped IDF1 | Timestamped IDSW | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| fixed_0 | 1.000000 | 0 | 1.000000 | 0 | 1.000000 | 0 | no delay |
| fixed_1 | 0.994500 | 11 | 0.846000 | 251 | 1.000000 | 0 | still useful |
| fixed_2 | 0.115000 | 1143 | 0.846000 | 251 | 1.000000 | 0 | critical failure |
| fixed_3 | 0.372500 | 480 | 0.846000 | 251 | 1.000000 | 0 | harmful |
| fixed_4 | 0.324000 | 630 | 0.846000 | 251 | 1.000000 | 0 | harmful |
| fixed_5 | 0.324500 | 495 | 0.846000 | 251 | 1.000000 | 0 | harmful |
| fixed_10 | 0.353500 | 514 | 0.846000 | 251 | 1.000000 | 0 | harmful |

Critical delay thresholds:

| Rule | First delay |
| --- | ---: |
| Arrival IDF1 below drop-delayed IDF1 | 2 frames |
| Arrival IDF1 drops at least 5 points from fixed_0 | 2 frames |
| Arrival IDSW reaches at least 50 | 2 frames |

Arrival-time event subset metrics at `fixed_2`:

Event tags are non-exclusive, so IDSW counts across subsets should be read as
overlapping concentrations rather than a partition that sums to total IDSW.

| Event subset | IDF1 | IDSW | Coverage |
| --- | ---: | ---: | ---: |
| Proximity | 0.150248 | 785 | 0.705500 |
| Crossing-like | 0.188264 | 430 | 0.409000 |
| High-motion | 0.152000 | 358 | 0.250000 |
| Normal | 0.241692 | 174 | 0.165500 |
| Support-only | 0.246964 | 163 | 0.123500 |
| Low-visibility | 0.000000 | 0 | 0.000000 |

## Interpretation

The finer fixed-delay scan moves the critical delay earlier than the previous
coarse result. `fixed_1` remains useful, but `fixed_2` already collapses
arrival-time fusion below drop-delayed. Timestamped pose fusion stays at the GT
upper bound for all fixed delays.

The IDSW concentration is strongest in proximity and crossing-like subsets, but
normal and support-only rows also contribute. `low_visibility` is empty in this
0-49 range because MATRIX has high multi-view coverage, so visibility stress
requires a different frame range or synthetic view-drop profile.

## Decision

Accepted.

Use 2 frames as the first measured critical delay threshold for this 0-49 GT
MATRIX slice. The next mainline expansion should either validate the threshold
on a longer range or add timestamp/pose uncertainty to test whether the GT
upper bound remains robust.

## Next Actions

- [ ] Expand to `0-199` after generating missing annotations/POMs for frames
  `50-199`.
- [ ] Add timestamp jitter / pose interpolation noise focused on proximity and
  crossing-like subsets.
- [ ] Add synthetic view-drop or select lower-coverage frame ranges before
  making claims about low-visibility behavior.
