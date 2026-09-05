# Current Status

Updated: 2026-09-05

## Latest governance closure

The formal successor Packet Census has been closed and its tracked report is
`summary_md/PACKET_CENSUS_RUN_REPORT.md`. This is a record-governance action;
it does not add a new scientific conclusion beyond the completed aggregation.

- Formal successor ID: `mdmt-mia-packet-census-z0-train-all-hfallback-v1`.
- Branch: `exp/20260903-001-mdmt-mia-p39-homography-fallback-successor-census`.
- State: `AGGREGATION_COMPLETE`; 25/25 accepted pairs and 12,026/12,026
  `CENSUS_FRAME_UNIT`s.
- The predecessor Census is **historical invalid** because Pair 39 encountered
  the scalar-homography failure; predecessor artifacts must never be mixed into
  the successor result.
- Aggregates are locally ignored and are not committed. Their frozen hashes are:
  `CENSUS_PAIR_MANIFEST.json`
  `152f2d7f3f76747aade836063a951034963bfb41f525a22ecf696d091bbf08b6`;
  `PACKET_CENSUS_PACKET_AUDIT.jsonl`
  `ab2440e1776cdd30ba8f793bc5da713580343ac342db29e153653cdf1bc2421a`;
  `PACKET_CENSUS_DESCRIPTIVE_SUMMARY.json`
  `5dbdd6c36b88c7705cdf6140faa2f1133d079424cc84c6864d86fc90828f923a`.

The raw audit remains ignored by design; only its hash is retained in the
tracked report and this status record.

## Next Planned Experiment

`exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation` 已完成 Source-MDA-v1
测量协议实现与 source-only preflight；Pair53/66 Tracking MVE 的 R0-R9 决策也已冻结。
Pair53/66 MVE 已在独立 package 完整执行，当前为
`PAIR53_PAIR66_MVE_PASS / POST_MVE_IMPLEMENTATION_FREEZE_READY /
FROZEN_15_PAIR_DEVELOPMENT_EXECUTOR_READY /
READY_FOR_MANUAL_15_PAIR_DEVELOPMENT_LAUNCH / SCIENTIFIC_OUTCOME_EMBARGO_ACTIVE`：22/22
scientific attempts accepted、8/8 instrumentation qualifications passed，运行时 guard、Y00
exact parity、cache 完整性和 Source-MDA real integration 已通过 execution/measurement audit。
本状态不读取或解释 Pair53/66 的 scientific outcome；下一步只能单独授权冻结的 15-pair
development。15-pair/d1--d5 的 255-row package 已静态 render，但尚未启动；不能先解封这两个
MVE pairs 的科学数值。

历史 E024 的 R1-R3 研究设计答辩已完成；Route B 的 Source-MDA 协议权威审计已另行完成：

```text
R1_CROSS_VIEW_IDENTITY_AUTHORITY: PASS
R2_FRAME_MAPPING_AUTHORITY: PASS
R2_IDENTITY_INDEXING_AUTHORITY: PASS
R2_BBOX_MAPPING_AUTHORITY: PASS
SOURCE_ANNOTATION_PROTOCOL_R1_R2_AUTHORITY_PASS
```

R3 的契约修订把机制门从 pooled nonzero write-in 收紧为：实际 delay-only
candidate -> High-score Supplement write-in 至少出现在 `10/15` development pairs。
冻结的 d1-d5 扫描选择最早通过完整 Gate A-F 的 onset，而不是幅度最大的 delay。

历史 official-export-equivalence gate 已以 `GT_PROTOCOL_GATE_FAIL` 结束：G1 严格来源审计
通过（88 XML），但 G2 仅 `5/28` 文件精确相等；其余 23 文件有 347 个 source-only rows。
该失败仅冻结为 official divergence fingerprint，
`OFFICIAL_EXPORT_FILTER_POLICY = UNKNOWN`；不得以它推断 filtering rule。

