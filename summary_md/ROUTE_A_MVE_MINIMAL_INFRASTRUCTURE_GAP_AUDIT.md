# ROUTE A MVE MINIMAL INFRASTRUCTURE GAP AUDIT

Audit scope: static source inspection only. The frozen `MVE_PREDECISIONS.md`
semantics supplied in the task are treated as the required measurement
contract. No implementation or experiment was performed.

## 1. Source files actually read

The inspected runtime snapshot is
`/mnt/data/yzm/experiments/mdmt_mia_official/variants/route_a_observer_mve0_v1`.

- `route_a_observer_manifest.json:1-24`
- `demo/supplement_MIA.py:1-45,135-255,470-595`
- `demo/utils/route_a_observer_runtime.py:1-252`
- `demo/utils/async_deadline_runtime.py:94-112,220-287,298-320,342-412`
- `demo/utils/cascade_runtime.py:172-258`
- `mmtrack/apis/inference.py:599-642`
- `mmtrack/models/mot/byte_track.py:213-272`
- `mmtrack/models/trackers/base_tracker.py:13-178`
- `mmtrack/models/trackers/byte_tracker.py:979-1298`
- `configs/mot/bytetrack/one_carafe_bytetrack_full_mdmt.py:12-59`

`SOURCE-PROVEN FACT` — This variant directory is not a Git worktree. Its
manifest identifies three changed observer files, and the current SHA-256 of
all three matches `route_a_observer_manifest.json:11-15`.

## 2. Existing infrastructure

- `SOURCE-PROVEN FACT` — A detector observation is copied before
  `ByteTracker.track()` at `mmtrack/models/mot/byte_track.py:241-260`.
  `RouteAObserverRuntime.capture_preassociation_detector()` creates
  `observation_key = [view_id, capture_frame, detector_row_index]` and persists
  the key, capture frame, source view, row index, bbox, score, class and packet
  digest (`demo/utils/route_a_observer_runtime.py:78-104`).
- `SOURCE-PROVEN FACT` — Delayed packets retain that key in the pair-scoped
  observer's `_pending` side state and carry it into arrival events
  (`route_a_observer_runtime.py:64-68,99-103,126-165`).
- `SOURCE-PROVEN FACT` — The receiver observer copies post-ByteTrack/pre-MIA
  rows, including frame, view, output row index and `observed_runtime_id`
  (`route_a_observer_runtime.py:106-124`; call order in
  `demo/supplement_MIA.py:198-215`). It does not capture a lineage key.
- `SOURCE-PROVEN FACT` — ByteTrack has a live memo keyed by integer ID.
  Each entry retains `frame_ids`, bbox/label history and Kalman state while it
  remains in `self.tracks` (`base_tracker.py:36-49,86-122`;
  `byte_tracker.py:1032-1059`).
- `SOURCE-PROVEN FACT` — A confirmed memo entry whose last update is older than
  the previous frame is treated as previously lost during prediction, but it
  remains matchable under the same integer key until expiry
  (`byte_tracker.py:1196-1213`). Successful first/tentative/second association
  writes that integer key into the current detection IDs
  (`byte_tracker.py:1205-1251`).
- `SOURCE-PROVEN FACT` — `cascade_runtime.py` uses the name `lineage` for
  `range(len(rows))` and later returns the row index
  (`cascade_runtime.py:181-201,239-253`). This is a frame-local pre-branch row
  identity, not an immutable ByteTrack track-instance identity.
- `SOURCE-PROVEN FACT` — The current MIA packet runtime explicitly rewrites the
  first ID column (`async_deadline_runtime.py:234-255`), and the resulting IDs
  are published as next-frame tracker feedback
  (`async_deadline_runtime.py:391-412`; `supplement_MIA.py:523-535`). On the
  next call ByteTrack updates its memo using those feedback IDs before detector
  association (`byte_tracker.py:1169-1176`). Therefore the row ID is a mutable
  runtime identity label, not source proof of immutable lineage.

## 3. Minimal missing infrastructure

### Observation key — `EXISTS`

- `SOURCE-PROVEN FACT` — Capture frame, source view and detector row identity
  are available at the earliest pre-association detector hook and are retained
  together as `observation_key` through delayed arrival
  (`route_a_observer_runtime.py:78-104,126-139`).
