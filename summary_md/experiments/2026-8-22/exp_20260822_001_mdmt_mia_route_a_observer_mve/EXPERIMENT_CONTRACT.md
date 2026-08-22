# EXPERIMENT_CONTRACT

## Identity

- Experiment ID: `exp_20260822_001_mdmt_mia_route_a_observer_mve`
- Title: Route A delayed pre-association observation candidate-regeneration observer MVE
- Type: `MECHANISM_MVE`
- Status: `MVE-0 COMPLETE / MVE-1 BLOCKED_BY_CROSS_VIEW_GEOMETRY_GATE`
- Target branch: `exp/20260803-002-mdmt-async-tracklet-fusion`
- Workspace branch state: `UNKNOWN`; the current filesystem root is not a Git worktree.
- Parent experiment: `exp_20260808_001_mdmt_mia_id_supplement_joint_transaction` (E023 cascade evidence)
- Decoupled failed gate: `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`
- Related evidence:
  - `learning/ROUTE_A_SOURCE_AUDIT.md`
  - `learning/ROUTE_A_MVE_BOUNDARY.md`
  - `summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md`
  - `summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/GT_PROTOCOL_GATE_REPORT.md`

This contract authorizes no implementation or execution. It defines what a later
executor may implement after explicit authorization.

## Question and evidence

- Research question: Can a delayed pre-association source observation, without
  rollback, replay, future/oracle information, ReID, commit, or tracker mutation,
  generate at arrival time a new admissible association candidate through
  candidate-independent reinterpretation against lawful receiver snapshots?
- FACT:
  - Detector bboxes/scores/classes exist before `ByteTracker.track()` and before
    MIA cross-view association.
  - `PacketRuntime` has integer frame-based capture/arrival metadata and a
    future-read guard, but no observation-level delayed service.
  - MIA has no bounded timestamp-indexed receiver history, stable lineage key,
    or exposed detector-to-track assignment map.
  - The current MIA homography is computed from prior/current matched-row centres;
    it is not independent pre-association calibration or pose geometry.
  - Copied observer side state can be isolated from tracker state.
  - The 2026-08-17 onset protocol ended at `GT_PROTOCOL_GATE_FAIL`; no tracking,
    MVE, or non-test GT result was produced.
- INFERENCE:
  - Observation packets, copied receiver snapshots, and a frozen tube can be
    added as observer bookkeeping without changing ByteTrack association.
  - Comparing observer-enabled core-output digests with `DROP_LATE` can detect
    unintended tracker feedback.
- ASSUMPTION:
  - For the mechanism placeholder only, source geometry is zero-displacement and
    the pixel-space support expands by exactly one pixel per elapsed frame on all
    four sides. This is deliberately not a calibrated or final motion/uncertainty
    model.
  - Pair 26 and Pair 48 remain suitable implementation-falsification inputs
    because they were frozen as E023 MVE pairs before Route A results exist.
- UNKNOWN:
  - Whether an independent, causally available cross-view transform exists for
    Pair 26 and Pair 48.
  - Whether any lawful Route A-only candidate will occur once such geometry is
    supplied.
  - Runtime of the proposed observer instrumentation.
- Primary hypothesis: Delayed pre-association source observations can causally
  generate new admissible association candidates at arrival time through
  candidate-independent reinterpretation, without modifying the underlying
  tracker.
- Alternative hypothesis: After all causal, geometry, and non-mutation gates
  pass, time-aligned reinterpretation generates no candidate key absent from
  both the lawful capture reference and `NAIVE_ARRIVAL`.

The hypotheses are separated by the predeclared `route_a_only_new_candidate_count`;
no identity label or tracking metric is needed.

## Design

- Primary variable: observer reasoning condition:
  `DROP_LATE`, `NAIVE_ARRIVAL`, or `ROUTE_A_OBSERVER_MVE`.
- Controlled variables:
  - pairs and full frame ranges;
  - source detector/tracker/config/checkpoint and cached detections;
  - fixed delay `5` frames for delayed conditions;
  - seed `7` where the inherited runtime requires a seed;
  - source packet schema and receiver snapshot schema;
  - transform provider and its provenance gate;
  - zero-displacement tube and one-pixel-per-frame support growth;
  - admissibility rule and candidate-key definition;
  - no jitter, loss, duplication, replay, ReID, GT, shadow input, or commit.
- Dataset / sequence / split:
  - MVE-0: MDMT official Pair 26 and Pair 48 image inputs, full inherited frame
    ranges, solely as fixed plumbing inputs; runtime identity GT must not be read.
  - MVE-1: the same pairs only if an independent transform covers both pairs and
    passes the provenance gate. Otherwise `NEEDS_DATA_SELECTION_AUDIT`; no pair
    substitution is allowed under this contract.
