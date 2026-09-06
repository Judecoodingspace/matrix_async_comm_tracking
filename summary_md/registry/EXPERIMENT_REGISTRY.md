# Logical Experiment Registry

This is a navigation registry, not a new scientific evaluation.  It condenses
the tracked [experiment index](../experiments/INDEX.md), current handoffs, and
the cited primary reports so that readers can find an experiment without
walking every historical directory.  Status and paper-readiness labels below
are documentation classifications only; the original card/report remains the
authority for each experiment's evidence and decision.

## Main research map

```text
Mechanism line (MATRIX, observation/tracklet experiments)
  mainline: delay harm -> uncertainty/authority -> fixed-lag/identity evidence
  diagnostic/negative: Backfill and geometry-only limits; local-tracklet blocks

Communication line (MDMT / MIA)
  mainline: local-tracklet readiness -> packet equivalence -> channel cascade
            -> E023 candidate/Supplement mechanism -> non-test onset validation
  current: 15-pair development completed; locked d1 needs holdout confirmation

Route-A diagnostic line (packet census / Homography repair)
  diagnostic: valid successor Z0 workload census; predecessor is historical invalid
```

`mainline` marks evidence that informed the active lineage.  `diagnostic` marks
measurement, readiness, or descriptive evidence.  `negative` marks a rejected
direction retained as evidence.  `superseded` marks a historical predecessor
that must not be mixed into its successor.

## Immutability and date convention

- Legacy experiment paths are immutable.  In particular, no historical
  directory is moved or renamed by this registry.
- A historical directory date identifies an experiment's **inception/root
  date**, not every later activity date.  An experiment can legitimately have
  implementation, execution, and analysis activities on later dates.
- Activity dates are recorded separately in
  [EXPERIMENT_TIMELINE.md](EXPERIMENT_TIMELINE.md).
- Only future experiments use the prospective path convention
  `summary_md/experiments/YYYY-MM-DD/<experiment_id>/`.  Existing
  `YYYY-M-D` paths remain canonical legacy paths.

## Readiness vocabulary

`READY`, `DEVELOPMENT_ONLY`, `NEEDS_HOLDOUT`, `DIAGNOSTIC_ONLY`,
`NEGATIVE_EVIDENCE`, `SUPERSEDED`, and `UNKNOWN` are the only readiness labels
used here.  They describe the present scientific role, not a retrospective
change to the original result.

## Complete experiment inventory

The primary artifact column points to the tracked card/report or the immutable
ignored-output root already recorded by the Index.  “Index card” refers to the
row in [INDEX.md](../experiments/INDEX.md), which retains the full method,
output, result, and decision.

