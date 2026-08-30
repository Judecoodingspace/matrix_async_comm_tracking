# EXPERIMENT_CONTRACT

## Identity

- Experiment ID: `exp_20260830_001_work1_pre_id_eligibility_mve`
- Short name: Work 1 Pre-ID candidate-eligibility preservation MVE
- Status: `PREEXECUTION_FROZEN / PLANNING_ONLY / EXECUTION_NOT_AUTHORIZED`
- Scientific role: `MECHANISM_EXISTENCE_PROBE`
- Workstream: Work 1 async candidate cascade paper
- Intervention family: `PRE_ID_CANDIDATE_ELIGIBILITY_PRESERVATION`
- Route A status: `PARKED_AFTER_PLANNING`
- Frozen planning provenance:
  - repository: `Judecoodingspace/matrix_async_comm_tracking`
  - branch: `exp/20260827-001-route-a-same-correspondence-geometry-diagnosis`
  - commit: `9aaebfaafb78a3715c6ec0be710d582bad127db8`
- Required source documents:
  - `summary_md/RESEARCH_SCOPE_REDUCTION_ROUTE_A_TO_CANDIDATE_CASCADE.md`
  - `summary_md/WORK1_ASYNC_CANDIDATE_CASCADE_PAPER_PLAN.md`
- Planned output root:
  `outputs/20260830_work1_pre_id_eligibility_mve/`
- Current execution state:
  `MVE_NOT_RUN / FORMAL_NOT_RUN / HELDOUT_NOT_ACCESSED`

This contract is pre-execution frozen for implementation-authorization review.
It does not authorize source modification, MVE
execution, GT grading, tracker write-in, Formal execution or held-out access.

## Question and evidence

### Research question

When all current-frame MIA inputs and processing are held fixed, does replacing
post-ID mutable Supplement eligibility with an immutable eligibility record
created before the first ID-state mutation remove eligibility loss caused only
by mutable ID-state timing, without adding candidates outside the pre-ID set or
mutating tracker state?

### Frozen scientific role

This MVE is a `MECHANISM_EXISTENCE_PROBE`. It tests whether at least one
pre-frozen, legal, complete non-test train unit exhibits the full chain:

```text
E_pre exists
-> post-ID membership disappearance
-> PRE_ID_FROZEN preserves eligibility
-> read-only High-score probe restores WRITEIN_OPPORTUNITY
```

It is not a prevalence, cross-pair robustness, majority-consistency,
delay-onset or tracking-performance study. One legal complete activated unit
is sufficient for mechanism-existence support. If none activates, the result
is `MVE_MECHANISM_NOT_ACTIVATED`; no pair may be added or replaced.

### `FACT`

- Frozen E023 v8 computes an old-unmatched candidate set before the first
  current-frame ID-state mutation/delivery.
- It then performs `new_A_to_B`, `new_B_to_A` and
  `old_unmatched_repair`, recomputes old-unmatched membership, and passes the
  final post-ID list to High-score `not_matched_supplement()`.
- Under delayed ID delivery, the current branch receives pre-mutation rows and
  association lists; timely delivery exposes post-mutation state.
- The frozen E023 artifact already represents current-frame row lineage as
  `pre_branch_row_index` and validates conservation by requiring equal row
  shape and equality of every row column except the runtime-ID column.
- E023 Formal supports d5 candidate-set-mediated compensation, but `S_cf`,
  `Yec`, synchronous shadow membership and counterfactual membership are
  diagnostic-only.
- The non-test compensation-onset experiment was not run because its GT
  protocol gate failed. Legal non-test GT safety grading is unavailable.
- The MDMT train directory contains 25 complete dual-view pairs in canonical
  numeric pair-ID order. The prior non-test compensation-onset MVE,
  development and holdout were explicitly not run, and the repository/output
  provenance audit found no Work 1 eligibility or Supplement outcome for any
  train pair.
- E023 Formal v8 binds its generated source artifact through
  `cascade_run_manifest.json`, `cascade_edge_manifest.json` and per-attempt
  provenance. The relevant hashes match the files currently present in the
  generated v8 artifact.

### `INFERENCE`

- Preserving an already legal pre-ID eligibility may remove accidental
  dependence on whether Supplement reads pre- or post-ID mutable association
  state.
- A frame-scoped row key plus a non-ID row fingerprint is sufficient for an
  observer-only MVE because the MVE stops before constructing an ID-bearing
  write-in row.
- A restored High-score write-in opportunity is mechanism evidence only; it is
  not evidence that the candidate is correct or improves tracking.

### `ASSUMPTION`

- Fixed d5 ID delay is a mechanism-stress condition inherited from E023, not a
  delay selected or optimized by this MVE.

### `UNKNOWN`

- Whether any frozen non-test MVE input contains pre/post eligibility
  disappearance events.
- Whether a disappearance-only token creates a High-score write-in
  opportunity.
- Whether preserved candidates are true or false associations; GT safety
  grading is blocked.
- Whether a later state-changing intervention would improve MDA, IDF1, MOTA or
  IDSW.
- Whether the effect generalizes beyond the eventual frozen MVE inputs and d5.

### Design-blocker check

```text
NO_MVE_DESIGN_BLOCKER_FOUND
```

