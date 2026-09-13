# C5 Shadow Oracle Opportunity Census Implementation Plan

```text
DOCUMENT_ROLE = C5_SHADOW_ORACLE_OPPORTUNITY_CENSUS_IMPLEMENTATION_PLAN_DRAFT
FROZEN_C4_AUTHORITY = 23afc5740cbaafacd77b78e5eac246e3abdf0b20
APPROVED_CONTRACT_AUTHORITY = 1a664abdba12bc3e720ac3e728003e5ecd4ffa04
APPROVED_CONTRACT_SHA256 = 7595cf1973ded33e1f9046be00556f8a9b87c6613853bff45ec81f79927d4e25
SCIENTIFIC_REDESIGN_ALLOWED = NO
CONTRACT_REINTERPRETATION_ALLOWED = NO
IMPLEMENTATION_AUTHORIZED_BY_THIS_PLAN = NO
SHADOW_EXECUTION_AUTHORIZED = NO
CLOSED_LOOP_INTERVENTION_AUTHORIZED = NO
```

## 1. Purpose and authority

This Plan translates the approved C5 Shadow Oracle Opportunity Census
Experiment Contract into a minimal future engineering delta. It answers only:

> How can the approved read-only Shadow Census be implemented mechanically at
> the true first-service event while preserving the exact frozen C4 trajectory
> and scientific semantics?

The binding chain is:

```text
approved Contract
-> frozen code touchpoints
-> event-local observation
-> pure predicate
-> detached Shadow evidence
-> mechanical qualification
```

The approved Contract is
`summary_md/communication/C5_SHADOW_ORACLE_OPPORTUNITY_CENSUS_EXPERIMENT_CONTRACT.md`
at commit `1a664abdba12bc3e720ac3e728003e5ecd4ffa04`.
The frozen C4 implementation is its parent,
`23afc5740cbaafacd77b78e5eac246e3abdf0b20`.

## 2. Frozen implementation fact map

All line references below bind to the frozen C4 implementation inherited by
the approved Contract authority.

| File | Symbol / lines | Current behavior | Why it matters for C5 |
| --- | --- | --- | --- |
| `src/tracking/mdmt_mia_async_deadline_runtime.py` | `_array()`, 39-40 | Converts to a NumPy array and makes a copy. | Existing copy semantics can prevent receiver-row aliasing in an event-local snapshot. |
| same | `_PacketCensusSidecar.emission()`, 431-462 | Assigns a four-field `packet_id`, records `source_state_version`, and defines `JSON_WIRE_BYTES` as canonical encoded UTF-8 length. | Supplies stable packet identity and the approved full-wire-byte denominator without reserialization. |
| same | `_PacketCensusSidecar._content_counts()`, 478-500 | Counts ID-State remaps, matched IDs, confirmed IDs, and row counts. | Existing Census fields are descriptive only; they do not implement current applicability. |
| same | `_C4SharedLogicalServer`, 544-927 | Owns FIFO queue, one non-preemptive in-service packet, per-frame budget, completions, ledger, and conservation seal. | The Shadow hook must observe this service without changing its transitions or evidence. |
| same | `_C4SharedLogicalServer.begin_frame()`, 676-688 | Opens a frame, replenishes `R`, and calls `_serve()` before returning completed packets. | Carried backlog may first start before the frame's delayed-arrival drain; receiver context must already be available. |
| same | `_C4SharedLogicalServer.admit()`, 690-735 | Builds an item with `service_start_frame=None`, queues it, calls `_serve()`, and returns only a full same-frame completion. | Newly admitted packets may start immediately; admission itself is not the observation event. |
| same | `_C4SharedLogicalServer._start_next()`, 737-743 | Pops the FIFO head, assigns `_in_service`, sets `service_start_frame`, and records `service_start`. | This is the sole approved true first-service hook. |
| same | `_C4SharedLogicalServer._serve()`, 752-773 | Calls `_start_next()`, then decrements `remaining_service_bytes` and frame budget in the first `service_slice`; continuation bypasses `_start_next()`. | The snapshot must finish after selection but before lines 761-769 mutate byte state. Continuations must not reclassify. |
| same | `_C4SharedLogicalServer._complete_current()`, 744-750 | Sets completion/availability frame, appends the whole item, and clears `_in_service`. | Completion is too late for the Shadow observation and must remain unchanged. |
| same | `PacketRuntime.__init__()`, 939-984 | Creates the server, `_applied_id_map`, `_last_id_packet_version`, counters, and feedback-integrity state. | These receiver-side fields are runtime-local and must only be copied, never mutated by Shadow code. |
| same | `PacketRuntime._wire()`, 998-1015 | Builds canonical wire data; `source_state_version` is `_packet_version + 1`; encoding and digest are finalized before admission. | The pure predicate must read the existing packet and must not add Shadow fields to the wire. |
| same | `PacketRuntime._send()`, 1017-1056 | Sends ID-State/Supplement through `service.admit`; immediate full completion returns through the existing timely path. | Event context has to reach the server through this call without changing return or queue behavior. |
| same | `PacketRuntime._apply_pending_id()`, 1083-1130 | Rejects the whole packet when `version <= _last_id_packet_version`; otherwise updates the version, checks different-target conflict before source presence, rewrites live row IDs, updates `_applied_id_map`, and unions confirmed/matched lists. | This is the mechanical reference for version, conflict, source-presence, and confirmed consistency tests. |
| same | `PacketRuntime.begin_frame()`, 1132-1161 | Calls server `begin_frame`, enqueues full completions into arrival heaps, drains channels, then invokes `_apply_pending_id` on copied current rows/lists. | The pre-drain rows and confirmed list passed into this method are the causally current snapshot for backlog first-start events. |
| same | `PacketRuntime.deliver_id_state()`, 1216-1238 | Derives `remap_events`, includes `matched_ids` and `confirmed_ids`, admits the packet, returns post-state only for timely completion, otherwise returns copied pre-state. | Post-association rows and current frame-local confirmed state are causally available during same-stage service start; only remap and confirmed effects enter the predicate. |
| same | `PacketRuntime.deliver_supplement()`, 1240-1264 | Admits Supplement through the same server but uses frame-scoped expiry semantics. | It must remain service-visible but outside all Shadow classification and scientific counters. |
| same | `PacketRuntime.finalize()`, 1289-1347 | Finalizes pending service, seals Packet Census/service evidence, and writes runtime trace/manifest. | Future Shadow evidence needs its own seal and must not change existing manifest semantics or acceptance. |
| `scripts/prepare_mdmt_mia_async_packet_variant.py` | `patch_variant()` injection sites around 179-237 | Copies/injects `PacketRuntime` calls into the generated author entry; `coID_confirme` and ID-state before/after values flow through existing calls. | Keeping C5 helper logic within the copied runtime avoids changing the frozen author call graph or adding a generated-package dependency. |
| `tests/test_mdmt_mia_c4_service_runtime.py` | existing C4 service tests | Covers same/cross-frame service, FIFO, non-preemption, atomic delivery, conservation, and parity. | Remains an unchanged regression authority for trajectory preservation. |

