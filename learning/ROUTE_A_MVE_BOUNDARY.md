# Route A Minimal MVE Boundary

## 1. MVE Scientific Question

Can a delayed source observation, without rollback, history rewrite, future
information, oracle/shadow input, or pending-hypothesis tracker effect, be
temporally reinterpreted **candidate-independently** and compared with lawful
receiver historical/current snapshots so as to create a new association
candidate opportunity?

This MVE tests the mechanism chain only.  It does not establish identity truth,
recover a historical capture-time pair, commit continuity, correct motion, or
claim performance improvement.

## 2. Source-Constrained Boundary

### Included minimum chain

```text
detector observation captured before ByteTrack association
  -> immutable factual source packet with capture-frame metadata
  -> fixed-frame-delay queue
  -> arrival-time causal snapshot retrieval
  -> one candidate-independent time-indexed evidence tube
  -> time-aligned historical/current candidate enumeration
  -> new candidate record
  -> observer-only side hypothesis
```

At every stage the MVE reads copied data only.  It does not call tracker update,
modify detector/tracker rows, alter matching cost/gates, add Supplement rows,
or send any side result into the next-frame feedback arrays.

### Explicitly excluded

- Supplement write-in, NMS/feedback mutation, ID remap, current-state correction,
  tracker fork, rename, merge, reactivation, or continuity commit.
- `S_cf`, shadow membership, GT identity, hidden remote state, future frames,
  replay, rollback, or historical tracker writes.
- Real ReID, learned temporal model, learned uncertainty, feature-bank updates,
  and full multi-evidence accumulation.

## 3. Minimal Sufficient Version

### Packet and causal snapshots

The source packet minimum is:

```text
observation_key = (source_view, capture_frame, detector_row_index)
source_view, capture_frame, emitted_frame, arrival_frame
bbox_xyxy, detector_score, detector_class
packet sequence/version and exact source-array copy digest
```

`observation_key` identifies a capture-time detector row only.  It must not
claim a source local track or global identity.

The receiver side ledger is a bounded copied snapshot per processed frame:

```text
(receiver_view, state_frame, output_row_index, observed_runtime_id,
 bbox_xyxy, row_score, local_status_if_observable, snapshot_digest)
```

This is sufficient to retrieve `B@t_k` and current `B@arrival` factually.  Its
handle is a snapshot address, not a proof that the same local track object
survives between frames.  It therefore permits D4 candidate creation and D5
*continuity hypotheses*, but not a lineage/identity commit.

### One tube, no target-conditioned propagation

The source audit exposes bbox/score/frame and no candidate-agnostic pose,
world velocity, temporal transform, or observation covariance.  The narrow
first construction is therefore:

```text
single image-coordinate zero-displacement propagation baseline
+ monotonic, explicit pixel-space uncertainty envelope as an audit quantity
+ optional most-recent already-arrived homography only as separately stamped
  cross-view context (never as a claim of capture-time calibration)
```

For each source observation, build all tube slices before receiver candidates
are enumerated:

```text
E_O(k) = { frame=k, source_bbox_reference, propagation_assumption="zero_displacement",
           spatial_envelope(k), capture_frame, arrival_frame, tube_digest }
for capture_frame <= k <= arrival_frame.
```

The envelope construction is deterministic and candidate-independent.  It is
an MVE placeholder, not a final motion or uncertainty model.  A candidate can
only test a frozen `E_O(k)`; it cannot provide a trajectory, velocity,
covariance, or other input to rebuild that tube.

To make a cross-view geometric comparison, the MVE must freeze one declared
transform provenance condition:

- **Permitted factual condition:** a homography that had already arrived by the
  relevant read point, stored with its own capture frame and age; or
- **No-transform condition:** record that cross-view geometry is incomparable
  and do not manufacture a spatial candidate.

The current source does not justify treating a homography calculated after the
same-frame `get_matched_ids` call as a pre-association source-packet field.
This is why transform provenance is a pre-implementation decision below.

### Candidate and hypothesis semantics

A time-aligned historical candidate is a factual record:

```text
(observation_key, tube_frame=k, receiver_snapshot_handle@k,
 transform_provenance, physical/logical-impossible flag,
 compatibility components)
```

A current candidate uses `k=arrival_frame`.  A candidate is **new** only when
the audited capture-time factual candidate ledger has no record for that exact
`(observation_key, receiver_snapshot_handle)` relationship and the arrival-time
ledger does.  This is an audit definition; it does not declare the pair true.

`authority` and `compatibility` are separate fields.  Low compatibility remains
recordable; only a documented physical/logical-impossible condition may reject
before the side hypothesis layer.  A hypothesis may retain competing receiver
snapshot/current-track references, support/conflict records, and status, but it
has no write path to tracker output.

### Appearance decision

`MINIMAL_SUFFICIENT`: **no appearance/ReID**.  The audited MIA-v8 route has no
such packet field.  The first MVE can falsify or establish the geometry/time
candidate-regeneration chain without pretending an unimplemented appearance
signal exists.

## 4. Required Diagnostics

Per run/configuration, record at least:

| Diagnostic | Required meaning |
| --- | --- |
| source observation count | Number of pre-association detector records packetized. |
| late arrival count | Packets with `arrival_frame > capture_frame`. |
| evidence tube construction count | Number of frozen single tubes; include tube digest. |
| historical candidate count | Time-aligned receiver snapshots considered. |
| current candidate count | Receiver snapshots considered at arrival. |
| physically impossible reject count | Rejected only with the named factual predicate and inputs. |
| low-compatibility retained count | Non-impossible candidates retained to side state. |
| new candidate count | Arrival-ledger candidate absent from capture-time factual ledger under the declared comparison rule. |
| capture-time-existing pairing count | Factual capture-time candidate records, not GT pair truth. |
| arrival-time-new pairing count | Factual arrival-time records newly created under the preceding definition. |
| hypothesis creation count | Side records created; include candidate references. |
| tracker mutation count | **Exactly 0**; separately hash/compare tracker output and feedback input. |

