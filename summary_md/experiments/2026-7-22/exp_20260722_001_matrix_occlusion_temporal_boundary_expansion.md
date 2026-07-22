# exp_20260722_001_matrix_occlusion_temporal_boundary_expansion

## Purpose

扩展遮挡场景下的成对反事实测量，判断异步 support 的因果收益主要由绝对延迟决定，还是由绝对延迟和在线遮挡窗口覆盖共同决定。

本轮不是重新证明短延迟 support 有用，而是把 `rho_episode` 过粗的问题拆开：在每个在线发布帧上，已经到达的最新 support 到底有多旧。

## Hypothesis

`rho_episode = delay_ms / occlusion_duration_ms` 只能提供 episode 级粗分层。真正影响在线 tracking gain 的变量至少包括：

- `delay_ms`
- `online_support_coverage_fraction`
- `fraction_rho_remaining_ge_1`
- `latest_support_age_ms_at_publish`

如果控制 `delay_ms` 后 coverage/freshness 仍能解释 `during_gain`，则应采用二维 temporal boundary；否则应收缩为 absolute-delay boundary。

## Setup

- Device: server workspace, CPU run
- Detector: not used, GT world-coordinate observations
- ReID: not used
- Dataset: `MATRIX/MATRIX_30x30`
- Smoke frame range: `0-49`
- Formal frame range: `0-999`
- Primary source: D1, `primary_drone_id=0`
- Support sources: D2-D8, `support_drone_ids=1 2 3 4 5 6 7`
- Delay distribution: `fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10`
- FPS: `2.0`, 1 frame = 500 ms
- Seed: `7`
- Tracker: `WorldNearestTracker`, distance threshold `1.0`
- Freshness threshold: `fresh_age_threshold_frames=1`

## Implementation

Code changes:

- `src/tracking/matrix_occlusion.py`
  - added `compute_episode_frame_freshness`
- `scripts/phase2_matrix_occlusion_counterfactual_calibration.py`
  - added `--fresh-age-threshold-frames`
  - added `temporal_boundary_frame_freshness.csv`
  - added episode-level freshness summary fields to `counterfactual_episode_gain.csv`
- `scripts/analyze_occlusion_temporal_boundary.py`
  - added temporal boundary model comparison
- `tests/test_phase2_occlusion.py`
  - added publish-time freshness unit test

New outputs:

```text
temporal_boundary_frame_freshness.csv
temporal_boundary_cell_summary.csv
temporal_boundary_model_comparison.csv
temporal_boundary_decision.md
```

## Smoke Command

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/phase2_matrix_occlusion_counterfactual_calibration.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 49 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_1 fixed_2 \
  --min-episode-length 2 \
  --seed 7 \
  --workers 4 \
  --output-dir outputs/20260722_matrix_occlusion_temporal_boundary_smoke_0_49
```

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/analyze_occlusion_temporal_boundary.py \
  --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_smoke_0_49 \
  --output-dir outputs/20260722_matrix_occlusion_temporal_boundary_smoke_0_49 \
  --seed 7 \
  --bootstrap-iterations 50
```

## Smoke Result

Smoke completed on `0-49` with 3 delay profiles and 20 occlusion episodes per delay. The purpose was wiring validation only; the eligible model rows are too few for a scientific boundary claim.

Key smoke facts:

| Check | Result |
| --- | ---: |
| Counterfactual script exit | pass |
| Analysis script exit | pass |
| `temporal_boundary_frame_freshness.csv` generated | yes |
| `temporal_boundary_model_comparison.csv` generated | yes |
| `M6_delay_publish_freshness` rows | 12 |

## Formal Command

Before formal, generate `POMs` and `annotations_positions` for frames `200-999`.

```bash
cd MATRIX/MATRIX_30x30
MPLCONFIGDIR=/tmp PYTHONPATH=. /usr/bin/python3 -c "from generatePOM import generate_POM; from generateAnnotation import annotate; max_timestep=1000; [ (generate_POM(t), annotate(t, max_timestep)) for t in range(200, max_timestep) ]"
```

Then run:

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/phase2_matrix_occlusion_counterfactual_calibration.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10 \
  --min-episode-length 2 \
  --seed 7 \
  --workers 8 \
  --output-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion
```

```bash
PYTHONPATH=src /usr/bin/python3 \
  scripts/analyze_occlusion_temporal_boundary.py \
  --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion \
  --output-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion \
  --seed 7
```

## Decision Rules

### Gate 1: Measurement Validity

Formal result is interpretable only if:

```text
Run A reproduction mismatch = 0
mask manifest mismatch = 0
lineage ambiguity = 0
no-effective-support gain != 0 rows = 0
```

### Gate 2: Boundary Coverage

Boundary fitting is considered data-ready only if:

```text
delay-rho cells with n>=5 >= 15
delay-rho-coverage cells with n>=5 >= 15
covered delay levels >= 4
covered rho buckets >= 3
covered coverage buckets >= 3
```

### Gate 3: Boundary Form

Compare:

```text
M1: gain ~ delay_s
M2: gain ~ online_support_coverage
M3: gain ~ delay_s + online_support_coverage
M4: gain ~ delay_s + online_support_coverage + interaction
M5: gain ~ delay_s + fraction_rho_remaining_ge_1 + interaction
M6: gain ~ delay_s + mean_latest_support_age_s + no_support_available_fraction
```

Decision:

- `absolute_delay_boundary`: M4 does not improve materially over M1.
- `joint_temporal_boundary`: M4 improves group-CV RMSE by at least 5% and R2 by at least 0.05.
- `boundary_underdetermined`: coverage gate fails.
- `boundary_inconclusive`: coverage gate passes but model signals disagree.

## Verification

```bash
PYTHONPATH=src python -m pytest tests/test_phase2_occlusion.py -q
# 48 passed
```

```bash
PYTHONPATH=src /usr/bin/python3 -m py_compile \
  src/tracking/matrix_occlusion.py \
  scripts/phase2_matrix_occlusion_counterfactual_calibration.py \
  scripts/analyze_occlusion_temporal_boundary.py
# passed
```

Note: `/usr/bin/python3` does not have pytest installed in this environment; pytest verification used the default Python with `PYTHONPATH=src`.

## Formal Result

Formal `0-999` completed after generating MATRIX derived files for frames `200-999`.

Output:

```text
outputs/20260722_matrix_occlusion_temporal_boundary_expansion/
```

Generated files:

```text
aggregate_pipeline_metrics.csv
counterfactual_decision.md
counterfactual_episode_gain.csv
counterfactual_gain_by_cell.csv
lineage_stability_audit.csv
replay_reproduction_audit.csv
temporal_boundary_frame_freshness.csv
temporal_boundary_cell_summary.csv
temporal_boundary_model_comparison.csv
temporal_boundary_decision.md
```

Key formal facts:

| Check | Result |
| --- | ---: |
| Metric episodes | 385 |
| Episode rows | 2310 |
| Frame freshness rows | 46836 |
| Run A reproduction mismatches | 0 |
| Mask manifest mismatch rows | 0 |
| No-effective-support nonzero gain rows | 0 |
| Delay-rho cells with `n>=5` | 8 |
| Delay-rho-coverage cells with `n>=5` | 10 |

Main model comparison:

| Model | R2 | RMSE | Group-CV RMSE |
| --- | ---: | ---: | ---: |
| `M1_delay_only` | 0.458015 | 0.313481 | 0.416513 |
| `M4_delay_coverage_interaction` | 0.758755 | 0.209144 | 0.277068 |

## Current Decision

`measurement_valid_boundary_still_sparse`

The paired counterfactual measurement is valid on `0-999`: reproduction and mask gates pass. The scientific signal favors a joint temporal boundary because delay×coverage interaction strongly improves over delay-only. However, the strict coverage gate still fails, so this run should not yet claim a final numeric harm threshold.

Tracked analysis:

```text
summary_md/experiments/2026-7-22/exp_20260722_001_matrix_occlusion_temporal_boundary_expansion_analysis.md
```

## Next Actions

- [ ] Refine the boundary decision gate: use group-CV and bootstrap stability as the main criterion, with cell sparsity reported as extrapolation risk.
- [ ] Add matched diagnostics within the same `rho_bucket` and within the same `delay_ms`.
- [ ] After the temporal gate is stable, introduce pose/world-coordinate noise to test whether `v * delay / gate_radius` becomes a third boundary dimension.
