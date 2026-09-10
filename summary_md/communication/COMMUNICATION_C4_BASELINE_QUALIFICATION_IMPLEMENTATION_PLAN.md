# Communication C4 Baseline Qualification Implementation Plan Candidate

```text
DOCUMENT_ROLE = C4_BASELINE_QUALIFICATION_IMPLEMENTATION_PLAN_CANDIDATE
CONTRACT_AUTHORITY = 24778f49ec9c913aadf95199343b12a75fd4078d
FROZEN_COMMUNICATION_BASE = cf5bc6f7acfc9cad39a393a985f56e788526dc2a
IMPLEMENTATION_AUTHORIZED_BY_THIS_PLAN = NO
DATASET_MVE_EXECUTION_AUTHORIZED = NO
GPU_EXECUTION_AUTHORIZED = NO
SEMANTIC_POLICY_AUTHORIZED = NO
```

## 1. Plan identity and authority

This document translates the final C4 Contract into an auditable, minimal
implementation delta. It does not authorize that delta, a dataset run, GPU
use, or any semantic scheduling policy. The sole scientific/governance
authority is commit
`24778f49ec9c913aadf95199343b12a75fd4078d`, specifically:

- `summary_md/communication/COMMUNICATION_C4_BASELINE_QUALIFICATION_MVE_CONTRACT.md`;
- `summary_md/communication/COMMUNICATION_C4_U1_U2_WORKLOAD_DERIVATION.md`.

Read-only preflight established that the authority is a commit, U1--U4 are
frozen, U5--U6 remain unresolved, and both implementation and dataset-level
MVE execution remain unauthorized. Team B's unavailable independent raw
Census hash check is not reopened as a Contract question. It is a mandatory
pre-execution gate in Section 16.

The plan preserves C1--C4, P1--P3, and U1--U4 exactly. Engineering names below
that do not yet exist are explicitly marked **proposed**; they are not claims
about current repository symbols.

## 2. Current implementation map

The following map comes from inspection of the authoritative tree rather than
from inferred filenames.

