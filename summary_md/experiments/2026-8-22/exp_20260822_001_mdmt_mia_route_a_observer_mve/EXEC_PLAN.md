# Route A Observer-Only MVE Execution Plan

## 1. Experiment Identity

- Experiment ID: `exp_20260822_001_mdmt_mia_route_a_observer_mve`
- Title: Route A delayed source-observation candidate-regeneration observer MVE
- Type: `MECHANISM_MVE`
- Status: `PLANNED`
- Parent experiment: E023,
  `exp_20260808_001_mdmt_mia_id_supplement_joint_transaction`
- Decoupled onset experiment:
  `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`
- Target branch: `exp/20260803-002-mdmt-async-tracklet-fusion`
- Scientific question: Can a delayed pre-association source observation form an
  arrival-time-new admissible candidate through candidate-independent,
  time-aligned observer reasoning while the underlying tracker remains exactly
  unchanged?
- Plan authority: planning only; no implementation or run is authorized here.

## 2. Hypothesis

Primary hypothesis:

> Delayed pre-association source observations can causally generate new
> admissible association candidates at arrival time through candidate-independent
> reinterpretation, without modifying the underlying tracker.

Null / alternative interpretation:

> After causal geometry, timing, observability, and tracker-invariance gates pass,
> the time-aligned Route A observer produces no candidate key absent from both
> the lawful capture ledger and `NAIVE_ARRIVAL`.

The discriminating observation is
`route_a_only_new_candidate_count > 0`, not a tracking or identity metric.

## 3. What This MVE Does Not Test

- whether a candidate has the correct identity;
- IDF1, IDSW, MOTA, MDA, tracking improvement, or recovery accuracy;
- B23/B41 local-lineage equivalence, death/rebirth recovery, or global identity;
- ReID, appearance, feature banks, multiple motion branches, learned models;
- commit policy, thresholds for commit, tracker rename/merge/reactivation;
- current-state correction, historical rewrite, rollback, or replay;
- generalization of E023/onset findings to non-test MDMT data;
- the failed onset GT conversion protocol.

## 4. Preconditions

| Precondition | State | Consequence |
| --- | --- | --- |
| D1 mechanism-only measurement protocol | `FROZEN` | No runtime identity GT or identity/tracking success metric. |
| D2 independent causal cross-view geometry | `FROZEN` | Same-frame association-derived MIA H is forbidden. |
| D3 candidate admissibility semantics | `FROZEN` | Rule/config hashes are fixed before results. |
| Independent causal cross-view transform currently available | `NO / NOT PROVEN` | `CROSS_VIEW_GEOMETRY_GATE=FAIL`; only MVE-0 may proceed. |
| Stable local lineage key | `NO` | Use receiver snapshot/runtime-label addresses only. |
| Detector→track mapping required | `NO` | First MVE targets receiver tracker snapshots, avoiding tracker-interface expansion. |
| Onset GT protocol | `FAILED AND DECOUPLED` | Do not read or repair it; no non-test GT is used. |

## 5. Frozen Inputs and Data Rule

### Data selection

- MVE-0 uses Pair 26 and Pair 48, already frozen as E023 implementation-MVE
  pairs before Route A outcomes exist.
- Use both views and the complete inherited frame range for each pair.
- No frame, observation, target count, or pair may be selected/removed after
  reading Route A diagnostics.
- The experiment reads images/detector cache and ordinary runtime rows only.
  Runtime identity GT, source XML identity, official MDA GT, `S_cf`, and shadow
  membership are forbidden inputs.
- MVE-1 uses the same pairs only if the independent transform covers both.
  Otherwise mark `NEEDS_DATA_SELECTION_AUDIT` and stop; do not silently choose
  another pair.

### Runtime freeze

- paper-aligned CARAFE + ByteTrack MIA v8;
- parent config/checkpoint/thresholds and detector cache unchanged;
- fixed observer packet delay: `5` frames;
- seed: `7` where applicable;
- no jitter, loss, duplication, replay, ReID, GT, or core output mutation;
- no parameter or rule sweep.

### Packet schema

```text
observation_key = (source_view, capture_frame, detector_row_index)
capture_frame
arrival_frame
bbox_xyxy
detector_score
detector_class
packet_version
packet_digest
```