The generated author loop resets `coID_confirme` once per frame, then calls
three `deliver_id_state` stages with the evolving current rows and confirmation
list. The pure predicate therefore uses the event-local current confirmed
state supplied to the runtime; it must not create a persistent confirmation
store.

## 3. Minimal implementation architecture

The proposed future implementation has four strictly separated pieces:

1. Pure snapshot/result helpers in
   `src/tracking/mdmt_mia_async_deadline_runtime.py`.
2. One observer callback from `_C4SharedLogicalServer._start_next`, after FIFO
   selection and before `_serve` decrements bytes.
3. A `PacketRuntime`-owned in-memory Shadow sidecar that classifies ID-State
   packets and writes separate evidence only during finalization.
4. A new C5-only runner/analyzer that renders exactly the frozen four cells in
   a new output namespace and validates seals; it does not alter the C4 runner.

Keeping the pure helper and sidecar in the existing runtime module is the
smallest compatible packaging delta: the existing variant patcher already
copies that module to `demo/utils/async_deadline_runtime.py`. No import,
tracker, evaluator, or author-stage rewrite is required.

Proposed internal symbol names are engineering labels, not scientific fields:

```text
_C5ShadowReceiverSnapshot
_C5ShadowPacketResult
_C5ShadowOpportunitySidecar
_snapshot_c5_receiver_state
_classify_whole_packet_currently_non_applicable
```

## 4. True first-service hook

The future server may accept an optional observer callable configured once by
`PacketRuntime`. `_start_next()` remains the only invocation site:

```text
assert _in_service is None
item = queue.popleft()
_in_service = item
item.service_start_frame = current_frame
record existing C4 service_start event
invoke read-only Shadow observer(item, current receiver context)
return to _serve
decrement first service slice
```

The observer is called only on the transition from queue to `_in_service`.
Cross-frame continuation retains `_in_service`, so `_start_next()` is not
entered and no reclassification occurs.

Required assertions/integrity evidence:

```text
SNAPSHOT_ONCE_PER_PACKET = YES
packet.service_start_frame was None before selection
packet.bytes_served_total == 0 at snapshot
packet.remaining_service_bytes == packet.JSON_WIRE_BYTES at snapshot
no prior Shadow record exists for packet_id
first subsequent byte event for packet_id is its first service_slice
```

These assertions do not enter queue ordering or service decisions. Any failure
invalidates Shadow qualification; it must not be converted into a scheduling
action or a baseline-service failure.

The observer invocation must be enclosed by a narrowly scoped Shadow-only
failure-isolation boundary. Its normative behavior is:

```text
Shadow observation begins
-> snapshot / predicate / Shadow integrity checks

success:
    append one valid Shadow record
    continue the baseline service transition

ANY Shadow-only exception, assertion, or integrity failure:
    capture bounded Shadow failure information
    mark the Shadow cell/run evidence INVALID or INCOMPLETE
    do not mutate queue, service, packet, receiver, or tracker state
    do not suppress, retry, reorder, or reclassify the packet
    continue the exact baseline service transition
```

The failure boundary must not catch or relabel an independent baseline runtime
failure. It catches only Shadow callback/snapshot/predicate/recorder failures.
It prescribes neither packet-service rollback nor queue rollback because the
baseline transition continues normally.

```text
SHADOW_FAILURE_SCOPE = C5_EVIDENCE_VALIDITY_ONLY
SHADOW_FAILURE_MUST_NOT_ABORT_BASELINE_SERVICE = YES
SHADOW_FAILURE_MUST_NOT_CHANGE_FIFO_TRAJECTORY = YES
SHADOW_FAILURE_MUST_NOT_DROP_SKIP_CANCEL_PACKET = YES

fail-close for Shadow scientific validity
!=
fail-close for baseline packet service
```

## 5. Event-context transport

The server currently has no receiver rows or confirmation list. A future
instrumented runtime must supply copied context at every call that can start
service, without storing references to caller-owned arrays.

- `PacketRuntime.begin_frame(frame_id, rows1, rows2, matched_ids,
  confirmed_ids)` constructs the context before calling the server's
  `begin_frame`. This is the current local-tracker state before same-frame
  completion drain.
- `deliver_id_state` constructs context from its post-stage
  `track_rows_view1/2` and `confirmed_ids_after` immediately before `_send`.
- `deliver_supplement` supplies its current post-stage rows and confirmed state
  before its constrained admission, solely so a FIFO head starting at that
  service call would have causally current receiver context. Supplement itself
  is never classified.
- No context is needed for Local Track or Homography because they cannot enter
  the constrained server.

The context should be an explicit argument scoped to the current `_serve`
invocation rather than a mutable global cache. This makes the causal producer
visible in the call signature and prevents later-stage replacement from
changing an earlier snapshot.

## 6. Minimal immutable receiver snapshot

For each ID-State first start, construct exactly:

```text
frame
packet_id
live_rows_view1 = copied current rows
live_rows_view2 = copied current rows
confirmed_ids = immutable tuple copied from current frame-local confirmed state
applied_id_map = immutable copied tuple of ((view_id, source_track_id), target_track_id)
last_id_packet_version = copied integer
```

Both view arrays are required because each remap effect selects its receiver
array by `view_id`. Arrays must be copied with `_array()` and made read-only, or
converted to immutable row tuples before classification. Lists and dictionaries
must be deep-copied and normalized into immutable tuples. The predicate may
derive per-view ID sets only from those copies.

The snapshot contains no GT identity, future state, lifecycle epoch, TTL,
supersession metadata, predicted outcome, or persistent confirmation history.
The in-memory snapshot may retain full copied rows for direct qualification,
but persisted evidence needs only the canonical replay projection defined in
Section 12. A digest may accompany that projection but cannot replace it.

## 7. Pure predicate

`_classify_whole_packet_currently_non_applicable(packet, snapshot)` must:

- have no access to `PacketRuntime`, the live server, files, evaluator, future
  frames, or mutable arrays;
- mutate neither argument;
- return one immutable engineering result;
- use only ID-State `remap_events`, `confirmed_ids`, `source_state_version`,
  and the approved snapshot fields;
- ignore `matched_ids` as an independent task effect;
- reject Supplement input fail-closed.

Recommended internal result shape:

```text
packet_applicability
packet_reason_flags
remap_effect_results
confirmed_effect_results
integrity_fields
```

Only Contract-approved metrics and descriptive counters may be aggregated.
Any extra assertion field must be labeled `INTEGRITY_ONLY` and
`NON_SCIENTIFIC`.

## 8. Literal version gate

The first predicate branch must match `_apply_pending_id()` exactly:

```text
if int(packet.source_state_version) <= int(snapshot.last_id_packet_version):
    whole_packet_currently_non_applicable = YES
    version_reject = YES
```

This mirrors the frozen whole-packet `continue` at runtime lines 1089-1095.
It is an implementation-relative reject, not a stale-value theory and not a
semantic-dominance rule. A version-rejected packet requires no remap or
confirmed-effect result to decide the whole-packet label.

Scientific effect counters follow the frozen consumer's short-circuit order:

```text
SCIENTIFIC_APPLICABILITY_EFFECT_COUNTERS =
ONLY_EFFECTS_EVALUATED_AFTER_VERSION_GATE_SURVIVAL

remap_total =
total remap effects entering applicability evaluation after version-gate survival

confirmed_total =
total confirmed effects entering applicability evaluation after version-gate survival
```