随后独立的 Route-B R1/R2 authority audit 已通过：它把 Source-MDA-v1 定义为内部机制复现的
source-annotation protocol，而不是 official-test export equivalent protocol。60 个 train/val
XML、1,610,691 条 source rows 的 fresh preflight 已通过。其后 Pair53/66 MVE 的 current
successful package 已完成 execution/measurement audit：22/22 accepted、8/8 qualification passed，
Y00 exact parity、runtime guards、cache integrity 和 Source-MDA real integration 均为 PASS。
当前状态是 `PAIR53_PAIR66_MVE_PASS / POST_MVE_IMPLEMENTATION_FREEZE_READY /
FROZEN_15_PAIR_DEVELOPMENT_EXECUTOR_READY /
READY_FOR_MANUAL_15_PAIR_DEVELOPMENT_LAUNCH / SCIENTIFIC_OUTCOME_EMBARGO_ACTIVE`。10 train holdout 与全部
5 val pairs 仍未被 tracking 消费；Pair53/66 的 scientific values 不得读取或解释。此前的
`Y01_PARAMETERIZATION_AUTHORITY_GAP` 已由 source-only frozen-runtime parity audit 关闭，
`Y01_d1` 是与 d3/d5 prediction-facing 等价的 canonical singleton。下一步只能是单独授权的
冻结 15-pair development。

计划目录：
`summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/`

Gate reports:

- `summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/SOURCE_MDA_V1_IMPLEMENTATION_REPORT.md`
- `summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/SOURCE_MDA_V1_G1_G7_PREFLIGHT_REPORT.md`
- `summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/SOURCE_MDA_V1_G6_FIXTURE_CLOSURE_REPORT.md`
- `summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/MVE_INHERITED_EVIDENCE_AUDIT.md`

## Latest Formal Result

E023 ID-delay candidate-set cascade Formal 已完成。14 个 official test pair、40 项测量门全部通过，
`Y00` 与冻结同步参考逐 JSON 等价。ID-state delay 在 d1/d5 均稳定损害 MDA：损失分别为
`0.013350` 和 `0.025750`。d1 的候选集合路径与额外 Supplement 补偿均不可辨识；d5 则满足
Pattern B：`R_edge=-0.018329`、`C_comp=0.049913`，说明延迟产生的 unmatched candidate 在
较长延迟下为及时 Supplement 提供了净补偿机会。正式总决策为
`heterogeneous_or_unresolved_mechanism`，表示机制随延迟改变，不表示测量无效或没有发现。

本轮关闭原 joint-transaction 解释。下一步不得在 official test 上调 d2/d3 阈值；应先在非测试
数据上验证补偿路径的出现边界，再设计不读取 oracle shadow 的版本感知 Supplement recovery。

正式分析：
`summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md`

## Previous Formal Result

`exp_20260805_003_mdmt_mia_async_state_channel_audit` 已完成 14-pair Formal，测量门全部通过，
正式决策为 `coupled_state_cascade_identified`。结果必须拆开解释：Local Track 的帧截止是最强
的上游阻断，导致 `all_channels` 在所有延迟下近似 `local_only`；ID state 对 IDSW/IDF1 最敏感；
Supplement 主要影响 MDA。5 帧延迟下，`ID state + Supplement` 与 `H + ID state + Supplement`
的 interaction loss 分别为 `0.064116` 和 `0.056203`，bootstrap CI 下界分别为 `0.022113` 和
`0.019310`，同方向 pair 分别为 `12/14` 和 `11/14`。因此支持存在状态级联，但不支持把
`all_channels` 解释为四通道均等协同。

正式分析：
`summary_md/experiments/2026-8-5/exp_20260805_003_mdmt_mia_async_state_channel_audit_analysis.md`

下一步优先研究 `ID state + Supplement` 的联合状态事务、版本冲突和有限窗口更新；保持 Local
Track timely，避免 Local 上游截止效应掩盖下游机制。之后再处理 Supplement 的 late recovery，
最后再评估 H 预测/不确定性。

## Latest Research Focus