- Frame range: complete pair inputs; no event-triggered trimming or removal.
- Seed(s): runtime seed `7`; no bootstrap or statistical seed because this is a
  mechanism MVE.
- Detector / tracker / checkpoint:
  - frozen parent E023 paper-aligned CARAFE + ByteTrack MIA v8;
  - config `one_carafe_bytetrack_full_mdmt.py`;
  - detector checkpoint
    `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth`;
  - expected SHA256
    `f50882a6814b08d8f9ee2db278825258b52d16463fff6fb45ff45484df7d9e96`;
  - executor must verify hashes before a run and stop on mismatch.
- Message schema and delay semantics:
  - `observation_key=(source_view,capture_frame,detector_row_index)`;
  - capture/arrival frame, bbox, detector score/class, packet version and digest;
  - `arrival_frame=capture_frame+5` for delayed conditions;
  - observation key denotes only a detector row, never a local/global identity.
- Receiver snapshot schema:
  `(receiver_view,state_frame,output_row_index,observed_runtime_id,bbox_xyxy,row_score,snapshot_digest)`.
  The runtime ID is an observed field, not stable lineage proof.
- Safety baseline: `DROP_LATE`; the late packet is counted and discarded before
  observer reasoning.
- Diagnostic upper/reference: a lawful zero-delay observer capture ledger made
  with the same frozen schemas/rule and only information available at capture.
  It is not an identity upper bound and cannot affect tracker state.
- Other required baseline: `NAIVE_ARRIVAL`; it uses the capture bbox directly at
  arrival with the same lawful transform/admissibility rule but no time-indexed
  tube or historical retrieval.
- Optional `CURRENT_ONLY_REINTERPRET`: excluded from the first contract. Adding
  it requires a contract amendment because it expands the condition matrix.

## Frozen candidate semantics

For a source observation `O` captured at `t_c` and read at `t_a`:

1. Construct every source-coordinate tube slice before enumerating candidates.
2. The core bbox remains the capture bbox (zero displacement).
3. At frame `k`, expand the bbox on every side by
   `r(k)=k-t_c` source-image pixels. This is deterministic and monotonic.
4. MVE-1 requires a transform `T(source_view,receiver_view,k)` whose provenance
   proves that it is independent of the evaluated candidate and was available
   no later than the read point. Transform all four support corners and take the
   finite receiver-image AABB.
5. A receiver snapshot at frame `k` is admissible iff its bbox has strictly
   positive intersection area with that transformed expanded support.
6. Missing/non-finite/causally late/association-derived geometry is not a weak
   candidate; it is `GEOMETRY_INADMISSIBLE`, and MVE-1 stops.
7. Record raw IoU with the unexpanded transformed core as compatibility. Do not
   threshold this value.
8. `low_compatibility_retained` means the receiver bbox intersects the expanded
   support but not the unexpanded core. This definition has no fitted threshold.
9. Candidate key:
   `(observation_key,receiver_view,observed_runtime_id)`. The receiver runtime ID
   remains a label-only address; candidate keys do not prove local lineage.
10. The lawful capture ledger contains keys admissible at `t_c` using only
    capture-time receiver snapshots and transform state available at `t_c`.
11. `arrival_time_new_pairing` is an admissible key produced at arrival from a
    time-aligned historical/current snapshot that is absent from the lawful
    capture ledger.
12. `route_a_only_new_candidate` is an arrival-time-new key produced by
    `ROUTE_A_OBSERVER_MVE` and absent from the `NAIVE_ARRIVAL` key set.

No result may change these definitions or `r(k)`.

## Measurement

- Primary metric: `route_a_only_new_candidate_count`. It directly distinguishes
  the frozen reinterpretation/history mechanism from direct stale-bbox use.
- Secondary metrics:
  - source observations, packets emitted, and late arrivals;
  - tube constructions and tube digest invariance;
  - historical/current snapshot and candidate counts;
  - impossible rejects and low-compatibility retained candidates;
  - capture-existing and arrival-new pairing counts;
  - side hypotheses;
  - tracker mutation count and core output/feedback digest mismatches.
- Explicitly forbidden metrics: IDF1, IDSW, MOTA/MDA improvement, identity
  accuracy, recovery precision/recall, or any GT-conditioned score.