| File | Existing symbol or entry | Current responsibility | Future C4 responsibility |
| --- | --- | --- | --- |
| `src/tracking/mdmt_mia_async_deadline_runtime.py` | `PacketRuntime` | Canonical JSON-wire transport, fixed-delay queues, channel-specific arrival consequences, runtime trace, and finalization | Remain the producer/consumer boundary; host a config-disabled shared logical-service path for only `id_state` and `supplement` |
| same | `_wire()` | Builds the canonical packet envelope; uses sorted compact JSON, round-trips it, computes `wire_digest`, and calls Census emission | Remain the single source of packet representation and `JSON_WIRE_BYTES`; expose the already computed encoded byte length to service admission without changing the wire |
| same | `_send()` | Calls `_wire()`; delivers zero-delay packets immediately or pushes delayed packets into per-channel heaps using `_queue_sequence` | Route Local/H through the current timely path; route ID/Supp through the proposed shared server only when C4 service mode is enabled; retain legacy fixed-delay behavior when disabled |
| same | `_drain()` | Deterministically drains fixed-delay arrival heaps by `(arrival_frame, _queue_sequence)` | Remain the exogenous fixed-delay drain; do not reuse it as the finite-service scheduler |
| same | `begin_frame()` | Sets `_current_frame`, drains Local/H/Supp arrivals, expires late Local/Supp, and invokes `_apply_pending_id()` | Open/replenish one frame's C4 service budget before draining newly completed service packets; preserve the current semantic consequence handlers |
| same | `deliver_local_track()` | Packetizes Local Track while returning the local UAV's own current state; readiness is gated separately | Timely bypass; never admitted to the constrained server |
| same | `deliver_homography()` and `seed_homography()` | Packetizes H, returns timely H or newest arrived/seeded H | Timely bypass in Unlimited/FIFO; existing delayed behavior only for the separate fixed-delay bridge |
| same | `deliver_id_state()` | Producer and immediate consumer boundary for ID-state updates; delayed calls return pre-stage state | Preserve packetization and return contract; consume same-frame completions immediately and later completions through `_apply_pending_id()` |
| same | `_apply_pending_id()` | Applies arrived remap events to future live rows with version, conflict, and obsolete checks | Remain the ID-state semantic consumer for completed packets; service logic must not alter version dominance |
| same | `deliver_supplement()` | Producer and immediate consumer boundary; late Supplement returns pre-stage state and empty supplement arrays | Preserve the current frame-scoped consumer; a packet not fully available in its opportunity becomes an auditable expired consequence |
| same | `commit_fused_state_to_tracker()` | Commits decoded fused state to the unchanged tracker feedback interface | No C4 change |
| same | `_PacketCensusSidecar.emission()` | Assigns the stable four-field Census `packet_id`; records `JSON_WIRE_BYTES`, diagnostic `SEMANTIC_ARRAY_RAW_BYTES`, routing, and content counts | Reuse packet identity and size authority; do not put service metadata into the canonical wire |
| same | `_PacketCensusSidecar.terminal()` / `finalize()` and `validate_packet_census_records()` | Records exactly-one packet terminals and validates emission/terminal/finalization conservation | Preserve Census semantics; link, rather than duplicate, C4 service evidence by `packet_id` |
| `scripts/prepare_mdmt_mia_async_packet_variant.py` | `patch_variant()` | Copies the authoritative runtime into `demo/utils/async_deadline_runtime.py` and injects `PacketRuntime` calls into the generated `demo/supplement_MIA.py` | Reuse unchanged if the reviewed implementation stays within the current runtime API; its structural assertions remain an installation gate |
| same | injected calls to `begin_frame()`, `deliver_local_track()`, `deliver_homography()`, `deliver_id_state()`, `deliver_supplement()`, `commit_fused_state_to_tracker()`, `finalize()` | Actual producer and consumer hooks in the generated author entry | Keep call order and tracker/H/detector boundaries unchanged |
| `scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py` | `delay_map()` and `condition_matrix()` | Existing Y00/Y10/Y01/Y11 fixed-delay rendering; `Y10_dN` means ID delay N and timely Supplement, `Y11_dN` delays both | Read-only implementation reference for exact `Y10_d1`/`Y11_d1`; do not import its oracle `Yec`, bootstrap, or wider matrix into C4 |
| same | `run_author()` / `run_conditions()` | One-pair author invocation with isolated attempts, cache mode, manifests, and recovery | Reuse its attempt-governance patterns in a proposed C4-only runner, not its scientific matrix |
| `scripts/run_mdmt_mia_author_sync.sh` | shell entry | Runs one `mia` pair through the generated author source; binds dataset, input, config, checkpoint, device, and output roots | Remain the runtime command beneath a future C4-only orchestrator |
| `scripts/evaluate_mdmt_mia_paper_alignment.py` | `main()` | Evaluates completed author JSON through existing MDA and MOT metrics and renders pair/view outputs | Reuse unchanged for MDA primary, IDSW secondary, and descriptive existing metrics |
| `src/evaluation/mdmt_mia_paper.py` | `cross_view_mda()`, `motmetrics_summary()`, `macro_average()` | Frozen evaluator definitions | No metric-definition change |
| `tests/test_mdmt_mia_async_deadline_runtime.py` | existing PacketRuntime tests | Fixed-delay consumer behavior, wire/Census isolation, finalization, and patcher checks | Existing regression suite; no semantic rewrites |
| `tests/test_packet_census_step3_revalidation.py` | existing lifecycle and validator tests | Positive/negative terminal conservation, instrumentation non-interference, and pending-at-end evidence | Existing regression and evidence-conservation suite |
| `tests/test_mdmt_mia_packet_interface.py` and `tests/test_mdmt_mia_active_packet_runtime.py` | existing interface/equivalence tests | Earlier packet interface and active transport compatibility | Regression-only coverage |

Current canonical serialization is exactly `PacketRuntime._wire()`:
`json.dumps(_json_safe(wire), sort_keys=True, separators=(",", ":"))`, then
`len(encoded.encode("utf-8"))` in `_PacketCensusSidecar.emission()`. C4 must
not reserialize payloads to determine service cost.

The current fixed-delay path is `_parse_delays()` -> `PacketRuntime.delays` ->
`_wire().arrival_frame` -> `_send()` per-channel heap -> `_drain()` at
`begin_frame()`. It is complete enough for U3 and is deliberately not the C4
finite FIFO implementation.

The current one-pair runtime command is
`bash scripts/run_mdmt_mia_author_sync.sh mia test <pair-id>`, with
`MIA_SOURCE_ROOT` selecting the generated async source and the environment
fields above selecting delay, output, input, cache, and device behavior.

```text
CURRENT_IMPLEMENTATION_MAP = COMPLETE
NEEDS_IMPLEMENTATION_DISCOVERY = NONE_AT_PLAN_LEVEL
```

## 3. Minimal implementation delta

### Recommended path

Add one small, deterministic service-state object inside
`src/tracking/mdmt_mia_async_deadline_runtime.py` and integrate it only at
`PacketRuntime._send()`, `PacketRuntime.begin_frame()`, and
`PacketRuntime.finalize()`. The proposed internal symbol is
`_C4SharedLogicalServer`; the exact name is an engineering detail, not a
scientific authority.

The service object owns no tracker, H, detector, evaluator, expiry, or version
logic. It receives the already canonicalized `(wire, encoded, wire_digest,
census_emission)` packet reference, its existing stable emission identity, and
`len(encoded.encode("utf-8"))`. It returns only fully completed packet
references. `PacketRuntime` continues to decide how a completed ID State or
Supplement affects the existing semantic consumer.

Configuration should be fail-closed and explicit, for example one proposed
JSON environment field `MIA_C4_SERVICE_CONFIG`, validated once in
`PacketRuntime.__init__()`:

```text
disabled / absent -> current legacy fixed-delay runtime, byte-for-byte where practical
{"mode":"unlimited"} -> shared interface, immediate complete service
{"mode":"fifo","rate_logical_bytes_per_frame":16649|26148|31987}
```

The implementation must reject unknown modes, rates outside the frozen set in
C4 qualification mode, finite mode combined with nonzero ID/Supp exogenous
delays, or attempts to admit Local/H. It must not interpret Unlimited as an
integer rate.

### Alternatives considered

- A separate replacement runtime file would isolate code physically but would
  duplicate canonical wire/Census/consumer logic and raise parity risk.
- Recasting `_queues` and `_drain()` as byte service would conflate exogenous
  fixed delay with endogenous FIFO and risk U3 regression.

The recommended additive object inside the existing runtime gives the smallest
semantic surface: packet producers, wire representation, consumer methods,
patcher hooks, tracker, H estimator, and evaluator remain unchanged.

## 4. Proposed runtime data flow

```text
ID State producer -------\
                          +-> PacketRuntime._wire()
Supplement producer -----/        |
                                  v
                         shared service admission
                                  |
                         deterministic FIFO queue
                                  |
                           in-service packet
                                  |
                    work-conserving frame service
                                  |
                    full completion only (atomic)
                                  |
             same-frame availability when completed at t
                                  |
          existing ID/Supplement semantic consumer boundary

Local Track producer -> PacketRuntime._wire/_send timely bypass -> existing consumer
Homography producer  -> PacketRuntime._wire/_send timely bypass -> existing consumer

Y10_d1 / Y11_d1 -> existing fixed-delay arrival heaps -> existing consumer
                  (separate exogenous mechanism bridge; not FIFO)
```

For finite or Unlimited C4 modes, Local Track and Homography must have zero
configured exogenous delay and remain outside service admission. For bridge
mode, C4 service is disabled and the existing delay map renders exactly
`Y10_d1={local:0, homography:0, id_state:1, supplement:0}` or
`Y11_d1={local:0, homography:0, id_state:1, supplement:1}`.

## 5. Server state model

The proposed minimal state follows current underscore-prefixed runtime style:

```text
_queue                         FIFO packet references not yet in service
_in_service                    zero or one non-preemptive packet reference
_remaining_service_bytes      integer bytes for _in_service
_current_frame                 most recently opened frame
_frame_service_budget         unconsumed bytes for the current frame
_packet_sequence              mechanical monotonic admission sequence
_completed                     completed packet references awaiting consumer drain
```

The service-state object must not inspect payload semantics beyond an admission
assertion that `channel in {id_state, supplement}`.

Mechanical transitions:

1. `enqueue`: require emission/enqueue frame `t` not earlier than packet
   emission; append `(enqueue_frame, packet_sequence, packet_ref, cost)`.
2. `start_service`: if no packet is in service and FIFO is nonempty, pop its
   head, set remaining bytes to the exact JSON wire cost, and record the start
   frame. Zero-byte packets, if canonical encoding ever permits one, complete
   atomically without negative accounting.
3. `consume_bytes`: subtract `min(frame_budget, remaining)` and record the
   exact service slice; never serve a later packet while remaining is positive.
4. `complete`: when remaining becomes zero, seal completion frame, move the
   whole packet reference to `_completed`, clear `_in_service`, and continue in
   the same frame if budget and FIFO work remain.
5. `make_available`: `PacketRuntime` drains only complete references into the
   unchanged ID/Supp consumer logic. No payload fragment is visible.
6. `carry_to_next_frame`: retain `_in_service` and positive remaining bytes;
   `begin_frame(t+1)` replenishes budget without reordering or preemption.

Required ordering constraints are: no service before enqueue, no completion
before service start, no availability before completion, no partial delivery,
and no preemption.

## 6. FIFO and deterministic tie-break

Reuse the existing monotonic emission order. `_PacketCensusSidecar.emission()`
already assigns a one-based `emission_ordinal` within a runtime instance, and
`PacketRuntime` already advances `_packet_version` and `_queue_sequence`
deterministically. The implementation should use a single monotonic admission
sequence issued immediately after `_wire()` and record its link to the Census
`packet_id` when Census is enabled. It must not depend on whether Census is
enabled.

FIFO order is `(enqueue_frame, packet_sequence)`. When multiple ID/Supp packets
are emitted during the same frame, their existing producer call order is the
tie-break. No channel rank is allowed.

```text
SEMANTIC_PRIORITY = NO
TIE_BREAK_INPUTS = ENQUEUE_FRAME_PLUS_STABLE_EMISSION_SEQUENCE_ONLY
FORBIDDEN_ORDER_INPUTS = CHANNEL_IMPORTANCE,AGE,EXPIRY,VERSION,MDA,TRACKING_STATE
```

## 7. Unlimited implementation plan

