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
| `exp_20260722_001_matrix_occlusion_temporal_boundary_expansion` | 2026-07-22 | 遮挡时间边界扩展 | MATRIX `0-999` | 成对反事实 + publish-time support freshness + delay/coverage 模型比较 | `outputs/20260722_matrix_occlusion_temporal_boundary_expansion/` | mainline | Formal 完成：385 episodes × 6 delays，Run A mismatch 0、mask mismatch 0。M4 delay×coverage interaction 明显优于 M1 delay-only：group-CV RMSE `0.277068` vs `0.416513`，R2 `0.758755` vs `0.458015`。 | `measurement_valid_boundary_still_sparse`；joint temporal boundary 信号成立，但 strict coverage gate 仍未通过，不能宣称最终数值阈值。Analysis: `summary_md/experiments/2026-7-22/exp_20260722_001_matrix_occlusion_temporal_boundary_expansion_analysis.md` |
| `exp_20260722_002_matrix_temporal_boundary_matched_diagnostics` | 2026-07-22 | 时间边界 gate 修正与匹配诊断 | MATRIX `0-999` | 复用上一轮 formal 输出；group-CV/R2/CI 模型稳定性 gate；same-rho delay、same-delay coverage、early-frame、spillover 诊断 | `outputs/20260722_matrix_temporal_boundary_matched_diagnostics/` | mainline | 测量 gate 继续通过：mismatch 0、mask mismatch 0、no-effective-support nonzero gain 0。M4 继续稳定优于 M1，delay_x_coverage CI `[-0.959284,-0.846348]` 不跨 0；same-delay coverage spread 仅 `0.005815`，early-frame gain drop `0.704866`。 | `early_frame_gap_boundary`；strict cell count 降级为外推风险，当前最可解释机制是遮挡早期在线发布帧缺少可用 support。Analysis: `summary_md/experiments/2026-7-22/exp_20260722_002_matrix_temporal_boundary_matched_diagnostics_analysis.md` |
| `exp_20260724_001_matrix_early_frame_online_proxy_readiness` | 2026-07-24 | 早期帧缺口在线代理可行性 | MATRIX `0-999` | 复用反事实 episode/frame 表；比较 delay-only、rho oracle、online freshness、early occlusion proxy、combined online proxy 的 group-CV 分类能力 | `outputs/20260724_matrix_early_frame_online_proxy_readiness/` | mainline | Episode-level M5 相比 M1：AUC `0.967811` vs `0.964606`，只提升 `0.003205`；F1 `0.889655` vs `0.813600`，提升 `0.076055`；recall `0.879260`，关键系数方向合理。Frame-level M5 AUC `0.969113` 明显高于 delay-only `0.830986`。 | `online_proxy_weak`；在线 proxy 有阈值校准和 frame-level 信号，但 episode-level ranking 增量不足，不直接进入 policy learning。Analysis: `summary_md/experiments/2026-7-24/exp_20260724_001_matrix_early_frame_online_proxy_readiness_analysis.md` |
| `exp_20260724_002_matrix_tracker_state_aware_reanchoring` | 2026-07-24 | Tracker-state-aware delayed re-anchoring | MATRIX `0-999` | BEV/SORT-style tracker；比较 drop、arrival、causal、fixed-lag、recovery-only、state-aware reanchoring | `outputs/20260724_matrix_tracker_state_aware_reanchoring/` | mainline | 1000ms: state-aware / fixed-lag lag2 occlusion IDF1 `0.870100`, IDSW `829`, vs drop `0.052011` / `5084`。1500ms: state-aware / fixed-lag lag3 IDF1 `0.724058`, IDSW `2101`, vs drop `0.052011` / `5084`。State-aware 与 best fixed-lag 打平。 | `fixed_lag_sufficient`；短窗口 delayed update 是强缓解机制，但当前 state-aware 规则没有超过固定窗口。Analysis: `summary_md/experiments/2026-7-24/exp_20260724_002_matrix_tracker_state_aware_reanchoring_analysis.md` |
| `exp_20260726_001_matrix_fixed_lag_useful_window_audit` | 2026-07-26 | Fixed-lag useful support window audit | MATRIX `0-999` | 复用 reanchoring 与 temporal-boundary formal 输出；按 episode 对齐 fixed-lag 与 drop，计算 `lag_eligible`、`useful_window_fraction` 和 delta | `outputs/20260726_matrix_fixed_lag_useful_window_audit/` | mainline | Eligible useful-window bucket survival spread `0.382940`；`[0,0.25)` bucket delta `0.000000`，`[0.5,0.75)` delta `0.203212`，`[0.75,1]` delta `0.382940`；2500ms lag5 比 state-aware lag3 IDF1 高 `0.437996`。 | `useful_window_modulated_fixed_lag`；`delay <= lag` 是资格条件，不是收益保证。下一轮 fixed-lag+noise 必须保留 useful-window 分层。Analysis: `summary_md/experiments/2026-7-26/exp_20260726_001_matrix_fixed_lag_useful_window_audit_analysis.md` |
| `exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness` | 2026-07-26 | Fixed-lag temporal-spatial robustness audit | MATRIX `0-999` | 重新跑 tracker；fixed-lag/drop/primary under support world-coordinate noise；high useful-window 分层和 temporal-spatial risk 诊断 | `outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness/` | mainline | Measurement gates 全通过。High useful-window 中，0.10m 仍有正收益：fixed2 occ IDF1 delta `0.107354`，fixed3 `0.094543`；0.25m 时 survival delta 转负：fixed2 `-0.077936`，fixed3 `-0.078924`，且 IDSW 高于 drop。 | `temporal_spatial_boundary_identified`；fixed-lag 是强缓解机制但不具备足够坐标噪声鲁棒性。下一步进入 message-content / identity-cue ablation 或 noise-aware fixed-lag update。Analysis: `summary_md/experiments/2026-7-26/exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness_analysis.md` |
| `exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation` | 2026-07-26 | Simulated identity cue message-content ablation | MATRIX `0-999` | fixed_2/fixed_3 + 0.25m support noise；比较 world_xy、world_xy+covariance、world_xy+simulated identity、world_xy+covariance+simulated identity | `outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation/` | mainline | Measurement gate 通过。High useful-window 中，world_xy 仍为负收益：1000ms survival delta `-0.077936`，1500ms `-0.078924`；medium `covariance+identity` 转为正收益：1000ms `0.289408` / IDSW delta `-4.327869`，1500ms `0.167618` / `-1.333333`。 | `identity_dimension_supported`；身份维度能补 0.25m geometry-only 边界，但需要与 covariance/authority control 联合使用。Analysis: `summary_md/experiments/2026-7-26/exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation_analysis.md` |
| `exp_20260731_001_matrix_identity_cue_quality_boundary` | 2026-07-31 | Identity cue quality boundary | MATRIX `0-999` | fixed_2/fixed_3 + 0.25m；扫描 embedding noise 与 identity threshold；离线阈值校准后对边界下侧补齐完整 tracking grid | `outputs/20260731_matrix_identity_cue_quality_boundary/` | mainline | Measurement gate 通过，30/30 checkpoints 完成，medium reference mismatch `0`。`margin=0.056747, threshold=0.20` 两 delay 均稳健通过；`margin=0.040019` 的五个 threshold 全部失败。 | `quality_boundary_identified`；离散边界 `(0.040019, 0.056747]`。下一步用真实/半真实 embedding 做候选条件化校准。Analysis: `summary_md/experiments/2026-7-31/exp_20260731_001_matrix_identity_cue_quality_boundary_analysis.md` |
| `exp_20260731_002_matrix_real_embedding_quality_transfer` | 2026-07-31 | Frozen real embedding quality and tracking transfer | MATRIX `0-999` | GT projected bbox + LoS；M3OT-GeM/OSNet 双冻结模型；身份两折候选条件化校准；fixed_2/fixed_3 + 0.25m | `outputs/20260731_matrix_real_embedding_quality_transfer/` | mainline | Measurement gate 通过，50/50 checkpoints 完成。M3OT margin `0.032300` 低于模拟边界并失败；OSNet margin `0.124401` 高于边界，covariance+appearance survival delta 为 `0.185434/0.090150`，IDSW delta 为 `-2.931694/-0.338798`。 | `tracking_transfer_supported` 且 `boundary_consistent`；真实身份维度收益迁移成功，但必须与位置权威控制联合。Analysis: `summary_md/experiments/2026-7-31/exp_20260731_002_matrix_real_embedding_quality_transfer_analysis.md` |
| `exp_20260801_001_matrix_identity_position_update_separation_audit` | 2026-08-01 | Identity/position/lifecycle update separation audit | MATRIX `0-999` | fixed_2/fixed_3 + 0.25m；OSNet frozen thresholds + simulated-medium；只拆分 support 状态动作，主视角 Hungarian 不变 | `outputs/20260801_matrix_identity_position_update_separation_audit/` | mainline | Measurement gate 通过，34/34 checkpoints 完成。identity-gated-position-only 最佳：OSNet IDF1 `0.386625/0.305918`，simulated-medium `0.638227/0.509608`；分离更新无稳定增益，生命周期效应为 0。 | `identity_gate_only_supported`；身份主要用于候选授权，support 模板写回有害；模拟线索恢复 `71.66%/68.09%` headroom。Analysis: `summary_md/experiments/2026-8-1/exp_20260801_001_matrix_identity_position_update_separation_audit_analysis.md` |
| `exp_20260801_002_matrix_incremental_tracklet_update_foundation` | 2026-08-01 | Observation-to-tracklet foundation | MATRIX smoke `0-49` | history-1 adapter equivalence；independent per-UAV bbox/OSNet local trackers；causal incremental message；local quality/aggregation audit | `outputs/20260801_matrix_incremental_tracklet_update_foundation_smoke/` | mainline-blocked | Gate A 四条件 prediction/action mismatch 均为 0；全视角 OSNet cache 从 25.59% 补齐至 100%；无 GT、因果和确定性 gate 通过。bbox_sort IDF1/purity `0.248/0.329`，bbox_osnet `0.074/0.959`，分别表现为身份合并和严重碎片化。 | `local_tracklet_quality_blocked`；不启动 0-999 formal，先修移动相机 local tracker。Analysis: `summary_md/experiments/2026-8-1/exp_20260801_002_matrix_incremental_tracklet_update_foundation_analysis.md` |
| `exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness` | 2026-08-02 | 移动相机局部轨迹就绪 | MATRIX Pilot `0-199` | BoT-SORT 成熟生命周期；稀疏光流 GMC 与冻结 OSNet 2x2 消融；每视角独立 local ID | `outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_pilot/` | mainline-blocked | 测量门全通过。GMC 将 no-app IDF1 `0.0275 -> 0.0877`、遮挡覆盖 `0.648 -> 0.936`，但 OSNet 增量近零；所有成熟配置 purity 均未过 `0.95`。GMC 后仅 `25.7%` 同人连续框满足默认 `IoU>=0.5` proximity 门。 | Pilot fallback 配置已锁但不代表通过；暂缓 Formal，先做 proximity candidate recall 与 soft/hard appearance gate 消融。Analysis: `summary_md/experiments/2026-8-2/exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness_analysis.md` |
| `exp_20260802_002_matrix_botsort_candidate_gate_repair` | 2026-08-02 | BoT-SORT 候选门最小修复 | MATRIX Pilot `0-199` | 固定 GMC；扫描 proximity `0.1/0.3/0.5`；比较标准软外观代价与 OSNet hard veto | `outputs/20260802_matrix_botsort_candidate_gate_repair_pilot/` | negative | Measurement Gate 全通过。`p=0.1 + hard veto` 为最佳纯度折中：IDF1 `0.137546`、purity `0.946417`、覆盖 `0.997379`；`p=0.3 + hard veto` purity `0.973078`，但 IDF1 仅 `0.077409`，hard-gate 同人总召回仅 `0.429553`。 | `hard_veto_tradeoff_only`；无配置通过 readiness，Formal 不运行。停止细调 proximity，下一步做 OC-SORT 最小对照。Analysis: `summary_md/experiments/2026-8-2/exp_20260802_002_matrix_botsort_candidate_gate_repair_analysis.md` |
| `exp_20260802_003_matrix_ocsort_motion_representation_audit` | 2026-08-02 | OC-SORT 运动与状态表达审计 | MATRIX Pilot `0-199` | BoT-SORT 最强参考；OC-SORT/Deep OC-SORT；GMC 与 OSNet 权限消融；clean world-XY CV 离线上限 | `outputs/20260802_matrix_ocsort_motion_representation_audit_pilot/` | mainline-blocked | Measurement 全通过。world CV p90 `0.269m`，GMC+CV 候选召回 `0.826`；最佳 image IDF1 `0.337` 但 purity `0.479`。world-XY purity `0.996`、IDF1 `0.548`，低 IDF1 主要与 `max_age=5` 和长 LoS gap 混杂。 | Formal 禁止。自动 world-motion 标签证据不足，分析结论为 `readiness_gate_lifecycle_confounded`；先按 active visible run 与长 gap 分层校准 readiness。Analysis: `summary_md/experiments/2026-8-2/exp_20260802_003_matrix_ocsort_motion_representation_audit_analysis.md` |
| `exp_20260802_004_matrix_local_tracklet_lifecycle_stratified_readiness` | 2026-08-02 | 局部轨迹生命周期分层就绪审计 | MATRIX Pilot `0-199` | 将连续活跃可见段与超过 5 帧的长间隔分开；重算局部 IDF1/purity/碎片，并审计重捕获与跨视角支撑桥 | `outputs/20260802_matrix_local_tracklet_lifecycle_stratified_readiness/` | mainline-blocked | Measurement 全通过。clean world-XY active-run IDF1 从全序列 `0.548384` 升至 `0.935778`；最佳 image active-run IDF1 `0.373450`、purity `0.433254`，无 image pipeline 通过。`537/537` 长 gap 的每个缺失帧均有其他 UAV 可见证据。 | `readiness_metric_recalibrated_local_tracker_still_blocked`；旧门槛确有长 gap 混杂，但图像局部关联仍未就绪。停止当前 Formal，并行比较公开移动相机 tracker 与最小 global stitching。Analysis: `summary_md/experiments/2026-8-2/exp_20260802_004_matrix_local_tracklet_lifecycle_stratified_readiness_analysis.md` |
| `exp_20260802_005_mdmt_dataset_neutral_local_tracklet_adapter` | 2026-08-02 | MDMT 数据集无关增量轨迹适配 | MDMT val-22 与 official test-26 two-view smoke | 将 local packet 与 MATRIX world-XY 解耦；XML identity 仅离线使用；接入官方 MDA GT | `outputs/20260802_mdmt_dataset_neutral_adapter_official_gt_smoke/` | adapter-ready | 运行时 GT/world-XY 读取均为 0；test-26 官方 51,900 行全部回连 XML，映射冲突 0；完整测试 203 passed。 | `adapter_ready_official_mapping_available`；官方 test MDA 评价可用，但 test 同号行有 3.47% 类别冲突，需报告标注噪声敏感性。Card: `summary_md/experiments/2026-8-2/exp_20260802_005_mdmt_dataset_neutral_local_tracklet_adapter.md` |
| `exp_20260803_001_mdmt_local_tracklet_readiness` | 2026-08-03 | MDMT 行人局部轨迹就绪 | val Pilot -> locked official test Formal | 在无 world XY/运行时 GT 的条件下比较 bbox SORT、BoT-SORT、Deep OC-SORT、GMC 与冻结 OSNet；使用 active-visible-run 指标 | `outputs/20260803_mdmt_local_tracklet_readiness/` | positive | 14 个 official test pair 的测量门全部通过；12 个有效行人序列贡献 124824 行、912 active runs。`bbox_sort` IDF1/purity 为 `0.997229/0.997500`，IDSW/fragmentation 为 `22/20`。 | `person_local_tracklet_ready`；停止优化 local tracker，进入 person-only 异步 incremental tracklet fusion。Analysis: `summary_md/experiments/2026-8-3/exp_20260803_001_mdmt_local_tracklet_readiness_analysis.md` |
| `exp_20260803_002_mdmt_async_incremental_tracklet_fusion` | 2026-08-03 | MDMT 异步增量 Tracklet 融合 | MDMT val calibration -> official test | 单帧 latest packet 对比稳定 local ID + pooled appearance 增量 packet；arrival、timestamped、fixed-lag、late recovery | `outputs/20260803_mdmt_async_incremental_tracklet_fusion_pilot/` | pilot complete, formal blocked | 14 项实现检查全通过；3/6 外观阈值不可校准，pooled precision=0.014642，latest recall 近零，Formal 未授权。 | `pilot_complete_calibration_blocked`。Card: `summary_md/experiments/2026-8-3/exp_20260803_002_mdmt_async_incremental_tracklet_fusion.md`；Analysis: `summary_md/experiments/2026-8-3/exp_20260803_002_mdmt_async_incremental_tracklet_fusion_analysis.md` |
| `exp_20260804_001_mdmt_sync_cross_view_tracklet_association` | 2026-08-04 | MDMT 同步跨视角 Tracklet 关联可行性 | MDMT val LOSO -> locked official test | delay=0；Oracle 上限；候选策略；latest/cumulative/EMA/window/gallery；单向量消息 | `outputs/20260804_mdmt_sync_cross_view_tracklet_association_pilot/` | implemented, pilot pending | reject-all、独立 measurement/calibration gates、LOSO 校准、同步 tracking 和 checkpoint 已实现；206 tests passed。 | `implemented_pilot_pending`。Card: `summary_md/experiments/2026-8-4/exp_20260804_001_mdmt_sync_cross_view_tracklet_association.md`；Analysis: `summary_md/experiments/2026-8-4/exp_20260804_001_mdmt_sync_cross_view_tracklet_association_analysis.md` |
| `exp_20260804_002_mdmt_author_mia_sync_reproduction` | 2026-08-04 | 作者 MIA-Net 同步复现 | MDMT paired views | 固定作者源码与旧版 MMTracking/MMDetection 环境；local/global/no-supplementation/full MIA 同步基线 | `/mnt/data/yzm/experiments/mdmt_mia_official/outputs/` | pair-26 metrics ready, full test pending | local/global/MIA 均完成 pair-26 的 300 帧双视角输出；AAS/MDA 为 `0.226674/0.226674/0.266068`。MIA 跨视角分数提高，但 view-2 IDF1 下降、IDSW 增加；尚不能宣布全测试集复现通过。 | `pair26_functional_reproduction_metrics_ready_full_test_pending`。Analysis: `summary_md/experiments/2026-8-4/exp_20260804_002_mdmt_author_mia_sync_reproduction_analysis.md` |
| `exp_20260804_003_mdmt_mia_carafe_paper_alignment_reproduction` | 2026-08-04 | MIA-Net CARAFE 论文设置对齐复现 | MDMT official test | isolated released/paper-aligned CARAFE+ByteTrack; pair-26 mechanism audit then 14-pair macro evaluation | `outputs/20260804_mdmt_mia_carafe_paper_alignment[_pilot]/` | formal_numeric_pass_gate_pending | All 42 runs complete; paper-aligned MIA is within Table III tolerance, but pair-55 frame-range reporting and determinism remain. Card: `summary_md/experiments/2026-8-4/exp_20260804_003_mdmt_mia_carafe_paper_alignment_reproduction.md` |
| `exp_20260805_002_mdmt_mia_active_packet_runtime_equivalence` | 2026-08-05 | MIA 主动消息驱动同步等价 | MDMT official test | `Local/H/ID/Supplement` 经过 JSON wire roundtrip 后驱动 MIA；显式 ByteTrack ID feedback；无延迟 | `outputs/20260805_mdmt_mia_active_packet_runtime_equivalence[_pilot]/` | formal passed | Pair-48 与 14-pair Formal 通过；28 个视角 JSON SHA256 全等，指标 delta 全为 0，58718/58718 packet emission/consumption，feedback mismatch 0。 | `active_packet_equivalent`；允许进入分通道延迟。Card: `summary_md/experiments/2026-8-5/exp_20260805_002_mdmt_mia_active_packet_runtime_equivalence.md` |
| `exp_20260805_003_mdmt_mia_async_state_channel_audit` | 2026-08-05 | MIA 异步状态通道独立与级联审计 | MDMT official test | 对 Local Track、Homography、ID state、Supplement 注入固定帧延迟；在线截止语义、无 replay | `outputs/20260805_mdmt_mia_async_state_channel_audit_formal_v2/` | complete | 14-pair Formal 测量门全部通过；Local Track 是上游流程阻断，ID state 对 IDSW/IDF1 最敏感；5 帧下 ID+Supplement 与 H+ID+Supplement 级联显著，但 all-channel 主要等于 Local-only。 | `coupled_state_cascade_identified`；Card: `summary_md/experiments/2026-8-5/exp_20260805_003_mdmt_mia_async_state_channel_audit.md`；Analysis: `summary_md/experiments/2026-8-5/exp_20260805_003_mdmt_mia_async_state_channel_audit_analysis.md` |
| `exp_20260808_001_mdmt_mia_id_supplement_cascade` | 2026-08-08 | ID delay 候选集合与 Supplement 闭环机制审计 | MDMT 14 official test pairs | `Y00/Y10/Y01/Y11/Yec` 预注册对比；d1/d5；oracle membership-only edge cut；pair bootstrap | `outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/` | complete | 40 项测量门全通过。ID delay 在 d1/d5 均稳定损害 MDA；d1 候选路径不可辨识，d5 的 `R_edge=-0.018329`、`C_comp=0.049913` 支持候选集合介导的补偿。 | `heterogeneous_or_unresolved_mechanism`；d5 Pattern B，d1 Pattern E。Analysis: `summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md` |
| `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation` | 2026-08-17 | 非测试数据上的候选集合补偿起点验证 | MDMT train/val frozen cohorts | `MDMT_SOURCE_ANNOTATION_MDA_V1`; isolated Pair53/66 MVE; frozen 15-pair development executor | `outputs/20260905_mdmt_mia_frozen_15_pair_development_v4/` | Development executor ready; outcome embargo active | Pair53/66 remains measurement-qualified without unblinding. The independent development package renders exactly 15 pairs × 17 rows = 255, d1--d5, `Y01 -> Y01_d1`, zero new qualification rows, and shared canonical image-hash-namespaced detector cache policy. | `READY_FOR_MANUAL_15_PAIR_CACHE_SEED`; no development attempt is run or reused from MVE. Reports: `POST_MVE_EXECUTION_MEASUREMENT_VALIDITY_AUDIT.md`; `DEVELOPMENT_EXECUTOR_IMPLEMENTATION_REPORT.md`; `DEVELOPMENT_DETECTOR_CACHE_POLICY_CLOSURE.md`. |
| `packet_census_z0_train_all_hfallback_v1` | 2026-09-03 | Packet Census Z0 successor closure | `ALL_PREAUDITED_RUNNABLE_TRAIN_PAIRS` (25 train pairs) | Frozen successor author runtime; Z0 logical offered-workload Census; all accepted attempts revalidated before aggregation | `outputs/packet_census_z0_train_all_hfallback_v1/` | complete | `AGGREGATION_COMPLETE`; 25/25 pairs, 12,026 frame units, 108,059 validated emissions. The three aggregate hashes are frozen in the tracked report; raw audit remains ignored. | Successor is the only valid Census cohort. The predecessor run is `historical invalid` due to Pair 39 scalar-homography failure and must not be mixed. Report: `summary_md/PACKET_CENSUS_RUN_REPORT.md` |

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
9. Temporal boundary expansion formal `0-999` is complete. The paired
   measurement remains valid, and the delay×coverage interaction model is much
   stronger than delay-only, but the strict coverage gate is still sparse. Do
   not claim a final numeric boundary yet; next refine the gate and add matched
   diagnostics.