The key means “this detector row at capture,” not identity or local lineage.

### Receiver snapshot schema

```text
(receiver_view, state_frame, output_row_index, observed_runtime_id,
 bbox_xyxy, row_score, snapshot_digest)
```

Snapshots are copied after current local ByteTrack output exists and before any
MIA cross-view ID mutation or Supplement write-in. `observed_runtime_id` is a
factual row field, not an immutable track handle.

## 6. Frozen Evidence and Candidate Rules

### Tube placeholder

For `t_c <= k <= t_a`:

```text
core_bbox(k) = capture_bbox
support_radius_px(k) = k - t_c
expanded_support(k) = core_bbox expanded by support_radius_px on all sides
```

This is `MECHANISM_PLACEHOLDER`, not `FINAL_MOTION_MODEL`. The entire list of
slices is constructed and hashed before receiver candidate enumeration.

### Geometry requirement

MVE-1 must receive an independently sourced transform record:

```text
source_view
receiver_view
geometry_state_frame
available_at_frame
transform payload/digest
provider/provenance class
association_derived = 0
```

At read frame `r`, require `available_at_frame <= r`, a finite transform, and a
provider independent of the evaluated candidate. Current MIA H cannot pass.

### Candidate rule

- Compare tube slice `k` only with receiver snapshots whose `state_frame == k`.
- Transform the four expanded-support corners; use their finite receiver-image
  axis-aligned envelope.
- Candidate is admissible iff the receiver bbox has positive intersection area
  with that envelope.
- Non-intersection is a predefined spatial-impossible reject.
- Missing/invalid/late/association-derived transform fails the geometry gate;
  it does not become a low-compatibility candidate.
- Record unexpanded-core IoU as compatibility; do not threshold it.
- Count `low_compatibility_retained` when expanded support intersects but the
  transformed unexpanded core does not.
- Evidence authority is recorded separately as detector score/provenance; it
  does not gate candidate existence.

### Pairing/newness rule

```text
candidate_key =
(observation_key, receiver_view, observed_runtime_id)
```

- `capture_time_existing_pairing`: key admissible at capture using only the
  same-frame receiver snapshot and transform available at capture.
- `arrival_time_new_pairing`: key admissible when the packet arrives, using a
  time-aligned historical/current snapshot, and absent from the capture ledger.
- `route_a_only_new_candidate`: arrival-time-new key present under
  `ROUTE_A_OBSERVER_MVE` and absent under `NAIVE_ARRIVAL`.
- These are runtime-label candidate opportunities, not identity or lineage
  claims.

## 7. Milestones

### M0 — Protocol and provenance gate

- Purpose: freeze manifests, input hashes, schemas, rules, pairs, delay, and
  geometry provenance before any Route A result exists.
- Inputs: this contract, source audit, E023 pair/config/checkpoint manifest, D1-D3.
- Outputs: frozen manifest, schema/rule digests, geometry provenance report.
- Allowed changes: `LOGGING`, `BOOKKEEPING` planning metadata only.
- Forbidden changes: data substitution, threshold/rule changes, current MIA H
  promotion, tracker/MIA-core edits.
- Diagnostics: pair/frame manifest; checkpoint/config hashes; GT/oracle field
  denylist; transform provider audit.
- Exit criteria: all non-geometry inputs frozen. If independent transform is not
  proven, declare geometry FAIL and route only to MVE-0.
- Stop conditions: hash mismatch, unverifiable input provenance, or any proposed
  use of onset GT/S_cf/current association-derived H.

### M1 — Observer plumbing (MVE-0)

- Purpose: prove capture, packet delay, causal arrival, copied snapshots, side
  records, and zero tracker effect.
- Inputs: pre-association detector rows, current local tracker output snapshots,
  fixed delay 5, condition selector.
- Outputs: observation/packet/snapshot ledgers, read provenance, tracker
  invariance table.
- Allowed changes: `LOGGING`, `BOOKKEEPING`, `SIDE_STATE` only.
- Forbidden changes: tracker interface/core, association output, row mutation,
  feedback change, candidate creation without legal geometry.