The frozen source provides a current-frame, runtime-ID-independent row index
and a non-ID row-conservation check. The observer-only MVE therefore does not
need a later mutable runtime ID, `matched_ids`, confirmed-ID state, GT identity,
future state or Route A lineage to measure eligibility preservation and
write-in opportunity.

If implementation inspection later shows that the probe cannot operate without
one of those forbidden inputs, the result becomes `MVE_DESIGN_BLOCKER` and the
epoch stops. It must not switch to Transaction-consistent, Version-aware or
Route A semantics.

### Primary hypothesis

For at least one mechanism-active current-frame event, `POST_ID_MUTABLE` drops a
pre-ID eligibility without an explicit logical invalidation, while
`PRE_ID_FROZEN` preserves that token exactly once and exposes the corresponding
High-score write-in opportunity. All subset, lifecycle, oracle-firewall and
non-interference gates remain satisfied.

### Alternative hypothesis

The mechanism is not activated on the frozen inputs, the pre-ID token cannot be
conserved without forbidden mutable identity state, preservation fails to
restore any write-in opportunity, or the observer violates subset, exactly-once,
oracle-firewall or non-interference requirements.

## Design

### Primary causal variable

```text
ELIGIBILITY_SOURCE = POST_ID_MUTABLE vs PRE_ID_FROZEN
```

No other scientific variable may change.

### Experimental conditions

#### Baseline — `POST_ID_MUTABLE`

Use the existing author control flow. High-score Supplement eligibility is the
old-unmatched membership recomputed after all three current-frame ID-state
mutation/delivery stages.

For the MVE, this set is read and evaluated by the observer but the core author
runtime remains unchanged.

#### Intervention — `PRE_ID_FROZEN`

Immediately after the existing pre-ID `get_matched_ids()` result and before
the first ID-state mutation/delivery, create immutable eligibility tokens from
the already legal pre-ID old-unmatched membership.

At the High-score boundary, the observer evaluates surviving tokens with the
same read-only opportunity probe used for the baseline. It does not union the
pre- and post-ID sets, write a bbox row, change IDs, append matched/confirmed
state, run NMS or feed the tracker.

### Frozen eligibility semantics

For frame-direction unit `u`, define:

```text
E_pre(u)  = eligibility tokens created before first ID mutation/delivery
E_post(u) = row-lineage tokens in the existing post-ID mutable membership
I_exp(u)  = E_pre tokens with an authorized explicit invalidation
E_int(u)  = E_pre(u) minus I_exp(u)
```

Required invariant:

```text
E_int(u) subset_of E_pre(u)
```

`E_post` is the baseline source only. It is never unioned with `E_pre` or
`E_int`.

### Token key and payload

The immutable token key is exactly:

```text
(frame_id, source_view_id, target_view_id, pre_id_row_index)
```

The key contains no runtime ID.

Minimal frozen payload:

```text
creation_stage = PRE_FIRST_ID_MUTATION
non_id_row_fingerprint = digest(row[1:])
source_center_snapshot
source_corner_snapshot
consumption_state = UNCONSUMED
```

The source center/corners are the existing pre-ID candidate payload, not newly
generated spatial evidence. No target candidate, target identity, ranking,
score fusion, history or future information is stored.

The MVE never needs an ID-bearing write-in row. `WRITEIN_OPPORTUNITY` means only
that the frozen author-equivalent geometric/detector checks would select a
target bbox; no source runtime ID is attached and no state is mutated.

### Lifecycle and invalidation

A token is valid only within its creation frame. It expires before processing
the next frame.

Authorized terminal transitions:

```text
UNCONSUMED -> CONSUMED_ONCE
UNCONSUMED -> INVALIDATED_ROW_LOST
UNCONSUMED -> INVALIDATED_ROW_REPLACED
UNCONSUMED -> EXPIRED_FRAME_END
```

Definitions:

- `INVALIDATED_ROW_LOST`: the source row index no longer exists at the
  High-score boundary.
- `INVALIDATED_ROW_REPLACED`: row shape changed or `row[1:]` no longer matches
  the frozen non-ID fingerprint.
- `CONSUMED_ONCE`: the observer evaluated the token once at the legal
  High-score boundary.
- `EXPIRED_FRAME_END`: the legal High-score boundary was not reached before
  the frame ended.

No additional logical-impossibility predicate is authorized in this MVE.
Adding one changes the eligibility semantics and requires
`NEEDS_RESEARCH_DECISION`.

The following is diagnostic only and is not invalidation:

```text
POST_ID_MEMBERSHIP_DISAPPEARED_ONLY
```

It means the conserved token is absent from `E_post`, with no authorized
terminal transition. ID rename alone cannot invalidate a token.

Exactly-once rules:

- every surviving token has `consume_count` exactly `1`;
- every explicitly invalidated or expired token has `consume_count` exactly
  `0`;
- duplicate consumption is an integrity failure;
- consumption affects only observer state.

### Controlled variables

- ID-state delay: fixed `d5`; no delay sweep or onset selection.
- Local Track, existing Homography channel and Supplement delivery: timely,
  matching the E023 d5 mechanism condition.
- Existing Homography matrices and all projection behavior: identical across
  conditions; no new H/F/BEV/flow path and no parameter change.
