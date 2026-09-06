# Current Experiment Stage

This is the short handoff for the MATRIX asynchronous multi-UAV MOT project.

## Current Mainline

### Next Planned Gate: Non-Test Compensation Onset Validation (2026-08-17)

- 新实验契约：`exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`。
- 本轮只验证 E023 候选集合补偿在 MDMT 非测试序列上的复现性与 d1-d5 出现区间；不实现
  version-aware recovery，不重新读取 official test 选择 delay。
- 历史 official-export-equivalence gate 于 2026-08-19 以 `GT_PROTOCOL_GATE_FAIL` 结束：G1
  通过，G2 仅 5/28 official-test 文件精确匹配，另有 347 source-only rows。该结果只保留为
  historical invalid predecessor/fingerprint；`OFFICIAL_EXPORT_FILTER_POLICY = UNKNOWN`，不得
  用它推断过滤规则。
- 随后的独立 Route-B 审计已通过：`R1_CROSS_VIEW_IDENTITY_AUTHORITY` 与 R2 frame/ID/bbox
  mapping authority 均为 `PASS`。`MDMT_SOURCE_ANNOTATION_MDA_V1` 仅是 internal mechanism
  replication 的 source-annotation protocol，不是 official-test export equivalent protocol。
- 独立 `MDMT_SOURCE_ANNOTATION_MDA_V1` implementation 与 clean-root fresh G1-G7 source-protocol
  preflight 已完成：60 个 train/val XML、1,610,691 source rows 的七项 structural gates 均为
  `PASS`，两次 deterministic artifact digest 相同。
- Pair53/66 Tracking MVE 已以新、独立 package 完整执行；22/22 scientific attempts accepted、
  8/8 instrumentation qualifications passed、Y00 双视角 exact parity 与 Source-MDA real path
  均通过。实现/测量有效性审计为 `PAIR53_PAIR66_MVE_PASS`，并已进入
  `FROZEN_15_PAIR_DEVELOPMENT_EXECUTION_COMPLETE / DEVELOPMENT_MEASUREMENT_VALIDITY_PASS /
  DEVELOPMENT_FULL_REPLICATION / EARLIEST_ONSET_D1`。15-pair/d1--d5 的 255-row package 已完整
  执行并完成一次性 scientific unblinding。ID-delay harm 在五档均复现；d1--d4 通过 A--F，d5
  仅 Gate A 失败。按冻结升序规则锁定 `d*=d1`，但 holdout confirmation 尚未获授权或执行。
  `Y01_d1` 是已关闭的 canonical singleton。不得运行旧 `RUN_PLAN.md` 的 Pair22/72 命令。
- 后续 MVE 只能使用冻结 development manifest 的前两个 pairs `53, 66`；10 train holdout 和全部
  val pairs 必须保持未消费直至 locked confirmation。
- R3 契约修订要求：实际 delay-only candidate -> High-score Supplement write-in 至少
  出现在 `10/15` development pairs，不能只在 pooled 数据中非零。
- 执行顺序冻结为：Research Decisions resolved -> GT protocol gate -> infrastructure -> two-pair MVE ->
  development sweep -> locked holdout confirmation -> scientific decision。
- 当前下一步为 `LOCK d1 AND PREPARE HOLDOUT CONFIRMATION`；不得自动运行 10 train holdout 或
  5 val pairs。
- Contract：
  `summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/EXPERIMENT_CONTRACT.md`
- Gate report:
  `summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/SOURCE_MDA_V1_G1_G7_PREFLIGHT_REPORT.md`
- MVE execution-preflight audit:
  `summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/MVE_INHERITED_EVIDENCE_AUDIT.md`

### Latest Update: E023 Cascade Formal Completed (2026-08-14)