Thus `remap_total`, `confirmed_total`, and every approved applicability/reason
subcounter exclude version-rejected packets. If raw payload content from a
version-rejected packet is retained for audit, it must use separately named
fields such as
`INTEGRITY_ONLY_VERSION_REJECT_REMAP_PAYLOAD_COUNT` and
`INTEGRITY_ONLY_VERSION_REJECT_CONFIRMED_PAYLOAD_COUNT`. Those fields must be
labeled `INTEGRITY_ONLY` and `NON_SCIENTIFIC`; they are not approved scientific
secondary metrics.

## 9. Literal remap effects

For each `(view_id, source_track_id) -> target_track_id`:

1. Select the copied row snapshot for `view_id`; reject unsupported view IDs.
2. Look up `(view_id, source_track_id)` in the copied `_applied_id_map`.
3. If an existing target differs, classify the effect non-applicable with
   `REMAP_CONFLICT`; this mirrors the frozen consumer's conflict-first
   `continue` at lines 1102-1108.
4. Otherwise, if no copied live row has `row[0] == source_track_id`, classify
   it non-applicable with `REMAP_SOURCE_ABSENT`.
5. Otherwise classify it conservatively as potentially applicable.

Same-key/same-target with a live source remains potentially applicable. The
predicate must not inspect timestamp recency, infer lifecycle continuity, or
introduce supersession.

## 10. Literal confirmed effects

For each `confirmed_id` in the packet:

```text
confirmed_id in snapshot.confirmed_ids
-> currently non-applicable / already present

confirmed_id not in snapshot.confirmed_ids
-> potentially applicable / new
```

The snapshot is the current frame-local state at the event. The implementation
must not consult a prior/future frame confirmation cache or add persistence.

## 11. Whole-packet aggregation

Aggregation is fixed:

```text
VERSION_REJECT
-> whole packet currently non-applicable

otherwise:
whole packet currently non-applicable
iff
ALL remap effects are non-applicable
AND
ALL confirmed effects are non-applicable
```

Consequences:

- any potentially applicable effect makes the packet not an opportunity;
- a mixed packet is not an opportunity;
- an empty task-effect packet is an opportunity;
- a matched-only delayed packet is an opportunity because `matched_ids` is not
  an independent audited task effect;
- no effect is dropped or separately transmitted.

## 12. Detached Shadow evidence

At first service, the sidecar classifies and appends an immutable in-memory
record keyed by the existing packet ID. It does not write synchronously into
the C4 ledger and exposes no result to `_serve`, `_send`, `_apply_pending_id`,
or the tracker.

During `PacketRuntime.finalize`, after existing C4 terminal/service evidence is
sealed, the sidecar writes its own files under a separate Shadow directory. A
write, schema, duplicate, timing, or seal failure makes the Shadow package
incomplete; it must not retroactively change C4 packet state or be interpreted
as a scientific result.

The Shadow result must never be stored in the canonical wire, service item cost,
FIFO key, completion logic, runtime receiver state, or feedback.

Every persisted first-service record must contain a minimal canonical replay
projection sufficient for an independent implementation to recompute the
predicate without future state or trust in the recorded classification:

```text
packet_id
frame
channel
source_state_version
snapshot.last_id_packet_version
packet.remap_events
packet.confirmed_ids
per-view live source-track-ID sets
current confirmed-ID set
relevant applied_id_map entries for every packet remap key
whole-packet classification
packet reason flags
per-effect remap classification and reasons
per-effect confirmed classification and reasons
JSON_WIRE_BYTES
integrity/schema version
```

The applied-map projection must include presence/absence and target value for
every remap key in the packet. Canonical ordering is required for maps, sets,
and effect lists. Full bbox geometry is excluded because the predicate does not
use it. GT, MDA, IDSW, future association, and future packet fields are
forbidden.

```text
INDEPENDENT_PREDICATE_REPLAY = YES
DIGEST_ONLY_EVIDENCE = NOT_SUFFICIENT
```

Canonical hashes may be added as integrity fields, but replay evidence may not
be replaced by a hash.

## 13. Approved metrics

### Primary packet/byte metrics

For each ID-State packet that reaches `_start_next` exactly once:

```text
checked_id_packet_count += 1
checked_id_packet_wire_bytes += existing item.JSON_WIRE_BYTES
```

If the predicate result is opportunity:

```text
whole_packet_non_applicable_count += 1
whole_packet_non_applicable_wire_bytes += existing item.JSON_WIRE_BYTES
```

Ratios use only these denominators. If a denominator is zero, serialize its
ratio as `null` with an `INTEGRITY_ONLY_DENOMINATOR_ZERO` flag rather than
misrepresenting it as zero opportunity.

`whole_packet_non_applicable_wire_bytes` remains baseline-trajectory
opportunity bytes, not realized service savings.

### Approved secondary packet counters

```text
version_reject_packet_count
empty_task_effect_packet_count
mixed_effect_packet_count
```

### Approved secondary effect counters

```text
remap_total
remap_applicable_count
remap_source_absent_count
remap_conflict_count

confirmed_total
confirmed_new_count
confirmed_already_present_count
```