- `INFERENCE` — The triple is unique inside one pair-scoped
  `RouteAObserverRuntime` run because one row index occurs once per
  `(view, capture_frame)`. When ledgers from multiple pair runs are combined,
  `pair_id` must remain part of the surrounding record namespace; the bare
  three-element value alone is not globally namespaced.
- `UNKNOWN` — Structural immutability is not enforced by the Python list type.
  No mutation of the key was found in the inspected runtime.

### Receiver lineage — `MISSING`

- `SOURCE-PROVEN FACT` — `self.tracks` is keyed only by the integer runtime ID;
  neither `BaseTracker.init_track()` nor `ByteTracker.init_track()` creates a
  separate immutable instance key (`base_tracker.py:36-49,86-122`;
  `byte_tracker.py:1032-1043`).
- `SOURCE-PROVEN FACT` — New unmatched detections receive values derived from
  `max_id`, not a separate lineage counter (`byte_tracker.py:1269-1286`).
- `SOURCE-PROVEN FACT` — Receiver snapshots expose only
  `observed_runtime_id` (`route_a_observer_runtime.py:106-124`).
- `SOURCE-PROVEN FACT` — MIA ID remaps can change a row's runtime ID before it
  is fed back into ByteTrack (`async_deadline_runtime.py:220-266,391-412`). No
  source field transfers an immutable track-instance identity across that
  rename.
- `SOURCE-PROVEN FACT` — The frame-local `cascade_runtime` row index called
  `lineage` is consumed with its pre-branch snapshot and cannot identify a
  track instance across frames (`cascade_runtime.py:219-253`).
- `INFERENCE` — The minimal gap is one run-scoped immutable lineage key plus a
  side mapping that preserves that key across an explicit runtime-ID remap.
  Runtime ID, Python dictionary identity and frame-local row index cannot meet
  the frozen lineage semantics.

### Tombstone/lifecycle — `PARTIAL`

- `SOURCE-PROVEN FACT` — Track materialization is observable at the
  `id not in self.tracks -> init_track` branch, and the first element of the
  existing `frame_ids` list identifies its memo-entry creation frame
  (`base_tracker.py:76-93,114-122`).
- `SOURCE-PROVEN FACT` — Lost state has no explicit event object. A frame gap is
  checked at `byte_tracker.py:1197-1203`; the retained entry can subsequently
  be associated again under the same memo key at `byte_tracker.py:1205-1251`.
- `SOURCE-PROVEN FACT` — Expiry/removal is explicit in control flow: a confirmed
  entry is removed after `num_frames_retain`, and an unmatched tentative entry
  is removed immediately (`byte_tracker.py:1061-1072`). The active config sets
  `num_frames_retain=30`
  (`configs/mot/bytetrack/one_carafe_bytetrack_full_mdmt.py:52-58`).
- `SOURCE-PROVEN FACT` — Removal uses `self.tracks.pop(invalid_id)` and retains
  no removed-track record. `reset()` also clears all track entries
  (`base_tracker.py:36-39`; `byte_tracker.py:1061-1072`). No tombstone containing
  `lineage_key`, `birth_frame`, and `death_frame/null` exists.
- `INFERENCE` — Existing birth/expiry control points are sufficient insertion
  anchors, but the bounded lifecycle record itself is missing.

### Hypothesis history — `MISSING`

- `SOURCE-PROVEN FACT` — The observer owns generic event lists and writes a
  `side_hypotheses.jsonl` file, but it sets `side_hypothesis_count` to zero and
  never records a side hypothesis
  (`route_a_observer_runtime.py:64-76,180-203`).
- `SOURCE-PROVEN FACT` — Current arrival processing records only the source
  observation key and a `NO_CROSS_VIEW_CANDIDATE` event; it contains no receiver
  lineage key, `first_seen_frame`, membership index or newness lookup
  (`route_a_observer_runtime.py:126-165`).
- `INFERENCE` — An empty output channel is not a history capable of deciding
  whether `(source_observation_key, receiver_lineage_key)` has appeared before.
  The minimal three-field run-scoped history is absent.