Also log every data read with `(read_at_frame, data_state_frame, provenance)` and
every homography with `(H_capture_frame, H_arrival/hold age, transform digest)`.

## 5. Hard Assertions

The MVE must fail closed if any assertion fails:

1. No read has `data_state_frame > read_at_frame`; no packet is consumed before
   its `arrival_frame`.
2. No `S_cf`, shadow-membership, GT identity, or remote state enters packet,
   tube, candidate, authority, compatibility, or hypothesis fields.
3. Tube inputs are finalized before candidate enumeration.  The same factual
   source packet produces the same `tube_digest` regardless of later candidate
   list/order.
4. No receiver target trajectory, target Kalman state, target covariance, or
   target feature is an input to source propagation.
5. Historical comparisons use `E_O(k)` only with a receiver snapshot whose
   `state_frame == k`; current comparisons use `k == arrival_frame`.
6. Receiver snapshots are copied/read-only; no historical/current tracker row,
   `self.tracks`, NMS array, `bil` feedback array, or ID state is mutated.
7. No hypothesis result is read by detector, ByteTrack, MIA matching,
   Supplement, NMS, or feedback.  `tracker_mutation_count == 0`.
8. A missing/late/association-derived transform is explicitly labelled; it is
   never silently treated as capture-time pose truth.

## 6. Comparator Boundary

| Comparator | Meaning | Mutation |
| --- | --- | --- |
| `DROP_LATE` | Record arrival but create no tube/candidate/hypothesis. | 0 |
| `NAIVE_ARRIVAL` | Compare capture bbox directly at arrival without the tube. | 0 |
| `CURRENT_ONLY_REINTERPRET` (optional) | Use frozen arrival slice only; omit historical lookup. | 0 |
| `ROUTE_A_OBSERVER_MVE` | Use frozen time-indexed tube, historical/current causal snapshots, and side hypotheses. | 0 |

These are mechanism comparators, not performance baselines or a final
association/commit policy.

## 7. Answer to the Ten Required Questions

1. **Observation-level network cut:** immediately after source detector output
   is formed in `byte_track.py:simple_test` (241-244), before
   `ByteTracker.track` (246-254) and before all MIA cross-view association.
2. **Pre-association fields:** bbox, score, detector class, detector-array
   index, source view call context, and frame loop index.  No immutable key,
   feature, world position, pose, covariance, or track handle is supplied.
3. **Receiver sufficient history now?** No at MIA level.  Internally retained
   ByteTrack samples exist while keyed entries live, but there is no bounded,
   timestamp-indexed, causal MIA history ledger.
4. **Stable historical handle?** No explicit lineage handle.  A runtime ID is a
   live dictionary key, not an immutable instance/birth/epoch identity.
5. **Can detector→track mapping be bookkeeping only?** Its association
   algorithm need not change, but its transient match pairs must first be
   exposed or logged at the tracker interface.  Pure MIA bookkeeping cannot
   reconstruct all pairs after the fact.
6. **Death/lost/rebirth auditable?** Partially: tentative/confirmed and removal
   conditions are source-defined, but no lost/dead event/tombstone/reactivation
   or continuity hook is exported.  Side bookkeeping can audit events, not
   prove rebirth continuity.
7. **First tube inputs:** source bbox/score/frame, derived centre/corners, fixed
   arrival frame, deterministic zero-displacement image-coordinate baseline,
   and explicit envelope.  A held homography is optional stamped context, not
   temporal motion or guaranteed capture-time geometry.
8. **Observer-only hypotheses with mutation zero?** Yes.  A copied side ledger
   follows the existing cascade diagnostic isolation pattern and has no feedback
   path.
9. **Does the first MVE need appearance/ReID?** No.
10. **Largest single blocker:** no approved, MIA-consumable causal receiver
    history plus stable lineage data contract.  For executing the current onset
    MVE, the already-failed GT protocol gate is the immediate authorization
    blocker.

## 8. Decision Gate

`NEEDS_RESEARCH_DECISION`

This is not `READY_FOR_MVE_IMPLEMENTATION`: current project status explicitly
forbids tracking/MVE under the failed onset GT protocol.  Once independent
measurement authorization exists, the observer-only MVE remains bounded enough
to implement without a tracker semantic change, provided the following two
decisions are frozen:

1. **Measurement/authorization decision:** an independently approved source
   annotation/export and evaluation protocol for any Route A MVE data; no
   tracking/MVE result may repair the failed onset protocol.
2. **Geometry-provenance decision:** whether MVE cross-view comparison can use
   only a previously arrived, age-stamped MIA homography, or must record
   no-transform/incomparable cases until an independent calibration/context
   source is approved.  This is necessary to prevent treating same-frame
   association-derived `H` as pre-association packet truth.

No third research decision is required to start the observer-only mechanism
test: appearance, final motion/uncertainty model, multi-hypothesis accumulation,
and commit policy remain deliberately outside this MVE.

## 9. Readiness Boundary

The source supports a later **observer-only** implementation with:

```text
capture packet + causal copied snapshots + deterministic candidate-independent
tube + stamped transform provenance + side candidate/hypothesis ledger +
zero tracker mutations.
```

It does not support a claim of stable local lineage resolution or a safe
current-state/identity correction transaction.  Those are follow-on Route A
questions and must not be smuggled into this MVE.

