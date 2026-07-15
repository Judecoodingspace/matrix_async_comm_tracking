# Current Status

Updated: 2026-07-15

## Latest Research Focus

The current focus is now the paired counterfactual value of support during D1
LoS occlusion. The latest formal run calibrates the measurement framework: Run
A exactly reproduces the causal baseline, Run B masks only the target episode
support, and no GT-ID based track repair is used. On MATRIX `0-199`, during
gain is strong at 500ms (`0.910`), still positive at 1000ms (`0.271`), and
near-zero after 1500ms (`0.049`, `0.013`, `0.001`). The boundary form remains
underdetermined because only 8 delay-rho cells have `n>=5`; the next action is
to expand the corrected paired audit to `0-999`.

The original Backfill-centered OOSM direction has been tested and rejected in
the controlled M3OT setup. The viable next direction is to evaluate MATRIX for
timestamp-aware asynchronous multi-UAV MOT, preferably in BEV/world coordinates
rather than ReID-only support fusion. The latest MATRIX follow-up shows that
authority cap plus ambiguity margin improves risk-aware delayed association
over v1/plain uncertain fusion, but still does not beat drop-delayed IDF1 under
moderate pose/world-coordinate noise. The support marginal value audit closes
the geometry-only Stage A condition as a harm-boundary result: support can
reduce pollution, but its net identity value is not enough to beat the
drop-delayed safety baseline under noisy world-coordinate support.

## Assets

Code:

```text
src/detection/yolo_reid.py
src/detection/osnet_reid.py
src/jetson_split_executor.py
src/tracking/delay_injection.py
src/tracking/matrix_gt.py
src/tracking/oosm_baselines.py
src/tracking/mot_metrics.py
scripts/phase1_matrix_async_pose_gt.py
scripts/phase1_matrix_delay_event_diagnostics.py
scripts/phase1_matrix_threshold_stability.py
scripts/phase1_matrix_time_pose_uncertainty.py
scripts/phase1_matrix_risk_aware_delayed_association.py
scripts/phase1_matrix_risk_aware_v2_ablation.py
scripts/phase1_matrix_support_marginal_value_audit.py
scripts/phase1_identity_probe.py
scripts/phase2_candidate_geometry_stress.py
scripts/phase2_backfill_vs_current.py
scripts/phase2_gated_oosm.py
scripts/phase2_common.py
scripts/validate_matrix_dataset.py
src/tracking/support_audit.py
tests/test_matrix_gt.py
```

Concept notes:

```text
ascii_diagrams/README.md
```

Weights:

```text
weights/m3ot_detector_best.pt
weights/visdrone_detector_best.pt
weights/gem_proj_head_l15.pt
```

Data:

```text
data/M3OT -> /home/nvidia/datasets/M3OT_raw/M3OT
data/MATRIX -> /home/nvidia/datasets/MATRIX_raw/MATRIX
MATRIX -> ../../datasets/MATRIX
```

In this server workspace, `MATRIX` resolves to `/mnt/data/yzm/datasets/MATRIX`.
`MATRIX_30x30.zip` has been extracted to `MATRIX/MATRIX_30x30`. The zip did
not include generated `POMs` or `annotations_positions` contents. Frames
`0-199` have now been generated with the MATRIX-provided scripts for GT
threshold-stability experiments.

## Verified Results

- M3OT default pair has 600 aligned frames and 4530 shared
  `(frame_id, track_id)` keys.
- Formal Phase 1 supports A1 in the identity-probe sense: delayed cross-view
  observations carry identity evidence.
- Formal Phase 2a accepts the mechanism: 564 `geometry_flip + history_gap`
  events where capture-time Backfill association succeeds and arrival-time
  association fails.
- Formal Phase 2b rejects broad Backfill: Backfill IDF1 `0.556604` loses to
  `Fuse-at-current + exp decay` IDF1 `0.579130` and to `Discard OOSM` IDF1
  `0.655564`.
