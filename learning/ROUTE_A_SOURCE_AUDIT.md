# Route A Feasibility Source Audit

Scope: static audit of the MDMT/MIA E023-v8 path, its active packet runtime, and
the current experiment gate.  No code, configuration, experiment, MVE, Formal,
or recovery-policy change was made.  Issue #26 and Draft PR #25 were read as
context; the repository's later 2026-08-19 gate records are the operational
status used below.

## Executive Verdict

`FEASIBLE_WITH_BOOKKEEPING` — an observer-only Route A MVE can capture an
observation, retain causal snapshots, create a side hypothesis, and leave the
tracker unchanged.

`FEASIBLE_WITH_INTERFACE_CHANGES` — a deployable observation-to-local-track
record and a usable receiver-history view require information that ByteTrack
currently keeps internally or that MIA immediately discards.

`FEASIBLE_BUT_REQUIRES_TRACKER_SEMANTIC_CHANGE` — a later Route A COMMIT that
claims safe continuity/current-state correction is not supplied by the current
ID-keyed feedback interface.  This is outside the observer-only MVE.

The present onset protocol remains `GT_PROTOCOL_GATE_FAIL`; its records forbid
tracking/MVE execution on that onset until an independently approved annotation/
export protocol exists.  This is an execution authorization block, not a claim
that the Route A mechanism has been refuted.

## Capability Matrix

| Route A Need | Existing Support | Evidence | Gap | Minimal Change Type |
| --- | --- | --- | --- | --- |
| source observation before association | Detector output exists before MIA association; packet helper can serialize rows. | `byte_track.py:234-265`; `supplement_MIA.py:187-205`; packet `deliver_local_track`. | Existing Local packet carries a whole detector array, not an immutable observation-level record/key. | BOOKKEEPING |
| timestamp / arrival semantics | Explicit capture/emitted/arrival frame and ordered queue. | `mdmt_mia_async_deadline_runtime.py:165-209`. | Fixed channel delay only; no wall-clock timestamp, duplicate/drop model, or per-message jitter field. | BOOKKEEPING |
| receiver causal history | ByteTrack stores per-ID samples internally until retention expiry; MIA keeps only previous final rows. | `base_tracker.py:86-143`; `byte_tracker.py:1061-1072`; `supplement_MIA.py:505-510`. | No MIA-owned bounded, timestamp-indexed receiver snapshot/history API. | INTERFACE |
| stable local lineage | `self.tracks[id]` has state while the dictionary entry lives. | `base_tracker.py:86-122`; `byte_tracker.py:1020-1029`. | `id` is both runtime label and dictionary key; no immutable instance/birth/epoch/lineage key. | INTERFACE |
| detector→track historical mapping | ByteTrack computes high/tentative/low LAPJV assignments. | `byte_tracker.py:1074-1125`, `1205-1251`. | Detector indices/match arrays are local variables and are not returned to MIA or retained with a detector key. | INTERFACE |
| death/rebirth state | Confirmation, tentative removal, and retention expiry are explicit. | `byte_tracker.py:1032-1072`; config `one_carafe_bytetrack_full_mdmt.py:51-58`. | No explicit lost/dead event log, reactivation API, or old→new continuity hook. | BOOKKEEPING |
| candidate-independent propagation inputs | Source bbox, score, frame index, and a held image homography are present. | `byte_track.py:241-265`; `async_deadline_runtime.py:315-340`. | No world position, pose, ego-motion, candidate-agnostic velocity, covariance, or temporal geometry history. | NEW_ESTIMATOR |
| uncertainty representation | Kalman mean/covariance is held per internal track. | `byte_tracker.py:1039-1043`, `1051-1059`, `1196-1203`. | It is neither observation-level nor MIA-exposed; using a target track's covariance to construct source evidence would violate D11. | NEW_ESTIMATOR |
| appearance evidence | The audited MIA-v8 path returns detector/track boxes only. | `byte_track.py:241-265`; `supplement_MIA.py:187-205`. | No crop/embedding/feature-bank/quality payload on this path. | NONE |
| observer-only hypothesis layer | Existing cascade runtime proves copied, isolated diagnostic side state is possible. | `mdmt_mia_cascade_runtime.py:102-160`, `162-215`, `255-345`. | Its membership and shadow inputs are diagnostic/oracle only and cannot be Route A input. | SIDE_STATE |
| current-state correction | Feedback rows become next-frame ByteTrack `update` input. | `async_deadline_runtime.py:391-412`; `byte_tracker.py:1169-1177`. | No public rename/merge/reactivation/continuity-correction transaction; an ID-key change can create a second dict entry. | TRACKER_CORE |