Unlimited enters through `_wire()` and the same shared-service admission call
as FIFO. The service object completes each eligible packet at its enqueue frame
without creating backlog or consuming a numeric `R`. It emits the same
completion event and returns through the same delivery/consumer boundary.

Unlimited parity must be verified mechanically against service-disabled
original timely behavior:

- identical canonical wire digest and ordered packet identities;
- identical availability frame to emission frame;
- identical decoded values at `deliver_id_state()` and
  `deliver_supplement()` return boundaries;
- identical tracker-feedback digest and author prediction JSON digest;
- zero queue-induced waiting, backlog, and completion delay;
- unchanged MDA/IDSW and all existing evaluator outputs where parity is tested.

At T0/T1 this comparator is an exact synthetic duplicate. At dataset level,
the execution material must freeze whether the comparator is a fresh
audit-only service-disabled run or an independently verified compatible timely
artifact. That choice changes only parity evidence production, not the six
scientific conditions. It is
`NEEDS_IMPLEMENTATION_RENDERING_DECISION` before execution authorization.

Forbidden implementation:

```text
if unlimited: bypass PacketRuntime or call the semantic consumer directly
```

Unlimited bypasses the bottleneck, not the communication abstraction.

## 8. Finite FIFO implementation plan

The only finite rates are global across all three pairs:

```text
R_STRONG = 16649 logical bytes/frame
R_MODERATE = 26148 logical bytes/frame
R_MILD = 31987 logical bytes/frame
PAIR_NORMALIZED_R = NO
POST_HOC_R_TUNING = FORBIDDEN
```

For each opened frame `t`, set the budget to exactly `R` and execute:

```text
while frame_budget > 0 and (_in_service exists or FIFO is nonempty):
    if no _in_service: start FIFO head
    served = min(frame_budget, remaining_service_bytes)
    record service slice; subtract served from both counters
    if remaining_service_bytes == 0:
        complete atomically at t; make packet available at t
        continue immediately with the next FIFO packet
```

Edge handling:

- `packet size > R`: serve across frames; retain the same in-service packet.
- completion mid-frame: spend the residual budget on the next FIFO packet.
- multiple completions: allow any number that fit in the same frame budget.
- empty queue: unused budget is legal and recorded; no synthetic work.
- packet enqueued after earlier service in frame: it may consume the remaining
  budget in that same frame, but never budget already consumed.
- final source frame with pending work: do not synthesize extra scientific
  frames. Finalize every incomplete packet as `PENDING_AT_END` with exact
  remaining bytes and reconcile it; execution materials may separately decide
  whether a non-consumer drain phase is needed for an audit, but cannot turn it
  into tracking availability.
- terminal accounting: every emitted constrained packet has exactly one
  terminal disposition even when it never completes.

Non-preemption applies across channel boundaries: an in-service ID packet is
not displaced by a Supplement packet or vice versa.

## 9. Event-time semantics

Reuse `capture_frame`/`emitted_frame` as the existing emission time and add
service fields only to out-of-band evidence:

```text
emission_frame             existing emitted_frame
enqueue_frame              frame admitted to shared service
service_start_frame        first positive service (or atomic zero-cost start)
service_completion_frame   frame remaining bytes reaches zero
availability_frame         frame full packet reaches existing consumer boundary
```

An ID/Supp packet emitted at frame `t` is enqueued before `_send()` returns and
is eligible to consume the remaining budget of `t`. If it completes at `t`,
both completion and availability are `t`, and the current producer call may
return the decoded packet under the original causal ordering. No internal
`t+1` handoff is allowed.

Packets completed at the start of a later `begin_frame()` become available in
that same later frame before the existing cross-view stages consume their
state. For Supplement, availability after its frame-scoped opportunity is
recorded as expired and cannot mutate state. Completion and semantic acceptance
are therefore distinct audited facts.

## 10. Service ledger and evidence schema

Add a condition-specific append-only service/event ledger, proposed filename
`c4_service_ledger_<sequence_name>.jsonl`, plus a small final summary. It must
reference the canonical packet; it must not repeat the full payload.

Required packet/event fields:

```text
run_id, condition, pair_id, runtime_instance_id
packet_id, wire_digest, channel
JSON_WIRE_BYTES
SEMANTIC_ARRAY_RAW_BYTES                 # diagnostic only
emission_frame, enqueue_frame
service_start_frame, service_completion_frame, availability_frame
packet_sequence
bytes_offered, bytes_served, remaining_service_bytes
frame_service_budget, frame_unused_budget
queue_length, queue_backlog_bytes
waiting_delay, service_duration, completion_delay
id_state_age_frames / id_state_terminal_consequence
supplement_terminal_consequence          # timely or expired
terminal_disposition, terminal_reason
```

Use event rows for enqueue, service slices, completion/availability, and
terminal disposition, with a packet-summary row or final summary to avoid
repeating invariant fields on every service slice. `packet_id`/`wire_digest`
link to Census and canonical payload authority. Local/H bypass events may be
small proof rows but must never appear as shared-server admissions.