- Formal Phase 2c rejects event-gated Backfill: event-gated IDF1 `0.628225`
  improves over global Backfill but remains below `Discard OOSM` and has 29
  more ID switches.
- `scripts/validate_matrix_dataset.py` was implemented and smoke-tested on a
  synthetic MATRIX-like package under `/tmp/matrix_min`.
- MATRIX real-package readiness validation passed on the first 50 timesteps
  after generating POMs and annotations. The sample has 50 annotation files,
  2000 annotation rows, 40 persistent `personID` identities, 0 missing
  `personID`/`positionID` rows, mean 6.612 visible views per row, 50 POM files,
  400 LoS files, 8 drone image directories, and 8000 intrinsic / 8000 extrinsic
  calibration files.
- First MATRIX GT/world-coordinate async pose experiment completed on frames
  `0-49` with 13,223 visible observations and 2,000 frame/person evaluation
  rows. Timestamped pose fusion kept IDF1 `1.000000` and IDSW `0` for all delay
  profiles. Arrival-time fusion degraded with delay: `fixed_3` IDF1
  `0.372500` / 480 IDSW, `fixed_5` IDF1 `0.324500` / 495 IDSW, `fixed_10`
  IDF1 `0.353500` / 514 IDSW, and `uniform_1_10` IDF1 `0.162000` / 870 IDSW.
- MATRIX delay/event diagnostics completed on frames `0-49` with 13,223 visible
  observations, 55 fixed-delay/pipeline runs, and 110,000 per-person trace rows.
  The first harmful fixed delay is `fixed_2` by all three rules: arrival-time
  IDF1 below drop-delayed, IDF1 drop >= 5 points from `fixed_0`, and arrival
  IDSW >= 50. At `fixed_2`, arrival-time fusion has IDF1 `0.115000` / IDSW
  `1143`, drop-delayed has IDF1 `0.846000` / IDSW `251`, and timestamped fusion
  remains IDF1 `1.000000` / IDSW `0`. Event-subset IDSW at `fixed_2`
  concentrates in proximity (`785`), crossing-like (`430`), and high-motion
  (`358`) rows.
- MATRIX threshold stability completed on frames `0-199` after generating
  missing derived files for `50-199`. Seven windows were tested:
  `0-49`, `50-99`, `100-149`, `150-199`, `0-99`, `100-199`, and `0-199`.
  All seven windows have `T_main=2`, `T_drop5=2`, `T_idsw_rate=2`, and
  timestamped sanity passes. Aggregate `0-199`: `fixed_1` arrival-time fusion
  remains useful (IDF1 `0.998000`, IDSW rate `2.625` per 1k GT), while
  `fixed_2` collapses below drop-delayed (arrival IDF1 `0.052875`, IDSW rate
  `617.625` per 1k GT; drop-delayed IDF1 `0.352500`, IDSW rate `253.000` per
  1k GT).
- MATRIX time/pose uncertainty stress completed on frames `0-199`. Zero
  uncertainty matches ideal timestamped fusion exactly. Moderate stress
  `fixed_2 + jitter_pm1_noise_0.50m` fails: IDF1 `0.066875`, IDSW rate
  `408.875` per 1k GT, below drop-delayed IDF1 `0.352500` and IDSW rate
  `253.000` per 1k GT. Jitter-only `jitter_pm1_noise_0.00m` at `fixed_2`
  drops to IDF1 `0.131625`; pose-noise-only `jitter_none_noise_0.50m` drops to
  IDF1 `0.081250`.
- MATRIX risk-aware delayed association v1 completed on frames `0-199` with
  reliable capture time and pose/world-coordinate noise only. Zero pose noise
  preserves oracle behavior: risk-aware IDF1 `1.000000`, IDSW rate `0`.
  Moderate stress `fixed_2 + pose_noise_0.50m` fails: risk-aware IDF1
  `0.062125`, IDSW rate `431.875` per 1k GT, below plain timestamped uncertain
  IDF1 `0.077125` / IDSW rate `354.875` and below drop-delayed IDF1
  `0.352500`. Gate accept rate increases with declared pose noise: `0.885008`
  at `0.25m`, `0.930780` at `0.50m`, and `0.989899` at `1.00m` for `fixed_2`.