- E023 已完成 14-pair Formal；40 项测量门全部通过，`Y00` 严格复现同步参考。
- `ID state` 延迟在 d1/d5 均造成稳定 MDA 与 IDSW 伤害。
- d1 的候选集合中介路径不可辨识；d5 支持
  `candidate_set_mediated_compensation`：延迟产生的 unmatched candidate 为及时 Supplement
  提供恢复机会，oracle edge-cut 反而降低 MDA。
- 当前阶段不是实现 joint transaction。下一步是在非测试数据上验证该补偿机制的延迟边界，
  然后设计不使用 oracle shadow、不可改写历史的版本感知恢复机制。

### Previous Update: Formal Channel Audit Completed (2026-08-08)

- Gate A (`exp_20260805_001`) 已完成 14-pair 严格同步等价：其 packet 仅为旁路审计，作者原始
  进程内对象仍驱动 MIA。
- `exp_20260805_002_mdmt_mia_active_packet_runtime_equivalence` 已在 Pair-26、Pair-48 与 14-pair
  Formal 逐 JSON 等价通过；`packetized_active_sync` 的 Local Track、H、ID state 与 Supplement
  均经过 JSON roundtrip，并显式将 NMS 后 ID/bbox 写回下一帧 ByteTrack。
- `exp_20260805_003_mdmt_mia_async_state_channel_audit` 已完成 14-pair Formal，测量门全部通过，
  决策为 `coupled_state_cascade_identified`。Local 与 Supplement 使用帧截止语义；H 使用最近
  已到达矩阵；ID 使用版本化、未来生效的 remap 事件。
- Formal 结果需要分开解释：Local Track 是上游流程阻断，`all_channels` 近似 `local_only`；
  ID state 对 IDSW/IDF1 最敏感；Supplement 主要影响 MDA；5 帧延迟下 ID state 与 Supplement
  出现稳定组合级级联。当前下一步是联合状态事务与有限窗口更新，不是继续扩大同一套延迟矩阵。

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
- Scope transition on 2026-08-01: the completed line is explicitly classified
  as observation-level asynchronous fusion. The active next stage is
  **incremental local-tracklet update**: every UAV independently maintains a
  causal local tracklet and emits its current state every frame. It does not
  wait for tracklet termination.
- Incremental-tracklet foundation smoke is implemented. Gate A exactly
  reproduces the observation-level reference, and no-GT/causality checks pass.
  Gate B is currently blocked: bbox-only local tracking merges identities
  (IDF1/purity `0.248/0.329`), while bbox+OSNet is pure but highly fragmented
  (IDF1/purity `0.074/0.959`). The active task is therefore mobile-camera
  local-tracker repair, not global asynchronous tracklet fusion.
- The first repair experiment is implemented as
  `exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness`. It compares
  mature BoT-SORT lifecycle with GMC and frozen OSNet in a 2x2 ablation. Pilot
  Pilot is complete and all measurement gates pass, but no mature configuration
  reaches the purity gate. GMC improves IDF1/coverage strongly; OSNet adds
  almost nothing because the default `IoU>=0.5` proximity mask excludes about
  `74.3%` of same-person consecutive pairs before appearance comparison.
  The candidate-generation repair `exp_20260802_002` is now also complete.
  `IoU>=0.1 + OSNet hard veto` improves IDF1/purity to `0.137546/0.946417`,
  but no configuration passes readiness. `IoU>=0.3 + hard veto` confirms the
  precision-recall failure: purity `0.973078`, IDF1 only `0.077409`.
  The OC-SORT motion/state representation Pilot is complete. World CV error
  p90 is `0.269m` and GMC+CV IoU>=0.1 candidate recall is `0.826`, so neither
  non-linear pedestrian motion nor candidate reachability alone explains the
  failure. Deep OC-SORT soft raises IDF1 to `0.337` but purity falls to `0.479`;
  hard veto restores purity and severe fragmentation. Clean world-XY reaches
  purity `0.996` but only IDF1 `0.548`, because the current readiness gate also
  penalizes local-ID termination across LoS gaps longer than `track_buffer=5`.
  Lifecycle-stratified readiness is now complete. Clean world-XY active-run
  IDF1 is `0.935778`, confirming that the old full-sequence gate mixed local
  continuity with long-gap identity recovery. No image tracker passes the
  corrected active-run gate: the best continuity variant reaches IDF1
  `0.373450` with purity `0.433254`, while high-purity variants remain severely
  fragmented. All `537` long gaps have complete support-view evidence, but no
  global stitching method has been implemented yet.
  **Current position: current local Formal remains blocked. Compare one public
  mobile-camera tracker under the corrected gate and, in parallel, start a
  minimum asynchronous global-stitching audit.**