10. Temporal boundary matched diagnostics are complete. Strict cell count is no
    longer a hard failure; model stability is accepted, but the clearest
    mechanism is `early_frame_gap_boundary`: support misses the early online
    publish frames, and same-delay coverage buckets add little separation in the
    current data.
11. Online proxy readiness is complete. Combined online proxies improve
    episode-level F1 and frame-level prediction, but add almost no episode-level
    AUC over delay-only. Current decision is `online_proxy_weak`; do not enter
    full policy learning from this signal alone.
12. Tracker-state-aware re-anchoring is complete. Bounded fixed-lag delayed
    update is the strongest current mitigation mechanism: it dramatically
    improves 1000ms/1500ms occlusion IDF1 and IDSW, but the current state-aware
    rule only ties the best fixed-lag ablation. Current decision is
    `fixed_lag_sufficient`; next test fixed-lag robustness under
    pose/world-coordinate noise.
13. Fixed-lag useful support window audit is complete. The decision is
    `useful_window_modulated_fixed_lag`: `delay <= lag` is an eligibility
    condition, not a gain guarantee. Eligible useful-window buckets have
    survival delta spread `0.382940`, so future fixed-lag noise results must be
    stratified by useful-window bucket.
14. Fixed-lag temporal-spatial robustness audit is complete. The current
    decision is `temporal_spatial_boundary_identified`: high useful-window
    fixed-lag still works at `0.10m` support world-coordinate noise, but at
    `0.25m` survival delta turns negative and IDSW rises above drop. Next move
    from pure world-coordinate support toward message-content / identity-cue
    ablation or noise-aware fixed-lag update.