- MATRIX risk-aware v2 ablation completed on frames `0-199`. All variants
  preserve zero-noise oracle behavior. At `fixed_2 + pose_noise_0.50m`, v2c
  cap+margin is best: IDF1 `0.177625`, IDSW rate `204.375` per 1k GT, better
  than v1 IDF1 `0.062125` / IDSW rate `431.875` and plain timestamped
  uncertain IDF1 `0.077125` / IDSW rate `354.875`. It still fails the Stage A
  pass condition because drop-delayed IDF1 is `0.352500`.
- MATRIX support marginal value audit completed on frames `0-199` for
  `fixed_2` with pose noise `0.25m`, `0.50m`, and `1.00m`. Decision is
  `close_stage_a_boundary`. V2C remains below drop-delayed IDF1 at all noisy
  levels: `0.153250`, `0.177625`, and `0.286125` vs drop-delayed `0.352500`.
  V2C still beats plain uncertain at `0.50m` and `1.00m`, and lowers IDSW at
  `0.50m`, but row-level support marginal value is negative overall:
  `helpful - harmful - weak/reject = -5615`.
- MATRIX server migration completed to
  `aiso-image@10.16.9.138:/mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/`
  using `migration_matrix_server_files.txt`. All manifest paths exist on the
  server, `validate_matrix_dataset.py --help` works, and transferred weight
  checksums match the Jetson source files. `python3 -m pytest tests/` failed on
  the server because `pytest` is not installed.

## Decision

Do not continue Backfill-centered development on the current M3OT ReID-only
setup.

Do continue only if the project is reframed around MATRIX-style asynchronous
BEV/world-coordinate multi-UAV MOT, after the real MATRIX package passes
field-readiness validation.

The first MATRIX GT experiment accepts timestamped pose fusion as the mainline
mechanism to stress further before detector/ReID noise is introduced. The
threshold-stability experiment accepts 2 frames as the stable harmful-delay
threshold on the `0-199` MATRIX GT slice under current world-coordinate
controls. Time/pose uncertainty stress shows plain timestamped buffering is not
robust enough under tested moderate uncertainty. Risk-aware delayed association
v1 is also insufficient: uncertainty widens the candidate gate without
adequately reducing support authority. V2 authority cap plus ambiguity margin
improves IDF1 and IDSW over v1/plain uncertain, but the support marginal value
audit shows geometry-only support does not provide enough net identity value to
beat drop-delayed under noisy world-coordinate support.

Close the old Stage A requirement that risk-aware geometry-only fusion must
exceed drop-delayed IDF1. Treat drop-delayed as a safety baseline and harm
boundary reference. The next mainline should add information content or change
update mechanics, for example appearance-augmented support risk or
identity/position update separation, rather than continue scalar v2 threshold
sweeps.

## Known Caveats

- The working directory is not a Git worktree, and
  `experiment_validation_plan.md` is absent.
- `rho_episode` and `rho_remaining` are post-hoc analysis variables, not
  real-time gate inputs.
- The 0-199 causal result has only 10 populated delay-rho cells with `n>=5`;
  do not claim a ratio-only threshold from it.

- Phase 2 used GT boxes plus ReID features to isolate OOSM timing; detector
  miss/false-positive behavior was not measured.
- CUDA is unavailable inside the restricted Codex sandbox with
  `NvRmMemInitNvmap failed`; formal CUDA runs succeeded outside the sandbox.
- The shell `python` resolves to `.venvs/headroom/bin/python`; use
  `/usr/bin/python3` for formal experiment runs.