Packet counters and effect counters are separate namespaces. Effect counters
must not be summed or relabeled as packet counts, and they are not required to
sum to `checked_id_packet_count`. Integrity-only counters may cover duplicate
IDs, unsupported channel/view, missing event context, duplicate observation,
schema failure, and incomplete seal, but must carry both `INTEGRITY_ONLY` and
`NON_SCIENTIFIC` labels.

`remap_total` and `confirmed_total` are scientific evaluated-effect totals:
they count only effects that enter applicability evaluation after the packet
survives the version gate. The corresponding applicable/reason subcounters use
the same population. Version-rejected raw payload totals, if recorded at all,
remain separate integrity-only metadata as defined in Section 8.

## 14. Frozen four-cell matrix

The future runner renders exactly:

| Role | Pair | Condition |
| --- | --- | --- |
| CONTROL | Pair23 | `FIFO_mild` |
| FRONTIER | Pair23 | `FIFO_strong` |
| FRONTIER | Pair44 | `FIFO_moderate` |
| FRONTIER | Pair66 | `FIFO_mild` |

It inherits the exact C4 dataset, split, frame range, checkpoint, tracker,
thresholds, message schema, service rates, evaluator definitions, and
determinism controls. It adds no pilot/debug scientific cells, pair search,
rate search, population expansion, or new tracking evaluation outcome.
Synthetic qualification cases are tests, not scientific cells.

## 15. Output and artifact isolation

A future run uses a new non-C4 namespace such as:

```text
outputs/c5_shadow_oracle_opportunity_census/<run_id>/
  runtime/<cell_id>/                 pre-existing runtime artifacts
  shadow/<cell_id>/                  first-service records and Shadow seal
  qualification/                     Q1-Q4 evidence and parity manifests
  summary/                            approved per-cell/aggregate tables
```

The exact `<run_id>`, artifact filenames, and schemas require independent
implementation-plan/qualification review. Nothing may write into or overwrite
`outputs/c4_baseline_qualification/c4_baseline_qualification_mve_004`.

Runtime, Shadow, qualification, and summary artifacts must remain separable.
An incomplete Shadow/qualification seal cannot be promoted to the scientific
summary.

## 16. Trajectory parity design — Q1

Qualification compares the frozen C4 baseline with Shadow-enabled execution
after projecting away only new Shadow-only evidence. Mechanical equality is
required where applicable for:

- canonical packet wire digests, identities, generation count and order;
- admission packet sequence and FIFO order;
- service-start sequence and frame;
- service-slice amount/order and remaining bytes;
- completion/availability frame and order;
- terminal class, pending-at-end state, completion delays and conservation;
- pre-existing runtime trace and manifest scientific fields;
- prediction/tracking outputs and feedback digests.

New Shadow records, Shadow seals, qualification reports, file timestamps,
absolute output roots, and explicitly scoped run/runtime identifiers are not
trajectory fields. The parity comparator must whitelist exclusions rather than
silently dropping unknown differences.

Q1 fails closed on any unexplained pre-existing field difference, packet count
or ordering change, service difference, prediction difference, feedback
difference, or missing counterpart. Synthetic Shadow failures—including
snapshot exception, predicate exception, duplicate observation, unsupported
view, missing context, and recorder failure—must still produce exact baseline
service parity while marking Shadow evidence `INVALID` or `INCOMPLETE`.

## 17. Event-local snapshot qualification — Q2

Independent synthetic/mechanical tests must establish the explicit event
chain for each observed packet:

```text
enqueue
-> service_start / observer snapshot
-> first service_slice with bytes_served > 0
```

Tests cover same-frame admission, carried backlog, a packet spanning frames,
multiple completions in one frame, and budget exhaustion before a queued
packet starts. Required findings:

- one snapshot per started ID-State packet;
- zero snapshots for never-started/pending ID-State packets;
- zero snapshots for Supplement packets;
- zero repeat snapshots for continuation slices;
- snapshot byte counters show zero bytes previously served;
- event-local state differs from deliberately mutated later-frame/stage state;
- post-snapshot mutations cannot alter the stored result.

The same fixtures must inject snapshot exception, predicate exception,
duplicate observation, unsupported view, missing context, and Shadow recorder
failure. In every case the packet follows the unchanged baseline service path,
while the Shadow validity state becomes `INVALID` or `INCOMPLETE` and no retry
or second classification occurs.

Evidence must be emitted from the event itself, not inferred solely from final
ledgers.

## 18. Predicate-versus-consumer consistency — Q3

A standalone suite uses only isolated/copied/synthetic state. It invokes the
pure predicate and a frozen `_apply_pending_id` reference on independent copies.
Its exact comparison target is:

```text
Q3_COMPARISON_TARGET = FROZEN_AUDITED_TASK_EFFECT_PROJECTION
WHOLE_RECEIVER_STATE_EQUIVALENCE_REQUIRED = NO
```