## Source Evidence

### A. Source observation capture point

| Field | Source fact |
| --- | --- |
| FILE / function / lines | `.../mmtrack/models/mot/byte_track.py`, `simple_test`, 229-265; `.../demo/supplement_MIA.py`, main loop, 187-205. |
| Input | Detector cache becomes `det_bboxes`/`det_labels` at 241-244.  The same `det_bboxes` is passed into `ByteTracker.track` at 246-254. |
| Output | `det_results` and `track_results` are separately converted at 256-265; MIA receives `det_bboxes` and `track_bboxes` separately at 194-205. |
| Before association? | **Yes** for `det_bboxes`: it exists before `ByteTracker.track` and before `get_matched_ids` / cross-view MIA stages. |
| Fields directly available | Detector bbox, detector score, class (then zeroed labels), view call context, and loop frame `i`.  Raw array position is an index but no immutable observation key is created. |
| Mutated later? | `track_bboxes` is subsequently ID-mutated/augmented/NMSed; raw `det_bboxes` is passed through helpers but is not made into a durable observation record. |
| Safe Route A cut | Immediately after detector output is formed and before `ByteTracker.track` / `deliver_local_track`; serialize a copy with `(capture_frame, source_view, detector_row_index, bbox, score, class)`.  This is a proposed packet boundary, not an existing packet schema. |

`deliver_local_track` (`src/tracking/mdmt_mia_async_deadline_runtime.py:291-314`)
already round-trips `tracker_rows` and `detector_candidates` as local state, but
its delayed Local packets expire at `begin_frame` (`268-274`).  Thus it proves a
serialization location, not an arrival-time observation service.

### B. Timestamp and delay semantics

| Item | Source fact |
| --- | --- |
| packet creation | `_wire`, `async_deadline_runtime.py:165-181`: `capture_frame`, `emitted_frame=capture_frame`, `arrival_frame=capture_frame+delay`, generic `source_state_version`, and `valid_until_frame=capture_frame`. |
| delay unit | Integer **frame** count from `MIA_ASYNC_CHANNEL_DELAYS`, parsed by `_parse_delays` at 69-91.  `supplement_MIA.py:301` only uses `fps` for display wait time; no runtime wall-clock timestamp is propagated. |
| delivery / order | `_send`, 183-197, pushes `(arrival_frame, queue_sequence, wire)`; `_drain`, 199-209, drains `arrival_frame <= frame_id`.  This provides deterministic arrival ordering for queued packets. |
| variable / duplicate / drop | Delay is fixed per channel per runtime construction.  The audited transport has no per-message delay field and no explicit duplication/drop injector.  Packets can instead be timely, queued, expired by channel deadline, or pending at end (`414-420`). |
| causal check | `_drain` rejects a packet whose `capture_frame > frame_id` and increments `future_read_violations` (204-206). |

### C. Receiver causal history

| State requested | Status | Source evidence / limit |
| --- | --- | --- |
| historical detector rows | NOT STORED | `det_bboxes` is a current output at `supplement_MIA.py:194,198`; no audited ring buffer persists it. |
| historical tracker bbox / score / runtime ID | AVAILABLE internally, NOT EXPOSED_TO_MIA | `BaseTracker.update` appends samples under `self.tracks[id]` when no momentum applies (`base_tracker.py:86-122`); `get` can read retained samples (145-178).  MIA has only current rows plus `track_bboxes_old` / `track_bboxes2_old`, assigned after NMS (`supplement_MIA.py:505-506`). |
| historical velocity / covariance | AVAILABLE internally, NOT EXPOSED_TO_MIA | Kalman mean/covariance is initiated/updated in `byte_tracker.py:1039-1059` and predicted at 1196-1203. |
| track status | TRANSIENT / DERIVABLE internally | `confirmed_ids` and `unconfirmed_ids` are predicates over live dict entries (1020-1029); no per-frame status history/event is exported. |
| lost/dead state | AMBIGUOUS at MIA layer | Entries survive only until `pop_invalid_tracks` removes them (1061-1072); MIA has no removal event or retained tombstone. |
| camera/geometry history | NOT STORED as a history | Runtime holds only newest arrived homography per direction in `_latest_h` (`275-282`, `330-340`), with capture age recorded. |

### D. Stable local track / lineage handle