The ledger writer must be deterministic, append-only during an attempt, and
closed by a finalization record after pending terminals are written. Service
ledger metadata remains out of `_wire()` so primary packet size cannot change
because observability is enabled.

Dataset-level C4 evidence mode must require the existing Census sidecar to be
enabled so every ledger packet reference resolves to its authoritative
four-field `packet_id`. Synthetic tests may use the deterministic local
`packet_sequence` without Census. An evidence-write failure must mark the
attempt invalid and block result use while leaving the consumer execution path
non-interfering; it must never be hidden as a successful qualification.

## 11. Conservation and invariants

Future tests and audits must prove:

1. **Logical-byte conservation:** for every constrained packet,
   `JSON_WIRE_BYTES = sum(bytes_served) + remaining_at_terminal`; no negative
   fields and no service slice exceeds the frame's residual budget.
2. **Per-frame budget conservation:**
   `R = sum(bytes_served_in_frame) + unused_budget`, with unused budget allowed
   only when no eligible queued/in-service work exists at that instant.
3. **Terminal-state conservation:** emitted constrained packets partition into
   completed-delivered, completed-expired/rejected, and pending-at-end.
4. **Exactly one terminal disposition:** no orphan emission, phantom terminal,
   duplicate terminal, or terminal identity mismatch.
5. **Queue reconciliation:** prior queue + enqueues - service starts equals
   ending queue membership; every member is unique.
6. **In-service reconciliation:** zero or one packet; its served plus remaining
   bytes equals its cost, and it never re-enters the queue.
7. **Completion/delivery reconciliation:** availability requires completion;
   each completion is delivered/expired/rejected exactly once.
8. **Pending-at-end reconciliation:** every incomplete packet records its
   queue/in-service location and remaining bytes before finalization.
9. **Causality/atomicity:** no future read, partial semantic delivery,
   completion-before-start, availability-before-completion, or preemption.
10. **Deterministic replay:** identical authority, config, synthetic inputs,
    and seed yield identical normalized ledgers and consumer-visible digests;
    nondeterministic attempt UUID/timestamps are excluded only by an explicit
    normalization rule.

These checks must be emitted per frame, aggregated per pair, and reconciled at
the whole-run level. A run-level equality without packet/frame reconciliation
is insufficient.

## 12. U1/U2 configuration rendering

The future C4-only runner must accept only:

```text
pair = 23 | 44 | 66
condition = Unlimited | FIFO_mild | FIFO_moderate | FIFO_strong | Y10_d1 | Y11_d1
```

Rendering table:

| Condition | C4 service mode | R | Existing fixed-delay map |
| --- | --- | ---: | --- |
| `Unlimited` | unlimited, same shared interface | none | all zero |
| `FIFO_mild` | finite FIFO | 31987 | all zero |
| `FIFO_moderate` | finite FIFO | 26148 | all zero |
| `FIFO_strong` | finite FIFO | 16649 | all zero |
| `Y10_d1` | disabled | none | Local 0, H 0, ID State 1, Supplement 0 |
| `Y11_d1` | disabled | none | Local 0, H 0, ID State 1, Supplement 1 |

The current one-pair author runner makes six conditions x three pairs = 18
mechanically implied scientific pair-condition executions. It does not imply
an order-dependent cache seed, parity duplicate, or deterministic-repeat
count. Those audit-only renderings must be frozen in execution material after
implementation audit and must not add a pair, R, delay, or scientific
condition.

The proposed dedicated orchestrator must reject pair-normalized rates,
unrecognized conditions, additional pairs, and resume checkpoints whose full
authority/config fingerprint differs.

## 13. U3 bridge implementation

Reuse the existing exogenous implementation in
`mdmt_mia_async_deadline_runtime.py`: `_parse_delays()`, `_wire()` arrival
calculation, `_send()` arrival heaps, `_drain()`, and the channel-specific
handlers in `begin_frame()`. Reuse the exact mapping already encoded by
`phase3_mdmt_mia_id_supplement_cascade_audit.py::delay_map()` and
`condition_matrix()` only as a read-only reference for `Y10_d1` and `Y11_d1`.

Do not call the finite service object for these conditions. Do not convert one
frame into bytes, match FIFO delays numerically, or label the bridge as a
scheduler. The C4-only runner should render only the two frozen bridge maps,
while sharing the same producer, consumer, detector/tracker environment,
author wrapper, and evaluator wherever their roles permit.

## 14. U4 tracking diagnostics

Reuse `scripts/evaluate_mdmt_mia_paper_alignment.py` and
`src/evaluation/mdmt_mia_paper.py` unchanged.

```text
PRIMARY_TRACKING_DIAGNOSTIC = MDA
PRIMARY_CONTRAST = FIFO_AT_EACH_FINITE_R_VS_UNLIMITED_WITHIN_SAME_PAIR
SECONDARY_TRACKING_DIAGNOSTIC = IDSW
OTHER_EXISTING_METRICS = DESCRIPTIVE_ONLY
SIGNIFICANCE_TEST = NO
POST_HOC_METRIC_PROMOTION = FORBIDDEN
```