- Detector outputs, tracker rows, row order, matched/confirmed state, existing
  thresholds, target detections, NMS, feedback and publication: identical
  shared inputs.
- Existing High-score projection, image-bound, detector-IoU, bbox-size and
  target-selection rules: unchanged and shared.
- Detector/tracker/checkpoint/source: frozen to one manifest before execution.
- Logger, observer schema and opportunity-probe version: frozen before the
  first MVE input.
- Runtime seed: `7`; no stochastic method branch. Pair selection never uses
  this seed and is canonical numeric ordering only.
- Historical rule retained for provenance:
  `No official test pair, held-out outcome, GT/XML/MDA GT, result-conditioned
  pair replacement or outcome-conditioned rerun.` The absolute runtime portion
  is `SUPERSEDED_BY_AUTHOR_RUNTIME_XML_GOVERNANCE_AMENDMENT`; official-test,
  held-out, outcome-conditioned selection/rerun, Work 1 oracle use, and GT
  grading remain prohibited.

### Dataset / sequence / split

Use only the following pre-execution-frozen non-test MDMT train inputs.

Pool construction is deterministic and outcome-blind:

1. enumerate raw MDMT `train` pair IDs having both view-1 and view-2 image
   directories;
2. require the two views to have identical frame-filename sets;
3. exclude a pair only if repository provenance shows that its Work 1
   eligibility/Supplement outcome was viewed, screened or used for selection;
4. do not exclude a pair merely because it participated in Route A geometry;
5. sort the remaining pair IDs as base-10 integers ascending;
6. take exactly the first five, both directions, with every available frame.

The audited complete pool is:

```text
23,25,27,28,29,30,32,39,42,44,45,50,51,53,54,58,63,64,65,66,69,70,74,76,78
```

Pollution audit evidence is outcome-free: the prior non-test onset record says
`RESULTS: NOT RUN`, and its gate report says MVE, development, holdout, Formal,
MIA and tracking were not run after G2. No Work 1 train output path or tracked
result was found. E023 used official-test pairs only. Route A geometry use is
not Work 1 contamination under RD-MVE-2. Therefore no pool member is excluded.

Frozen selection:

| Pair | Directions | Full frame filenames | Frames/view | Sorted-filename-set SHA-256 |
| --- | --- | --- | ---: | --- |
| 23 | `1->2`, `2->1` | `00000001.jpg`-`00000700.jpg` | 700 | `e2f265adf10f0fa9191bad891aa0ebe28b9fb85f5dd77cf4e5e9ca69409e877b` |
| 25 | `1->2`, `2->1` | `00000001.jpg`-`00000500.jpg` | 500 | `8aff41881ed27abda031186b90628a5e0c69b3d898e2d3b3b6631bbef22388ab` |
| 27 | `1->2`, `2->1` | `00000361.jpg`-`00000700.jpg` | 340 | `96d4ae0b4f794d2a99a7e97f6915367f3f85de5fd4e5cb6b05105d55ed7b1364` |
| 28 | `1->2`, `2->1` | `00000001.jpg`-`00000700.jpg` | 700 | `e2f265adf10f0fa9191bad891aa0ebe28b9fb85f5dd77cf4e5e9ca69409e877b` |
| 29 | `1->2`, `2->1` | `00000001.jpg`-`00000700.jpg` | 700 | `e2f265adf10f0fa9191bad891aa0ebe28b9fb85f5dd77cf4e5e9ca69409e877b` |

The filename-set digest is over newline-delimited canonical sorted basenames;
both views have the same digest for every selected pair. Before any future
implementation run, `MVE_INPUT_MANIFEST.json` must serialize these exact ten
units and add content hashes for the resolved images. Any missing file,
filename-set drift, view mismatch or content-hash drift is
`MVE_INPUT_MANIFEST_DRIFT`: stop; do not replace the pair.

This MVE has no development selection and no held-out phase. Its inputs cannot
later be relabeled as untouched formal held-out evidence.

### Frozen E023 Formal v8 source provenance

The baseline authority is the generated source artifact actually named by the
E023 Formal run, not current main or this planning branch:

```text
repository-state branch:
  exp/20260803-002-mdmt-async-tracklet-fusion
repository-state commit:
  7fcea6808bff2e17e435b39e3f44c00d73d92488
generated source artifact:
  /mnt/data/yzm/experiments/mdmt_mia_official/variants/
  packetized_id_supplement_cascade_v8
formal run manifest:
  outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/
  cascade_run_manifest.json
formal run-manifest SHA-256:
  14d23ca17faef9d5f96769d771e02cb12eb615a5a2c96de9d072f47d450ab17e
variant manifest:
  cascade_edge_manifest.json
variant-manifest SHA-256:
  0eb11be11898af2c8b9ba3de8140ca5beac9de3df5ba9213bdafe715b9b9e5ed
run fingerprint:
  0831fcfa4e12da8f8abe6b598fdf86dc5a802f983953c0076146f6952e83e3e8
```

The aggregate run manifest names that artifact and variant-manifest digest;
all 140 per-attempt provenance records expose the same repository commit and
variant-manifest digest. The short Work 1 control flow is frozen to:

| Relevant file | Frozen SHA-256 | Required source region |
| --- | --- | --- |
| `demo/supplement_MIA.py` | `4c8674425462dc8e14dc1f53eaaa62a83d93879e45b4cb46a05b38ea78008616` | pre-ID capture and `new_A_to_B`, `new_B_to_A`, `old_unmatched_repair`, post-ID recomputation and High-score calls at lines 312-452 |
| `demo/utils/cascade_runtime.py` | `b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2` | row snapshot/conservation and author High-score input preparation at lines 162-253 and 293-407 |
| `demo/utils/supplement.py` | `415484d61c9b805f26ba77032af8a2e67617266a861420557f0d886ff1be5ec6` | `not_matched_supplement()` at lines 9-176 |

The current artifact hashes equal the hashes inside the variant manifest.
The historical commit object is not present in the current reconstructed local
Git object store, so the generated artifact plus its hash-closed Formal
manifest chain is the executable source authority. A future authorization must
fail closed if any one of these four digests differs; it may not substitute a
newer ref or reconstructed helper.

### Safety baseline

`POST_ID_MUTABLE` is the unmodified author eligibility source and the sole MVE
baseline.

The safety question—whether preserved candidates are correct—is not answerable
without a legal GT protocol. It must be reported as:

```text
GT_SAFETY_UNGRADED
```

The existing non-test GT blocker does not block this observer-only mechanism
MVE. It blocks candidate-correctness, false-write-in, safe-write-in, GT
identity, MDA, IDF1, MOTA, IDSW, overall-delay-robustness and deployment-benefit
claims. Mechanism support cannot remove or bypass that blocker.

### Diagnostic upper bound

None. `S_cf`, `Yec`, synchronous shadow membership and counterfactual
membership are prohibited from MVE runtime and are not run as an upper bound.

### Intervention stop boundary

```text
read-only High-score WRITEIN_OPPORTUNITY
-> STOP
```

No bbox append, runtime-ID selection, matched/confirmed mutation, NMS change,
tracker feedback, identity decision or tracker commit is part of this MVE.

## Measurement

### Unit and complete denominator

Unit:

```text
u = one non-test pair-direction
```

The ledger contains one row for every `E_pre` token. Tokens may not disappear
from bookkeeping because they are absent from `E_post`, invalidated, expired or
produce no opportunity.

### Primary mechanism metrics

For each unit:

```text
N_pre
  = |E_pre|

N_explicit_invalid
  = |I_exp|

N_disappearance_only
  = count(e in E_pre where e not in E_post and e not in I_exp)

N_preserved_disappearance
  = count(disappearance-only e where e in E_int)

preservation_rate
  = N_preserved_disappearance / N_disappearance_only
```

If `N_disappearance_only=0`, `preservation_rate` is `NA`, not zero or one, and
the unit provides no activation evidence.

Required integrity counts:

```text
N_subset_violation
N_post_only_injected
N_duplicate_token
N_duplicate_consumption
N_consumed_after_expiry
N_consumed_after_invalidation
N_runtime_id_key_field
N_forbidden_runtime_field
```

All must equal zero.

### High-score opportunity metrics

The same mutation-free author-equivalent probe is applied separately to
`E_post` and `E_int`:

```text
N_trigger_post
N_trigger_pre_frozen
N_writein_opportunity_post
N_writein_opportunity_pre_frozen
N_restored_writein_opportunity
```

`N_restored_writein_opportunity` counts tokens that:

1. are `POST_ID_MEMBERSHIP_DISAPPEARED_ONLY`;
2. remain in `E_int`;
3. produce `WRITEIN_OPPORTUNITY` under the shared read-only probe;
4. have no corresponding opportunity under `POST_ID_MUTABLE` because the token
   was absent from `E_post`.

No metric labels an opportunity correct, beneficial or safe.

### Non-interference checks

Compare the same frozen input with Work 1 observer OFF and ON. Required exact
equality after excluding only observer ledgers:

- detector rows/scores/labels;
- ByteTrack rows, row order, bboxes and runtime IDs;
- all three ID-state stage outputs;
- actual author High-score/low-score Supplement inputs and outputs;
- NMS outputs;
- tracker feedback and next-frame state digests;
- final tracking predictions;
- packet emission/consumption accounting.

Required:

```text
CORE_OUTPUT_DIFF = 0
TRACKER_MUTATION_COUNT_FROM_OBSERVER = 0
```

### Oracle firewall

Historical rule, retained verbatim:

Runtime schema, imports, field names and access logs must show zero use of:

- `S_cf`;
- `Yec`;
- shadow membership or shadow state;
- counterfactual membership;
- GT identity, XML or MDA GT;
- future state;
- held-out results;
- Route A spatial/temporal/candidate state.

Those signals may be discussed in historical offline diagnosis only. They may
not be loaded by the MVE process, probe, ledger or selector.

```text
SUPERSEDED_BY_AUTHOR_RUNTIME_XML_GOVERNANCE_AMENDMENT
```

The supersession applies only to the absolute prohibition on the frozen
author runtime's already-existing first-frame XML initialization. Every other
listed oracle prohibition remains active.

## AUTHOR-RUNTIME XML GOVERNANCE AMENDMENT

