# Observation-level asynchronous fusion milestone complete

## Scope

The completed experiments validate delayed cross-view **observation-to-track**
fusion under controlled MATRIX conditions. This milestone is not a complete
tracklet-level or end-to-end MVMOT system.

## Accepted findings

- Capture-time alignment is necessary; arrival-time fusion is unsafe.
- Fixed-lag replay is the strongest simple online mitigation.
- Useful support window modulates fixed-lag gain.
- Geometry-only support becomes harmful near 0.25m controlled world-XY noise.
- OSNet identity evidence is useful as candidate authorization.
- Updating a shared support appearance template is weaker than a
  primary-anchored identity gate.

## Completed experiment chain

### M3OT falsification

- [x] `exp_20260616_001_oosm_backfill_smoke`
- [x] `exp_20260616_002_event_gated_oosm`

### MATRIX observation-level timing and geometry

- [x] `exp_20260621_001_matrix_readiness`
- [x] `exp_20260622_001_matrix_async_pose_gt`
- [x] `exp_20260623_001_matrix_delay_event_diagnostics`
- [x] `exp_20260625_001_matrix_threshold_stability`
- [x] `exp_20260625_002_matrix_time_pose_uncertainty`
- [x] `exp_20260625_003_matrix_risk_aware_delayed_association`
- [x] `exp_20260625_004_matrix_risk_aware_v2_ablation`
- [x] `exp_20260626_001_matrix_support_marginal_value_audit`

### Occlusion causality and temporal boundary

- [x] `exp_20260630_002_matrix_occlusion_delay_ratio_audit`
- [x] `exp_20260630_003_matrix_causal_oosm_delay_ratio_audit`
- [x] `exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration`
- [x] `exp_20260722_001_matrix_occlusion_temporal_boundary_expansion`
- [x] `exp_20260722_002_matrix_temporal_boundary_matched_diagnostics`
- [x] `exp_20260724_001_matrix_early_frame_online_proxy_readiness`

### Fixed-lag mitigation and multi-cue evidence

- [x] `exp_20260724_002_matrix_tracker_state_aware_reanchoring`
- [x] `exp_20260726_001_matrix_fixed_lag_useful_window_audit`
- [x] `exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness`
- [x] `exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation`
- [x] `exp_20260731_001_matrix_identity_cue_quality_boundary`
- [x] `exp_20260731_002_matrix_real_embedding_quality_transfer`
- [x] `exp_20260801_001_matrix_identity_position_update_separation_audit`

## Latest experiment

- `exp_20260801_001_matrix_identity_position_update_separation_audit`
- decision: `identity_gate_only_supported`
- OSNet occlusion IDF1 at fixed_2/fixed_3: `0.386625/0.305918`
- simulated-medium headroom recovery: `71.66%/68.09%`

## Durable records

- `summary_md/experiments/INDEX.md`
- `summary_md/current_experiment_stage.md`
- `summary_md/experiments/2026-8-1/exp_20260801_001_matrix_identity_position_update_separation_audit_analysis.md`
- `summary_md/decisions/20260801_incremental_tracklet_update_transition.md`

## Decision

Close the observation-level mechanism milestone and transition to incremental
local-tracklet updates.
