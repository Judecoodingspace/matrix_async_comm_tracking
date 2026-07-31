# Current Status

Updated: 2026-07-31

## Latest Research Focus

The current focus is transferring the simulated identity-cue result to frozen
real CNN appearance evidence. `exp_20260731_002_matrix_real_embedding_quality_transfer`
is implemented and pending a user-run smoke/formal. It uses MATRIX GT projected
bboxes with LoS filtering, frozen M3OT-GeM and OSNet embeddings, person-disjoint
two-fold candidate-conditioned threshold calibration, visible terminal progress,
and per-condition checkpoint/resume.

The current decision is `identity_dimension_supported`. At `0.25m` support
world-coordinate noise, high useful-window `world_xy` fixed-lag remains harmful
(`fixed_2` survival delta `-0.077936`, `fixed_3` `-0.078924`), and
covariance-only is still insufficient. `world_xy + covariance + simulated
identity` restores positive survival and reduces IDSW below drop-delayed at
both transition delays: medium cue gives `fixed_2` survival delta `0.289408`
/ IDSW delta `-4.327869` and `fixed_3` `0.167618` / `-1.333333`. The next
step is cue-quality boundary / real appearance message-content ablation, with
checkpoint/resume added before larger formal matrices.

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
scripts/phase2_matrix_occlusion_counterfactual_calibration.py
scripts/analyze_occlusion_temporal_boundary.py
scripts/analyze_occlusion_temporal_boundary_matched.py
scripts/analyze_occlusion_online_proxy_readiness.py
scripts/phase2_matrix_tracker_state_aware_reanchoring.py
scripts/analyze_matrix_fixed_lag_useful_window.py
scripts/phase2_matrix_fixed_lag_temporal_spatial_robustness.py
scripts/phase2_matrix_fixed_lag_simulated_identity_cue_ablation.py
scripts/validate_matrix_dataset.py
src/tracking/support_audit.py
src/tracking/matrix_reanchoring.py
src/tracking/matrix_identity_cue.py
tests/test_matrix_gt.py
tests/test_temporal_boundary_matched.py
tests/test_online_proxy_readiness.py
tests/test_matrix_reanchoring.py
tests/test_fixed_lag_useful_window.py
tests/test_fixed_lag_temporal_spatial_robustness.py
tests/test_matrix_simulated_identity_cue.py
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
- MATRIX temporal boundary expansion smoke completed on frames `0-49`. The
  counterfactual script now writes `temporal_boundary_frame_freshness.csv`, and
  `analyze_occlusion_temporal_boundary.py` writes
  `temporal_boundary_cell_summary.csv`,
  `temporal_boundary_model_comparison.csv`, and
  `temporal_boundary_decision.md`. The smoke generated 12 eligible rows for
  `M6_delay_publish_freshness`; this is wiring validation only, not a boundary
  claim.
- MATRIX temporal boundary expansion formal completed on frames `0-999` after
  generating derived `POMs` and `annotations_positions` for frames `200-999`.
  The formal run has 385 occlusion episodes, 2310 episode rows, and 46836
  frame-freshness rows. Measurement gates pass: Run A mismatch `0`, mask
  mismatch rows `0`, and no-effective-support nonzero gain rows `0`. The
  joint delay×coverage model improves strongly over delay-only (`R2` `0.758755`
  vs `0.458015`, group-CV RMSE `0.277068` vs `0.416513`), but the strict
  coverage gate remains sparse: delay-rho cells with `n>=5` = `8`,
  delay-rho-coverage cells with `n>=5` = `10`.
- MATRIX temporal boundary matched diagnostics completed by reusing the
  `0-999` formal outputs. The refined gate keeps the measurement validity
  checks, replaces strict cell count with model-stability checks, and reports
  sparsity as extrapolation risk. Decision is `early_frame_gap_boundary`:
  `M4_delay_coverage_interaction` remains stable over `M1_delay_only`
  (`0.277068` vs `0.416513` group-CV RMSE; CI `[-0.959284, -0.846348]`), but
  same-delay coverage spread is only `0.005815` and early-frame gain drops
  `0.704866` from 500ms to 1000ms.