`exp_20260805_002_mdmt_mia_active_packet_runtime_equivalence` 已完成 Pair-26、Pair-48 与
14-pair Formal。Gate B 通过：28 个视角 JSON SHA256 全等，MOTA/IDF1/IDSW/MDA delta 全为 0，
主动 packet emission/consumption 为 `58718/58718`，feedback chain mismatch 为 0。

当前开始 `exp_20260805_003_mdmt_mia_async_state_channel_audit`：在独立
`packetized_async_deadline` 变体中对 `Local Track`、`Homography`、`ID state`、`Supplement`
分别注入 `0/1/2/5/10` 帧固定延迟。Local/Supplement 采用帧截止语义，H 使用最近到达状态，
ID 使用仅作用未来存活轨迹的版本化 remap。Pilot 已完成，`pilot_ready_formal`；测量门、d0 JSON
等价和 pair-26/48 的 `all_channels_d5` 重复确定性均通过。当前仅有 2 个 pair 的机制信号，不能
替代 14-pair Formal。

首次 Pilot 在 `id_state_only_d1` 的 pair-26 第 2 帧中断。根因是作者 `get_matched_ids()` 将
历史确认但已不在另一视角当前帧出现的 ID 加入 H 的 source 点，却未加入 destination 点，导致
`cv2.findHomography` 收到不等长点集。异步变体现仅将双侧当前帧均可见的确认 ID 作为 H 对应点。
旧 Pilot 结果仅保留为失败诊断，不能与修复后条件混合；下一次 Pilot 使用新的 `run-id` 全量重跑，
并重新通过 `d0` JSON 等价门。

`exp_20260804_003_mdmt_mia_carafe_paper_alignment_reproduction` is the active
mainline. It extends the completed author pair-26 run without adding delay: an
isolated paper-aligned source variant audits `>=10` global matches, `50/100 px`
ID distances, and the paper's low-score supplementation. Pair-26 is first used
only to validate the patch and evaluator; the decision then depends on a macro
evaluation over all 14 official test pairs. No asynchronous `Tracklet`, `H`,
`ID state`, or supplementation message experiment is authorized before this
synchronous gate completes.

The pair-26 Pilot wrapper stall is fixed. The old live-log monitor launched
`tail -F | tr | grep` in the background but terminated only `grep`, so the
wrapper waited after each author condition and never returned control to the
six-condition Python loop. The wrapper now streams through foreground
`tee | tr | grep`, preserves the author exit code, and exits naturally at EOF.
A regression test reproduces the old hang and now passes. The first three
conditions (`released_mia`, `paper_thresholds_only`, `paper_low_score_only`)
already have complete two-view JSON outputs; resume should start from
`paper_aligned_mia`.

The first 14-pair Formal attempt stopped at `paper_aligned_local`, pair 48,
frame 640 because the released local transform helper called
`cv2.findHomography` with only three correspondence pairs. A compatibility
guard now enforces the paper's five-local-match minimum and reuses the previous
homography when evidence is insufficient or RANSAC is degenerate. The isolated
variant manifest records this patch and its SHA256. The runner input is also
isolated by `condition/pair/test`; the previous shared input root had caused
later tasks to reprocess earlier pairs. Pair 48 local-only validation is the
next command; the complete Formal must then be rerun from pair-isolated inputs.