`BaseTracker.update` branches solely on whether runtime `id` is a current
`self.tracks` dictionary key (`base_tracker.py:86-93`); `init_track` creates a
new `Dict` under that key (114-122).  There is no immutable track-instance ID,
birth ID, epoch, alias table, or tracker-level rename.  Hence:

```text
runtime ID         = dictionary key while live
array row index    = current output ordering only
track object       = self.tracks[runtime ID] while retained
local lineage key  = NO_EXPLICIT_LINEAGE_KEY
```

Minimum MVE bookkeeping is a monotonic **side snapshot handle** such as
`(view, snapshot_frame, output_row_index, observed_runtime_id)`.  It may label
`B23@t103` without claiming it is a stable local lineage.  A later claim that
`B23@t103 → B41@t105` is one local instance needs an exposed immutable handle or
explicit lifecycle/alias event; a same numeric ID is insufficient.

### E. Death, lost, and rebirth semantics

`ByteTracker.init_track` marks non-frame-zero tracks tentative (`1032-1043`).
`update_track` confirms a tentative entry only after `num_tentatives` bbox
samples (`1045-1059`).  `pop_invalid_tracks` deletes a track when it has been
unmatched for `num_frames_retain` frames, or when a tentative track is unmatched
in the current frame (`1061-1072`).  The active MDMT config sets
`num_frames_retain=30` (`one_carafe_bytetrack_full_mdmt.py:51-58`).

There is no named lost object state separate from a retained unmatched
dictionary entry, no removal record exposed to MIA, no reactivation branch, and
no old/new continuity hook.  An unmatched high-score detection receives a new
ID at `1282-1286`.  Therefore death/rebirth **can be observed as side-state
events only after bookkeeping**; it is not an existing local continuity proof.

### F. Historical observation-to-track association

`ByteTracker.assign_ids` constructs IoU/category costs and LAPJV arrays `row`
and `col` (`1074-1125`).  In `track`, high-score match data is held in local
`first_det_inds`, `first_match_track_inds`, and `first_match_det_inds`; the
assigned live ID is put in `first_det_ids` (`1183-1218`).  Tentative and low
score matching follow at `1225-1251`.  These values are neither returned in the
public result (`1297-1298`) nor retained in the MIA packet/schema.

Thus `observation_key → local_track_handle` is **TRANSIENT_INSIDE_BYTETRACK**,
not exposed.  Persisting existing assignment pairs alongside copied detector
indices needs an interface/output instrumentation change, but does **not** need
to alter LAPJV matching itself.  It still supplies tracker continuity, not
identity correctness.

### G. Candidate-independent propagation inputs

| Input | Audit status | Source-bound interpretation |
| --- | --- | --- |
| source bbox / score / class | AVAILABLE_NOW | Detector rows from `byte_track.py:241-265`. |
| capture and arrival frame | AVAILABLE_NOW | Packet envelope `async_deadline_runtime.py:165-175`. |
| source pixel center/corners | CAN_DERIVE_WITHOUT_ORACLE | `calculate_cent_corner_pst`, `common.py:94-128`, derives them from row geometry. |
| cross-view image homography | AVAILABLE_NOW, provenance-limited | MIA computes `f1/f2` from already matched row centres (`supplement_MIA.py:312-325`, `359-364`); runtime holds only the latest arrived matrix (`315-340`).  It maps views, not capture-to-arrival motion, and is association-derived context. |
| world position / camera pose / ego-motion / map | NOT_AVAILABLE | None is carried by the audited MDMT/MIA-v8 packet/output path. |
| candidate-agnostic temporal velocity / covariance | NOT_AVAILABLE | Internal Kalman state is per track and target-specific; MIA receives no candidate-independent temporal state. |
| explicit propagated uncertainty | REQUIRES_NEW_ESTIMATOR | No observation-level tube or uncertainty object exists. |

`CONFLICT_WITH_CURRENT_ROUTE_A_ASSUMPTION`: a cross-view transform is present,
but it is not an independently calibrated pose/world geometry service and is
computed after current-frame matching.  It may be audited as previously arrived
context, but cannot be asserted to be a capture-time, pre-association transform
without a narrower provenance decision.  This does not block an observer-only
MVE if that MVE records the transform age/provenance and does not use it to
write tracker state.

### H. Appearance / identity evidence

The audited active v8 MIA path only transports detector and tracker boxes
(`byte_track.py:241-265`; `supplement_MIA.py:187-205`).  No crop, embedding,
feature bank, similarity, visibility, or quality field is consumed by this
path.  Other repository modules with ReID names are outside this MIA execution
path and are not evidence that MIA has this payload.