- Diagnostics: source/packet/late/snapshot counts, queue conservation, per-frame
  core output and feedback digests, observer ON/OFF equality.
- Exit criteria: all MVE-0 assertions pass; tracker mutation and digest mismatch
  counts are zero; geometry-unavailable events are fail-closed.
- Stop conditions: future read, alias/write, GT/oracle read, packet misordering,
  or any core digest divergence.

### M2 — Candidate-independent evidence construction

- Purpose: create and freeze the single zero-displacement/monotonic-envelope
  tube without reading candidate state.
- Inputs: arrived factual source packet only.
- Outputs: time-indexed slices, construction input list, tube digest.
- Allowed changes: `SIDE_STATE` only.
- Forbidden changes: target trajectory/Kalman/covariance/feature input, multiple
  branches, learned propagation, output feedback.
- Diagnostics: construction count, source-to-tube referential integrity,
  candidate-order permutation invariance, repeat digest equality.
- Exit criteria: same source packet always produces the same tube digest before
  candidates are enumerated.
- Stop conditions: candidate-dependent input, unfrozen formula/config, or any
  tube change after candidate enumeration begins.

M2 may be exercised in MVE-0, but without geometry it cannot authorize cross-view
candidate enumeration or a mechanism verdict.

### M3 — Time-aligned candidate regeneration (MVE-1)

- Purpose: test whether lawful geometry plus time-aligned history produces a
  Route-A-only new candidate opportunity.
- Inputs: frozen tube, copied receiver snapshots, geometry record that passed D2.
- Outputs: candidate events, capture ledger, naive ledger, Route A ledger, side
  hypotheses, condition summaries.
- Allowed changes: `SIDE_STATE`; a read-only geometry `INTERFACE` if required.
- Forbidden changes: `TRACKER_CORE`, current MIA H fallback, detector→track
  instrumentation, GT/ReID, commit, row/feedback mutation.
- Diagnostics: historical/current/admissible/impossible/low-compatibility/new/
  Route-A-only counts; time alignment; transform provenance.
- Exit criteria: all candidate records satisfy frozen keys/rules and all A1-A12
  assertions pass.
- Stop conditions: geometry gate FAIL, transform fallback, candidate-specific
  propagation, or rule tuning.

M3 is currently `BLOCKED_BY_CROSS_VIEW_GEOMETRY_GATE`.

### M4 — Mechanism audit and verdict

- Purpose: issue exactly one allowed verdict without identity interpretation.
- Inputs: completed gate/assertion/invariance/condition summaries.
- Outputs: `RESULTS.md`, `DECISION.md`, immutable artifact manifest.
- Allowed changes: `LOGGING`/reporting only.
- Forbidden changes: rerun selection, threshold changes, excluded metrics,
  identity/lineage/performance claims, automatic Formal escalation.
- Diagnostics: artifact completeness, duplicate-free attempt accounting,
  decision-table evaluation.
- Exit criteria: exactly one registered verdict with cited gate evidence.
- Stop conditions: incomplete artifacts, mixed attempts, or a conclusion broader
  than the verdict space.

## 8. MVE Conditions

| Condition | Delay | Unique change | Geometry behavior | Tracker mutation |
| --- | ---: | --- | --- | ---: |
| `DROP_LATE` | 5 | Discard arrived observation before observer reasoning. | None. | 0 |
| `NAIVE_ARRIVAL` | 5 | Use capture bbox directly at arrival; no tube/history. | Same approved provider/rule as Route A; fail closed if absent. | 0 |
| `ROUTE_A_OBSERVER_MVE` | 5 | Frozen tube plus time-aligned historical/current retrieval. | Same approved provider/rule as Naive; fail closed if absent. | 0 |

`CURRENT_ONLY_REINTERPRET` is omitted. It is not needed to distinguish Route A
from Naive in the first MVE and would expand the run matrix.

Fairness requirements:

- identical images, cached detections, ByteTrack/MIA core, pair frames, seed,
  packet schema, delay, geometry provider, support rule, and compute-independent
  logging fields;
- only the observer treatment differs;
- no condition gets GT, shadow, ReID, extra remote state, or a different history
  window;
- all core tracker outputs and next-frame feedback must be exact across conditions.