The prior `exp_20260804_002_mdmt_author_mia_sync_reproduction` established the
legacy environment and pair-26 baseline. The alignment Pilot is now complete:
all six pair-26 conditions have valid two-view JSON/TXT outputs and the released
MDA/AAS regression is within tolerance. The Pilot is a measurement and mechanism
audit only; its pair-26 result does not establish full-paper reproduction.
The isolated 14-pair Formal is complete: all 42 paper-aligned conditions
finished. Overall paper-aligned MIA reaches MOTA `0.513848`, IDF1 `0.666922`,
and MDA `0.383154`, within the predefined Table III tolerance. The numerical
reproduction therefore passes, but the measurement gate remains pending: pair
55 view 1 has one prediction frame beyond the official GT range, and the
determinism audit has not yet been run. Do not start asynchronous ablations
until these two checks are explicitly closed.
Frozen OSNet cannot supply a usable cross-view appearance-only candidate signal on
MDMT, so the next gate is an isolated reproduction of the authors' synchronous
MIA-Net before any further delay sweep. The compatibility workspace is separate
from this repository, uses Python 3.8 / Torch 1.10 / MMCV 1.5 / MMDetection 2.25.1,
references the existing data and `epoch_12.pth`, and does not retrain a detector.
The isolated environment, one-image author tracker smoke, author local/global
matching, and full MIA pair-26 runs are complete. Each pipeline has two complete
300-frame JSON outputs. The author-compatible evaluator reports pair-26 AAS/MDA
`0.226674` for local/global and `0.266068` for MIA. MIA improves the
cross-view score but lowers view-2 IDF1 and raises view-2 IDSW, so this is a
functional pair-level result, not yet an accepted synchronous baseline. Batch
evaluation over all official test pairs is the next action; no delay should be
injected before that gate is complete.

Verification:

```text
PYTHONPATH=src:scripts python -m pytest tests/ -q -> 206 passed, 2 skipped
py_compile shared fusion, sync association module, packet schema and CLI -> passed
```

The latest evaluation command was:

```bash
PYTHONPATH=src python scripts/evaluate_mdmt_author_sync.py \
  --dataset-root /mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking \
  --official-mda-gt-root data/MDMT_official_mda_gt \
  --output-dir outputs/20260804_mdmt_author_mia_sync_reproduction_pair26
```

The evaluator uses only completed author JSON outputs and official MDA GT. It
does not inject delay or alter the MIA method. Durable details are in
`summary_md/experiments/2026-8-4/exp_20260804_002_mdmt_author_mia_sync_reproduction_analysis.md`.

The first Pilot attempt stopped during tracking because validation sequence `49`
has no visible person annotations in V1 after person-only filtering, so the
`V1->V2` primary packet stream is empty and `min(primary_packets)` raises
`ValueError`. This is an unhandled empty-stream edge case, not an Oracle or
appearance result. Calibration checkpoints and 36 tracking checkpoints for
sequences `22, 36, 46` are preserved. After adding an explicit
`skipped_no_primary_person` audit row, rerun the same Pilot with `--resume`; do
not interpret the partial output as a completed experiment.

`exp_20260803_002_mdmt_async_incremental_tracklet_fusion` is implemented on the
stacked branch `exp/20260803-002-mdmt-async-tracklet-fusion`. It adds a
dataset-neutral one-embedding wire packet, separate primary/support appearance
galleries, arrival-time fusion, capture-time replay, fixed-lag update, and
future-only late recovery. Published online global IDs are immutable.

The complete five-sequence MDMT val Pilot has now finished. All 14 implementation
measurement checks pass and embedding coverage is `1.0`, but only 3/6 threshold
rows pass precision `>=0.95`. Both pooled cross-view directions have precision
`0.014642`; V2-primary same-view ReID has precision `0.022989`; latest cross-view
cues pass precision only at effectively zero recall (`0.000079/0.000119`). The
final `measurement_invalid` therefore means calibration failure, not GT leakage,
causality failure, or packet-schema failure. Formal remains unauthorized
(`selected_config.json.formal_allowed=false`). Durable analysis:
`summary_md/experiments/2026-8-3/exp_20260803_002_mdmt_async_incremental_tracklet_fusion_analysis.md`.

The next action is not the official-test command. First separate measurement and
calibration gates, make failed calibration reject all rather than fall back to a
near-all-accept threshold, fix the independent AAS bootstrap branch in H1, and
audit candidate-conditioned latest/pooled/gallery appearance quality.

Verification:

```text
PYTHONPATH=src python -m pytest tests/ -q -> 195 passed, 2 skipped
py_compile MDMT dataset/message/fusion/CLI modules -> passed
git diff --check -> passed
```