The future report should have one row per pair and finite rate containing MDA
and IDSW for FIFO, Unlimited, and the within-pair difference. Existing MOTA,
IDF1, and other evaluator fields may be shown descriptively. Cross-pair
summaries are descriptive only. `Y10_d1`/`Y11_d1` comparisons are directional
mechanism context, not numeric FIFO matches. Tracking degradation is not a
qualification correctness gate.

## 15. Test strategy

No test is created or executed by this plan.

### T0 — pure unit tests, no dataset

Add a proposed isolated test file
`tests/test_mdmt_mia_c4_service_runtime.py` for the proposed internal service
object. Cover work-conserving continuation, a packet larger than R, same-frame
completion/availability metadata, multiple completions, empty queue and unused
budget, mid-frame enqueue, FIFO ordering, equal-enqueue stable tie-break,
atomic delivery, non-preemption, final pending state, byte conservation, and
deterministic normalized replay.

### T1 — synthetic PacketRuntime integration

Using synthetic NumPy packets and a fake/observed consumer boundary, cover:

- Local/H zero-delay bypass and absence from service admissions;
- ID/Supp sharing one queue;
- exact Unlimited versus service-disabled parity;
- finite FIFO same-frame and cross-frame timings;
- `_apply_pending_id()` age/obsolete consequences without changing its rules;
- timely versus expired Supplement consequences;
- ledger linkage, terminal uniqueness, and instrumentation-on/off
  non-interference.

### T2 — existing regression and non-interference

Run the existing suites for
`tests/test_mdmt_mia_async_deadline_runtime.py`,
`tests/test_packet_census_step3_revalidation.py`,
`tests/test_mdmt_mia_packet_interface.py`, and
`tests/test_mdmt_mia_active_packet_runtime.py`. Add static assertions that the
patcher still installs the intended runtime/calls and that canonical encoded
wire bytes and fixed-delay Y10/Y11 mappings have not drifted. No detector,
tracker, evaluator, dataset, or GPU is needed.

### T3 — dataset-level C4 MVE

```text
T3_STATUS = NOT_AUTHORIZED_BY_THIS_PLAN
```

T3 may begin only after all gates in Section 16 and a separate explicit MVE
Execution Authorization pass.

## 16. Dataset-MVE pre-execution gates

All gates are conjunctive:

| Gate | Requirement |
| --- | --- |
| G1 | Contract authority equals `24778f49ec9c913aadf95199343b12a75fd4078d` |
| G2 | This Implementation Plan receives Team B PASS at its immutable SHA |
| G3 | Implemented delta audit passes and matches its frozen authority |
| G4 | T0/T1/T2 unit, synthetic, and regression qualification passes |
| G5 | Recompute SHA-256 from the authoritative filesystem copy of `PACKET_CENSUS_PACKET_AUDIT.jsonl` |
| G6 | Recomputed SHA-256 exactly equals `ab2440e1776cdd30ba8f793bc5da713580343ac342db29e153653cdf1bc2421a` |
| G7 | Locked-d1 Train Holdout completion is confirmed without inspecting its scientific outcome for C4 design |
| G8 | Holdout/Val scientific outcomes were not used for C4 design, rendering, rates, or gates |
| G9 | Dedicated communication implementation/execution worktree is verified |
| G10 | Dedicated communication output root is empty/new or authority-compatible |
| G11 | Dedicated writable communication cache root is verified |
| G12 | No output/cache symlink resolves into any Holdout output or cache |
| G13 | No shared environment mutation; environment and dependency identity are frozen |
| G14 | If and only if later GPU use is authorized, GPU ownership and `CUDA_VISIBLE_DEVICES`/device mapping are verified |
| G15 | Projected storage, free-space, inode, and output-growth preflight passes |
| G16 | Separate explicit C4 MVE Execution Authorization names exact implementation SHA, command, roots, and matrix |

```text
IF_ANY_G1_TO_G16_FAIL = DATASET_MVE_EXECUTION_BLOCKED
CENSUS_SHA_LIMITATION_BLOCKS_PLAN = NO
CENSUS_SHA_LIMITATION_BLOCKS_IMPLEMENTATION = NO
CENSUS_SHA_LIMITATION_BLOCKS_DATASET_MVE_IF_UNVERIFIED = YES
```

## 17. Storage implementation plan

Prefer one canonical packet payload and references from the service ledger.
Write condition-specific event/service ledgers and compact summaries; do not
write full queue snapshots by default. Do not duplicate input images,
embeddings, detector tensors/caches, or packet payloads across conditions.
Detector cache reuse, if later authorized, must be read-only from a dedicated
communication cache authority and never from Holdout storage.