- Measurement gates:
  - assertions A1-A12 in `EXEC_PLAN.md` all pass;
  - packet count conservation and deterministic ordering;
  - observer ON/OFF and all three conditions have identical per-frame core
    tracker output and next-feedback digests;
  - source/tube/candidate tables have unique keys and referential integrity;
  - `CROSS_VIEW_GEOMETRY_GATE` passes before MVE-1 candidate creation.
- Known confounders and checks:
  - runtime-ID reuse: report candidate keys as label observations only;
  - post-association H leakage: reject transform provenance;
  - result-tuned support: hash frozen config before any result table is read;
  - hidden observer feedback: cross-condition exact digest equality;
  - future/history mismatch: every read logs read frame and state frame;
  - pair selection: no pair replacement/removal.
- Output directory: `outputs/20260822_mdmt_mia_route_a_observer_mve/`.
- Required tables:
  - `manifest.json`
  - `source_observations.jsonl`
  - `packet_events.jsonl`
  - `receiver_snapshots.jsonl`
  - `evidence_tubes.jsonl`
  - `candidate_events.jsonl`
  - `side_hypotheses.jsonl`
  - `hard_assertions.csv`
  - `condition_summary.csv`
  - `tracker_invariance.csv`
  - `geometry_provenance.json`

## Runs

- Minimum viable experiment:
  - MVE-0 observer plumbing only while geometry gate is failed;
  - Pair 26 and Pair 48;
  - `DROP_LATE`, `NAIVE_ARRIVAL`, `ROUTE_A_OBSERVER_MVE`, fixed delay 5;
  - 6 pair-condition runs plus one exact repeat of
    `ROUTE_A_OBSERVER_MVE × Pair 48` for determinism: 7 pair-runs total;
  - MVE-0 must create no cross-view candidate when geometry is unavailable.
- MVE-1:
  - not ready under current source facts;
  - after geometry PASS, repeat the same 7-run matrix without changing packet,
    tube, candidate, or measurement definitions.
- Formal experiment: out of scope and unauthorized. No full pair sweep follows
  automatically from this MVE.
- Compute budget / expected condition count: 7 pair-runs per stage. Runtime is
  `UNKNOWN`; record measured runtime from the first authorized plumbing run, but
  do not use it to change the run matrix.
- Checkpoint and resume behavior:
  - isolated attempt root per `stage × condition × pair × attempt`;
  - preserve aborted artifacts and restart the same condition cleanly;
  - never merge tracker state or partial event files across attempts;
  - maximum one infrastructure restart per pair-condition, then stop for review.

## Decision

- Success pattern for MVE-0:
  - all plumbing/causality/invariance assertions pass;
  - cross-view candidate count remains zero because geometry fails closed;
  - verdict remains `MVE_INCONCLUSIVE_DUE_TO_GEOMETRY`.
- Success pattern for MVE-1:
  - geometry gate passes;
  - all A1-A12 and tracker invariance checks pass;
  - `route_a_only_new_candidate_count > 0` on at least one frozen pair;
  - verdict `CANDIDATE_REGENERATION_MECHANISM_PRESENT`.
- Failure pattern:
  - valid MVE-1 completes with eligible late observations but
    `route_a_only_new_candidate_count == 0` on both frozen pairs:
    `CANDIDATE_REGENERATION_MECHANISM_NOT_OBSERVED`;
  - insufficient factual observability:
    `MVE_INCONCLUSIVE_DUE_TO_OBSERVABILITY`;
  - any causal assertion failure: `MVE_INVALID_CAUSALITY_VIOLATION`;
  - any tracker mutation/invariance failure: `MVE_INVALID_TRACKER_MUTATION`.
- Stop criteria: any forbidden input, transform failure, result-dependent change,
  tracker-core requirement, or failed hard assertion.
- Decision gate now:
  `MVE-0_IMPLEMENTATION_BOUNDARY_DEFINED / MVE-1_BLOCKED_BY_CROSS_VIEW_GEOMETRY_GATE`.
- Next action for each decision:
  - MVE-0 boundary accepted: explicitly authorize observer-only implementation;
  - geometry gate remains fail: stop after plumbing evidence;
  - geometry gate passes: separately authorize MVE-1 run using this unchanged
    contract;
  - invalidity verdict: fix only the scoped measurement defect, then repeat the
    identical matrix; do not reinterpret the scientific result.
- Conditions requiring `NEEDS_RESEARCH_DECISION`:
  - replacing Pair 26/48 because an independent transform does not cover them;
  - changing the transform family/provenance rule;
  - changing the candidate key, support-growth formula, admissibility rule,
    baseline, dataset, scientific claim, or adding identity evidence.

No new blocking research decision is raised by this plan. The active MVE-1
block is the already-frozen D2 gate, not an unresolved semantic choice.