- MATRIX early-frame online proxy readiness completed by reusing the `0-999`
  counterfactual episode/frame outputs. Decision is `online_proxy_weak`.
  Episode-level M5 combined online proxy improves F1 (`0.889655` vs delay-only
  `0.813600`) and recall is `0.879260`, but AUC improves only `0.003205`
  (`0.967811` vs `0.964606`). Frame-level M5 has strong AUC (`0.969113`) over
  delay-only (`0.830986`), so the signal is real but not yet sufficient for
  full policy learning.
- MATRIX tracker-state-aware re-anchoring formal completed on frames `0-999`.
  Decision is `fixed_lag_sufficient`. In the transition zone, fixed-lag delayed
  update is very strong: at `1000ms`, `fixed_lag_oosm_lag2/3/5` and
  `state_aware_reanchoring` have occlusion IDF1 `0.870100` / IDSW `829`, versus
  drop-delayed `0.052011` / `5084` and arrival-time `0.155521` / `3988`. At
  `1500ms`, `fixed_lag_oosm_lag3/5` and state-aware have IDF1 `0.724058` /
  IDSW `2101`. Current state-aware ties, but does not beat, the best fixed-lag
  ablation.
- MATRIX fixed-lag useful support window audit completed by reusing the
  `0-999` formal outputs. Decision is `useful_window_modulated_fixed_lag`.
  `delay <= lag` is an eligibility condition, not a guarantee of gain:
  eligible useful-window bucket survival spread is `0.382940`. State-aware
  lag3 at `2500ms` has occlusion IDF1 `0.078017`, while fixed-lag lag5 has
  `0.516013`, confirming that useful correction window size is still a
  controlling factor.
- MATRIX fixed-lag temporal-spatial robustness formal completed on frames
  `0-999`. Measurement gates pass: primary-only invariant mismatch `0`,
  drop-delayed invariant mismatch `0`, primary perturbation mismatches `0`,
  and pose0 prior reproduction mismatch `0`. Decision is
  `temporal_spatial_boundary_identified`: high useful-window fixed-lag remains
  useful at `0.10m` noise (`fixed_2` IDF1 delta `0.107354`, `fixed_3`
  `0.094543`), but at `0.25m` survival delta turns negative (`fixed_2`
  `-0.077936`, `fixed_3` `-0.078924`) and IDSW exceeds drop-delayed.
- MATRIX simulated identity cue ablation formal completed on frames `0-999`.
  Measurement gate passes: primary perturbation mismatches `0`, identity lookup
  key uses no `person_id`, and clean truth is used under noisy support.
  Decision is `identity_dimension_supported`. In high useful-window episodes,
  `fixed_lag_world_xy` remains harmful at `0.25m` noise, but medium
  `fixed_lag_world_xy_covariance_identity` gives survival delta `0.289408` /
  IDSW delta `-4.327869` at 1000ms and `0.167618` / `-1.333333` at 1500ms.

## Recent Commands

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_fixed_lag_temporal_spatial_robustness.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 \
  --lag-frames 1 2 3 5 \
  --pose-noise-levels 0.00 0.10 0.25 0.50 \
  --seed 7 \
  --output-dir outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness

PYTHONPATH=src python -m pytest tests/ -q

PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_fixed_lag_simulated_identity_cue_ablation.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 999 \
  --fps 2 \
  --primary-drone-id 0 \
  --support-drone-ids 1 2 3 4 5 6 7 \
  --delay-profiles fixed_2 fixed_3 \
  --lag-frames 2 3 \
  --pose-noise-m 0.25 \
  --identity-strengths strong medium weak \
  --seed 7 \
  --output-dir outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation

PYTHONPATH=src python -m pytest tests/ -q
```

Notes: noisy `arrival_time_sort` and nonzero-noise `fixed_0` sanity are skipped
by default in this runner because they are computationally expensive and not
part of the main fixed-lag robustness decision. Future long formal runners
should write per-combination checkpoints to support resume.
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

For the occlusion-support temporal boundary, accept `early_frame_gap_boundary`
as the current refined mechanism. Online proxies are useful but weak at the
episode action level, and the next tracker-mechanism experiment shows bounded
fixed-lag delayed update is the strongest current mitigation. Do not enter full
policy learning yet. First test whether fixed-lag OOSM remains robust under
pose/world-coordinate noise and spatial staleness.

## Known Caveats

- The working directory is not a Git worktree, and
  `experiment_validation_plan.md` is absent.
- `rho_episode` and `rho_remaining` are post-hoc analysis variables, not
  real-time gate inputs.
- The 0-999 temporal-boundary result no longer fails solely because of sparse
  delay-rho cell count, but sparsity remains an extrapolation risk. Do not claim
  a final numeric harm threshold; the accepted mechanism-level decision is
  `early_frame_gap_boundary`.
- `online_proxy_weak` means the proxy is not useless. It improves threshold
  behavior and frame-level prediction, but episode-level ranking is already
  dominated by delay-only under current zero-noise fixed-delay controls.

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

## Latest Session Update (2026-07-24 online proxy readiness)

Changed files:

```text
scripts/analyze_occlusion_online_proxy_readiness.py
tests/test_online_proxy_readiness.py
summary_md/experiments/2026-7-24/exp_20260724_001_matrix_early_frame_online_proxy_readiness.md
summary_md/experiments/2026-7-24/exp_20260724_001_matrix_early_frame_online_proxy_readiness_analysis.md
mermaid/exp_20260724_001_matrix_early_frame_online_proxy_readiness/online_proxy_readiness_flow.mmd
mermaid/overall_experiment_design_20260709.mmd
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
GLOSSARY.md
```

Outputs created:

```text
outputs/20260724_matrix_early_frame_online_proxy_readiness_smoke/
outputs/20260724_matrix_early_frame_online_proxy_readiness/
```

Verified results:

- Decision: `online_proxy_weak`.
- Episode rows: `2214`; frame rows: `45624`.
- Episode M5 vs M1: AUC `0.967811` vs `0.964606`, F1 `0.889655` vs
  `0.813600`, recall `0.879260`.
- Frame M5 vs M1: AUC `0.969113` vs `0.830986`.
- Interpretation: online proxy is useful for calibration and frame-level
  prediction, but episode-level ranking gain is too small for full policy
  learning.
- GitHub tracking issue created:
  `https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/3`.

Commands run:

```bash
PYTHONPATH=src /usr/bin/python3 -m py_compile scripts/analyze_occlusion_online_proxy_readiness.py tests/test_online_proxy_readiness.py
PYTHONPATH=src python -m pytest tests/test_online_proxy_readiness.py -q
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src /usr/bin/python3 scripts/analyze_occlusion_online_proxy_readiness.py --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion --matched-dir outputs/20260722_matrix_temporal_boundary_matched_diagnostics --output-dir outputs/20260724_matrix_early_frame_online_proxy_readiness_smoke --max-episode-rows 400 --max-frame-rows 4000 --seed 7
PYTHONPATH=src /usr/bin/python3 scripts/analyze_occlusion_online_proxy_readiness.py --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion --matched-dir outputs/20260722_matrix_temporal_boundary_matched_diagnostics --output-dir outputs/20260724_matrix_early_frame_online_proxy_readiness --seed 7
```

Failed attempts:

```text
The first formal run was interrupted because full frame-level standard-library
logistic group-CV was too slow. The script now keeps full frame dataset output
but uses a deterministic balanced frame sample for auxiliary frame-level model
comparison.
```

## Previous Session Update (2026-07-22 matched diagnostics)

Changed files:

```text
scripts/analyze_occlusion_temporal_boundary_matched.py
tests/test_temporal_boundary_matched.py
summary_md/experiments/2026-7-22/exp_20260722_002_matrix_temporal_boundary_matched_diagnostics.md
summary_md/experiments/2026-7-22/exp_20260722_002_matrix_temporal_boundary_matched_diagnostics_analysis.md
mermaid/exp_20260722_002_matrix_temporal_boundary_matched_diagnostics/matched_diagnostics_flow.mmd
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
GLOSSARY.md
```

Outputs created:

```text
outputs/20260722_matrix_temporal_boundary_matched_diagnostics_smoke/
outputs/20260722_matrix_temporal_boundary_matched_diagnostics/
```

Verified results:

- New analyzer writes `matched_rho_delay_diagnostics.csv`,
  `matched_delay_coverage_diagnostics.csv`, `early_frame_gain_profile.csv`,
  `spillover_gain_diagnostics.csv`,
  `boundary_gate_refined_model_stability.csv`, and
  `boundary_gate_refined_decision.md`.
- Formal decision is `early_frame_gap_boundary`.
- Gate 1 passed: Run A reproduction mismatches `0`, mask mismatch rows `0`,
  no-effective-support nonzero gain rows `0`.
- Gate 2 passed: M4 group-CV RMSE `0.277068` vs M1 `0.416513`, R2 `0.758755`
  vs `0.458015`, delay_x_coverage CI `[-0.959284, -0.846348]`.
- Gate 3 points to early-frame gap: same-delay coverage spread `0.005815`,
  early-frame gain drop `0.704866`.
- GitHub tracking issue created:
  `https://github.com/Judecoodingspace/matrix_async_comm_tracking/issues/2`.