- MDMT transition Gate 0 is now implemented. `tracklet_packets.py` defines a
  dataset-neutral fixed-size message, and the MDMT adapter runs paired views
  without runtime identity/world-XY access. Official MDA GT was located for all
  14 test pairs and imported under `data/MDMT_official_mda_gt/`. Current decision
  is `adapter_ready_official_mapping_available`. Test global evaluation is
  authorized, with the 3.47% cross-view class-conflict rate reported as label noise.
- MDMT person local-tracklet readiness `exp_20260803_001` has completed Pilot and
  locked official-test Formal. All measurement gates pass. On `124824` visible
  person detections and `912` active runs, `bbox_sort` reaches IDF1 `0.997229`,
  purity `0.997500`, IDSW `22`, and fragmentation `20`. Current decision is
  `person_local_tracklet_ready`. Local tracking no longer blocks the mainline;
  the active task is a minimum person-only asynchronous incremental-tracklet
  fusion audit. Cross-view category-conflict sensitivity remains a required
  evaluation gate.
- `exp_20260803_002_mdmt_async_incremental_tracklet_fusion` full val Pilot is
  complete. All 14 implementation-level measurement gates pass, but appearance
  calibration is blocked: pooled cue precision is `0.014642` in both directions,
  V2-primary same-view ReID precision is `0.022989`, and latest cross-view recall
  is effectively zero (`0.000079/0.000119`). The current output label
  `measurement_invalid` conflates valid measurement plumbing with failed cue
  calibration. **Current position: official-test Formal is not authorized. Fix
  reject-all fallback and run a candidate-conditioned tracklet appearance audit
  before any delay sweep.**
- `exp_20260804_001_mdmt_sync_cross_view_tracklet_association` remains an
  appearance-only negative baseline. The V1->V2 val branch also needs an empty
  primary-person stream guard before it can be formally closed, but it is no
  longer a mainline blocker.
- The active mainline is `exp_20260804_003_mdmt_mia_carafe_paper_alignment_reproduction`.
  It keeps `delay=0` and audits the published CARAFE+ByteTrack parameter
  protocol in an isolated source copy before any full-test or async conclusion.
  Pair-26 is a mechanism/evaluator audit; only the 14-pair macro result can be
  compared with Table III. `Tracklet`, homography, ID-state and supplementation
  delay ablations remain explicitly blocked.
