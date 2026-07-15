# Experiment Index

This is the short tracked index for experiment cards. Keep each experiment to
one row so future sessions do not need to re-read full logs.

Experiment cards are grouped by experiment date under:

```text
summary_md/experiments/YYYY-M-D/
```

Status labels:

- `planned`: design exists, not run yet
- `smoke`: wiring or small-scale validation
- `mainline`: active support for the current paper/system story
- `baseline`: useful comparison or primitive
- `negative`: useful because it rejected an idea
- `superseded`: replaced by a later experiment

| Exp ID | Date | Topic | Dataset | Method | Output | Status | Key Result | Decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `exp_20260616_001_oosm_backfill_smoke` | 2026-06-16 | A1/A2 minimum OOSM smoke | M3OT `1/rgb` + `2/rgb` val `*-08` | Delay injection, identity probe, candidate-geometry stress, controlled Backfill/Fuse-at-current baselines | `outputs/20260616_oosm_backfill_validation/` | negative | Phase 1 supports A1. Phase 2a mechanism accepted: 564 geometry-flip/history-gap events, Backfill target-event acc 1.000 vs Fuse-current 0.000. Phase 2b: Discard OOSM IDF1 0.656 best; Backfill IDF1 0.557 loses to exp decay 0.579 and has 590 IDSW. | A2 rejected. Do not expand broad Backfill framework; only consider one gated/event-triggered follow-up if needed. |
| `exp_20260616_002_event_gated_oosm` | 2026-06-16 | Event-gated OOSM Backfill follow-up | M3OT `1/rgb` + `2/rgb` val `*-08` | Observable candidate-geometry gate + controlled Backfill tracker | `outputs/20260616_oosm_backfill_validation/phase2c_*` | negative | Event-gated Backfill uses only 411 support updates and beats global Backfill IDF1 0.628 vs 0.557, but remains below Discard OOSM IDF1 0.656 and has 29 more IDSW. | Rejected. Selective gating is safer than global OOSM, but still not better than discarding support OOSM. |
| `exp_20260621_001_matrix_readiness` | 2026-06-21 | MATRIX dataset readiness for asynchronous multi-UAV MOT | MATRIX | Dataset-field validator for personID stability, world/grid position, views, POM, LoS, calibration | `summary_md/experiments/2026-6-21/matrix_dataset_readiness.md` | mainline | Real-package validation passed on first 50 timesteps after generating POMs/annotations: 2000 rows, 40 persistent personIDs, 0 missing ID fields, mean 6.612 visible views, 8 drone dirs, 8000 intrinsic and 8000 extrinsic files. | Accepted for GT/world-coordinate asynchronous pose-tracking experiments; use `personID` as identity and `positionID` as grid/location key. |
| `exp_20260622_001_matrix_async_pose_gt` | 2026-06-22 | First GT/world-coordinate async pose tracking test | MATRIX `0-49` | D1 primary track, D2-D8 delayed support, fixed/uniform delay, arrival-time vs timestamped pose fusion | `outputs/20260622_matrix_async_pose_gt/` | mainline | Timestamped pose fusion IDF1 1.000 and IDSW 0 for all delays. Arrival-time fusion degrades with delay: fixed_3 IDF1 0.3725 / 480 IDSW; fixed_5 0.3245 / 495; uniform_1_10 0.1620 / 870. | Accepted. Stale support can be worse than dropping delayed support; timestamp/capture-pose metadata are required for support fusion. |
| `exp_20260623_001_matrix_delay_event_diagnostics` | 2026-06-23 | Critical delay threshold + event subset diagnostics | MATRIX `0-49` | Fixed delay scan `0-10`, per-person trace, event-subset IDF1/IDSW attribution | `outputs/20260623_matrix_delay_event_diagnostics/` | mainline | Critical delay is `fixed_2`: arrival-time IDF1 0.115 / 1143 IDSW vs drop-delayed 0.846 / 251 and timestamped 1.000 / 0. IDSW concentrates in proximity (785), crossing-like (430), and high-motion (358) subsets. | Accepted. Use 2 frames as first measured harmful-delay threshold for this slice; validate on longer range and stress timestamp/pose uncertainty next. |
| `exp_20260625_001_matrix_threshold_stability` | 2026-06-25 | Critical delay threshold stability | MATRIX `0-199` | Generate derived files for `50-199`; scan fixed delays `0-10` over 7 frame windows; normalized threshold rules and event coverage | `outputs/20260625_matrix_threshold_stability/` | mainline | Stable: all 7 windows have `T_main=2`, `T_drop5=2`, `T_idsw_rate=2`, and timestamped sanity passes. Aggregate `0-199`: fixed_1 arrival IDF1 0.998, fixed_2 arrival IDF1 0.052875 vs drop-delayed 0.3525. | Accepted. Treat 2 frames as the stable harmful-delay threshold for current MATRIX GT/world-coordinate setup; next add timestamp/pose uncertainty before adaptive fusion. |
| `exp_20260625_002_matrix_time_pose_uncertainty` | 2026-06-25 | Timestamp/pose uncertainty stress | MATRIX `0-199` | Frame-level timestamp jitter and support world-XY Gaussian noise on timestamped fusion, compared to drop-delayed and ideal timestamped baselines | `outputs/20260625_matrix_time_pose_uncertainty/` | mainline | Moderate stress `fixed_2 + jitter_pm1_noise_0.50m` fails: IDF1 0.066875 / IDSW rate 408.875 per 1k GT vs drop-delayed IDF1 0.3525 / 253.0. Jitter-only and pose-noise-only both show severe sensitivity. | Accepted. Plain timestamp-aware buffering is insufficient under tested uncertainty; next method direction should be uncertainty-aware delayed association/gating. |
| `exp_20260625_003_matrix_risk_aware_delayed_association` | 2026-06-25 | Risk-aware delayed association v1 | MATRIX `0-199` | Reliable capture time, pose/world-coordinate noise only, residual divided by uncertainty-scale gate plus weighted update | `outputs/20260625_matrix_risk_aware_delayed_association/` | negative | Zero-noise oracle is preserved, but `fixed_2 + pose_noise_0.50m` fails: risk-aware IDF1 0.062125 / IDSW rate 431.875 vs plain uncertain IDF1 0.077125 / 354.875 and drop IDF1 0.3525. Accept rate rises with noise, reaching 0.930780 at 0.50m. | V1 rejected / needs tuning. Do not enter Stage B yet; redesign uncertainty policy so higher uncertainty limits support authority rather than only widening the gate. |
| `exp_20260625_004_matrix_risk_aware_v2_ablation` | 2026-06-25 | Risk-aware v2 ablation | MATRIX `0-199` | Compare v1, authority cap, ambiguity margin, and cap+margin under reliable capture time and pose/world-coordinate noise | `outputs/20260625_matrix_risk_aware_v2_ablation/` | mainline | v2c is best at `fixed_2 + pose_noise_0.50m`: IDF1 0.177625 / IDSW rate 204.375 vs v1 0.062125 / 431.875 and plain uncertain 0.077125 / 354.875, but still below drop-delayed IDF1 0.3525. | Partially supported. Authority cap is necessary and cap+margin is best, but Stage A is not passed; next address support-only evidence and separate identity vs position updates. |
| `exp_20260626_001_matrix_support_marginal_value_audit` | 2026-06-26 | Stage A support marginal value audit | MATRIX `0-199` | Per-frame/person trace alignment for drop, plain uncertain, v1, v2a, and v2c; support marginal value categories and gate outcome aggregation | `outputs/20260626_matrix_support_marginal_value_audit/` | mainline | V2C remains below drop-delayed IDF1 at all noisy levels: 0.153250 / 0.177625 / 0.286125 vs drop 0.352500, while net marginal value is negative (`helpful - harmful - weak/reject = -5615`). V2C still beats plain uncertain at 0.50m and 1.00m and lowers IDSW. | Accepted as Stage A boundary result: `close_stage_a_boundary`. Stop geometry-only threshold sweeps; treat drop-delayed as safety baseline and move toward multi-cue or identity/position-separated support. |
| `exp_20260630_002_matrix_occlusion_delay_ratio_audit` | 2026-06-30 | 遮挡时长与延迟比值描述性审计 | MATRIX `0-199` | 单帧事件修复、六档 delay、episode rho 与 message rho_remaining | `outputs/20260630_matrix_occlusion_delay_ratio_audit/` | mainline | 76 个 metric episodes、77 个全部 episodes；offline timestamped 各 delay IDF1 1.0，arrival 遮挡 IDF1 从 500ms 的 0.990 降至 1000ms 的 0.197。 | `descriptive_only_proceed_to_causal_audit`；不从 offline oracle 宣称在线边界。 |
| `exp_20260630_003_matrix_causal_oosm_delay_ratio_audit` | 2026-06-30 | 因果在线 OOSM delay-ratio 审计 | MATRIX `0-199` | Arrival-time 可用性、capture-time rollback/replay、冻结历史在线输出 | `outputs/20260630_matrix_causal_oosm_delay_ratio_audit/` | mainline | Causal 遮挡 IDF1：500ms 0.990、1000ms 0.393、5000ms 0.184；offline corrected 始终 1.0。 | `insufficient_evidence`；已有 delay 效应，但 rho-only 与联合边界需扩展数据。 |
| `exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration` | 2026-07-05 | 遮挡支撑成对反事实测量校准 | MATRIX `0-199` | Run A 保留目标遮挡支撑，Run B 仅屏蔽目标遮挡支撑；检查 Run A 复现、lineage 稳定和 delay-rho gain | `outputs/20260705_matrix_occlusion_counterfactual_measurement_calibration/` | mainline | 测量 gate 全通过：Run A mismatch 0、mask mismatch 0、lineage ambiguity 0。During gain：500ms 0.910、1000ms 0.271、1500ms 0.049、2500ms 0.013、5000ms 0.001。 | `measurement_valid_but_underdetermined`；成对反事实测量可信，但只有 8 个有效 delay-rho cell，下一步扩展到 `0-999`。 |

