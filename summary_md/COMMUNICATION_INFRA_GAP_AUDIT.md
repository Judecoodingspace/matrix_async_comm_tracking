# Communication Infrastructure Gap Audit

## 1. Scope

This is a read-only source audit of the frozen communication-side base at
commit `c3332d2d33d054a135480c4c05ca9adba3fc2b7c`. It asks whether the current
packetized MIA runtime exposes a sufficiently explicit producer, logical packet,
arrival, and consumer boundary for a later packet census and, eventually, a
shared bandwidth-constrained communication service.

No dataset, GT, tracker run, evaluation, scheduler, queue implementation, or
Work 1 artifact was read or executed. The only write is this document.

Primary source files inspected:

- `src/tracking/mdmt_mia_async_deadline_runtime.py`
- `src/tracking/mdmt_mia_active_packet_runtime.py`
- `src/tracking/mdmt_mia_packets.py`
- `src/tracking/mdmt_mia_packet_runtime.py`
- `scripts/prepare_mdmt_mia_active_packet_variant.py`
- `scripts/prepare_mdmt_mia_async_packet_variant.py`
- `scripts/phase3_mdmt_mia_async_state_channel_audit.py`
- `tests/test_mdmt_mia_active_packet_runtime.py`
- `tests/test_mdmt_mia_async_deadline_runtime.py`
- the three `exp_20260805_00{1,2,3}` experiment records

## 2. Frozen evidence

The prior experiments establish only a qualitative temporal profile for this
audit:

- Local Track is current-frame deadline-sensitive.
- Homography can use the latest arrived matrix and expose its age.
- ID state is version/freshness-sensitive.
- Supplement is frame-scoped and expires when delayed.

No official-test metric, effect size, or result-derived channel order is used
to define bandwidth, priority, weights, or a scheduler.

The zero-delay active runtime is the relevant compatibility reference: enabled
state boundaries serialize through JSON and return decoded copies to the author
pipeline (`mdmt_mia_active_packet_runtime.py:109-134`). The asynchronous runtime
then replaces that immediate transport with explicit fixed-delay availability
semantics (`mdmt_mia_async_deadline_runtime.py:115-209`).

## 3. Four-channel producer/consumer map

| Channel | Producer boundary and upstream stage | Actual payload | Arrival/consumer boundary | State effect |
| --- | --- | --- | --- | --- |
| Local Track | Generated `demo/supplement_MIA.py` calls `deliver_local_track()` twice immediately after the two ByteTrack result rows are obtained. Injection anchors: `prepare_mdmt_mia_active_packet_variant.py:83-91`; runtime: `mdmt_mia_async_deadline_runtime.py:307-320`. | `view_id`, encoded tracker rows, encoded detector candidates, `max_track_id`. Rows contain runtime ID/bbox/score according to the author tracker representation; no GT identity is added. | `_send("local")`; delayed packets are drained at `begin_frame()` and marked expired (`268-287`). `local_cross_view_ready()` gates entry into the existing cross-view MIA stages; the generated main flow takes the local-only NMS/feedback branch when unavailable (`prepare_mdmt_mia_async_packet_variant.py:133-163`). | The local UAV retains its own decoded/current rows. A nonzero local delay blocks that frame's cross-view H/ID/Supplement path; an old local bbox is not substituted as current remote state. |
| Homography | Called directly after each `compute_transf_matrix()` for `A_to_B` and `B_to_A`; anchors `prepare_mdmt_mia_active_packet_variant.py:93-105`; runtime `mdmt_mia_async_deadline_runtime.py:322-340`. | `direction`, encoded current matrix, encoded previous matrix, `matching_point_count`, and derived `estimation_mode`. | Arrived H packets are drained by `begin_frame()` into `_latest_h[direction]` (`275-282`). The current `deliver_homography()` either returns the timely decoded matrix or the latest arrived/seeded matrix. | Only the H returned to the existing downstream projection/association path changes. No estimator parameter is changed. `h_age_frames` is recorded for held/applied state. |
| ID state | Called after each of three existing mutation stages: `new_A_to_B`, `new_B_to_A`, and `old_unmatched_repair`; anchors `prepare_mdmt_mia_active_packet_variant.py:107-161`; runtime `mdmt_mia_async_deadline_runtime.py:342-364`. | `stage`, encoded post-stage rows for both views, matched/confirmed ID lists, both max IDs, derived `remap_events`, and `post_state_digest`. The envelope supplies `source_state_version`. | Delayed send returns the captured pre-stage rows/lists. At a later `begin_frame()`, `_apply_pending_id()` drains arrivals, checks version, conflict, and current live-row presence, then applies legal remaps to current rows (`221-266`). | A delayed update affects only future live runtime state. It neither rewrites published history nor restores a dead row. Obsolete/conflicting remaps are logged and skipped. |
| Supplement | Called after the existing high-score and low-score Supplement helpers; anchors `prepare_mdmt_mia_active_packet_variant.py:163-195`; runtime `mdmt_mia_async_deadline_runtime.py:366-389`. | `stage`, encoded post-stage rows for both views, matched/confirmed ID lists, encoded supplement rows for both views, `low_score`, and `post_state_digest`. | Timely decoded values return to the existing NMS/feedback path. A delayed call returns the pre-Supplement rows/lists and empty supplement arrays. Later drain at `begin_frame()` only records expiry (`283-286`). | A late Supplement cannot mutate current or historical state. Its content is discarded after its frame-scoped opportunity expires. |