The first full-val Pilot attempt exposed a threshold-search complexity bug after
printing `sequence=5/5`: each unique similarity threshold rescanned every pair,
giving near-quadratic work. Implementation version 2 replaces this with one
stable sort plus cumulative TP/FP counts (`O(N log N)`) and prints each
direction/cue pair count. A one-million-pair benchmark completes in `0.830s`.
The old running process must be stopped and restarted because Python has already
loaded implementation version 1.

`exp_20260803_001_mdmt_local_tracklet_readiness` Formal is complete. The scope is
MDMT person-only tracking with GT bbox and active-visible-run evaluation. All
measurement gates pass, including zero runtime GT/world-XY reads, deterministic
replay, 100% embedding coverage, and exact reconciliation of all `600923`
official GT rows. Across `124824` visible person detections and `912` active
runs, `bbox_sort` is the strongest baseline: IDF1 `0.997229`, purity `0.997500`,
IDSW `22`, fragmentation `20`, and packet coverage `1.0`. The durable decision
is `person_local_tracklet_ready`; local tracking no longer blocks the mainline.
The next experiment is person-only asynchronous incremental-tracklet fusion,
with a category-consistent official cross-view evaluation subset.

The dataset-neutral packet and MDMT local-tracklet adapter are now implemented.
Runtime packets expose neither XML identity nor world XY. Official paired MDA GT
was located in the upstream repository for all 14 test sequences and downloaded
to ignored local storage at `data/MDMT_official_mda_gt/`. Test-26 reconciles all
`51,900` official rows to XML with zero unmatched rows and zero mapping conflicts.
The full 14-pair audit then reconciled all `600,923` official rows with zero
unmatched rows and zero mapping conflicts; every file follows XML ID plus one.
The corrected decision is `adapter_ready_official_mapping_available`. New code:
`src/tracking/tracklet_packets.py`, `src/datasets/mdmt.py`,
`scripts/phase3_mdmt_local_tracklet_adapter_readiness.py`, and
`scripts/prepare_mdmt_official_mda_gt.py`. MATRIX compatibility is preserved
through `tracking.matrix_local_tracklet` re-exports. The complete regression
suite passes (`203 passed`).

Cross-view scoring is available on the official test protocol: `mango_eval.py`
uses equal IDs in paired official GT as the ground-truth association, and those
IDs equal XML IDs plus one. The original `31,888` full-dataset class conflicts
therefore indicate annotation inconsistency, not absence of an ID convention.
Within official test pairs the conflict rate is `6,538/188,500 = 3.47%`; formal
reports must include an annotation-noise sensitivity result.

MDMT has been placed at
`/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/` and a
read-only preflight is complete. The package contains all `44` paired sequences
and `39,678` images, so local-tracklet adapter work may begin. Cross-view global
evaluation is not yet authorized: same-number XML IDs produce `31,888`
same-frame class conflicts across views, so an authoritative cross-view identity
mapping must be located or validated first. No calibration, pose, timestamp, or
FPS metadata was found. Durable note:
`summary_md/codex_notes/20260802_mdmt_dataset_preflight.md`.

The next stage is now formally defined as **incremental local-tracklet update**.
Each UAV will independently maintain a causal local tracklet and send its
current state every capture frame; the system will not wait for a completed
tracklet. The completed observation-level experiments remain controlled
mechanism evidence and become the history-length-1 reference.

The latest experiment is
`exp_20260802_004_matrix_local_tracklet_lifecycle_stratified_readiness`. The
analysis-only `0-199` audit is complete. It separates active visible-run local
tracking from long-gap termination, reacquisition, and global-stitching demand.
All measurement gates pass. The decision is
`readiness_metric_recalibrated_local_tracker_still_blocked`.