## 4. Minimal insertion points

- **Observation key:** `SOURCE-PROVEN FACT` — The existing earliest legal point
  is the hook between `outs_det` construction and `self.tracker.track()` in
  `mmtrack/models/mot/byte_track.py:241-260`; key construction already occurs
  in `route_a_observer_runtime.py:78-104`. No earlier detector-internal identity
  is required by the frozen MVE.
- **Lineage birth:** `INFERENCE` — The least invasive observable birth anchors
  are the new-ID decision in `ByteTracker.track()`
  (`byte_tracker.py:1269-1286`) and the memo-entry creation branch in
  `BaseTracker.update()` (`base_tracker.py:86-93`). Because feedback IDs can be
  remapped, a side-only remap-preservation hook is also required at the existing
  ID-remap event boundary (`async_deadline_runtime.py:234-255`); otherwise a
  rename can be mistaken for a birth.
- **Tombstone:** `INFERENCE` — The earliest exact death/expiry point is
  immediately before `self.tracks.pop(invalid_id)` in
  `ByteTracker.pop_invalid_tracks()` (`byte_tracker.py:1061-1072`). A run-end
  clear may remain side-state only; no track history beyond the frozen three
  lifecycle fields is needed.
- **Hypothesis newness:** `INFERENCE` — The smallest existing side-layer anchor
  is `RouteAObserverRuntime.process_arrivals()`
  (`route_a_observer_runtime.py:126-165`), after a future candidate has passed
  all hard-impossible checks and its receiver lineage has resolved. The lookup
  must stop at first-seen recording and must not return data to MIA/ByteTrack.
- `UNKNOWN` — Exact non-interference of these points cannot be proven until an
  implementation exists; this audit does not authorize that implementation.

## 5. Scientific boundary check

`SOURCE-PROVEN FACT` — The current observer establishes a suitable read-only
pattern: it copies arrays, its public hooks expose no result to core tracking,
and the manifest declares no observer assignment back to core
(`route_a_observer_runtime.py:28-35,50-51,78-124`;
`route_a_observer_manifest.json:16-23`).

For any later implementation, all of the following are mandatory boundaries,
not claims that unimplemented code has already passed validation:

| Core state/path | Required boundary |
| --- | --- |
| detector | `INFERENCE` — read capture metadata only; no output or threshold change |
| ByteTrack matching | `INFERENCE` — observe assignments/birth only; no cost, pair or ID change |
| Kalman state | `INFERENCE` — no mean/covariance read for the frozen records and no write |
| track survival | `INFERENCE` — observe existing expiry only; no lifetime extension or shortening |
| NMS | `INFERENCE` — no input, ordering, threshold or output change |
| runtime ID | `INFERENCE` — record labels/remaps only; never allocate, rename or replace runtime IDs |
| feature bank | `INFERENCE` — no read or write |
| MIA association | `INFERENCE` — no candidate injection, selection, ID transaction or score change |
| feedback | `INFERENCE` — no row, ID, bbox or label modification |
| next-frame tracker state | `INFERENCE` — no side-state value may be consumed by tracker state transition |

`UNKNOWN` — Since the missing infrastructure is not implemented, its actual
non-interference has not been tested or source-proven. A later implementation
would need a separate pre-run audit; this document does not enter that stage.

## 6. Final verdict

`MINIMAL_INFRASTRUCTURE_GAPS_IDENTIFIED`

- `SOURCE-PROVEN FACT` — The source observation key and capture provenance are
  already present and reusable in the pair-scoped observer.
- `SOURCE-PROVEN FACT` — No immutable receiver track-instance lineage key is
  exposed or preserved across runtime-ID remaps.
- `SOURCE-PROVEN FACT` — Birth/expiry control points exist, but removal discards
  the entry and no bounded tombstone remains.
- `SOURCE-PROVEN FACT` — No three-field hypothesis newness history or lookup
  exists.
- `INFERENCE` — Therefore the current source cannot scientifically distinguish
  a first legal observation-to-lineage hypothesis from a repeated one and
  cannot yet measure `NEW_ASSOCIATION_OPPORTUNITY_CREATED` under the frozen
  fail-closed semantics.