- The preceding `exp_20260804_002_mdmt_author_mia_sync_reproduction`.
  It first freezes and reproduces the authors' synchronous MIA-Net under its
  required legacy stack, using the existing MDMT data and detector checkpoint.
  No delay, custom ReID replacement, or message-interface refactor is allowed
  until the local/global/no-supplementation/full-MIA synchronous comparison is
  deterministic and evaluated with the author MDA/AAS protocol.
  The isolated environment and one-image tracker smoke are valid. The author
  local, global-matching, and full-MIA entries all completed test pair 26 with
  two 300-frame JSON outputs. The author-compatible evaluator reports AAS/MDA
  `0.226674` for local/global and `0.266068` for full MIA. This is only a
  pair-level functional result: full MIA improves cross-view association but
  lowers view-2 IDF1 and raises view-2 IDSW. Batch evaluation over all official
  test pairs is required before accepting the synchronous baseline or injecting
  delay.

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
  - `scripts/analyze_occlusion_temporal_boundary_matched.py`
  - `scripts/analyze_occlusion_online_proxy_readiness.py`
  - `scripts/phase2_matrix_tracker_state_aware_reanchoring.py`
  - `scripts/phase2_matrix_identity_cue_quality_boundary.py`
  - `scripts/phase2_matrix_identity_position_update_separation.py`
  - `scripts/prepare_matrix_local_tracklet_osnet_cache.py`
  - `scripts/phase3_matrix_incremental_tracklet_foundation.py`
  - `scripts/phase3_matrix_mobile_camera_local_tracklet_readiness.py`
  - `scripts/phase3_matrix_botsort_candidate_gate_repair.py`
  - `scripts/phase3_matrix_ocsort_motion_representation_audit.py`
  - `scripts/analyze_matrix_local_tracklet_lifecycle_stratified.py`
- Support audit helpers:
  `src/tracking/support_audit.py`
- Tests:
  - `tests/test_matrix_gt.py`
  - `tests/test_temporal_boundary_matched.py`
  - `tests/test_online_proxy_readiness.py`
  - `tests/test_matrix_reanchoring.py`
  - `tests/test_matrix_identity_cue_quality_boundary.py`
  - `tests/test_matrix_incremental_tracklet.py`
  - `tests/test_matrix_mobile_camera_local_tracklet.py`
  - `tests/test_matrix_ocsort_motion_representation.py`
  - `tests/test_matrix_local_tracklet_lifecycle_stratified.py`

## Latest Result

Experiments:

```text
summary_md/experiments/2026-6-30/exp_20260630_002_matrix_occlusion_delay_ratio_audit.md
summary_md/experiments/2026-6-30/exp_20260630_003_matrix_causal_oosm_delay_ratio_audit.md
summary_md/experiments/2026-7-5/exp_20260705_001_matrix_occlusion_counterfactual_measurement_calibration.md
summary_md/experiments/2026-7-22/exp_20260722_001_matrix_occlusion_temporal_boundary_expansion.md
summary_md/experiments/2026-7-22/exp_20260722_002_matrix_temporal_boundary_matched_diagnostics.md
summary_md/experiments/2026-7-24/exp_20260724_001_matrix_early_frame_online_proxy_readiness.md
summary_md/experiments/2026-7-24/exp_20260724_002_matrix_tracker_state_aware_reanchoring.md
summary_md/experiments/2026-7-26/exp_20260726_001_matrix_fixed_lag_useful_window_audit.md
summary_md/experiments/2026-7-26/exp_20260726_002_matrix_fixed_lag_temporal_spatial_robustness.md
summary_md/experiments/2026-7-26/exp_20260726_003_matrix_fixed_lag_simulated_identity_cue_ablation.md
summary_md/experiments/2026-7-31/exp_20260731_001_matrix_identity_cue_quality_boundary.md
summary_md/experiments/2026-8-2/exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness.md
summary_md/experiments/2026-8-2/exp_20260802_002_matrix_botsort_candidate_gate_repair.md
summary_md/experiments/2026-8-2/exp_20260802_003_matrix_ocsort_motion_representation_audit.md
summary_md/experiments/2026-8-2/exp_20260802_004_matrix_local_tracklet_lifecycle_stratified_readiness.md
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
- Online proxy readiness is complete. Current decision is `online_proxy_weak`:
  `M5_combined_online_proxy` improves episode-level F1 from `0.813600` to
  `0.889655`, but episode-level AUC improves only from `0.964606` to
  `0.967811`. Frame-level M5 AUC is strong (`0.969113`), but this is not enough
  to justify full policy learning yet.
- Tracker-state-aware delayed re-anchoring formal `0-999` is complete. Current
  decision is `fixed_lag_sufficient`: at `1000ms`, state-aware and
  `fixed_lag_oosm_lag2/3/5` all reach occlusion IDF1 `0.870100` / IDSW `829`,
  versus drop-delayed IDF1 `0.052011` / IDSW `5084`; at `1500ms`, state-aware
  and `fixed_lag_oosm_lag3/5` reach IDF1 `0.724058` / IDSW `2101`. The method
  signal is strong, but the current state-aware rule does not exceed the best
  fixed-lag ablation.
- Fixed-lag useful support window audit is complete. Current decision is
  `useful_window_modulated_fixed_lag`: eligible useful-window buckets have
  survival delta spread `0.382940`, with `[0,0.25)` at `0.000000`,
  `[0.5,0.75)` at `0.203212`, and `[0.75,1]` at `0.382940`. Therefore
  `delay <= lag` is an eligibility condition, not a guarantee of gain.
- Fixed-lag temporal-spatial robustness audit is complete. Current decision is
  `temporal_spatial_boundary_identified`: high useful-window fixed-lag remains
  useful at `0.10m` support world-coordinate noise (`fixed_2` occlusion IDF1
  delta `0.107354`, `fixed_3` `0.094543`), but at `0.25m` survival delta turns
  negative (`fixed_2` `-0.077936`, `fixed_3` `-0.078924`) and IDSW becomes
  worse than drop-delayed.
- Simulated identity cue ablation is complete. Current decision is
  `identity_dimension_supported`: at `0.25m` support noise, high useful-window
  `world_xy` fixed-lag remains harmful (`fixed_2` survival delta `-0.077936`,
  `fixed_3` `-0.078924`), covariance-only is still insufficient, while
  `world_xy + covariance + simulated identity` restores positive survival and
  lowers IDSW below drop at both transition delays. Medium cue gives
  `fixed_2` survival delta `0.289408` / IDSW delta `-4.327869` and `fixed_3`
  `0.167618` / `-1.333333`.
- Identity cue quality boundary formal is complete. Current decision is
  `quality_boundary_identified`. All measurement gates pass, all `30/30`
  condition checkpoints are complete, and the previous medium condition is
  reproduced exactly. The minimum passing tested mean same/different margin is
  `0.056747` at threshold `0.20`; the next lower fully tested margin `0.040019`
  fails at all five thresholds. The discrete boundary is therefore
  `(0.040019, 0.056747]` under the current simulated generator and MATRIX
  pressure setting.
- Real embedding quality transfer formal is complete. Current decision is
  `tracking_transfer_supported` and `boundary_consistent`. M3OT-GeM margin
  `0.032300` is below the simulated boundary and fails. OSNet margin `0.124401`
  is above it; covariance + appearance passes both 1000ms and 1500ms with
  survival delta `0.185434/0.090150` and IDSW delta
  `-2.931694/-0.338798`.
- Identity/position/lifecycle update separation formal is complete. Decision is
  `identity_gate_only_supported`; all `34/34` checkpoints and measurement gates
  pass. `identity_gated_position_only` is best: OSNet occlusion IDF1 is
  `0.386625/0.305918`, and simulated-medium is `0.638227/0.509608` at
  `fixed_2/fixed_3`. Separated update has no stable gain, lifecycle-only has
  exactly zero effect, and simulated-medium recovers `71.66%/68.09%` of the
  zero-noise headroom. The current evidence points to identity candidate
  selection and support-template authority, not lifecycle bookkeeping.

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

1. Keep GMC fixed and audit `proximity_thresh={0.1,0.3,0.5}` candidate recall.
2. Compare standard BoT-SORT soft appearance cost with an explicit OSNet hard veto.
3. Rerun the `0-199` Pilot; do not use the fallback config as a passing config.
4. Only after at least one mature variant passes all four readiness thresholds,
   compare history-1 observation packets with history>1 incremental tracklet
   packets in asynchronous global fusion.

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
