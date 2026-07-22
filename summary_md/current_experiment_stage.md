# Current Experiment Stage

This is the short handoff for the MATRIX asynchronous multi-UAV MOT project.

## Current Mainline

- The old M3OT ReID-only Backfill direction was rejected.
- The active question is how asynchronous communication of pose/world-coordinate
  observations affects persistent multi-UAV multi-object tracking.
- The current mainline is MATRIX GT/world-coordinate tracking before
  detector/ReID noise.
- Use `personID` as the identity key.
- Treat `positionID` as a per-frame grid/location key, not a stable identity.
- Timestamped pose fusion is now the accepted mechanism to stress further:
  delayed support observations should be associated at capture time, not arrival
  time.
- Latest support marginal value audit shows authority cap plus ambiguity
  margin is the best geometry-only variant, but support marginal value remains
  negative under noisy world-coordinate support. The geometry-only Stage A
  condition is now closed as a harm-boundary result.

## Current Data

- Dataset root: `MATRIX/MATRIX_30x30`
- The first expanded validated range is frames `0-999`.
- Generated derived files for frames `0-999`:
  - `MATRIX/MATRIX_30x30/POMs/rectangles_*.pom`
  - `MATRIX/MATRIX_30x30/annotations_positions/*.json`
- Readiness report:
  `summary_md/experiments/2026-6-21/matrix_dataset_readiness.md`

## Current Code

- Loader and GT async tracker:
  `src/tracking/matrix_gt.py`
- Experiment CLIs:
  - `scripts/phase1_matrix_async_pose_gt.py`
  - `scripts/phase1_matrix_delay_event_diagnostics.py`
  - `scripts/phase1_matrix_threshold_stability.py`
  - `scripts/phase1_matrix_time_pose_uncertainty.py`
  - `scripts/phase1_matrix_risk_aware_delayed_association.py`
  - `scripts/phase1_matrix_risk_aware_v2_ablation.py`
  - `scripts/phase1_matrix_support_marginal_value_audit.py`
  - `scripts/phase2_matrix_occlusion_counterfactual_calibration.py`
  - `scripts/analyze_occlusion_temporal_boundary.py`
- Support audit helpers:
  `src/tracking/support_audit.py`
- Tests:
  `tests/test_matrix_gt.py`

## Latest Result

Experiments:

```text
summary_md/experiments/2026-6-30/exp_20260630_002_matrix_occlusion_delay_ratio_audit.md
summary_md/experiments/2026-6-30/exp_20260630_003_matrix_causal_oosm_delay_ratio_audit.md
summary_md/experiments/2026-7-5/exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration.md
summary_md/experiments/2026-7-22/exp_20260722_001_matrix_occlusion_temporal_boundary_expansion.md
summary_md/experiments/2026-7-22/exp_20260722_002_matrix_temporal_boundary_matched_diagnostics.md
```

Latest causal/counterfactual result:

- Offline timestamped correction is delay-invariant on `0-999`: occlusion IDF1
  `0.872278` at every delay.
- Causal online occlusion IDF1 is near the offline upper bound at 500ms
  (`0.865872`) but drops sharply at 1000ms (`0.225852`) and 5000ms
  (`0.128107`).
- Paired counterfactual measurement calibration is now complete on `0-199`:
  Run A reproduction mismatches `0`, mask mismatch rows `0`, and lineage
  ambiguity `0`.
- During-gain confirms strong support value at short delay and rapid decay:
  `500ms` mean gain `0.910`, `1000ms` `0.271`, `1500ms` `0.049`,
  `2500ms` `0.013`, and `5000ms` `0.001`.
- The boundary form is now clearer but not final: delay×coverage interaction is
  much stronger than delay-only (`M4` group-CV RMSE `0.277068` vs `M1`
  `0.416513`, R2 `0.758755` vs `0.458015`), but the strict coverage gate still
  fails with only `8` delay-rho cells and `10` delay-rho-coverage cells at
  `n>=5`.
- Ratio-only is disfavored: within `rho<0.25`, mean gain drops from `0.915576`
  at 500ms to `0.146273` at 1000ms, `0.023258` at 1500ms, and `0.008351` at
  2500ms.
- Temporal boundary expansion formal `0-999` is complete, and the follow-up
  matched diagnostics are complete.
- Refined decision is now `early_frame_gap_boundary`. Measurement remains valid:
  Run A reproduction mismatches `0`, mask mismatch rows `0`, and
  no-effective-support nonzero gain rows `0`.
- Model stability passes after relaxing strict cell count into extrapolation
  risk: `M4_delay_coverage_interaction` group-CV RMSE `0.277068` vs
  `M1_delay_only` `0.416513`, R2 `0.758755` vs `0.458015`, and
  `delay_x_coverage` CI `[-0.959284, -0.846348]` does not cross zero.
- Matched diagnostics show the clearest mechanism is early online support gap,
  not simple coverage buckets. Same-delay coverage spread is only `0.005815`,
  while early-frame gain drops by `0.704866` from 500ms to 1000ms.

Previous Stage A result:

Experiment:

```text
summary_md/experiments/2026-6-26/exp_20260626_001_matrix_support_marginal_value_audit.md
```

Output:

```text
outputs/20260626_matrix_support_marginal_value_audit/
```

Key result:

- Decision is `close_stage_a_boundary`.
- V2C remains below drop-delayed IDF1 at all noisy levels:
  `0.25m` IDF1 `0.153250`, `0.50m` IDF1 `0.177625`, and `1.00m` IDF1
  `0.286125`, vs drop-delayed IDF1 `0.352500`.