Commands run:

```bash
PYTHONPATH=src /usr/bin/python3 -m py_compile scripts/analyze_occlusion_temporal_boundary_matched.py
PYTHONPATH=src python -m pytest tests/test_temporal_boundary_matched.py -q
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src /usr/bin/python3 scripts/analyze_occlusion_temporal_boundary_matched.py --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion --output-dir outputs/20260722_matrix_temporal_boundary_matched_diagnostics_smoke --max-rows 2000 --seed 7
PYTHONPATH=src /usr/bin/python3 scripts/analyze_occlusion_temporal_boundary_matched.py --input-dir outputs/20260722_matrix_occlusion_temporal_boundary_expansion --output-dir outputs/20260722_matrix_temporal_boundary_matched_diagnostics --seed 7
```

Failed attempts:

```text
`rtk` is not installed in this shell, so status/file reads used regular shell
commands.
```

## Previous Session Update (2026-07-15 paired counterfactual calibration)

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

## Latest Session Update (2026-07-24 tracker-state-aware re-anchoring)

Changed files:

```text
src/tracking/matrix_reanchoring.py
scripts/phase2_matrix_tracker_state_aware_reanchoring.py
tests/test_matrix_reanchoring.py
summary_md/experiments/2026-7-24/exp_20260724_002_matrix_tracker_state_aware_reanchoring.md
summary_md/experiments/2026-7-24/exp_20260724_002_matrix_tracker_state_aware_reanchoring_analysis.md
mermaid/exp_20260724_002_matrix_tracker_state_aware_reanchoring/reanchoring_flow.mmd
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
GLOSSARY.md
mermaid/overall_experiment_design_20260709.mmd
```

Outputs created:

```text
outputs/20260724_matrix_tracker_state_aware_reanchoring_smoke/
outputs/20260724_matrix_tracker_state_aware_reanchoring/
```

Commands run:

```bash
PYTHONPATH=src python -m pytest tests/test_matrix_reanchoring.py -q
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src /usr/bin/python3 -m py_compile src/tracking/matrix_reanchoring.py scripts/phase2_matrix_tracker_state_aware_reanchoring.py tests/test_matrix_reanchoring.py
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_tracker_state_aware_reanchoring.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 49 --fps 2 --primary-drone-id 0 --support-drone-ids 1 2 3 4 5 6 7 --delay-profiles fixed_0 fixed_2 fixed_3 --lag-frames 1 2 3 --seed 7 --output-dir outputs/20260724_matrix_tracker_state_aware_reanchoring_smoke
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_tracker_state_aware_reanchoring.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 999 --fps 2 --primary-drone-id 0 --support-drone-ids 1 2 3 4 5 6 7 --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 fixed_10 --lag-frames 1 2 3 5 --seed 7 --output-dir outputs/20260724_matrix_tracker_state_aware_reanchoring
```

Verified result:

```text
Decision: fixed_lag_sufficient
1000ms: fixed_lag/state-aware occlusion IDF1 0.870100, IDSW 829
1500ms: fixed_lag/state-aware occlusion IDF1 0.724058, IDSW 2101
state-aware ties but does not beat best fixed-lag
```