- MATRIX generated annotations/POMs currently cover frames `0-199`. Each POM is
  large, so continue generating only the timestep range needed for each
  experiment unless a full run requires all frames.
- `arrival_time_exp_decay` currently matches `arrival_time_fusion` in the GT
  prototype because weighted state updates are not implemented yet.
- The `0-49` event diagnostics have no `low_visibility` rows because this slice
  has high multi-view coverage. Low-visibility claims require a different range
  or synthetic view-drop stress.
- The timestamp jitter experiment uses coarse frame-level jitter (`±1`/`±2`
  frames), so treat it as a stress test rather than a calibrated sensor-clock
  model.
- The risk-aware v1 experiment assumes reliable capture time. Its negative
  result is about pose/reprojection uncertainty and gate/weight design, not
  capture-time label error.
- The v2 ablation produces large gate diagnostics (`2,262,000` rows for the
  formal run). Future parameter sweeps should disable full per-observation
  diagnostics unless needed.
- The support marginal category is a local trace-alignment attribution proxy,
  not a strict causal counterfactual. Use it for Stage A boundary decisions and
  event-subset prioritization, not as a replacement for full MOT metrics.

## Latest Session Update (2026-07-15 paired counterfactual calibration)

Implemented:

```text
src/tracking/matrix_occlusion.py
scripts/phase2_matrix_occlusion_counterfactual_calibration.py
tests/test_phase2_occlusion.py
```

Formal outputs:

```text
outputs/20260705_matrix_occlusion_counterfactual_measurement_calibration/
summary_md/experiments/2026-7-5/exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration.md
summary_md/experiments/2026-7-5/exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration_analysis.md
mermaid/exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration/counterfactual_calibration_flow.mmd
```

Verified results:

- 456 episode-delay rows from 76 occlusion episodes and 6 delay profiles.
- Run A reproduction mismatches: `0`.
- Mask manifest mismatch rows: `0`.
- Lineage ambiguity: `0`.
- Mean during gain: `0ms 0.908`, `500ms 0.910`, `1000ms 0.271`,
  `1500ms 0.049`, `2500ms 0.013`, `5000ms 0.001`.
- Decision: `measurement_valid_but_underdetermined`.

Verification:

```text
PYTHONPATH=src python -m pytest tests/ -q  # 80 passed
PYTHONPATH=src /usr/bin/python3 -m py_compile src/tracking/matrix_occlusion.py scripts/phase2_matrix_occlusion_counterfactual_calibration.py  # passed
```

Exact next action: generate MATRIX derived files for frames `200-999`, then run:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_occlusion_counterfactual_calibration.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10 \
  --min-episode-length 2 \
  --seed 7 \
  --workers 8 \
  --output-dir outputs/20260705_matrix_occlusion_counterfactual_measurement_calibration_expanded