## 9. Measurement Protocol

| Term | Frozen operational definition |
| --- | --- |
| source observation | One detector row copied after detector output and before ByteTrack association, identified by `(view,capture_frame,row_index)`. |
| late arrival | A unique emitted observation packet consumed only when `arrival_frame > capture_frame` and current frame is at least `arrival_frame`. |
| receiver snapshot | One copied local ByteTrack output row before any current-frame MIA cross-view mutation/write-in, addressed by view/frame/row/runtime label. |
| admissible candidate | A time-aligned receiver snapshot with positive bbox intersection against the transformed frozen expanded support under a D2-passing transform. |
| physically impossible reject | A valid-geometry, time-aligned receiver bbox with zero intersection against expanded support. Missing/invalid geometry is a gate failure, not this category. |
| low-compatibility retained | Expanded support intersects the receiver bbox but unexpanded transformed core does not. |
| arrival-time-new pairing | Candidate key absent from the lawful capture ledger and admissible when processed at arrival against historical/current snapshots. |
| Route-A-only new candidate | Arrival-new key produced by Route A and absent from Naive. |
| side hypothesis | Read-only record referencing source observation, snapshot, authority, compatibility, support/conflict, and status; it has no consumer in tracker/MIA. |
| tracker mutation | Any observer-originated change to detector/tracker rows, `self.tracks`, NMS inputs/outputs, IDs, survival, matching, features, or feedback, or any per-frame core/feedback digest mismatch against `DROP_LATE`. |

Primary mechanism measure:

```text
route_a_only_new_candidate_count
```

No statistical performance threshold is used. A positive count is an existence
witness only after all causal and observability gates pass.

## 10. Required Diagnostics

```text
source_observation_count
packet_emitted_count
late_arrival_count
evidence_tube_construction_count
historical_snapshot_count
current_snapshot_count
historical_candidate_count
current_candidate_count
physically_impossible_reject_count
low_compatibility_retained_count
capture_time_existing_pairing_count
arrival_time_new_pairing_count
route_a_only_new_candidate_count
side_hypothesis_count
tracker_mutation_count
core_output_digest_mismatch_count
feedback_digest_mismatch_count
```

`tracker_mutation_count`, `core_output_digest_mismatch_count`, and
`feedback_digest_mismatch_count` must all be zero.

## 11. Hard Assertions

| ID | Assertion | Planned check |
| --- | --- | --- |
| A1 | No future information access. | Every packet/read records `read_at_frame`, `capture_frame`, `arrival_frame`, `state_frame`; require capture/state/availability frames `<= read_at_frame` as applicable. |
| A2 | No S_cf/shadow membership. | Schema denylist plus runtime read counters; prohibited keys must be absent from all Route A artifacts. |
| A3 | No GT identity in candidate generation. | No GT path/field in manifest or schemas; runtime GT-read count must be zero outside frozen author offline init, which is separately tagged and never exposed to observer records. |
| A4 | Tube frozen before candidate enumeration. | Record `tube_finalized_sequence < first_candidate_sequence` and tube digest. |
| A5 | Same source yields identical tube independent of candidate. | Rebuild under permuted/empty candidate enumerations and require identical digest. |
| A6 | Historical comparison is time aligned. | Require `tube_slice_frame == receiver_state_frame` on every historical candidate row. |
| A7 | No target state in source propagation. | Exact allowlist of tube inputs; reject target runtime ID, trajectory, Kalman mean/covariance, feature, candidate list. |
| A8 | No historical tracker mutation. | Snapshots are copied/non-aliased; pre/post history digests equal. |
| A9 | No pending-hypothesis tracker effect. | No hypothesis consumer outside side ledger; observer ON/OFF core digests equal. |
| A10 | Tracker mutation count zero. | Mutation counter and per-frame core/feedback exact comparisons all zero. |
| A11 | Admissibility fixed before results. | Contract/config/schema hash written before first condition; no later hash change accepted. |
| A12 | Transform provenance satisfies D2. | Required for MVE-1 only. `CROSS_VIEW_GEOMETRY_GATE` rejects association-derived/current MIA H, late availability, missing provider, or non-finite transform. In MVE-0 record `NOT_APPLICABLE_GEOMETRY_FAIL_CLOSED`, not PASS. |