Clean world-XY active-run IDF1 is `0.935778`, versus `0.548384` under the old
full-sequence metric, so the previous readiness gate was materially confounded
by long gaps. No image tracker passes the corrected gate: Deep OC-SORT soft has
the best active-run IDF1 (`0.373450`) but purity is only `0.433254`; high-purity
hard-gate methods remain highly fragmented. Across `537` long gaps, every
missing frame has the target visible in at least one other UAV. This establishes
global-stitching headroom, not stitching success. Current local Formal remains
blocked; the next two tasks are a public mobile-camera tracker comparison and a
minimum global-stitching audit.

Implementation and `0-49` smoke are complete. History-1 reproduces all four
legacy delay/fold conditions with zero prediction, track-ID, action, and metric
mismatch. The message schema has no GT identity, and future-read, local-to-global
ID reuse, and determinism mismatches are all zero. The previous OSNet cache was
found to cover only `25.59%` of the all-view local stream; a missing-crop cache
preparation CLI now raises this to `100%` and the experiment hard-fails below
`95%` coverage.

The previous BoT-SORT decision was `hard_veto_tradeoff_only`. On that Pilot,
`IoU>=0.1 + hard veto` is the best purity/continuity trade-off with IDF1
`0.137546`, purity `0.946417`, minimum-view IDF1 `0.116761`, and occlusion
support coverage `0.997379`. The planned `IoU>=0.3 + hard veto` reaches purity
`0.973078` but only IDF1 `0.077409`, because its offline hard-gate same-pair
recall is only `0.429553`. Formal and asynchronous global tracklet fusion remain
blocked; the OC-SORT comparison has now been completed.

The OC-SORT Pilot finds world CV p90=`0.269029m` and GMC+CV IoU>=0.1 candidate
recall=`0.826277`. Deep OC-SORT soft raises image IDF1 to `0.337211` but purity
falls to `0.478666`; hard veto gives purity `0.968358` but IDF1 `0.096966` and
fragmentation `28142`. The clean world-XY diagnostic has purity `0.995616` and
IDF1 `0.548384`. Across 320 view-person sequences, 537 LoS gaps exceed the
five-frame buffer, explaining most world-oracle fragmentation. The script's
automatic `world_motion_or_annotation_bottleneck` branch is therefore too
coarse; the structured conclusion is `readiness_gate_lifecycle_confounded`.
The next action is to separate active visible-run quality from long-gap
reacquisition/stitching before comparing another tracker.

The earlier decision was `local_tracklet_quality_blocked`. On smoke,
`bbox_sort` macro local IDF1/purity is `0.248077/0.329275` (identity merging),
whereas `bbox_osnet` is `0.073641/0.959313` (pure but severely fragmented).
The old foundation's `0-999` formal remains intentionally blocked. Pilot shows
GMC is necessary but insufficient: best mature IDF1 is about `0.088`, purity
about `0.749`, and the fallback-selected configs all have
`purity_gate_pass=false`. An offline candidate audit shows only `25.70%` of
same-person consecutive pairs reach the default `IoU>=0.5` appearance-candidate
region after GMC, despite OSNet same-person threshold acceptance of `91.15%`.
That candidate-recall and soft-vs-hard appearance experiment is now complete.

## Latest Implementation Update (2026-08-02 mobile-camera readiness)

Implemented:

```text
src/tracking/matrix_mature_local_tracklet.py
scripts/prepare_matrix_local_tracklet_osnet_cache.py
scripts/phase3_matrix_mobile_camera_local_tracklet_readiness.py
tests/test_matrix_mobile_camera_local_tracklet.py
tests/test_matrix_botsort_candidate_gate_repair.py
scripts/phase3_matrix_botsort_candidate_gate_repair.py
src/tracking/matrix_ocsort_local_tracklet.py
scripts/phase3_matrix_ocsort_motion_representation_audit.py
tests/test_matrix_ocsort_motion_representation.py
scripts/analyze_matrix_local_tracklet_lifecycle_stratified.py
tests/test_matrix_local_tracklet_lifecycle_stratified.py
summary_md/experiments/2026-8-2/
mermaid/exp_20260802_001_matrix_mobile_camera_local_tracklet_readiness/
mermaid/exp_20260802_002_matrix_botsort_candidate_gate_repair/
mermaid/exp_20260802_003_matrix_ocsort_motion_representation_audit/
mermaid/exp_20260802_004_matrix_local_tracklet_lifecycle_stratified_readiness/
```