Failed or corrected attempts:

```text
Initial decision logic incorrectly accepted a tie with fixed-lag as state-aware
trade-off success. The rule was corrected so state-aware must strictly beat the
best fixed-lag/recovery competitor. The formal decision was refreshed from
existing CSVs without rerunning tracker outputs.
```

## Latest Session Update (2026-07-26 fixed-lag temporal-spatial robustness)

Changed files:

```text
src/tracking/matrix_reanchoring.py
scripts/phase2_matrix_fixed_lag_temporal_spatial_robustness.py
tests/test_fixed_lag_temporal_spatial_robustness.py
summary_md/experiments/2026-7-26/exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness.md
summary_md/experiments/2026-7-26/exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness_analysis.md
mermaid/exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness/temporal_spatial_flow.mmd
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
GLOSSARY.md
mermaid/overall_experiment_design_20260709.mmd
```

Outputs created:

```text
outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness_smoke/
outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness/
```

Commands run:

```bash
PYTHONPATH=src python -m pytest tests/test_fixed_lag_temporal_spatial_robustness.py -q
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src /usr/bin/python3 -m py_compile src/tracking/matrix_reanchoring.py scripts/phase2_matrix_fixed_lag_temporal_spatial_robustness.py
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_fixed_lag_temporal_spatial_robustness.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 49 --fps 2 --primary-drone-id 0 --support-drone-ids 1 2 3 4 5 6 7 --delay-profiles fixed_1 fixed_2 --lag-frames 1 2 3 --pose-noise-levels 0.00 0.25 --seed 7 --output-dir outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness_smoke
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_fixed_lag_temporal_spatial_robustness.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 999 --fps 2 --primary-drone-id 0 --support-drone-ids 1 2 3 4 5 6 7 --delay-profiles fixed_0 fixed_1 fixed_2 fixed_3 fixed_5 --lag-frames 1 2 3 5 --pose-noise-levels 0.00 0.10 0.25 0.50 --seed 7 --output-dir outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness
```

Verified result:

```text
Decision: temporal_spatial_boundary_identified
Measurement gates: all pass
0.10m high-window: fixed2 IDF1 delta 0.107354, fixed3 0.094543
0.25m high-window: fixed2 survival delta -0.077936, fixed3 -0.078924
Full tests: 113 passed
```

Implementation notes:

```text
Noisy arrival_time_sort is disabled by default in the robustness runner because
it creates many stale support tracks and is not part of the main fixed-lag
decision. Nonzero-noise fixed_0 sanity is also skipped by default; fixed_0
noise=0.00 still reproduces prior results.
```

## Latest Session Update (2026-07-26 simulated identity cue ablation)

Changed files:

```text
src/tracking/matrix_identity_cue.py
src/tracking/matrix_reanchoring.py
scripts/phase2_matrix_fixed_lag_simulated_identity_cue_ablation.py
tests/test_matrix_simulated_identity_cue.py
summary_md/experiments/2026-7-26/exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation.md
summary_md/experiments/2026-7-26/exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation_analysis.md
mermaid/exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation/sim_identity_flow.mmd
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
GLOSSARY.md
mermaid/overall_experiment_design_20260709.mmd
```

Outputs created:

```text
outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation_smoke/
outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation/
```

Commands run:

```bash
PYTHONPATH=src python -m pytest tests/test_matrix_simulated_identity_cue.py tests/test_matrix_reanchoring.py -q
PYTHONPATH=src /usr/bin/python3 -m py_compile src/tracking/matrix_identity_cue.py src/tracking/matrix_reanchoring.py scripts/phase2_matrix_fixed_lag_simulated_identity_cue_ablation.py
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_fixed_lag_simulated_identity_cue_ablation.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 49 --fps 2 --primary-drone-id 0 --support-drone-ids 1 2 3 4 5 6 7 --delay-profiles fixed_2 fixed_3 --lag-frames 2 3 --pose-noise-m 0.25 --identity-strengths strong medium --seed 7 --output-dir outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation_smoke
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_fixed_lag_simulated_identity_cue_ablation.py --matrix-root MATRIX/MATRIX_30x30 --frame-start 0 --frame-end 999 --fps 2 --primary-drone-id 0 --support-drone-ids 1 2 3 4 5 6 7 --delay-profiles fixed_2 fixed_3 --lag-frames 2 3 --pose-noise-m 0.25 --identity-strengths strong medium weak --seed 7 --output-dir outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation
PYTHONPATH=src python -m pytest tests/ -q
```