Packet arrival and semantic consumption are distinct for delayed packets:
`_drain()` establishes availability, while the channel-specific code in
`begin_frame()` decides whether the arrived packet is applied, held, obsolete,
conflicting, or expired.

## 4. Packet schema map

### Actual asynchronous runtime envelope

`PacketRuntime._wire()` constructs the active logical packet
(`mdmt_mia_async_deadline_runtime.py:165-181`):

```text
kind
capture_frame
emitted_frame
arrival_frame
source_state_version
valid_until_frame
payload
```

Additional ordering and routing facts:

- `_packet_version` is a process-global monotonic emission version, not a
  per-channel version.
- `_queue_sequence` is an internal heap tie-breaker. It is not serialized into
  the packet.
- There is no explicit packet ID.
- Local has `view_id`; H has `direction`.
- ID routing is implicit in `stage` and individual remap-event `view_id` fields.
- Supplement has `stage` and two-view state arrays but no explicit source-view,
  target-view, or direction field.
- No uniform source endpoint, destination endpoint, link ID, queue class, or
  transmission sequence field exists.

`valid_until_frame` is currently set to `capture_frame` for all four channels.
It is not a universal expiry check: control flow gives Local/Supplement strict
frame scope, while H is held and ID uses version/live-row checks.

### Schema-reference dataclasses versus actual runtime packet

`mdmt_mia_packets.py:55-238` defines frozen dataclasses for Local, H, ID, and
Supplement and `wire_roundtrip()` at `253-256`. These are useful schema and
roundtrip references, but the asynchronous runtime does not instantiate these
dataclasses. Its authoritative runtime object is the generic `_wire()` dict
above. The dataclass, runtime wire dict, and trace event must not be treated as
one object.

## 5. Serialization audit

Three representations are distinct:

1. **Logical packet representation:** the generic Python dict returned by
   `_wire()`.
2. **JSON wire roundtrip:** `_wire()` performs canonical `json.dumps(...,
   sort_keys=True, separators=(",", ":"))` and immediately `json.loads()` the
   result (`165-181`). NumPy arrays are encoded as dtype, shape, and base64 data
   (`31-42`). This decoded dict drives the in-process runtime.
3. **Diagnostic/audit representation:** `_record()` creates a smaller event,
   and `finalize()` writes those events as JSONL plus an aggregate manifest
   (`153-163`, `414-446`). The trace does not contain the complete semantic
   payload and does not preserve the emitted JSON byte count.

There is no socket, byte stream, framing protocol, network stack, compression,
or external serialize/deserialize endpoint. The JSON roundtrip is therefore an
actual byte-producing serialization operation inside one process, but not an
actual network transport.

Consequently,
`len(json.dumps(packet).encode("utf-8"))` is not presently defensible as
“communication payload size” without qualification:

- the actual canonical separators/sort order must match `_wire()`;
- `packet` must mean the actual wire dict, not a dataclass or trace event;
- base64 expansion is an implementation choice;
- the runtime packet sometimes bundles complete two-view state snapshots;
- transport framing, headers, compression, retransmission, and link-level
  overhead are undefined.

Interpretation of JSON-wire bytes as physical communication bytes is
`NEEDS_RESEARCH_DECISION`.

## 6. Delay implementation audit

Current delay is a fixed per-channel frame offset, not bandwidth contention:

```text
arrival_frame = capture_frame + configured_channel_delay
```

`_parse_delays()` reads one nonnegative integer per channel from
`MIA_ASYNC_CHANNEL_DELAYS` (`69-91`). `_send()` either returns immediately when
arrival equals capture or pushes the packet into that channel's independent
heap (`183-197`). `_drain()` releases packets whose scheduled arrival is no
later than the current frame (`199-209`).