```

## Latest Session Update (2026-06-30 delay-ratio and causal OOSM)

Implemented:

```text
src/tracking/matrix_gt.py
src/tracking/matrix_occlusion.py
src/tracking/delay_injection.py
scripts/phase2_matrix_occlusion_delay_ratio_audit.py
scripts/phase2_matrix_causal_oosm_delay_ratio_audit.py
tests/test_phase2_occlusion.py
```

Formal outputs:

```text
outputs/20260630_matrix_occlusion_delay_ratio_audit/
outputs/20260630_matrix_causal_oosm_delay_ratio_audit/
```

Verification:

```text
PYTHONPATH=src python -m pytest tests/ -q  # 75 passed
PYTHONPATH=src /usr/bin/python3 -m py_compile ...  # passed
```

Exact next action: generate MATRIX derived files for frames `200-999`, then
repeat both audits with `--frame-end 999`.

Post-analysis correction: before that expansion, add persistent track-ID
reconciliation and a paired leave-one-episode-support-out counterfactual. The
current global rho-bucket slicing is descriptive because tracker state crosses
episode boundaries and rollback can change track-ID allocation order.

## Latest Session Update (2026-06-26 Stage A support audit)

Changed files:

```text
src/tracking/support_audit.py
scripts/phase1_matrix_support_marginal_value_audit.py
tests/test_matrix_gt.py
GLOSSARY.md
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
summary_md/experiments/2026-6-26/exp_20260626_001_matrix_support_marginal_value_audit.md
summary_md/experiments/2026-6-26/exp_20260626_001_matrix_support_marginal_value_audit_analysis.md
mermaid/exp_20260626_001_matrix_support_marginal_value_audit/support_marginal_value_flow.mmd
```

Outputs created:

```text
outputs/20260626_matrix_support_marginal_value_audit_smoke/
outputs/20260626_matrix_support_marginal_value_audit/support_marginal_value_summary.csv
outputs/20260626_matrix_support_marginal_value_audit/support_marginal_value_by_event_subset.csv
outputs/20260626_matrix_support_marginal_value_audit/support_gate_outcome_breakdown.csv
outputs/20260626_matrix_support_marginal_value_audit/support_only_case_samples.csv
outputs/20260626_matrix_support_marginal_value_audit/stage_a_transition_decision.md
```

Verified results:

- Added `src/tracking/support_audit.py` for trace alignment, support marginal
  category classification, gate outcome aggregation, and category summaries.
- Added `scripts/phase1_matrix_support_marginal_value_audit.py`.
- Added regression tests for trace alignment, mutually exclusive support
  categories, gate aggregation count conservation, and support-only summary
  coverage.
- Smoke run on frames `0-49` completed and generated all planned output files.
- Formal run on frames `0-199` completed with decision
  `close_stage_a_boundary`.
- V2C remains below drop-delayed IDF1 at all noisy levels, while net support
  marginal value is negative overall (`-5615`).

Commands run:

```bash
PYTHONPATH=src python -m pytest tests/test_matrix_gt.py
PYTHONPATH=src /usr/bin/python3 -m py_compile src/tracking/support_audit.py scripts/phase1_matrix_support_marginal_value_audit.py src/tracking/matrix_gt.py tests/test_matrix_gt.py
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_support_marginal_value_audit.py --help
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_support_marginal_value_audit.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 49 --delay-profiles fixed_2 --pose-noise-levels 0.25 0.50 --seed 7 --output-dir outputs/20260626_matrix_support_marginal_value_audit_smoke
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_support_marginal_value_audit.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 199 --delay-profiles fixed_2 --pose-noise-levels 0.25 0.50 1.00 --seed 7 --output-dir outputs/20260626_matrix_support_marginal_value_audit
```

Failed attempts:

```text
None in this session. The AGENTS.md-preferred `rtk` wrapper is not installed
in this workspace, so raw shell commands were used.
```

## Previous Session Update (2026-06-26 Risk v2 analysis)

Changed files:

```text
tests/test_matrix_gt.py
summary_md/current_status.md
summary_md/experiments/2026-6-25/exp_20260625_004_matrix_risk_aware_v2_ablation_analysis_results/README.md
summary_md/experiments/2026-6-25/exp_20260625_004_matrix_risk_aware_v2_ablation_analysis_results/enhanced_analysis.md
summary_md/experiments/2026-6-25/exp_20260625_004_matrix_risk_aware_v2_ablation_analysis_results/enhanced_analysis_zh.md
```

Verified results:

- Risk-aware v2 ablation implementation, formal outputs, and tracked
  experiment records already exist.
- Added a deterministic regression test that confirms v2 gate diagnostics are
  reproducible under a fixed seed.
- Confirmed `risk_v2_gate_diagnostics.csv` contains the requested v2 fields:
  residual distance, uncertainty scale, observation sigma, d1/d2/margin,
  authority cap, base/final weight, accept flag, and reject reason.
- Current formal decision remains `risk_v2_needs_redesign`: v2c is best, but no
  v2 pipeline passes the fixed_2 + pose_noise_0.50m Stage A rule.
- Created an enhanced analysis package under
  `summary_md/experiments/2026-6-25/exp_20260625_004_matrix_risk_aware_v2_ablation_analysis_results/`.
  It follows the 7-dimension framework and adds gate diagnostics, event-subset
  interpretation, and an explicit Stage A transition judgment.
- Added a Chinese version of the enhanced analysis for direct handoff use.

Commands run:

```bash
PYTHONPATH=src python -m pytest tests/test_matrix_gt.py
PYTHONPATH=src /usr/bin/python3 -m py_compile src/tracking/matrix_gt.py scripts/phase1_matrix_risk_aware_v2_ablation.py tests/test_matrix_gt.py
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_risk_aware_v2_ablation.py --help
head -n 1 outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_gate_diagnostics.csv
head -n 5 outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_ablation_summary.csv
awk -F, 'NR==1 || ($4=="fixed_2" && ($1=="pose_noise_0.50m" || $1=="baseline")) {print}' outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_metrics.csv
awk -F, 'NR==1 || ($2=="fixed_2" && $3=="pose_noise_0.50m") {print}' outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_gate_summary.csv
rg -n "^## [1-7]\\. |^## 流程图|risk_v2_needs_redesign|0\\.177625|support_only|Stage A" summary_md/experiments/2026-6-25/exp_20260625_004_matrix_risk_aware_v2_ablation_analysis_results/enhanced_analysis.md
```

Failed attempts:

```text
Initial pytest run failed because the new test used Python 3.9+ `list[...]`
annotations while the default `python` is Python 3.8. The test was changed to
Python 3.8-compatible syntax and then passed.
```

## Previous Session Update (2026-06-25)

Changed files:

```text
src/tracking/matrix_gt.py
scripts/phase1_matrix_risk_aware_v2_ablation.py
tests/test_matrix_gt.py
GLOSSARY.md
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
summary_md/experiments/2026-6-25/exp_20260625_004_matrix_risk_aware_v2_ablation.md
summary_md/experiments/2026-6-25/exp_20260625_004_matrix_risk_aware_v2_ablation_analysis.md
mermaid/exp_20260625_004_matrix_risk_aware_v2_ablation/risk_v2_ablation_flow.mmd
```

Outputs created:

```text
outputs/20260625_matrix_risk_aware_v2_ablation_smoke/
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_metrics.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_event_subset_metrics.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_gate_diagnostics.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_gate_summary.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_ablation_summary.csv
outputs/20260625_matrix_risk_aware_v2_ablation/risk_v2_decision.md
```

Commands run:

```bash
PYTHONPATH=src python -m pytest tests/test_matrix_gt.py
PYTHONPATH=src /usr/bin/python3 -m py_compile src/tracking/matrix_gt.py scripts/phase1_matrix_risk_aware_v2_ablation.py
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_risk_aware_v2_ablation.py --help
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_risk_aware_v2_ablation.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 49 --seed 7 --output-dir outputs/20260625_matrix_risk_aware_v2_ablation_smoke
PYTHONPATH=src /usr/bin/python3 scripts/phase1_matrix_risk_aware_v2_ablation.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 199 --seed 7 --output-dir outputs/20260625_matrix_risk_aware_v2_ablation
```

Failed attempts:

```text
git status --short failed because this directory is not a Git worktree.
```

## Next Command

Design the next mechanism experiment around appearance-augmented support risk
or identity/position update separation. Use the support audit output as the
diagnostic baseline:

```bash
sed -n '1,220p' summary_md/experiments/2026-6-26/exp_20260626_001_matrix_support_marginal_value_audit_analysis.md
```

The next experiment should keep `drop_delayed`, `timestamped_uncertain_fusion`,
v1, v2a, and v2c as required baselines. Use `personID` as the identity key and
treat `positionID` as a per-frame grid/location key rather than a stable
identity.