Verified result:

```text
Decision: identity_dimension_supported
Measurement gates: all pass
1000ms high-window: world_xy survival delta -0.077936, cov+identity medium 0.289408
1000ms high-window: world_xy IDSW delta 2.259563, cov+identity medium -4.327869
1500ms high-window: world_xy survival delta -0.078924, cov+identity medium 0.167618
1500ms high-window: world_xy IDSW delta 2.915301, cov+identity medium -1.333333
Full tests: 117 passed
```

Implementation notes:

```text
Simulated identity cue uses GT person_id only to generate hidden sensor-side
embedding prototypes. Runtime association uses observation_sensor_key
(capture_time, drone_id, position_id, bbox) and does not read person_id.
The result supports identity as an information dimension, not real ReID
deployment readiness.
```

## Latest Session Update (2026-07-31 identity cue quality boundary)

Changed files:

```text
scripts/phase2_matrix_identity_cue_quality_boundary.py
tests/test_matrix_identity_cue_quality_boundary.py
summary_md/experiments/2026-7-31/exp_20260731_001_matrix_identity_cue_quality_boundary.md
summary_md/experiments/2026-7-31/exp_20260731_001_matrix_identity_cue_quality_boundary_analysis.md
mermaid/exp_20260731_001_matrix_identity_cue_quality_boundary/identity_quality_boundary_flow.mmd
```

Outputs:

```text
outputs/20260731_matrix_identity_cue_quality_boundary_smoke_calibrated/
outputs/20260731_matrix_identity_cue_quality_boundary/
```

Verified result:

```text
Decision: quality_boundary_identified
Measurement valid: 1
Condition checkpoints: 30 / 30
Medium reference reproduction mismatches: 0
Minimum passing tested margin: 0.056747 at threshold 0.20
Largest fully tested failing margin: 0.040019
Boundary interval: (0.040019, 0.056747]
```

The initial global pair calibration selected threshold `0.10` at margin
`0.056747`, but tracking passed only at `0.20`. This establishes the next
methodological requirement: real ReID threshold calibration must use the
geometry-shortlisted candidate distribution.

## Next Command

Design the real/semi-real appearance readiness audit:

```text
MATRIX bbox crops -> ReID/CNN embedding -> geometry candidate shortlist
-> candidate-conditioned same/different similarity
-> calibrated identity threshold -> fixed-lag tracker evaluation
```

Before the next formal, run:

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

## Latest Documentation Update (2026-07-31 idea mainline curation)

Changed files:

```text
ascii_diagrams/07_current_idea_mainline.md
ascii_diagrams/README.md
summary_md/current_status.md
```

The new overview selects the current problem, failure, mechanism, and evidence
terms from `GLOSSARY.md`; links the existing six ASCII explainers; separates
rejected historical branches from the current fixed-lag + geometry +
covariance + identity story; and records that the real-embedding runner is
implemented but not yet experimentally validated.

## Latest Environment Update (2026-07-31 real embedding preflight)

Prepared the local runtime without system-wide installation:

```text
ultralytics 8.4.113
gdown 5.2.2
torchreid 1.4.0 from .venvs/deep-person-reid
OSNet x0.25 MSMT17 checkpoint in weights/osnet_x0_25_msmt17.pth
CUDA device: NVIDIA GeForce RTX 3090
```

Both real embedding backends passed a GPU forward preflight. OSNet produced a
finite normalized 512-D embedding; M3OT YOLO layer-15 + GeM produced a finite
normalized 256-D embedding. A Python 3.8 checkpoint-key compatibility issue in
`src/detection/osnet_reid.py` was fixed and covered by a regression test.

Smoke and formal runs remain intentionally pending for manual execution.