There are four independent heaps. There is no shared server, capacity, service
time, contention, packet-size-dependent completion time, drop policy, or
cross-channel ordering policy. `_queue_sequence` only stabilizes equal-arrival
ordering inside the current implementation.

## 7. Expiry, version, and hold semantics

- **Local:** when configured delay is nonzero, current-frame cross-view
  readiness is false (`268-292`). Arrived delayed Local packets are counted as
  expired; their payload is not used as a later current-frame remote track.
- **H:** `_latest_h[direction]` stores `(source_capture_frame, matrix)`. Arrivals
  replace that latest-arrived state; otherwise the current call returns the
  held matrix and records age (`275-282`, `322-340`).
- **ID:** every emitted packet receives a monotonic global
  `source_state_version`. `_last_id_packet_version` rejects non-newer ID
  packets. Remaps must also be conflict-free and must find their source runtime
  ID in the current live rows (`221-266`). Thus an old version cannot overwrite
  a newer applied ID packet, and a stale remap cannot recreate a missing row.
- **Supplement:** its envelope is frame-scoped; nonzero delay suppresses the
  captured mutation immediately, and later arrival is logged as expired with
  no write-in (`283-286`, `366-389`). End-of-run pending packets are also
  classified without semantic application (`414-420`).

## 8. Packet-size feasibility

| Quantity | Current feasibility | Gap |
| --- | --- | --- |
| Semantic payload bytes | Array raw bytes are deterministically available from dtype/shape/data; scalar/list structural bytes can be calculated for an emitted packet. | Current trace retains only a digest, not raw-array byte totals or a scalar-size convention. Minimal emission-side instrumentation is required for a census. |
| Serialized JSON bytes | The exact canonical `encoded` string already exists inside `_wire()`. | Its byte length is discarded. Recording `len(encoded.encode("utf-8"))` at emission is minimal instrumentation. It must be labeled `JSON_WIRE_BYTES`, not physical link bytes. |
| Packet metadata overhead | Envelope fields can be serialized separately from payload under a frozen accounting rule. | No accounting rule is frozen, and the packet has no physical framing. This is `NEEDS_RESEARCH_DECISION`. |
| Physical communication payload | Not currently defined. | Requires a decision on packet atomicity, endpoint/direction metadata, array encoding, and transport framing. It cannot be inferred from the diagnostic JSONL. |

No census was run in this audit.

## 9. Emission-frequency feasibility

The structure is known; observed frequency still requires a future census:

| Channel | Structural emission class | Evidence |
| --- | --- | --- |
| Local | Every processed frame, once per view; tracker/detector arrays may be empty. | Two unconditional `deliver_local_track()` hooks after ByteTrack rows (`prepare_mdmt_mia_active_packet_variant.py:83-91`). |
| H | Every frame that reaches the cross-view path, once per direction. | Two hooks after the two H estimators (`93-105`). Local deadline skip can prevent the entire path. |
| ID | Stage-driven but structurally up to three emissions per cross-view-active frame. | Hooks after `new_A_to_B`, `new_B_to_A`, and `old_unmatched_repair` (`107-161`). Remap-event lists may be empty. |
| Supplement | Two stage emissions per cross-view-active frame: high-score and low-score; supplement arrays may be empty. | Hooks at `163-195`. |

Exact counts, empty-payload fractions, and sequence-to-sequence variability are
`STRUCTURE_KNOWN_FREQUENCY_REQUIRES_CENSUS`.

## 10. Candidate queue insertion point

The smallest existing boundary is:

```text
existing deliver_* producer
  -> PacketRuntime._wire()
  -> PacketRuntime._send()
  -> [future communication service boundary]
  -> packet becomes available
  -> PacketRuntime._drain()
  -> existing channel-specific consumer
```

The minimal future implementation surface would be confined to:

- `src/tracking/mdmt_mia_async_deadline_runtime.py`, and its copied legacy
  runtime counterpart;
- `scripts/prepare_mdmt_mia_async_packet_variant.py`, only as needed to install
  the frozen runtime and preserve its call boundaries;
- a launcher/config interface for future communication-service parameters,
  after those parameters receive a separate research decision.

The future service may alter only service order, transmission completion, and
arrival/availability time. It must not mutate `wire["payload"]`.

The following must remain unchanged: detector and detection cache semantics,
ByteTrack matching/Kalman/lifecycle, H estimation, all three author ID helpers,
both Supplement helpers, NMS, explicit tracker feedback commit, output
publication, and evaluation.