Q3 never defines opportunity as whole receiver-state non-mutation. It compares
only the frozen audited delayed task effects `{remap_events, confirmed_ids}`:

```text
VERSION_REJECT
-> frozen consumer whole-packet short-circuit

REMAP_CONFLICT
-> corresponding remap creates no audited remap application

REMAP_SOURCE_ABSENT
-> corresponding remap creates no audited remap application

SAME_KEY_SAME_TARGET + live source
-> remains on the potentially applicable audited remap path

CONFIRMED_ALREADY_PRESENT
-> creates no new audited confirmed effect

CONFIRMED_NEW
-> potentially creates an audited confirmed effect

MATCHED_ONLY
-> may mechanically affect the matched container but produces no effect in
   the frozen audited delayed-effect set

EMPTY_TASK_EFFECT
-> produces no audited remap/confirmed task effect
```

```text
MATCHED_IDS_MECHANICAL_MUTATION
DOES_NOT_INVALIDATE
MATCHED_ONLY_OPPORTUNITY_CLASSIFICATION
```

This holds only when no frozen audited remap or confirmed effect is produced.

Required cases:

| Case | Required Shadow classification relation |
| --- | --- |
| version reject | whole packet opportunity via `VERSION_REJECT` |
| source absent | remap non-applicable |
| different-target conflict | remap non-applicable via conflict-first frozen path |
| same-key/same-target with live source | remap potentially applicable |
| confirmed new | confirmed potentially applicable |
| confirmed already present | confirmed non-applicable |
| mixed effects | whole packet not opportunity |
| empty task-effect packet | whole packet opportunity |
| matched-only packet | whole packet opportunity |

Inputs and post-call states are hashed/canonicalized to prove the pure predicate
does not mutate them. Q3 does not run detector/tracker evaluation, read
MDA/IDSW, alter formal state, or seed formal caches.

## 19. Metric and denominator qualification — Q4

Synthetic packet/event fixtures must prove:

- checked-packet denominator includes only ID-State packets that enter true
  first service;
- each started packet appears exactly once even across continuation frames;
- queued-at-end packets that never start are excluded;
- Supplement starts are excluded;
- checked bytes equal the full existing `JSON_WIRE_BYTES`, never bytes served
  so far, raw array bytes, payload-only bytes, or estimated savings;
- opportunity packet/byte numerators are strict subsets of their denominators;
- ratios reconcile exactly when denominators are non-zero;
- packet-level and effect-level counters remain disjointly named and typed;
- effect reason accounting follows the frozen consumer short-circuit/order;
- `remap_total`, `confirmed_total`, and their scientific subcounters exclude
  version-rejected payloads;
- any version-rejected raw payload counts are separately labeled
  `INTEGRITY_ONLY` and `NON_SCIENTIFIC`;
- per-record sums reconcile with cell-level summaries and the final seal.

No scientific threshold, significance test, or outcome gate is introduced.

## 20. Proposed file-touch matrix

This is a future proposal only; this Plan changes none of these files.

| File | Current role | Proposed classification/change | Why required | Scientific semantics changed? | Trajectory risk | Qualification |
| --- | --- | --- | --- | --- | --- | --- |
| `src/tracking/mdmt_mia_async_deadline_runtime.py` | Frozen wire, Packet Census, C4 server, delayed consumer | `INSTRUMENT_ONLY`: pure snapshot/predicate/sidecar plus one `_start_next` observer hook and explicit context plumbing | Exact event-local read and detached evidence | NO | High: central service path | Q1-Q4 and all existing C4 tests |
| `scripts/prepare_mdmt_mia_async_packet_variant.py` | Copies runtime and injects existing author hooks | `UNCHANGED` | In-module helper design preserves current copy topology | NO | None | Existing patcher/runtime smoke |
| `scripts/run_mdmt_mia_c4_baseline_qualification.py` | Frozen C4 matrix runner | `UNCHANGED` | C4 authority must remain isolated | NO | None | Q1 reference |
| `scripts/run_mdmt_mia_c5_shadow_oracle_opportunity_census.py` | Does not exist | `NEW_EVIDENCE_WRITER`: exact four-cell renderer, isolated run namespace, seals, no policy action | Governed C5 qualification and aggregation | NO | Medium: launch/input binding | Dry-run matrix and fail-closed manifest tests |
| `tests/test_mdmt_mia_c5_shadow_oracle.py` | Does not exist | `TEST_ONLY`: pure predicate, Q2-Q4 fixtures | Mechanical semantic/timing qualification | NO | None | Required cases in Sections 17-19 |
| `tests/test_mdmt_mia_c5_shadow_trajectory_parity.py` | Does not exist | `TEST_ONLY`: Shadow-off/on canonical projection parity | Q1 non-interference | NO | None | Exact synthetic parity plus frozen regression suites |
| `src/evaluation/mdmt_mia_paper.py` | Frozen MDA/MOT evaluator | `UNCHANGED` | Shadow opportunity metrics do not require evaluator changes | NO | None | Hash/authority binding only |
| tracker/detector/model/config files | Frozen scientific pipeline | `UNCHANGED` | No tracking/model change is permitted | NO | None | Changed-file allowlist |