The adapter uses Ultralytics BoT-SORT `8.4.113`, precomputed OSNet features,
and externally audited sparse-optical-flow GMC. It remaps the process-global
Ultralytics internal track number into a per-UAV local namespace. World state
is accumulated only after image-plane association. Pilot locks the four mature
variant configs; Formal refuses to run without that config file.

Local dependency preflight installed `lap==0.5.12` under
`.venvs/local-tracklet`. Candidate-gate target tests pass (`20 passed`). The cache preparation
script reports progress every loading chunk and writes resumable embedding
checkpoints. The all-view cache and both earlier Pilots are complete. OC-SORT
adds 10 focused tests, and lifecycle stratification adds 8 focused tests; the
complete suite passes (`196 passed`). The
user-terminal Pilot is now complete; Formal was not launched. The runner
selected `delta_t/inertia` before comparing Deep OC-SORT no-app, soft
appearance, and hard veto, and wrote `formal_allowed=0`.

GitHub synchronization is prepared in
`scripts/manage_github_tracklet_transition.sh`, including the new experiment
issue body. This workspace currently has no discoverable Git worktree and
`gh auth status` reports an invalid token, so no remote update was claimed. The
next synchronization commands are:

```bash
gh auth refresh -h github.com
bash scripts/manage_github_tracklet_transition.sh
```

The identity/position/lifecycle update separation formal is complete. Decision
is `identity_gate_only_supported`; measurement is valid with `34/34`
checkpoints and zero reference mismatches. The best method is
`identity_gated_position_only`: OSNet occlusion IDF1 is `0.386625/0.305918`,
and simulated-medium is `0.638227/0.509608` at 1000/1500ms. Separated update
does not stably beat current joint, and lifecycle-only has exactly zero effect.

The main attribution has changed: delayed appearance is useful primarily for
selecting which track may receive a position update. Writing support appearance
back into the shared template reduces survival, while a primary-anchored
identity gate is substantially stronger. Simulated-medium recovers
`71.66%/68.09%` of zero-noise headroom, so the predefined tracker-architecture
bottleneck does not trigger. The next focus is cross-view template authority,
followed by an explicit appearance-assisted primary-reacquisition path.

The real CNN appearance transfer formal is complete. Its decision is
`tracking_transfer_supported` and `boundary_consistent`. M3OT-GeM has margin
`0.032300`, below the simulated failure boundary, and does not improve tracking.
OSNet has margin `0.124401`; with covariance it passes both transition delays:
survival delta is `0.185434/0.090150` and IDSW delta is
`-2.931694/-0.338798` at 1000/1500ms. The update-separation formal now shows
that the gain is mainly candidate authorization, not support-template writing.

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
src/tracking/matrix_local_tracklet.py
scripts/prepare_matrix_local_tracklet_osnet_cache.py
scripts/phase3_matrix_incremental_tracklet_foundation.py
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
scripts/phase2_matrix_identity_position_update_separation.py
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
tests/test_matrix_identity_position_update_separation.py
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

Run the identity/position separation smoke manually:

```bash
PYTHONPATH=src /usr/bin/python3 scripts/phase2_matrix_identity_position_update_separation.py \
  --matrix-root MATRIX/MATRIX_30x30 \
  --frame-start 0 --frame-end 49 \
  --delay-profiles fixed_2 fixed_3 --lag-frames 2 3 \
  --pose-noise-m 0.25 \
  --identity-sources osnet_x0_25_msmt17 simulated_medium \
  --real-embedding-dir outputs/20260731_matrix_real_embedding_quality_transfer \
  --simulated-reference-dir outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation \
  --zero-noise-reference-dir outputs/20260724_matrix_tracker_state_aware_reanchoring \
  --progress-every 25 --resume \
  --output-dir outputs/20260801_matrix_identity_position_update_separation_audit_smoke
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

At this preflight checkpoint, smoke and formal runs were still pending; the
subsequent formal result is recorded below.

## Latest Formal Update (2026-08-01 real embedding transfer)

Formal `0-999` completed with 50/50 condition checkpoints. The initial report
incorrectly returned `measurement_invalid` because a source-string gate matched
`person_id` inside the runtime-key function's docstring. The gate now changes
only GT personID and checks whether the runtime key changes; it reports no
identity leakage. Existing formal checkpoints were preserved and finalized via
`--finalize-only`.

Verified decision:

```text
tracking_transfer_supported
boundary_consistent
passing backend: osnet_x0_25_msmt17
```

## Latest Implementation Update (2026-08-01 state separation)

Implemented `exp_20260801_001_matrix_identity_position_update_separation_audit`:

```text
src/tracking/matrix_reanchoring.py
scripts/phase2_matrix_identity_position_update_separation.py
tests/test_matrix_identity_position_update_separation.py
summary_md/experiments/2026-8-1/
mermaid/exp_20260801_001_matrix_identity_position_update_separation_audit/
```

The tracker now exposes explicit current-joint, position-only, strict
identity-only, identity-plus-lifecycle, and separated support update policies.
The default preserves prior behavior. The runner reuses the existing OSNet
cache, writes per-condition checkpoints and progress messages, and does not
run CNN extraction. Target tests and full regression tests are recorded in the
implementation handoff.

Verification:

```text
PYTHONPATH=src python -m pytest tests/ -q -> 147 passed
py_compile matrix_reanchoring + experiment runner + new tests -> passed
```

## Latest Formal Update (2026-08-01 state separation)

Formal `0-999` completed with `34/34` condition checkpoints. Measurement gates
all pass, including zero primary perturbation, zero GT runtime-key leakage, and
exact reproduction of both real and simulated references.

Verified decision:

```text
identity_gate_only_supported
identity candidate selection supported: yes
separated update supported: no
lifecycle effect dominant: no
tracker architecture bottleneck: no
```

Best occlusion IDF1 at `fixed_2/fixed_3`:

```text
OSNet identity-gated position-only:       0.386625 / 0.305918
simulated-medium identity-gated position: 0.638227 / 0.509608
```

Durable analysis:
`summary_md/experiments/2026-8-1/exp_20260801_001_matrix_identity_position_update_separation_audit_analysis.md`.

## Latest Research Decision (2026-08-01 tracklet transition)

The prior system is now explicitly scoped as asynchronous cross-view
observation-to-track fusion, not a complete two-stage MVMOT implementation.
The next message unit is a per-frame incremental local-tracklet state. Decision
record:
`summary_md/decisions/20260801_incremental_tracklet_update_transition.md`.

GitHub issue bodies and authenticated-terminal commands are prepared under
`summary_md/github/`. Remote issue creation remains pending because the Codex
sandbox has an empty read-only `.git` directory and its isolated `gh` account
token is invalid; do not copy credentials into the sandbox.

Exact next command from the authenticated project terminal:

```bash
bash scripts/manage_github_tracklet_transition.sh
```
# 2026-09-05: manual train detector-cache preparation integration

Pair53/66 cache seed adapter is ready for researcher-operated execution:
`scripts/seed_mdmt_mia_onset_detector_cache.py` (`plan`, `seed`, `status`, `verify`).
It reuses the unchanged E023 NPZ writer, isolates engineering attempts and only
publishes a complete, provenance-bound shared cache. Real train inputs imply
1000 entries for Pair53 and 600 for Pair66. Neither cache was seeded here.
Reference remains live; all existing packetized scientific/qualification paths
remain cache-read. Existing execution package and executor semantics are unchanged.

Focused verification: 25 passed (new cache fixtures plus existing executor tests);
py_compile and diff whitespace checks passed. No real scientific/qualification
run or outcome read. Next manual commands and the API-only MVE invocation:
`summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/DETECTOR_CACHE_SEED_INTEGRATION.md`.