Before T3, compute projected storage from verified inputs rather than freezing
an arbitrary GB threshold:

1. after G5/G6, count constrained packet emissions and sum wire bytes for pairs
   23/44/66 from the authoritative Census;
2. use T0/T1 serialized ledger records to measure bytes per enqueue, service
   slice, terminal, and summary row;
3. bound service-slice rows for each frozen R from exact packet sizes and
   frame service mechanics, then calculate all 18 scientific cells plus any
   separately approved audit-only parity/replay artifacts;
4. add measured prediction, log, manifest, checkpoint, and cache footprints
   from an authority-compatible non-Holdout dry preflight, without reading
   scientific outcomes;
5. compare projected bytes/inodes and safety margin with the dedicated
   filesystem's current free capacity; anomalous or insufficient capacity
   blocks execution and requires an explicit disposition, not silent pruning.

Failed attempts use four tiers:

- **Tier 0 permanent governance:** run/attempt identity, Git/config/input
  authority, command/runtime identity, pair/condition/seed, time, exit code,
  status, failure class, and disposition record.
- **Tier 1 permanent minimum forensic:** failure report, bounded relevant
  stderr/stack trace, manifest, required hashes, and relevant ledger excerpt or
  summary.
- **Tier 2 quarantine until audited:** large debug traces, partial
  non-authoritative outputs, and temporary intermediates.
- **Tier 3 regenerable/redundant heavy:** full queue dumps, duplicated packet
  payloads, images, embeddings, tensors, and caches; do not generate by
  default.

Tier 2/3 material may be compacted, archived, or deleted only after failure
audit and sealing of the permanent minimum package, with a sealed disposition
record naming what changed, why, the policy, time, and authority. Automatic
`rm -rf` on failure, silent overwrite, silent erasure, relabeling, or removal
of an attempt from history is forbidden. No absolute retention duration or GB
threshold is frozen here.

## 18. Output, cache, and worktree isolation

Future implementation and execution require three distinct dedicated roots:

```text
IMPLEMENTATION_WORKTREE = TO_BE_FROZEN_IN_IMPLEMENTATION_AUTHORIZATION
MVE_OUTPUT_ROOT = TO_BE_FROZEN_IN_EXECUTION_MATERIAL
MVE_WRITABLE_CACHE_ROOT = TO_BE_FROZEN_IN_EXECUTION_MATERIAL
```

They must be resolved to canonical absolute paths and checked against every
Holdout worktree/output/cache root. No symlink or bind path may point into
Holdout storage. The runner must refuse an incompatible existing run manifest,
write each attempt below an immutable attempt directory, and promote only an
audited complete attempt without overwriting earlier attempts.

Environment variables must be explicit in the run manifest, including source,
dataset, input, output, cache, service condition, delays, device, and Python
isolation. No environment package mutation is allowed.

## 19. No hidden scientific decisions

Engineering may choose internal class placement, immutable packet-reference
representation, exact validated config encoding, append-only JSONL layout,
test fixtures, and purely mechanical sequence fields. It may not choose a new
pair, R, delay, metric, statistical test, semantic freshness definition,
semantic priority, scheduler weight, EDF/Random/Round Robin/RL/MARL policy,
PHY/SINR/Mbps model, or all-four-channel constrained server.

If implementation reveals that a required behavior cannot be achieved without
changing C1--C4 or U1--U4, record:

```text
NEEDS_RESEARCH_DECISION
```

and stop that implementation path. Do not silently repair the Contract in
code.

## 20. Exact proposed implementation change list

This is a proposed delta, not authorization to edit.

| File | Symbol | Change type | Purpose | Scientific logic changed? |
| --- | --- | --- | --- | --- |
| `src/tracking/mdmt_mia_async_deadline_runtime.py` | **proposed** `_C4SharedLogicalServer` | ADD internal class | Deterministic Unlimited/finite shared service state and service ledger events | NO |
| same | existing `PacketRuntime.__init__()` | MODIFY | Validate config and construct disabled/Unlimited/FIFO service state | NO |
| same | existing `PacketRuntime._wire()` | MINIMAL MODIFY or return plumbing only | Pass already encoded byte length/packet reference to admission without changing encoding | NO |
| same | existing `PacketRuntime._send()` | MODIFY | Timely-bypass Local/H; admit ID/Supp to shared service when enabled; retain fixed-delay path when disabled | NO |
| same | existing `PacketRuntime.begin_frame()` | MODIFY | Replenish and consume the frame budget before existing completed-packet consequence drains | NO |
| same | existing `PacketRuntime.finalize()` | MODIFY | Seal pending service dispositions and reconciled service summary before finalization | NO |
| `tests/test_mdmt_mia_c4_service_runtime.py` | **proposed** pure/integration tests | ADD | T0/T1 C4 mechanics and parity | NO |
| `tests/test_mdmt_mia_async_deadline_runtime.py` | existing regression module | MINIMAL ADD if needed | Assert legacy fixed-delay and interface non-regression | NO |
| `tests/test_packet_census_step3_revalidation.py` | existing conservation module | MINIMAL ADD if needed | Assert Census/service linkage and terminal conservation | NO |
| `scripts/run_mdmt_mia_c4_baseline_qualification.py` | **proposed** exact C4 orchestrator | ADD after separate authorization | Render only frozen pairs/conditions, attempts, fingerprints, storage checks, evidence, and evaluator call | NO |