No standalone helper module is proposed because it would require a new
generated-variant copy/import path. If independent review prefers a separate
module, the patcher/import delta and parity risk must be reviewed explicitly;
it cannot be treated as an invisible refactor.

## 21. Risk register

| Severity / risk | Prevention | Qualification | Fail-close condition |
| --- | --- | --- | --- |
| P0 future leakage | Snapshot only in `_start_next`; pass explicit current context; prohibit later reconstruction | Q2 event chain and later-state mutation fixtures | Any field originates after first slice/start event |
| P0 wrong observation timing | Sole observer call after selection and before decrement | Assert zero served bytes and next event is first slice | Observer at admission, completion, frame end, or continuation |
| P0 instrumentation changes service trajectory | Result never enters FIFO/budget/return paths; Shadow-only failures are isolated and baseline service always continues | Q1 canonical Shadow-off/on parity plus injected callback/recorder failures | Any queue, slice, completion, prediction, or feedback delta |
| P1 mutable snapshot aliasing | Deep-copy rows/list/map; freeze representations | Mutate live inputs after observation and compare stored result/hash | Stored snapshot/result changes |
| P1 repeat classification | `_start_next` only plus unique packet-ID set | Multi-frame continuation test | Duplicate first-service record |
| P1 packet/effect counter confusion | Separate schemas/namespaces and reconciliation | Q4 typed counter tests | Effect count presented as packet count |
| P1 wire-byte denominator mismatch | Reuse item `JSON_WIRE_BYTES` | Compare with canonical emission/service item | Payload/RAW/served bytes used instead |
| P1 Supplement included | Channel guard before snapshot/classification | Supplement-start fixture | Supplement changes any scientific counter |
| P1 `matched_ids` treated as effect | Predicate reads only remap/confirmed task effects | Matched-only fixture | Matched membership makes packet applicable |
| P1 same-key supersession introduced | Same-target/live-source stays applicable; no time ordering input | Explicit Q3 fixture | Same key/time automatically removes effect |
| P2 logging/output coupling | Buffer separate records; isolate recorder failures; write after C4 sealing; no shared ledger fields | I/O failure and output isolation tests | Shadow I/O changes service or yields accepted incomplete result |
| P2 incomplete evidence sealing | Required start/end status and per-cell seal | Interrupted/failure fixtures | Summary produced from unsealed cell |
| P2 duplicate counting | Unique existing packet ID plus exact first-start cardinality | Q2/Q4 duplicate fixtures | Duplicate or missing checked record |

## 22. Staged future implementation sequence

No stage below is authorized by this draft.

### I1 — pure snapshot and predicate

- File: `src/tracking/mdmt_mia_async_deadline_runtime.py`.
- Delta: immutable snapshot/result representations and pure Contract-literal
  predicate; no runtime hook.
- Tests: all Q3 cases and input non-mutation.
- Stop: any Contract ambiguity, consumer mismatch, or need for new lifecycle,
  TTL, supersession, or Supplement semantics.

### I2 — event-local first-service hook

- File: runtime module only.
- Delta: explicit context arguments and one ID-State observer call in
  `_start_next` before byte decrement.
- Tests: Q2 same-frame, backlog, continuation, exhausted-budget cases.
- Stop: snapshot cannot be proven once-only or causally current.

### I3 — Shadow evidence sidecar

- File: runtime module only.
- Delta: in-memory detached records and separate finalize-time evidence/seal.
- Tests: output isolation, schema failure, duplicate, snapshot/predicate/recorder
  exception, missing context, unsupported view, and interrupted finalization;
  every Shadow failure preserves baseline service.
- Stop: evidence affects service/control flow or incomplete data is accepted.

### I4 — metric aggregation and runner

- File: new C5 runner plus its tests.
- Delta: approved counters/ratios, exact four-cell rendering, isolated output
  namespace, no C4 runner/evaluator modification.
- Tests: Q4 reconciliation, dry-run matrix, authority/input/output guards.
- Stop: any new cell/rate/metric/outcome-dependent selection appears.

### I5 — synthetic/mechanical qualification

- Files: two new C5 test modules; existing tests remain unchanged.
- Delta: complete Q1-Q4 suite and frozen regression invocation.
- Tests: Sections 16-19 plus existing C4 service/packet suites.
- Stop: any Q1-Q4 failure.

### I6 — trajectory-parity package

- Files: C5 runner/test support only unless separately reviewed.
- Delta: canonical projection comparator and pre-existing behavior manifests.
- Tests: Shadow-off/on exact equality with explicit exclusion allowlist.
- Stop: unknown/excluded pre-existing difference or missing counterpart.