```text
GOVERNANCE_DECISION_ALREADY_FROZEN_BEFORE_WRITEBACK
THIS IS AN EXPLICIT GOVERNANCE AMENDMENT
```

Scientific invariant:

```text
WORK1_DECISION_GT_INDEPENDENT
```

The frozen original-MIA first-frame XML initialization remains
`XML_RUNTIME_CAUSAL`, but source audit classifies it as
`NOT_CONTINUAL_DECISION_ORACLE`. This amendment does not retroactively
reinterpret the old rule.

### Rule 1 — Frozen initialization only

The frozen original-MIA author runtime may read XML only for its
already-existing first-frame initialization role. This permission covers only
the frozen role already present in the author runtime. Later-frame GT refresh,
new XML reads, a new GT-derived cache, new initialization logic, changed XML
interpretation, or expanded XML usage is forbidden.

### Rule 2 — Initialization provenance frozen

Before launch, freeze and validate the author source path and SHA-256, XML
files and SHA-256 hashes, initialization-code region/hash, initialization
frame, and initialization semantics. Any drift is:

```text
AUTHOR_INITIALIZATION_PROVENANCE_DRIFT
```

and stops before runtime. An expected hash baseline may not be regenerated
from the observed runtime inputs.

### Rule 3 — A/B/C initialization identity

A, B, and C must have exactly identical XML files/hashes, initialization-code
hash, initialization frame, initialization bbox/ID/label output digests for
both views, and post-initialization tracker-state digest. Comparison is exact;
no tolerance is permitted. Any mismatch is:

```text
ABC_INITIALIZATION_MISMATCH
```

and invalidates the attempt before non-interference interpretation.

### Rule 4 — Work 1 direct oracle firewall

The Work 1 observer, token, probe, ledger, selector, and orchestrator may not
directly read, receive, retain, infer provenance from, or serialize XML paths,
raw GT bboxes, raw GT identities, raw GT labels, GT visibility/outside/
occlusion, GT-derived correctness or candidate validity, or MDA/IDF1/MOTA/
IDSW grading inputs. Ordinary author tracker state may be observed only as:

```text
SHARED_FROZEN_AUTHOR_STATE
```

It must not be interpreted as GT truth. Initialization hashes/digests and the
completion marker are validity metadata, not mechanism inputs or metrics.

### Rule 5 — Explicit initialization boundary

Passive validity instrumentation must establish:

```text
AUTHOR_GT_INITIALIZATION_COMPLETE
```

after XML parsing, first-frame `inference_mot()` initialization, and
initialization tracker-state construction, but before Work 1 `E_pre`, token,
probe, eligibility-ledger, or opportunity-ledger records. Required ordering:

```text
last_author_GT_read
< AUTHOR_GT_INITIALIZATION_COMPLETE
< first_Work1_E_pre_record
```

Any earlier Work 1 scientific record is:

```text
WORK1_RECORD_BEFORE_INITIALIZATION_COMPLETE
```

and stops the attempt. The marker records only frame, completion Boolean,
state digest, and sequence number; its return is ignored and it cannot affect
author control flow or state.

### Rule 6 — GT must not decide Work 1 behavior

XML/GT may not decide token creation beyond existing `E_pre`, token validity,
preserve/reject, candidate generation/ranking, the read-only probe outcome,
Supplement or write-in decisions, or positive/false candidate status.

### Rule 7 — GT safety grading remains blocked

```text
GT_SAFETY_UNGRADED
```

Correctness classification, false/safe write-in, MDA, IDF1, MOTA, IDSW, and
tracking-performance claims remain forbidden.

### Rule 8 — Claim boundary

Any future result is limited to:

```text
mechanism / non-interference under the frozen original-MIA initialization protocol
```

It may not be described as a fully GT-free tracker, GT-free runtime, XML-free
MIA, GT-free initialization, autonomous tracker, deployment-ready tracking,
or GT-free deployment result.

### WORK1_DYNAMIC_M2_PREEXECUTION_GATE

The amendment is enforced by five fail-closed gates:

| Gate | Required check | Failure label |
| --- | --- | --- |
| `G-XML1` | frozen author/XML/reader/initialization provenance exact match | `G_XML1_INITIALIZATION_PROVENANCE_FAIL` |
| `G-XML2` | exact A/B/C initialization-record equality | `G_XML2_ABC_INITIALIZATION_MISMATCH` |
| `G-XML3` | static Work 1 oracle interface and future runtime counters | `G_XML3_WORK1_ORACLE_FIREWALL_FAIL` |
| `G-XML4` | `last_GT_read < marker < first_E_pre` | `G_XML4_INITIALIZATION_BOUNDARY_FAIL` |
| `G-XML5` | ledger/aggregate/decision/report claim-schema firewall | `G_XML5_CLAIM_BOUNDARY_FAIL` |

Gate order is frozen:

```text
M2_SYNTHETIC_PARITY_PASS
-> G-XML1 PASS
-> G-XML3 STATIC PASS
-> SOURCE / DERIVATIVE HASH PASS
-> authorization review
-> future A/B/C launch
-> G-XML2 PASS
-> G-XML4 PASS
-> G-XML3 DYNAMIC PASS
-> CORE_OUTPUT_DIFF check
-> TRACKER_MUTATION_COUNT_FROM_OBSERVER check
```