Any applicable assertion failure is fail-closed; no partial scientific verdict
is allowed. A12 being unavailable is the registered MVE-0 boundary and forces
`MVE_INCONCLUSIVE_DUE_TO_GEOMETRY`; it is not reported as an A12 pass.

## 12. CROSS_VIEW_GEOMETRY_GATE

### Required PASS evidence

- independent provider type and source are named;
- transform does not depend on current or evaluated candidate association;
- its capture/state/availability times are explicit and causal;
- transform direction, coordinate frames, image scaling, and finite-domain rules
  are documented;
- Pair 26 and Pair 48 both have complete required coverage;
- transform manifest/config hashes are frozen before Route A results;
- a source audit confirms that current MIA matched-row H is not used as fallback.

### Current state

```text
CROSS_VIEW_GEOMETRY_GATE = FAIL
reason = NO_INDEPENDENT_CAUSAL_TRANSFORM_PROVEN_FOR_FROZEN_PAIRS
```

Consequences:

- MVE-0 observer plumbing may be implemented after explicit authorization;
- MVE-0 must emit zero cross-view candidates and end
  `MVE_INCONCLUSIVE_DUE_TO_GEOMETRY` when otherwise valid;
- MVE-1 and any candidate-regeneration mechanism claim are blocked;
- current post-association MIA H cannot be used to clear the gate.

## 13. Instrumentation Plan

| Need | Change type | Boundary |
| --- | --- | --- |
| observation key and pre-association packet copy | `BOOKKEEPING` | Read-only hook after detector output, before ByteTrack association. |
| observer delay queue | `SIDE_STATE` | Separate from Local/H/ID/Supplement runtime behavior; no return value to core path. |
| receiver causal snapshot ledger | `BOOKKEEPING` | Copy local ByteTrack rows before cross-view MIA mutation. |
| read/provenance/assertion counters | `LOGGING` | Observer artifacts only. |
| frozen tube and digest | `SIDE_STATE` | Construct from packet allowlist before candidate enumeration. |
| candidate/hypothesis ledgers | `SIDE_STATE` | No tracker/MIA consumer. |
| core/feedback invariance hashes | `LOGGING` | Compare conditions without altering rows. |
| independent geometry provider | `INTERFACE` | Read-only input for MVE-1; must pass D2. |
| detector→track assignment exposure | `NONE` | Not required by this MVE. |
| stable lineage or tracker lifecycle API | `NONE` | Explicitly outside first MVE. |
| tracker core or correction interface | `STOP / RESEARCH REVIEW` | Any need for this invalidates observer-only scope. |

No implementation file is specified by this planning document; the executor
must first map these boundaries without changing tracker/MIA core semantics.

## 14. Run Matrix and Budget

### MVE-0

```text
2 pairs × 3 conditions = 6 pair-condition runs
+ 1 exact repeat: Pair 48 × ROUTE_A_OBSERVER_MVE
= 7 pair-runs
```

Purpose: implementation/causality/invariance falsification only. Runtime is
`UNKNOWN`; measure it from the first authorized attempt without changing the
matrix.

### MVE-1

Same 7-run matrix, only after geometry PASS. It is not ready and must not be
queued, partially run, or simulated with current MIA H.

### Resume/restart

- one isolated attempt directory per stage/condition/pair/attempt;
- an interrupted attempt is `ABORTED` and excluded wholly;
- one clean infrastructure restart is permitted with unchanged hashes;
- no tracker state or partial artifacts cross attempts;
- a second infrastructure failure stops the MVE for review;
- parameter/rule retries: zero.

## 15. Expected Artifacts

Tracked planning/reporting:

```text
summary_md/experiments/2026-8-22/
  exp_20260822_001_mdmt_mia_route_a_observer_mve/
    EXPERIMENT_CONTRACT.md
    EXEC_PLAN.md
    RESULTS.md                 # created only after an authorized run
    DECISION.md                # created only after an authorized run

learning/MVE_CHANGE_EXPLAINER.md  # created during authorized implementation
```

Ignored/raw runtime output:

```text
outputs/20260822_mdmt_mia_route_a_observer_mve/
  manifest.json
  geometry_provenance.json
  source_observations.jsonl
  packet_events.jsonl
  receiver_snapshots.jsonl
  evidence_tubes.jsonl
  candidate_events.jsonl
  side_hypotheses.jsonl
  hard_assertions.csv
  condition_summary.csv
  tracker_invariance.csv
  attempts/
```

Flowchart:

```text
mermaid/exp_20260822_001_mdmt_mia_route_a_observer_mve/
  route_a_observer_mve_plan.mmd
```

## 16. Stop Rules

Stop immediately if:

- future information is required or read;
- GT identity is required to construct or score candidates;
- `S_cf`, shadow state, or any oracle is required;
- source propagation depends on candidate state;
- historical/current tracker state or outputs are mutated;
- a pending hypothesis changes detector/tracker/MIA/feedback behavior;
- candidate/tube definitions must be tuned after viewing results;
- cross-view geometry cannot satisfy D2 (stop before MVE-1);
- implementation requires `TRACKER_CORE` semantic changes;
- Pair 26/48 must be replaced without a contract amendment;
- condition outputs are not core-digest identical;
- attempts or partial artifacts are mixed;
- an identity, lineage, performance, or Formal claim is proposed.

## 17. Verdict Space

Only one of the following may appear in `DECISION.md`:

```text
CANDIDATE_REGENERATION_MECHANISM_PRESENT
CANDIDATE_REGENERATION_MECHANISM_NOT_OBSERVED
MVE_INCONCLUSIVE_DUE_TO_GEOMETRY
MVE_INCONCLUSIVE_DUE_TO_OBSERVABILITY
MVE_INVALID_CAUSALITY_VIOLATION
MVE_INVALID_TRACKER_MUTATION
```

Decision mapping:

| Gate/evidence | Verdict |
| --- | --- |
| MVE-0 otherwise valid, geometry FAIL | `MVE_INCONCLUSIVE_DUE_TO_GEOMETRY` |
| MVE-1 valid and Route-A-only new count > 0 on at least one frozen pair | `CANDIDATE_REGENERATION_MECHANISM_PRESENT` |
| MVE-1 valid, eligible observations exist, Route-A-only new count = 0 on both pairs | `CANDIDATE_REGENERATION_MECHANISM_NOT_OBSERVED` |
| Required snapshots/observations cannot be factually audited | `MVE_INCONCLUSIVE_DUE_TO_OBSERVABILITY` |
| Any applicable A1-A7/A11 failure, or an A12 violation after MVE-1 was wrongly allowed to start | `MVE_INVALID_CAUSALITY_VIOLATION` |
| Any A8-A10 mutation/invariance failure | `MVE_INVALID_TRACKER_MUTATION` |

Forbidden verdicts include `ROUTE_A_WORKS`, `ROUTE_A_FAILS`, performance or
identity-recovery claims.

## 18. Exact Decision Gate

```text
CURRENT:
  MVE-0_IMPLEMENTATION_BOUNDARY_DEFINED
  CROSS_VIEW_GEOMETRY_GATE=FAIL
  MVE-1_BLOCKED

AFTER AUTHORIZED MVE-0:
  if any causality/mutation assertion fails -> invalid verdict and STOP
  if assertions pass and geometry still FAIL -> MVE_INCONCLUSIVE_DUE_TO_GEOMETRY

AFTER SEPARATE GEOMETRY PASS + MVE-1 AUTHORIZATION:
  if route_a_only_new_candidate_count > 0 -> MECHANISM_PRESENT
  else if eligible late observations exist -> MECHANISM_NOT_OBSERVED
  else -> INCONCLUSIVE_DUE_TO_OBSERVABILITY
```

There is no automatic Formal, no automatic method implementation, and no
threshold/model revision after any verdict.

## 19. Blocking Research Decisions

No new blocking research decision is introduced. D1-D3 remain frozen.

The current MVE-1 blocker is a failed implementation/evidence gate under D2:
no independent causal transform has been proven for the frozen pairs. Changing
the transform family or pair set would require `NEEDS_RESEARCH_DECISION`; this
plan does not make that change.