### I7 — qualification seal

- Files: generated evidence only during a separately authorized qualification,
  not during implementation drafting.
- Delta: authority bindings, Q1-Q4 outcomes, changed-file inventory, and
  fail-closed readiness state.
- Stop: any incomplete or mismatched binding; no automatic execution.

## 23. Qualification and execution gates

Required future ordering:

```text
Implementation Plan draft
-> Independent Implementation Plan Review
-> corrective revision if required
-> approved Implementation Plan authority
-> explicit implementation authorization
-> implementation
-> independent delta audit
-> Q1-Q4 mechanical qualification
-> separate Shadow Census execution authorization
```

`IMPLEMENTATION_PLAN_DRAFTED != IMPLEMENTATION_AUTHORIZED`.

The four-cell scientific Census cannot start unless Q1-Q4 all pass and a
separate execution authorization binds the implementation, generated variant,
frozen cells, inputs, outputs, and seals.

## 24. No scientific drift and non-authorization

This Plan introduces no TTL, supersession, latest-wins rule, priority, EDF,
packet cancellation, drop policy, repacketization, effect-level service, new
`R`, cell, metric, threshold, significance test, generalization claim,
Supplement predicate, utility predictor, optimizer, ACK/feedback channel,
bandit, RL/MARL, or closed-loop decision.

If implementation convenience requires any such change:

```text
IMPLEMENTATION_PLAN_STATUS = BLOCKED_RESEARCH_DECISION_REQUIRED
RESEARCH_DECISION_REQUIRED = YES
```

No such conflict is present in this draft.

## 25. Team B corrective mapping

| Team B item | Revised section | Resolution |
| --- | --- | --- |
| `C5-PLAN-FAIL-01` | Sections 4, 16, 17, 21, 22 | Normative Shadow-only failure boundary continues baseline service and marks only Shadow evidence invalid/incomplete; injected failure parity is mandatory. |
| `C5-PLAN-Q3-02` | Section 18 | Q3 now targets the frozen audited `{remap_events, confirmed_ids}` projection, not whole receiver-state equality, and explicitly preserves matched-only opportunity semantics. |
| `C5-PLAN-COUNT-03` | Sections 8, 13, 19 | Approved scientific effect totals and subcounters include only effects evaluated after version-gate survival; rejected-payload content is optional integrity-only metadata. |
| `C5-PLAN-AUDIT-04` | Sections 6 and 12 | Every first-service record must persist a canonical minimal replay projection; digest-only evidence is forbidden. |

## 26. Plan status

```text
C5_IMPLEMENTATION_PLAN_DRAFT_STATUS = COMPLETE
PLAN_BASE_SHA = 1a664abdba12bc3e720ac3e728003e5ecd4ffa04
CONTRACT_AUTHORITY_VERIFIED = YES
CONTRACT_SHA256_VERIFIED = YES

TRUE_FIRST_SERVICE_HOOK_PLANNED = YES
EVENT_LOCAL_SNAPSHOT_PLANNED = YES
PURE_PREDICATE_PLANNED = YES
TRAJECTORY_PARITY_QUALIFICATION_PLANNED = YES
Q1_PLANNED = YES
Q2_PLANNED = YES
Q3_PLANNED = YES
Q4_PLANNED = YES

NEW_SCIENTIFIC_RULE_ADDED = NO
NEW_METRIC_ADDED = NO
NEW_THRESHOLD_ADDED = NO
NEW_CELL_ADDED = NO
SUPPLEMENT_SCOPE_EXPANDED = NO
CLOSED_LOOP_LOGIC_ADDED = NO

IMPLEMENTATION_BLOCKERS = NONE
RESEARCH_DECISION_REQUIRED = NO

SHADOW_FAILURE_SCOPE = C5_EVIDENCE_VALIDITY_ONLY
SHADOW_FAILURE_MUST_NOT_ABORT_BASELINE_SERVICE = YES
SHADOW_FAILURE_MUST_NOT_CHANGE_FIFO_TRAJECTORY = YES
SHADOW_FAILURE_MUST_NOT_DROP_SKIP_CANCEL_PACKET = YES

Q3_COMPARISON_TARGET = FROZEN_AUDITED_TASK_EFFECT_PROJECTION
WHOLE_RECEIVER_STATE_EQUIVALENCE_REQUIRED = NO

VERSION_REJECT_SCIENTIFIC_EFFECT_COUNTERS_EXCLUDE_REJECTED_PAYLOADS = YES
INDEPENDENT_PREDICATE_REPLAY = YES
DIGEST_ONLY_EVIDENCE_ALLOWED = NO

IMPLEMENTATION_AUTHORIZED = NO
SHADOW_EXECUTION_AUTHORIZED = NO
CLOSED_LOOP_INTERVENTION_AUTHORIZED = NO

NEXT_AUTHORIZED_STAGE =
INDEPENDENT_IMPLEMENTATION_PLAN_REVIEW
```