15. Simulated identity cue ablation is complete. The current decision is
    `identity_dimension_supported`: under `0.25m` support noise,
    world-coordinate-only fixed-lag remains harmful, covariance-only is not
    enough, and `world_xy + covariance + simulated identity` restores positive
    high-window survival while reducing IDSW below drop at both 1000ms and
    1500ms. Next replace simulated identity with calibrated/real appearance
   evidence and add checkpoint/resume for larger matrices.
16. Real CNN appearance transfer is complete. OSNet crosses the simulated
   quality boundary and improves both transition delays only when covariance
   limits noisy position authority; M3OT-GeM remains below the boundary.
17. Identity/position/lifecycle update separation formal is complete. The
   decision is `identity_gate_only_supported`: identity-gated position update
   is substantially stronger than covariance-only/current-joint, separated
   update has no stable gain, and lifecycle-only has zero effect. Simulated
   identity recovers more than 60% headroom, so the predefined architecture
   bottleneck is not triggered. Next isolate cross-view appearance-template
   authority and add an explicit primary-reacquisition identity path.
18. The research unit now transitions from per-frame support observations to
   causal incremental local-tracklet updates. Previous experiments remain the
   observation-level mechanism baseline. The next gate is independent per-UAV
   local tracking plus exact history-length-1 reproduction before any detector,
   Mamba, or end-to-end expansion.