**MVE conclusion:** appearance/ReID is not required for a first, observer-only
test of spatial-temporal candidate regeneration.  It must not be silently
substituted with oracle/shadow identity labels.

### I. Current-state correction interface

`commit_fused_state_to_tracker` serializes final rows, extracts `(bbox, id)` and
returns them as next-frame feedback (`async_deadline_runtime.py:391-412`).
At the next `ByteTracker.track`, `bil` feedback calls `self.update` with
`frame_id-1` (`byte_tracker.py:1169-1177`).  Existing IDs update their existing
dict entry; absent IDs call `init_track` (`base_tracker.py:86-122`), which
initiates a fresh Kalman state (`byte_tracker.py:1032-1043`).

There is no public transaction for rename, merge, reactivation, aliasing,
historical correction, or current-only continuity correction.  Directly changing
an output row `73→88` can update/create `self.tracks[88]` while `self.tracks[73]`
remains until retention removal.  This creates the documented duplicate/stale
key and hidden-feedback risks.  A later COMMIT therefore requires tracker
semantic/interface work; it is deliberately excluded from the MVE.

### J. Observer-only hypothesis layer

`CascadeEdgeRuntime.capture_prebranch` copies inputs and checks for aliases
(`mdmt_mia_cascade_runtime.py:162-215`).  Its record structures store frame,
view, pre-branch row index, and outcome counts (`255-345`) without changing
ByteTrack.  This is evidence that a side-state ledger can preserve snapshots
and write diagnostics with tracker mutation zero.

Its counterfactual membership (`S_cf` / shadow) is explicitly an oracle
diagnostic boundary, not a Route A input.  Route A may reuse only the isolation
pattern: copied factual packet/snapshot data and a side ledger of source
evidence, historical/current candidates, authority, compatibility, support,
conflict, and status.

## Semantic Risks

| Risk | Audit finding and mandatory MVE guard |
| --- | --- |
| FUTURE_INFORMATION_RISK | `_drain` has a capture-frame guard, but a new history reader must enforce `state_frame <= arrival_frame`; record every read frame. |
| HIDDEN_HISTORICAL_ACCESS_RISK | Internal ByteTrack samples are accessible only through the tracker object and disappear on removal.  Do not treat that implicit memory as an MIA history API; copy a bounded causal snapshot ledger. |
| LINEAGE_AMBIGUITY | **Observed.** Runtime ID/dict key is not immutable lineage.  Snapshot handles must not be reported as continuity proof. |
| DUPLICATE_TRACK_RISK | **Observed.** Feedback ID replacement may initialize a new dict key while the old key survives.  No MVE commit. |
| SELF_FULFILLING_ASSOCIATION_RISK | **Possible if violated.** Per-target Kalman trajectory/covariance cannot construct the source tube.  Freeze the tube before candidate enumeration and hash it. |
| TRACKER_FEEDBACK_RISK | **Observed in architecture.** NMS-final MIA rows are fed back next frame.  Observer MVE must not write these arrays or `bil`. |
| ORACLE_LEAKAGE_RISK | **Observed diagnostic facility.** Cascade shadow/counterfactual membership is quarantined; it must be absent from Route A packet, candidate, and hypothesis inputs. |
| TIMESTAMP_MISMATCH | **Observed limitation.** Only frame indices and fixed channel delays are explicit.  Every evidence/candidate record must carry capture, arrival, state-frame, and homography-capture/age where used. |
| HISTORY_MUTATION_RISK | **Possible through tracker objects/feedback.** Route A historical lookups must use copied snapshots; never call an update, replay, or row rewrite for a past frame. |

## Audit-Limited Conclusions

1. The earliest valid Route A network cut is detector output before
   `ByteTracker.track`; it currently has bbox, score, class, view context, and
   loop frame, but no immutable observation key.
2. Current MIA does **not** expose detector-to-track pairs, stable local lineage,
   or a bounded receiver history.  Those are data-contract gaps, not evidence
   that the side-only MVE mechanism is impossible.
3. The source supplies an image homography only as current/held,
   association-derived context; it supplies no independent temporal motion or
   uncertainty representation.  A first tube must state and audit its minimal
   candidate-independent propagation assumption rather than imply existing pose
   support.
4. The only source-supported safe first boundary is observer-only.  Current or
   future tracker correction is a separate tracker-semantic question.