`G-XML1` or static `G-XML3` failure blocks launch. `G-XML2`, `G-XML4`,
or dynamic `G-XML3` failure invalidates the attempt and prohibits
non-interference interpretation. XML initialization audits are
`EXECUTION_VALIDITY_EVIDENCE`, never `WORK1_MECHANISM_EVIDENCE`, and cannot
select a pair/frame/candidate or enter a mechanism metric.

### Frozen read-only High-score probe parity

Source authority is frozen
`demo/utils/supplement.py:not_matched_supplement()` at lines 9-176 under the
hash above. Its actual decision sequence is:

1. preserve source-candidate order and project center/corners with
   `cv2.perspectiveTransform` (lines 17-28);
2. derive the raw projected bbox and reject only when it is wholly outside the
   hard-coded `1920 x 1080` bounds (lines 34-40);
3. clip the projected bbox to those bounds while iterating target detections,
   preserving detector row order (lines 87-108);
4. require strict `max(iou) > 0.3` and form the strict `iou > 0.3` index set
   (lines 110-114);
5. for one passing row, select the global max-IoU row; for multiple passing
   rows, select maximum detector score and the first row in detector-return
   order on an exact score tie (lines 116-126);
6. reject selected width `<20`, then selected height `<20` (lines 128-132);
7. only then is `WRITEIN_OPPORTUNITY=YES`.

The additional deterministic parity fields required beyond RD-MVE-4 are the
source-candidate ordinal/`pre_branch_row_index`, raw and clipped projected bbox,
complete ordered IoU vector, strict-threshold passing-index vector,
selection-branch label, selected target score, and exact score-tie position.
Without them, final target equality would not prove ordering/branch parity.

Exact trace schema, in order:

```text
source_candidate_ordinal
pre_branch_row_index
projected_center_float32
projected_corners_float32
raw_projected_bbox_float32
image_bound_pass
clipped_projected_bbox_float32
ordered_target_rows_float32
ordered_iou_vector
iou_threshold = 0.3
iou_gate_pass
passing_target_indices
selection_branch = NONE | UNIQUE_MAX_IOU | MULTI_MAX_SCORE
selected_target_index
selected_target_bbox
selected_target_score
score_tie_indices
selected_width
width_gate_pass
selected_height
height_gate_pass
high_score_trigger
WRITEIN_OPPORTUNITY
```

`high_score_trigger` means that this source token is presented to the helper;
`WRITEIN_OPPORTUNITY` means that all author checks through line 132 pass.

#### First-mutation boundary

For `diagnostic_events=None`, all required author decision locals exist after
the height check at lines 131-132. The parity reference must stop before line
133 executes. This is before the E023 diagnostic flag mutation at line 136 and
before the first scientific runtime mutation/output construction at lines
137-149: target-row concatenation, `matched_ids` append, `coID_confirme`
append and `supplement_bbox` update. No author helper call used by parity may
cross that boundary on a successful case.

The reference trace is obtained without editing the frozen helper: a test-only
line tracer, restricted by exact file hash and function name, records the
listed locals at the author decision lines and raises a dedicated stop sentinel
before line 133 on a successful path. It invokes the helper only on deep-copied
fixture inputs with `diagnostic_events=None`. Rejection paths return normally.

#### Frozen non-GT parity fixture

The fixture is synthetic constants embedded in the future parity test; it
loads no image, detector, tracker, GT, XML, MDA, identity, future, shadow or
held-out artifact. All numeric arrays are `numpy.float32`; Homography is the
`3 x 3` identity; source center is the midpoint of each listed source-corner
box; target rows are `[x1,y1,x2,y2,score]` in the exact listed order.
Unused track-row inputs are empty fixed-shape arrays, mutable list inputs are
fresh empty copies, `candidate_lineage` is canonical ordinal, and the unused
source-ID input is an opaque sentinel never read before the stop boundary.

| Case | Source corner box(es) | Ordered target row(s) | Required branch/result |
| --- | --- | --- | --- |
| `OUTSIDE` | `[1930,100,1970,200]` | `[0,0,100,100,0.5]` | image-bound reject |
| `NO_IOU` | `[100,100,200,200]` | `[300,300,400,400,0.9]` | IoU reject |
| `UNIQUE` | `[100,100,200,200]` | `[110,110,190,190,0.2]`; `[500,500,600,600,0.99]` | `UNIQUE_MAX_IOU`, index 0, opportunity |
| `MULTI_SCORE` | `[100,100,300,300]` | `[100,100,220,300,0.6]`; `[180,100,300,300,0.9]` | `MULTI_MAX_SCORE`, index 1, opportunity |
| `MULTI_TIE` | `[100,100,300,300]` | `[100,100,220,300,0.9]`; `[180,100,300,300,0.9]` | exact-score tie, first returned row/index 0 |
| `WIDTH_REJECT` | `[100,100,130,200]` | `[100,100,119,200,0.9]` | IoU pass, width reject |
| `HEIGHT_REJECT` | `[100,100,200,130]` | `[100,100,200,119,0.9]` | IoU/width pass, height reject |
| `CLIP_SUCCESS` | `[-10,100,100,200]` | `[0,100,100,200,0.8]` | clipping, index 0, opportunity |
| `SOURCE_ORDER` | `[100,100,200,200]`; `[300,300,400,400]` | `[600,600,700,700,0.9]` | two rejects in source order 0 then 1 |