`scripts/prepare_mdmt_mia_async_packet_variant.py` should remain unchanged if
its existing runtime-source copy and hook assertions accept the reviewed
runtime delta. Modify it only if an implementation audit proves a mechanical
installation change is unavoidable; that contingency is
`NEEDS_IMPLEMENTATION_DISCOVERY`, not pre-authorized expansion.

Files and authorities explicitly frozen / not to change:

- `summary_md/communication/COMMUNICATION_C4_BASELINE_QUALIFICATION_MVE_CONTRACT.md`;
- `summary_md/communication/COMMUNICATION_C4_U1_U2_WORKLOAD_DERIVATION.md`;
- `src/evaluation/mdmt_mia_paper.py` metric definitions;
- `scripts/evaluate_mdmt_mia_paper_alignment.py` evaluator definitions;
- detector implementation and checkpoint;
- tracker core and association thresholds;
- Homography estimator/helpers;
- GT, XML, image, annotation, split, and pair authority;
- frozen Census artifacts and hashes;
- locked-d1 Holdout worktree, output, cache, environment, and all Holdout/Val
  scientific outcomes.

## 21. Rollback and failure strategy

The service layer is additive and disabled when its config is absent. The old
timely and fixed-delay behaviors remain directly regression-testable. A failed
implementation attempt must live on its isolated branch/worktree, must not
change Contract authority, and must preserve its immutable attempt evidence.
Rollback means selecting the last audited commit/config-disabled path or
reverting through a new history-preserving commit; it never means deleting or
rewriting authoritative history. Force push, rebase of authoritative history,
and silent attempt replacement are forbidden.

Runtime/config validation must fail closed before execution on invalid
mode/rate/channel admission or mixed endogenous/exogenous ID/Supp timing.
Conservation failure, evidence I/O failure, nondeterminism, or parity failure
must invalidate the attempt and block result use without changing semantic
runtime flow merely because instrumentation is enabled. Failure must not be
rescued by tracking outcomes.

## 22. Plan-level definition of done

```text
IMPLEMENTATION_PLAN_DONE means:
- actual code insertion points identified
- minimal file/symbol delta defined
- server algorithm fully specified
- Unlimited/FIFO semantics renderable
- event-time and evidence schema specified
- conservation and test plan specified
- storage/worktree/output/cache isolation specified
- dataset pre-execution gates specified

IMPLEMENTATION_DONE = NO
MVE_EXECUTED = NO
EXECUTION_AUTHORIZATION_CREATED = NO
```

This candidate stops at planning. Team B must independently audit its immutable
commit before any implementation authority can be issued.

## 23. Plan self-audit record

```text
FINAL_CONTRACT_AUTHORITY_MATCH = YES
ACTUAL_REPO_SYMBOLS_INSPECTED = YES
INVENTED_NONEXISTENT_RUNTIME_SYMBOL = NO

C1_CHANGED = NO
C2_CHANGED = NO
C3_CHANGED = NO
C4_CHANGED = NO
U1_CHANGED = NO
U2_CHANGED = NO
U3_CHANGED = NO
U4_CHANGED = NO
U5_RESOLVED = NO
U6_RESOLVED = NO

WORK_CONSERVING_PRESERVED = YES
SAME_FRAME_SEMANTICS_PRESERVED = YES
UNLIMITED_SAME_INTERFACE_PRESERVED = YES
LOCAL_H_BYPASS_PRESERVED = YES
ID_SUPPLEMENT_SHARED_SERVER_PRESERVED = YES

PAIR_23_44_66_PRESERVED = YES
R_16649_26148_31987_PRESERVED = YES
Y10_Y11_BRIDGE_PRESERVED = YES
MDA_IDSW_HIERARCHY_PRESERVED = YES

CENSUS_SHA_PREFLIGHT_GATE_INCLUDED = YES
HOLDOUT_COMPLETION_GATE_INCLUDED = YES
STORAGE_GOVERNANCE_INCLUDED = YES

IMPLEMENTATION_STARTED = NO
RUNTIME_FILE_CHANGED = NO
TEST_FILE_CHANGED = NO
SCRIPT_CHANGED = NO
TRACKER_EXECUTED = NO
EVALUATOR_EXECUTED = NO
DATASET_MVE_EXECUTED = NO
GPU_JOB_STARTED = NO
HOLDOUT_OUTCOME_READ = NO
VAL_OUTCOME_READ = NO
ONLY_IMPLEMENTATION_PLAN_FILE_CHANGED = YES
```