Before a real shared queue is designed, packet atomicity and endpoint semantics
for the bundled ID/Supplement messages remain unresolved. That does not block a
descriptive census of the current logical emission units, but it does block
calling them final physical link packets.

## 11. Required instrumentation

A future census needs only passive emission/arrival bookkeeping, not semantic
algorithm changes:

- immutable packet ID or an auditable `(source_state_version, kind)` key;
- canonical JSON-wire byte count at `_wire()`;
- semantic array raw-byte total and a frozen scalar/list accounting label;
- channel plus explicit source/target/direction attribution, with bundled
  packets marked rather than guessed;
- empty/nonempty payload indicators appropriate to each channel;
- one emission record and one terminal outcome record per packet;
- payload digest preserved from emission through arrival;
- arrival/availability and semantic outcome recorded separately;
- census completeness conservation: emitted equals timely + applied/held +
  expired/obsolete/conflict + pending-at-end, under precisely frozen outcome
  definitions.

The existing manifest already provides aggregate emitted/consumed/expired/
obsolete/conflict/applied counts, and emission events already contain a wire
digest. However, later Local/H/Supplement outcome events do not consistently
carry the packet version, so the existing trace cannot always prove one-to-one
packet lineage without the additional packet key.

## 12. Future non-interference gate

When future communication capacity is effectively unlimited, the new runtime
must exactly reduce to the current `delay=0` active packet runtime.

Required comparisons:

- exact packet count by channel and stage;
- exact payload digest sequence;
- exact capture/emission/arrival frame sequence;
- zero unmatched or duplicate packet lineage;
- exact two-view prediction JSON bytes;
- exact MDA, MOTA, IDF1, and IDSW after runtime completion.

Existing support:

- active/async packet manifests: aggregate packet counts and safety counters;
- async packet trace: channel/action timing and emitted wire digest;
- prediction JSON and existing equivalence/evaluation scripts: final output and
  metric equality;
- feedback digest chain: next-frame tracker-state continuity.

Needed instrumentation:

- stable packet ID on emission and all terminal outcomes;
- explicit serialized/semantic byte fields;
- complete emitted-packet ledger rather than the current mixed diagnostic event
  stream;
- an exact census completeness validator.

Metric computation remains an offline evaluation activity and must never enter
runtime queue decisions.

## 13. Work 1 isolation

The audited runtime and patch path import neither Work 1 observer infrastructure
nor Work 1 traces. This research line does not depend on A/B/B-repeat/C/Parent
traces, `PRE_ID_FROZEN`, E_pre/E_post labels, `S_cf`, `Yec`, GT identity, or
Route A.

The repository contains later cascade-diagnostic files mentioning `Yec`, but
they are not imported by `mdmt_mia_async_deadline_runtime.py` or
`prepare_mdmt_mia_async_packet_variant.py` and were not used as evidence here.
Only the frozen packet runtime and qualitative four-channel semantics are
reused.

## 14. Unresolved research decisions

The following decisions are deliberately not made in this audit:

1. Whether the current canonical JSON representation is merely an audit wire
   format or the future communication payload format.
2. The byte-accounting definition for semantic scalars, JSON/base64 expansion,
   and metadata overhead.
3. Whether each current ID/Supplement stage is one atomic packet or must be
   separated by source/target communication edge.
4. The explicit source, destination, and direction schema for all channels.
5. Whether `valid_until_frame` remains channel-specific policy metadata or is
   replaced by separately named deadline/version/hold semantics.
6. Any bandwidth, service discipline, queue ordering, priority, deadline,
   channel weight, or scheduler policy.

Items 1-5 are required before interpreting census bytes as physical network
traffic or implementing a shared queue. They are not required to measure the
current logical packet units descriptively, provided every size category is
reported under its exact name and no communication-capacity claim is made.

## 15. Go/no-go decision

`READY_FOR_PACKET_CENSUS_DESIGN`

Rationale:

- producer, logical serialization, fixed-delay availability, and semantic
  consumer boundaries are explicit and source-auditable;
- current logical packet size and emission frequency can be measured with
  minimal passive instrumentation at `_wire()`/`_send()`;
- the unlimited-capacity non-interference reference is already well defined by
  the delay-zero active packet runtime;
- unresolved physical packetization and byte-accounting questions are clearly
  fenced as research decisions before queue/scheduler implementation.

This verdict authorizes only design of a passive packet census. It does not
authorize running a census, defining bandwidth, implementing a shared queue, or
selecting any scheduler.