## Current Mainline Chain

1. Keep the M3OT Backfill/ReID-only direction rejected.
2. Use MATRIX GT/world-coordinate tracking to isolate asynchronous pose/world
   observation timing before detector/ReID noise.
3. Treat timestamped pose fusion as the GT upper-bound mechanism and
   arrival-time fusion as the stale-observation failure baseline.
4. Current accepted result: arrival-time fusion has a stable 2-frame harmful
   delay threshold on MATRIX `0-199` under fixed-delay GT controls.
5. Current accepted result: ideal timestamped fusion fails under moderate
   timestamp/pose uncertainty, so the next method should be uncertainty-aware
   delayed association/gating rather than a plain capture-time buffer.
6. Current negative result: the first residual/uncertainty-scale risk gate keeps
   zero-noise oracle behavior but fails under moderate pose noise. Redesign the
   risk policy before moving to camera-projection or detector stages.
7. Current Stage A boundary result: authority cap plus ambiguity margin improves
   over v1/plain uncertain fusion, but support marginal value remains negative
   and v2c never beats drop-delayed IDF1 under noisy world-coordinate support.
   Close the geometry-only Stage A condition and move next toward multi-cue or
   identity/position-separated support.
8. Occlusion support has confirmed online value: causal capture-time replay is
   near-oracle at 500ms but drops sharply at 1000ms. Paired counterfactual
   calibration confirms the measurement is valid without GT-ID leakage, but
   only 8 delay-rho cells have `n>=5`; expand to `0-999` before claiming a
   publishable boundary.