- V2C still improves over plain uncertain fusion at `0.50m` and `1.00m` and
  lowers IDSW at `0.50m`, so the gate has value as harm control.
- Row-level support marginal value is negative overall:
  `helpful - harmful - weak/reject = -5615` across the three noisy levels.

## Current Decision

Accepted: timestamped pose/world-coordinate fusion is worth expanding on
MATRIX. Stale support observations can be worse than dropping support entirely
when fused at arrival time. The first measured harmful-delay threshold on the
validated `0-199` MATRIX GT slice is 2 frames. Stage A is now **closed as a
harm-boundary result**: geometry-only gate under GT identity has a documented
decision blind spot (pose noise and identity confusion are indistinguishable
on Mahalanobis distance alone).

The drop-delayed baseline is repositioned as a **safety baseline / harm
boundary reference**, not as a required IDF1 lower bound.

**Research direction clarified (2026-06-30 discussion with supervisor)**:
- The work is positioned as a **tracking mechanism paper**, NOT a
  resource-allocation paper.
- Core contribution: Risk-Aware Delayed Association algorithm with (1)
  capture-time back-propagation, (2) multi-dimensional risk gate, (3)
  per-dimension decay-weighted update.
- Communication asynchrony is the **perturbation to be handled**, not a
  variable to be optimized.
- Message content types (pose, bbox, ReID, covariance) are reframed as
  **information dimensions** for the risk gate, each with its own temporal
  decay characteristic — NOT as transmission options to optimize for bandwidth.

**Supervisor's three directions**:
1. **Occlusion scenario**: Move experiments from Simple scenario to Complex
   scenario with per-camera Line-of-Sight (LoS) filtering. MATRIX provides
   `pedestrianLoS.py` for this. In occluded scenes, support observations carry
   non-zero marginal information gain → the algorithm has room to demonstrate
   value. No dataset change needed.
2. **Delay-frame sync**: MATRIX extracted at 2 FPS → 1 frame = 500 ms. All
   delay profiles must report both frame count and milliseconds.
3. **Message content as information dimensions**: The multi-dimensional risk
   gate requires ablating which dimensions contribute to decision quality.
   Communication cost of each dimension is reported as deployment context
   (in Discussion section), NOT as the paper's core contribution.

## Next Action

Immediate next action:

1. Design an online-proxy readiness experiment for the early-frame gap
   mechanism. Candidate proxy variables: `latest_support_age_ms`,
   `time_since_last_primary_seen`, `frames_since_support_arrived`, and
   early occlusion run length.
2. Keep `rho_episode` as a post-hoc diagnostic only; do not use it as an online
   gate input because the true occlusion duration is unknown until the episode
   ends.
3. After online proxy readiness, add pose/world-coordinate noise and test
   whether `v*delay/gate_radius` becomes a third boundary dimension.

Deferred multi-cue mainline:

Next mainline (Phase 2: Multi-Dimensional Risk Gate):

**P0 — Foundation**:
1. Implement delay-frame sync: add `frames_to_ms()` / `ms_to_frames()` to
   `delay_injection.py`, based on MATRIX 2 FPS (500 ms/frame). Report all
   delays in both units.
2. Identify Complex scenario frame range and apply LoS filtering to find
   frames where main UAV is occluded but at least one support UAV has LoS.

**P0 — Core experiment**:
3. Design and run a **multi-dimensional risk gate ablation**:
   - Gate dimensions: (a) world-coordinate, (b) +covariance, (c) +velocity,
     (d) +bbox-consistency, (e) +simulated-identity, (f) full multi-dim.
   - Each configuration tested under the same delay × noise matrix as Stage A.
   - Output: per-configuration IDF1/IDSW + per-dimension contribution analysis.

**P1 — Mechanism**:
4. Test identity/position update separation: allow noisy support to contribute
   weak position evidence without rewriting identity state.

**Required baselines for all experiments**:
- `sync_oracle` (upper bound)
- `drop_delayed` (safety baseline / lower bound)
- `arrival_time_fusion` (naive async baseline)
- `timestamped_uncertain_fusion` (Stage A plain timestamped)
- `risk_aware_v2c` (best Stage A geometry-only variant)

## Literature Review (2026-06-26)

A targeted literature review on the role of support views in MVMOT and whether
two-stage method performance is dominated by single-view tracker quality:

```text
relatedwork/20260626_mvmot_support_view_role_literature_review.md
```

Key takeaways relevant to roadmap decisions:

- Two-stage methods (track-then-associate) inherently make support views
  auxiliary; single-view tracker quality is the performance upper bound.
  This is documented in GMT (CVPR 2026), Dynamic Message Passing NN (IEEE 2024),
  and OCMCTrack (CVPR 2024W).
- SCFusion (arXiv:2509.08421) shows single-view quality is a necessary but
  not sufficient condition for fusion quality — per-view auxiliary loss (β=0.1)
  amplifies fusion IDF1 to 95.9% on WildTrack.
- The current Stage A finding (risk-aware < drop-delayed under pose noise) is
  consistent with literature expectations, not an anomalous failure.
- Five roadmap-turn questions are posed in the review for Codex-assisted
  judgment. The three most actionable: (1) is Stage A pass condition #3
  theoretically attainable? (2) should the roadmap switch from serial to
  parallel multi-cue gate? (3) should the strategic contribution be reframed
  from "beating drop-delayed" to "systematically quantifying the harm
  threshold of asynchronous support"?
- Literature favors either relaxing Stage A pass condition (option B: risk-aware >
  plain-uncertain under noise, already satisfied by v2c) or accepting Stage A as
  complete and advancing to Stage B (option C).