For every fixture case, the author trace and probe trace must have identical
field presence, sequence length, branch labels, booleans and integer indices;
all float32 arrays/scalars must be exactly equal after canonical serialization.
The frozen author helper/source hash and the fixture constants are part of
`PROBE_PARITY_AUDIT.json`. Any mismatch, untraced branch, boundary crossing or
author-side mutable-object change is `G7_PROBE_PARITY_FAIL` and stops the MVE.
This fixture establishes semantic parity only; it is not an MVE run.

### Measurement gates

1. `G1_PROVENANCE`: the frozen E023 source/config/checkpoint authority and the
   exact ten-unit input manifest are hash-complete and immutable; any source or
   input drift stops rather than substituting another artifact/pair.
2. `G2_CREATION_BOUNDARY`: every token is created after the pre-ID
   `get_matched_ids()` result and before the first ID mutation/delivery.
3. `G3_ROW_IDENTITY`: key has the frozen four fields, no runtime ID, and every
   consumed token passes non-ID row conservation.
4. `G4_SUBSET`: `E_int subset_of E_pre`; no post-only injection or union.
5. `G5_INVALIDATION_SEPARATION`: disappearance-only is never encoded as
   explicit invalidation.
6. `G6_EXACTLY_ONCE`: all valid tokens are consumed once; all terminal tokens
   are consumed zero times.
7. `G7_PROBE_PARITY`: the frozen branch-complete non-GT fixture passes exact
   field-by-field author/probe trace equality, and the author trace stops before
   line 133 without mutating any supplied object.
8. `G8_ORACLE_FIREWALL`: all forbidden runtime reads and fields are zero.
9. `G9_NON_INTERFERENCE`: `CORE_OUTPUT_DIFF=0` and observer tracker mutation
   count is zero.
10. `G10_ACTIVATION`: at least one complete unit has
    `N_disappearance_only>0`.
11. `G11_OPPORTUNITY`: at least one complete unit has
    `N_restored_writein_opportunity>0`.

G1-G9 are validity gates. G10-G11 are mechanism-activation gates and cannot
rescue a validity failure.

### Known confounders and checks

- Correctly removed candidates versus harmful deletion: deliberately
  unresolved without GT; report all preserved opportunities as ungraded.
- d5 specificity: no delay sweep; do not infer onset or universality.
- Pair selection: exact non-test manifest must be outcome-independent.
- Probe drift: G7 requires author-helper parity on shared inputs.
- Existing geometry quality: same inputs and parameters for both conditions;
  no geometry interpretation or tuning.
- Runtime ID rename: excluded from the key and row-conservation fingerprint.
- Row replacement/reordering: fail closed as explicit invalidation, never
  repaired by ID, IoU, appearance or another association.

### Required outputs

```text
MVE_INPUT_MANIFEST.json
ELIGIBILITY_LEDGER.jsonl
OPPORTUNITY_LEDGER.jsonl
ELIGIBILITY_AGGREGATE_BY_PAIR_DIRECTION.csv
TOKEN_LIFECYCLE_AUDIT.json
PROBE_PARITY_AUDIT.json
ORACLE_FIREWALL_AUDIT.json
NON_INTERFERENCE_AUDIT.json
MVE_DECISION.md
```

Raw outputs remain under the output root. Any durable conclusion must be
summarized later in a tracked result document; this contract contains no
result.

## Runs

### Minimum viable experiment

- Inputs: frozen train pairs `23,25,27,28,29`, both directions, full frame
  filename sets specified above; exactly 10 pair-direction units.
- Delay: ID-state d5 only; other channels timely.
- Conditions: `POST_ID_MUTABLE` and `PRE_ID_FROZEN`, evaluated side by side
  from the same upstream current-frame state.
- Execution: one author baseline run plus one observer OFF/ON equivalence run;
  no state-changing intervention run.
- Scientific condition count:
  `2 x N_pair_direction`, with both sources computed from the same frame trace.
- No GT grading, delay scan, seed sweep, candidate selection or held-out run.

### Formal experiment

```text
NOT_AUTHORIZED / OUT_OF_SCOPE_FOR_THIS_CONTRACT
```

Formal safety and tracking evaluation require a separate contract after a
legal non-test GT protocol and a successful observer-only MVE.

### Compute budget / expected runtime

One detector/tracker trace per frozen pair-direction plus one OFF/ON
non-interference duplicate. Detector outputs may be reused only when exact
source/checkpoint/input hashes match. The future serialized
`MVE_INPUT_MANIFEST.json` must reproduce the frozen pair/direction/frame table
exactly and add resolved content hashes; it has no authority to select or
replace an input.

### Checkpoint and resume behavior

Each pair-direction attempt has an isolated root and fingerprint covering
source, config, checkpoint, input frames, delay and observer schema. Partial or
fingerprint-mismatched attempts cannot be promoted. A replacement attempt must
start clean and preserve the aborted attempt as provenance.

## Decision

### Success pattern

Return:

```text
MVE_PRE_ID_ELIGIBILITY_MECHANISM_SUPPORTED
```

only if:

- G1-G9 all pass;
- G10 and G11 both pass;
- every activated unit has `preservation_rate=1`;
- all integrity violation counts are zero;
- the result remains explicitly `GT_SAFETY_UNGRADED`.

This means only that immutable pre-ID eligibility removes the measured
post-membership-disappearance dependency and restores at least one read-only
write-in opportunity without crossing the observer boundary.

It does not authorize actual Supplement write-in or claim tracking benefit.

### Failure and non-activation patterns

- `MVE_DESIGN_BLOCKER`: legal row identity cannot be maintained without later
  mutable ID/association state or another forbidden information source.
- `MVE_VALIDITY_FAIL`: any G1-G9 failure.
- `MVE_MECHANISM_NOT_ACTIVATED`: G1-G9 pass but G10 fails.
- `MVE_NO_WRITEIN_OPPORTUNITY_RESTORED`: G1-G10 pass but G11 fails.
- `MVE_ELIGIBILITY_DEPENDENCE_NOT_REMOVED`: any activated unit has
  `preservation_rate<1` without an authorized explicit invalidation.

None may be rescued by adding pairs after outcomes, changing delay, unioning
candidate sets, adding invalidation predicates or using oracle information.

### Stop criteria

Stop immediately on:

- frozen E023 source/manifest hash drift or frozen input-manifest drift;
- inability to construct the frozen row key before first ID mutation;
- need for post-ID runtime ID, `matched_ids`, confirmed-ID state or another
  mutable identity field to evaluate `PRE_ID_FROZEN` opportunity;
- any `E_int` token outside `E_pre`;
- post-ID disappearance encoded as invalidation;
- duplicate consumption or cross-frame token survival;
- probe/helper semantic mismatch;
- oracle/GT/future/held-out read;
- observer-induced core output or tracker-state difference;
- official-test use, outcome-conditioned input replacement or parameter change.

On the first two cases, label `MVE_DESIGN_BLOCKER` and stop. Do not escalate to
Transaction-consistent, Version-aware or Route A.

### Exact decision gate

```text
IF G1..G9 PASS
AND G10 PASS
AND G11 PASS
AND every activated-unit preservation_rate == 1
THEN MVE_PRE_ID_ELIGIBILITY_MECHANISM_SUPPORTED

ELSE use the first applicable frozen failure/non-activation label
```

### Next action by result

- Success: request a new Research Decision for GT-safe, state-changing
  development evaluation; do not implement it automatically.
- `MVE_MECHANISM_NOT_ACTIVATED`: stop this input epoch; do not add or replace
  pairs from observed outcomes.
- `MVE_NO_WRITEIN_OPPORTUNITY_RESTORED`: reject the proposed mechanism on this
  MVE; do not broaden the intervention.
- `MVE_ELIGIBILITY_DEPENDENCE_NOT_REMOVED`: reject the frozen preservation
  semantics.
- `MVE_VALIDITY_FAIL`: repair only the violated measurement boundary under a
  fresh attempt; scientific semantics remain unchanged.
- `MVE_DESIGN_BLOCKER`: stop Work 1 intervention drafting at this family.

### Conditions requiring `NEEDS_RESEARCH_DECISION`

- changing the Work 1 paper claim;
- changing the legal runtime information boundary;
- adding an invalidation predicate;
- changing the intervention family or allowing pre/post union;
- allowing a state-changing write-in or tracker commit;
- changing the MVE success/failure meaning;
- changing dataset/split after the input manifest is frozen;
- introducing any Route A, geometry, motion, appearance or identity-recovery
  component.

Module names, JSON encoding, hash library, container type and helper naming are
engineering decisions provided they preserve this contract exactly.

## Pre-execution resolution and remaining blockers

Resolved from repository/source provenance without reading Work 1 outcomes:

1. `MVE_INPUT_MANIFEST_FROZEN`: pair IDs, two directions, complete frame sets,
   canonical pool/order, pollution rule and drift action are fixed above.
2. `FROZEN_SOURCE_PROVENANCE_RESOLVED`: the Formal run/attempt manifests bind
   the exact E023 v8 generated artifact, manifest and three relevant source
   hashes.
3. `PROBE_PARITY_CONTRACT_FROZEN`: exact author decision order, extra
   deterministic fields, first-mutation boundary, non-GT fixture and equality
   rule are fixed above.

Remaining blockers/limits:

1. `IMPLEMENTATION_AUTHORIZATION_ABSENT`: no source, observer, token, probe or
   test implementation may begin until separately authorized after review.
2. `EXECUTION_AUTHORIZATION_ABSENT`: no detector/tracker, parity fixture, MVE,
   Formal or held-out execution is authorized by this document.
3. `GT_SAFETY_UNGRADED`: the failed non-test GT protocol does not block the
   observer-only MVE, but it continues to block every correctness, safety and
   performance claim enumerated above.

These are not invitations to broaden the intervention. Any attempt to resolve
them by changing paper scope, dataset semantics, information boundary,
eligibility semantics or intervention meaning requires
`NEEDS_RESEARCH_DECISION`.

## Final planning status

```text
MVE_CONTRACT_READY_FOR_IMPLEMENTATION_AUTHORIZATION_REVIEW
```

This status does not authorize implementation or execution.