| Experiment ID / start | Research question; dataset/protocol | Status | Main artifact | Current scientific role | Paper readiness |
| --- | --- | --- | --- | --- | --- |
| `exp_20260616_001_oosm_backfill_smoke` / 2026-06-16 | Can OOSM Backfill beat simple alternatives? M3OT val paired views. | complete | `outputs/20260616_oosm_backfill_validation/`; Index card | negative: broad Backfill rejected | `NEGATIVE_EVIDENCE` |
| `exp_20260616_002_event_gated_oosm` / 2026-06-16 | Does observable event-gating rescue Backfill? M3OT val paired views. | complete | `outputs/20260616_oosm_backfill_validation/phase2c_*`; Index card | negative follow-up | `NEGATIVE_EVIDENCE` |
| `exp_20260621_001_matrix_readiness` / 2026-06-21 | Are MATRIX identity, pose, and calibration fields usable? MATRIX. | complete | `experiments/2026-6-21/matrix_dataset_readiness.md` | mainline dataset authority | `DIAGNOSTIC_ONLY` |
| `exp_20260622_001_matrix_async_pose_gt` / 2026-06-22 | Does capture-time pose fusion avoid stale-support harm? MATRIX `0-49`. | complete | `outputs/20260622_matrix_async_pose_gt/`; Index card | mechanism mainline foundation | `DEVELOPMENT_ONLY` |
| `exp_20260623_001_matrix_delay_event_diagnostics` / 2026-06-23 | Where does harmful arrival-time delay begin? MATRIX `0-49`. | complete | `outputs/20260623_matrix_delay_event_diagnostics/`; Index card | diagnostic threshold evidence | `DIAGNOSTIC_ONLY` |
| `exp_20260625_001_matrix_threshold_stability` / 2026-06-25 | Is the harmful delay threshold stable? MATRIX `0-199`. | complete | `outputs/20260625_matrix_threshold_stability/`; Index card | mechanism boundary evidence | `DEVELOPMENT_ONLY` |
| `exp_20260625_002_matrix_time_pose_uncertainty` / 2026-06-25 | Is timestamped fusion robust to time/pose error? MATRIX `0-199`. | complete | `outputs/20260625_matrix_time_pose_uncertainty/`; Index card | uncertainty boundary | `DIAGNOSTIC_ONLY` |
| `exp_20260625_003_matrix_risk_aware_delayed_association` / 2026-06-25 | Does risk-aware delayed association v1 help? MATRIX `0-199`. | complete | `outputs/20260625_matrix_risk_aware_delayed_association/`; Index card | rejected v1 | `NEGATIVE_EVIDENCE` |
| `exp_20260625_004_matrix_risk_aware_v2_ablation` / 2026-06-25 | Which authority-control ablation helps under noise? MATRIX `0-199`. | complete | `outputs/20260625_matrix_risk_aware_v2_ablation/`; Index card | partial mainline evidence | `DEVELOPMENT_ONLY` |
| `exp_20260626_001_matrix_support_marginal_value_audit` / 2026-06-26 | Is noisy geometry-only support marginally useful? MATRIX `0-199`. | complete | `outputs/20260626_matrix_support_marginal_value_audit/`; Index card | Stage-A harm boundary | `NEGATIVE_EVIDENCE` |
| `exp_20260630_002_matrix_occlusion_delay_ratio_audit` / 2026-06-30 | Describe occlusion-duration/delay ratios. MATRIX `0-199`. | complete | `outputs/20260630_matrix_occlusion_delay_ratio_audit/`; Index card | descriptive diagnostic | `DIAGNOSTIC_ONLY` |
| `exp_20260630_003_matrix_causal_oosm_delay_ratio_audit` / 2026-06-30 | Test causal online OOSM delay-ratio effects. MATRIX `0-199`. | complete | `outputs/20260630_matrix_causal_oosm_delay_ratio_audit/`; Index card | causal diagnostic | `DIAGNOSTIC_ONLY` |
| `exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration` / 2026-07-05 | Validate paired counterfactual support measurement. MATRIX `0-199`. | complete | `outputs/20260705_matrix_occlusion_counterfactual_measurement_calibration/`; Index card | measurement calibration | `DIAGNOSTIC_ONLY` |
| `exp_20260722_001_matrix_occlusion_temporal_boundary_expansion` / 2026-07-22 | Extend temporal boundary evidence. MATRIX `0-999`. | complete | `outputs/20260722_matrix_occlusion_temporal_boundary_expansion/`; analysis card | mainline boundary evidence | `DEVELOPMENT_ONLY` |
| `exp_20260722_002_matrix_temporal_boundary_matched_diagnostics` / 2026-07-22 | Diagnose matched temporal-boundary gates. MATRIX `0-999`. | complete | `outputs/20260722_matrix_temporal_boundary_matched_diagnostics/`; analysis card | diagnostic refinement | `DIAGNOSTIC_ONLY` |
| `exp_20260724_001_matrix_early_frame_online_proxy_readiness` / 2026-07-24 | Is an early-frame online proxy sufficient? MATRIX `0-999`. | complete | `outputs/20260724_matrix_early_frame_online_proxy_readiness/`; analysis card | weak-proxy diagnostic | `DIAGNOSTIC_ONLY` |
| `exp_20260724_002_matrix_tracker_state_aware_reanchoring` / 2026-07-24 | Does state-aware reanchoring beat fixed lag? MATRIX `0-999`. | complete | `outputs/20260724_matrix_tracker_state_aware_reanchoring/`; analysis card | fixed-lag mainline evidence | `DEVELOPMENT_ONLY` |
| `exp_20260726_001_matrix_fixed_lag_useful_window_audit` / 2026-07-26 | What predicts fixed-lag usefulness? MATRIX `0-999`. | complete | `outputs/20260726_matrix_fixed_lag_useful_window_audit/`; analysis card | mechanism diagnostic | `DIAGNOSTIC_ONLY` |
| `exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness` / 2026-07-26 | How robust is fixed lag to spatial noise? MATRIX `0-999`. | complete | `outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness/`; analysis card | robustness boundary | `DEVELOPMENT_ONLY` |
| `exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation` / 2026-07-26 | Can identity content repair geometry-only limits? MATRIX `0-999`. | complete | `outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation/`; analysis card | identity-dimension evidence | `DEVELOPMENT_ONLY` |
| `exp_20260731_001_matrix_identity_cue_quality_boundary` / 2026-07-31 | What identity-cue quality is needed? MATRIX `0-999`. | complete | `outputs/20260731_matrix_identity_cue_quality_boundary/`; analysis card | quality diagnostic | `DIAGNOSTIC_ONLY` |
| `exp_20260731_002_matrix_real_embedding_quality_transfer` / 2026-07-31 | Does frozen real embedding evidence transfer? MATRIX `0-999`. | complete | `outputs/20260731_matrix_real_embedding_quality_transfer/`; analysis card | transfer evidence | `DEVELOPMENT_ONLY` |
| `exp_20260801_001_matrix_identity_position_update_separation_audit` / 2026-08-01 | Which support state action helps? MATRIX `0-999`. | complete | `outputs/20260801_matrix_identity_position_update_separation_audit/`; analysis card | identity-gate evidence | `DEVELOPMENT_ONLY` |
| `exp_20260801_002_matrix_incremental_tracklet_update_foundation` / 2026-08-01 | Is the observation-to-tracklet adapter ready? MATRIX smoke. | blocked | `outputs/20260801_matrix_incremental_tracklet_update_foundation_smoke/`; analysis card | local quality block | `DIAGNOSTIC_ONLY` |
| `exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness` / 2026-08-02 | Are mobile-camera local tracks ready? MATRIX pilot. | blocked | `outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_pilot/`; analysis card | readiness diagnostic | `DIAGNOSTIC_ONLY` |
| `exp_20260802_002_matrix_botsort_candidate_gate_repair` / 2026-08-02 | Can candidate-gate repair clear readiness? MATRIX pilot. | complete | `outputs/20260802_matrix_botsort_candidate_gate_repair_pilot/`; analysis card | negative repair evidence | `NEGATIVE_EVIDENCE` |
| `exp_20260802_003_matrix_ocsort_motion_representation_audit` / 2026-08-02 | Is motion representation the local failure? MATRIX pilot. | blocked | `outputs/20260802_matrix_ocsort_motion_representation_audit_pilot/`; analysis card | lifecycle-confounding diagnostic | `DIAGNOSTIC_ONLY` |
| `exp_20260802_004_matrix_local_tracklet_lifecycle_stratified_readiness` / 2026-08-02 | Separate active-run continuity from long gaps. MATRIX pilot. | blocked | `outputs/20260802_matrix_local_tracklet_lifecycle_stratified_readiness/`; analysis card | local-tracker block | `DIAGNOSTIC_ONLY` |
| `exp_20260802_005_mdmt_dataset_neutral_local_tracklet_adapter` / 2026-08-02 | Is a dataset-neutral MDMT local packet/evaluation adapter viable? MDMT val/test smoke. | complete | `outputs/20260802_mdmt_dataset_neutral_adapter_official_gt_smoke/`; experiment card | MDMT communication-line adapter authority | `DEVELOPMENT_ONLY` |
| `exp_20260803_001_mdmt_local_tracklet_readiness` / 2026-08-03 | Are MDMT person local tracks ready? MDMT val then official test. | complete | `outputs/20260803_mdmt_local_tracklet_readiness/`; analysis card | communication-line prerequisite | `DEVELOPMENT_ONLY` |
| `exp_20260803_002_mdmt_async_incremental_tracklet_fusion` / 2026-08-03 | Can asynchronous incremental tracklets be calibrated? MDMT val/test. | blocked | `outputs/20260803_mdmt_async_incremental_tracklet_fusion_pilot/`; analysis card | calibration block | `DIAGNOSTIC_ONLY` |
| `exp_20260804_001_mdmt_sync_cross_view_tracklet_association` / 2026-08-04 | Is synchronous cross-view association feasible? MDMT val/test. | pilot pending | `outputs/20260804_mdmt_sync_cross_view_tracklet_association_pilot/`; analysis card | alternate diagnostic branch | `UNKNOWN` |
| `exp_20260804_002_mdmt_author_mia_sync_reproduction` / 2026-08-04 | Can author MIA synchronous behavior be reproduced? MDMT paired views. | partial | `/mnt/data/yzm/experiments/mdmt_mia_official/outputs/`; analysis card | predecessor reproduction evidence | `DIAGNOSTIC_ONLY` |
| `exp_20260804_003_mdmt_mia_carafe_paper_alignment_reproduction` / 2026-08-04 | Align author CARAFE/ByteTrack MIA reproduction. MDMT official test. | complete | `outputs/20260804_mdmt_mia_carafe_paper_alignment*/`; experiment card | synchronous authority predecessor | `DEVELOPMENT_ONLY` |
| `exp_20260805_002_mdmt_mia_active_packet_runtime_equivalence` / 2026-08-05 | Does active packet runtime reproduce synchronous MIA exactly? MDMT official test. | complete | `outputs/20260805_mdmt_mia_active_packet_runtime_equivalence*/`; experiment card | packetized baseline authority | `DEVELOPMENT_ONLY` |
| `exp_20260805_003_mdmt_mia_async_state_channel_audit` / 2026-08-05 | Which asynchronous state channels matter? MDMT official test. | complete | `outputs/20260805_mdmt_mia_async_state_channel_audit_formal_v2/`; analysis card | channel-cascade authority | `DEVELOPMENT_ONLY` |
| `exp_20260808_001_mdmt_mia_id_supplement_cascade` / 2026-08-08 | Does delayed ID create a candidate/Supplement compensation path? MDMT official test. | complete | `outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/`; `FORMAL_ANALYSIS_REPORT.md` | E023 mechanism authority | `DEVELOPMENT_ONLY` |
| `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation` / 2026-08-17 | Is the E023 compensation path reproduced on frozen non-test cohorts, and at which onset? MDMT train development/holdout/val protocol with Source-MDA-v1. | development complete | `FROZEN_15_PAIR_DEVELOPMENT_SCIENTIFIC_ANALYSIS.md`; `outputs/20260906_mdmt_mia_frozen_15_pair_development_analysis_v1/` | **current mainline**; development onset is d1 | `NEEDS_HOLDOUT` |
| `packet_census_z0_train_all_hfallback_v1` / 2026-09-03 | What is the logical Z0 packet workload after accepted H-fallback repair? 25 preaudited MDMT train pairs. | complete | `summary_md/PACKET_CENSUS_RUN_REPORT.md`; ignored successor output root | Route-A descriptive successor census | `DIAGNOSTIC_ONLY` |

## Current active experiment pointer

`exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation` is rooted
at the immutable legacy path
[`summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/`](../experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/).
Its start date is **2026-08-17**; its latest recorded scientific activity is
**2026-09-06**.  The development result selected `d1` by the frozen ascending
rule, but locked holdout confirmation is not run.  Its paper-readiness label is
therefore **`NEEDS_HOLDOUT`**, not `READY`.