19. Mobile-camera local-tracklet readiness Pilot is complete and blocked.
   GMC is necessary, but default BoT-SORT appearance candidate generation is
   too restrictive for MATRIX at 2 FPS.
20. The minimum candidate-gate repair is also complete. Relaxing proximity to
   `0.1` improves IDF1 substantially and hard veto raises purity, but the best
   IDF1 is only `0.1375`; `p=0.3` achieves high purity by rejecting too many
   true matches. Global tracklet fusion and Formal remain blocked. Compare an
   OC-SORT or mobile-camera/UAV tracker next rather than tuning proximity again.
21. The OC-SORT motion-representation Pilot is complete and Formal is blocked.
   World motion and GMC+CV candidate reachability pass, but image association
   retains a merge-versus-fragmentation trade-off. The clean-world diagnostic
   exposes that the current readiness gate also measures long-gap lifecycle and
   long-term ReID, so it must be stratified before another tracker comparison.
22. Lifecycle-stratified readiness is complete. Clean world-XY reaches active-run
   IDF1 `0.9358`, confirming that the old full-sequence gate mixed local tracking
   with long-gap identity recovery. No image tracker passes the corrected gate,
   so the local infrastructure remains blocked. All `537` long gaps have a
   complete cross-view support bridge; this is evidence availability, not a
   stitching result. Next compare one public mobile-camera tracker and run a
   separate minimum global-stitching audit.
23. The dataset-neutral packet and MDMT local-tracklet adapter are implemented.
   Official paired MDA GT exists for all 14 test sequences, and the evaluator
   defines cross-view association through equal GT IDs. Test-26 reconciles all
   51,900 rows with zero conflicts. Cross-view test evaluation is now available;
   the 3.47% class-conflict rate remains an annotation-noise risk.
24. MDMT person local-tracklet readiness Pilot and Formal are complete. All
   measurement gates pass. On 124,824 visible test detections and 912 active
   runs, `bbox_sort` reaches IDF1 `0.997229`, purity `0.997500`, IDSW `22`, and
   fragmentation `20`. The decision is `person_local_tracklet_ready`; stop
   local-tracker tuning and proceed to person-only asynchronous incremental
   tracklet fusion.
