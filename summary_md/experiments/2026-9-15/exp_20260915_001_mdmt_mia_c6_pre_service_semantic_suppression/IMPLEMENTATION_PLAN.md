# C6 TRUE-First-Service ID-State Semantic Suppression — Implementation Plan

**Status:** `PLAN ONLY — NOT AUTHORIZED FOR IMPLEMENTATION, QUALIFICATION, OR SCIENTIFIC EXECUTION`

**Experiment ID:** `exp_20260915_001_mdmt_mia_c6_pre_service_semantic_suppression`

This document translates the frozen C6 Contract into the smallest auditable
code, test, qualification, and evidence path. It changes no Research Decision,
does not authorize any implementation, and reports no tracking outcome.

## 1. Authority binding

### 1.1 Mechanically observed plan-time authority

```text
REPO_ROOT = /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking
WORKTREE_PATH = /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/c5_shadow_validator_path_corrective
CURRENT_BRANCH = plan/20260915-c6-pre-service-semantic-suppression-implementation-plan
CURRENT_HEAD_SHA = 989ee15285866b119a643f1f1ccdf52d2d02009f
WORKTREE_CLEAN_BEFORE_PLAN = YES

C6_CONTRACT_COMMIT_SHA = 989ee15285866b119a643f1f1ccdf52d2d02009f
C6_CONTRACT_PARENT_SHA = 09747e7de973b8a08f0cd08c97e3649fc2b8496b
C6_CONTRACT_RAW_SHA256 = f89bb6d2f1c218b85fee7d77916a3f911d19687f34fbef9c51196b6e245de125
C6_CONTRACT_HASH_MATCH = YES

BASE_IMPLEMENTATION_SHA = 9a511c3ce300b5dedb1f2e970f131ddd2522b0c0
C5_PRODUCTION_IMPLEMENTATION_SHA = 846350036f4169b0715e4d33caaa54c947a5e8e7
C5_QUALIFICATION_SHA = f4fafe81f86cf00b0ac28b340ad0aa929507e295
C5_RUN004_AUTHORITY_SHA = 09747e7de973b8a08f0cd08c97e3649fc2b8496b

C5_APPLICABILITY_PREDICATE_PATH = src/tracking/mdmt_mia_async_deadline_runtime.py
C5_APPLICABILITY_PREDICATE_FUNCTION = _classify_whole_packet_currently_non_applicable
C5_APPLICABILITY_PREDICATE_SHA256 = b870c9fe4364d01cd1f8c7ce59240d6fa97d2ce65caff809afef3f1f9c6c0a66
C5_PREDICATE_EXACT_SOURCE_SPAN_SHA256 = 7736b2efed023056ae215e2d7ea6ef13f54cd80d18f0dbe500b317a4ceff9e39

TRUE_FIRST_SERVICE_PATH = src/tracking/mdmt_mia_async_deadline_runtime.py
TRUE_FIRST_SERVICE_FUNCTION = _C4SharedLogicalServer._start_next
SERVICE_RUNTIME_PATH = src/tracking/mdmt_mia_async_deadline_runtime.py
SERVICE_LEDGER_PATH = <PacketRuntime.output_dir>/c4_service_ledger_<sequence_name>.jsonl
PACKET_LIFECYCLE_REPRESENTATION = _C4SharedLogicalServer item dict plus C4 ledger and packet-census terminal records
```

The contract's predicate fingerprint is the raw SHA-256 of the entire frozen
C5 runtime file. Because C6 must change that file, implementation qualification
must additionally compare the exact source span of the predicate at lines
204–246 against `C5_PREDICATE_EXACT_SOURCE_SPAN_SHA256`; a changed whole-file
hash alone is expected and must not be mistaken for permission to alter the
predicate.

### 1.2 Frozen Run004 baseline authority

```text
RUN_ID = c5_shadow_census_20260914_004
RUN_END_RAW_SHA256 = d0941f0c487c0e63324f999d9cdb2101f7013fa15b229459b09f272bdd3f9a05
AUTHORIZATION_PATH = summary_md/communication/c5_shadow_census_formal_execution_authorization/C5_SHADOW_CENSUS_EXECUTION_AUTHORIZATION_RUN_004.json
OUTPUT_ROOT = outputs/c5_shadow_oracle_opportunity_census/c5_shadow_census_20260914_004
```

Frozen per-cell C5 Shadow seal hashes are:

| Cell | Raw SHA-256 |
| --- | --- |
| P23 / FIFO-mild | `d46e0a910ecb2cbe0cce5cb5131ee6dea010fdd34d8194a2dbab562dca0688b9` |
| P23 / FIFO-strong | `bd53485bcdd93b7b276426900360d7341333bf960ad714f8776831473c098226` |
| P44 / FIFO-moderate | `ec530381f35090812dd60130246c367e2873b72c337a849fd10c3b63e407deab` |
| P66 / FIFO-mild | `063ba60e148d04b90bf9fbc60353e685d0caf2d38fc45ec10e28b633e9d435a9` |

The generated-author C5 authority is
`/mnt/data/yzm/experiments/mdmt_mia_official/variants/c5_generated_author_source_binding_001`.
Its runtime, entry, and manifest fingerprints are respectively
`b870c9fe...c0a66`, `f7113f3d...d5316`, and `02f2f001...e224` as recorded by
Q5. C6 must create a new immutable generated-author variant; it must never
overwrite that C5 directory.

### 1.3 Frozen external execution inputs

The Run004 launcher resolves the following concrete authorities:

- dataset root: `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking`;
- split and pairs: `train`, pairs `23`, `44`, `66`, with synchronized views
  `<pair>-1` and `<pair>-2` and their `new_xml` files;
- config: `/mnt/data/yzm/experiments/mdmt_mia_official/run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py`;
- detector checkpoint:
  `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth`;
- author entry: `demo/supplement_MIA.py` under the governed generated source;
- device default: `cuda:0`;
- delays: zero for Local, Homography, ID-State, and Supplement;
- deterministic controls: `PYTHONHASHSEED=0`, `PYTHONNOUSERSITE=1`, isolated
  run-input/output/cache roots;
- service rates: P23/mild `31987`, P23/strong `16649`, P44/moderate
  `26148`, P66/mild `31987` logical bytes per frame.

The existing authority records paths and source fingerprints but does not put a
complete dataset/checkpoint byte manifest in the C6 Contract. Therefore, before
the first implementation commit is accepted, a read-only authority precheck
must record the current raw input/config/checkpoint fingerprints and per-pair
frame horizons, bind them to Run004's isolated input links and completed
manifests, and fail if that binding is not unique. Those values are not free
parameters and may not be guessed or replaced. This precheck reads identities
and horizons only, never tracking outputs.

## 2. Frozen Contract summary

C6 changes one variable: an enabled/disabled semantic gate at an ID-State
packet's treatment-path TRUE first-service boundary. The enabled treatment
re-evaluates the exact C5 predicate against current treatment receiver state.
A whole-packet non-applicable result terminates only that packet instance as
`SUPPRESSED`, charges zero service bytes, produces no normal completion,
delivery, consumer update, or feedback, and leaves the current frame's service
budget available to the next treatment FIFO head. A serviceable or mixed packet
begins baseline service and is never re-evaluated.

The causal invariant is:

```text
Treatment internally remains strict FIFO.
Treatment is not Baseline minus suppressed baseline packets.
```

Future treatment packet population may diverge through the intervention's
receiver-state consequences. C5 labels are descriptive baseline evidence and
must never be replayed as C6 decisions. Run004 is reused, never rerun. C6 does
not inspect tracking metrics and cannot authorize C7.

## 3. Architecture inspection

Each row reports the actual current implementation, not only Contract prose.

| # | PATH | FUNCTION / CLASS | CURRENT ROLE | REUSABLE_FOR_C6 | WHY |
| ---: | --- | --- | --- | --- | --- |
| 1 | `src/tracking/mdmt_mia_async_deadline_runtime.py:752` | `_C4SharedLogicalServer`; `admit()` | Stores one dict per packet in `_items`, appends it to a `deque` `_queue`, and keeps zero or one `_in_service` item. | YES | It already carries wire, identity, original byte cost, remaining/served bytes, timing, and terminal fields. |
| 2 | same, `admit()` / `_start_next()` | shared FIFO ordering | Admission appends in producer order; selection uses `popleft()`; an in-service packet is never preempted. | YES | Removing only the already-selected suppressible head preserves treatment-internal FIFO without a scheduler. |
| 3 | same, `_start_next()` | service selection | Moves exactly the current queue head to `_in_service`. | YES | This is the only legal selection point; no queue scan is required. |
| 4 | same, `_start_next()` | TRUE first-service detection | Sets `service_start_frame` after selection and calls the C5 observer before `_serve()` deducts bytes. | PARTIAL | The location is exact, but C6 needs a fail-closed decision before the normal `service_start` transition; C5's failure-isolated observer cannot control service. |
| 5 | same, lines 175–246 | `_C5ShadowReceiverSnapshot`, `_snapshot_c5_receiver_state()`, `_classify_whole_packet_currently_non_applicable()` | Builds an immutable event-local receiver snapshot and applies the whole-packet C5 predicate, including version reject, empty, mixed, remap, and confirmed-ID rules. | YES | C6 must call this exact predicate; no copy or rewrite is permitted. |
| 6 | same, `_serve()` | service-byte decrement | Deducts `min(frame_budget, remaining_service_bytes)`, increments item and frame served totals, and emits `service_slice`. | YES | Suppression branches before this block; passing packets use it unchanged. |
| 7 | same, `begin_frame()` / `_serve()` | partial-service continuation | Retains `_in_service` across frames and replenishes finite budget at the next consecutive frame. | YES | A passed packet stays in service, so no later gate invocation or mid-service abort is possible. |
| 8 | same, `_complete_current()` / `take_completed()` / `mark_terminal()` | completion transition | Sets completion/availability, appends to `_completed`, later marks semantic terminal disposition. | YES | Suppressed packets must bypass all three; passing packets remain unchanged. |
| 9 | same, `PacketRuntime._send()`, `begin_frame()`, `_drain()`, `_apply_pending_id()` | receiver update/application | Same-frame completions return to the producer caller; later ID completions enter the ID arrival heap and are applied at `begin_frame()`. | YES | If suppression never enters `_completed`, neither immediate nor delayed consumer path can observe it. |
| 10 | same, `record_feedback_input()` / `commit_fused_state_to_tracker()` | feedback generation | Records opaque input/output digests around tracker state publication. | YES | Existing digests support G13 without opening tracking values; suppression adds no feedback call. |
| 11 | same, `_event()`, `seal_evidence()`, `normalized_events()` | C4 service ledger | Writes append-only service events and a conservation summary at `<output_dir>/c4_service_ledger_<sequence>.jsonl`. | PARTIAL | Existing identity/slice/frame evidence is sufficient; only a distinct suppression event and C6-aware conservation fields are needed. |
| 12 | same, `_PacketCensusSidecar.emission()` / `_C4SharedLogicalServer._packet_id()` | packet identity | Uses `{census_run_id, sequence_name, runtime_instance_id, emission_ordinal}` when census is enabled. | YES | Run004 Shadow rows and ledger slices already expose the same canonical key. |
| 13 | same, `admit()`, `mark_terminal()`, `finalize_pending()`, `seal_evidence()` | lifecycle/status representation | Item dict holds `terminal_disposition`, `terminal_reason`, and `terminal_location`; census holds one terminal class per emission. | PARTIAL | Add only `SUPPRESSED` and its byte partition; do not redesign lifecycle machinery. |
| 14 | same, `_C5ShadowOpportunitySidecar.observe_first_service()` / `finalize()` | C5 Shadow evidence | Observes started ID-State only, records predicate inputs/results, and writes a detached record/seal; failures do not alter C5 service. | PARTIAL | Reuse its schema concepts and pure predicate, but treatment decisions require a new fail-closed C6 sidecar, not mutation of observational C5 behavior. |
| 15 | runtime `seal_evidence()` and `scripts/run_mdmt_mia_c5_shadow_oracle_opportunity_census.py:_validate_cell_outputs()` | validator/seal machinery | Recomputes C4 conservation and checks exact manifests/Shadow paths; runner uses exclusive JSON and terminal run records. | PARTIAL | Reuse canonical JSON, exclusive writes, exact-path checks, and seal pattern; add independent C6 decision/ledger reconciliation. |
| 16 | `scripts/run_mdmt_mia_c5_shadow_oracle_opportunity_census.py` and `scripts/run_mdmt_mia_author_sync.sh` | `validate()`, `_controlled_environment()`, `launch_cells()`; shell author launcher | Binds authorities, exact four-cell matrix, isolated roots, generated source, controlled environment, and sequential author execution. | PARTIAL | Create a C6-specific fail-closed runner; leave the frozen C5 runner and generic shell launcher unchanged. |
| 17 | `tests/test_mdmt_mia_c4_service_runtime.py`, `tests/test_mdmt_mia_c5_shadow_oracle.py`, `tests/test_mdmt_mia_c5_shadow_trajectory_parity.py`, `tests/test_mdmt_mia_c5_execution_gate.py` | existing C4/C5 tests | Cover FIFO, conservation, first-service observation, predicate boundaries, failure isolation, trajectory parity, authorization, source binding, and four-cell completion. | YES | They remain unchanged regressions; new C6 tests add intervention-specific assertions. |

The concrete Run004 P23/FIFO-strong paths inspected for schema compatibility
are:

```text
outputs/c5_shadow_oracle_opportunity_census/c5_shadow_census_20260914_004/
  shadow/pair_23__FIFO_strong/c5_shadow_records_23-1.jsonl
  runtime/pair_23__FIFO_strong/mia/train_23/results/mia_train_23/
    c4_service_ledger_23-1.jsonl
```

Both carry the same four packet-identity fields. No tracking result was opened.

## 4. Reuse map

| Component | Decision | Classification | Constraint |
| --- | --- | --- | --- |
| `_start_next()` selected-head boundary | Reuse with a narrow conditional call | `ESSENTIAL_FOR_CONTRACT` | Gate enabled only; disabled branch must produce the frozen event path. |
| Exact C5 snapshot and predicate | Direct call, no duplicate | `ESSENTIAL_FOR_CONTRACT` | Source-span and behavioral identity must pass. |
| C4 `deque`, `_in_service`, budget, `_serve()` | Reuse unchanged for passed work | `ESSENTIAL_FOR_CONTRACT` | No look-ahead, priority, or new scheduler. |
| Census packet ID | Reuse as canonical join key | `ESSENTIAL_FOR_CONTRACT` | Duplicate/missing/mismatched identity fails closed. |
| C4 service ledger | Extend minimally | `ESSENTIAL_FOR_CONTRACT` | No general trace or full queue snapshots. |
| C5 Shadow labels | Baseline derivation only | `ESSENTIAL_FOR_CONTRACT` | Never loaded by treatment runtime or runner decision path. |
| C5 runner patterns | Copy only governance/launch primitives into a new C6 runner | `ESSENTIAL_FOR_CONTRACT` | Frozen C5 runner remains byte-identical. |
| Generic async-variant builder and author shell launcher | Reuse without source changes | `ESSENTIAL_FOR_CONTRACT` | Generate a new exclusive C6 variant root. |
| Per-effect packet compaction | Reject | `OUT_OF_SCOPE` | Violates RD5. |
| Queue introspection, matched-work lineage, scheduling policy | Reject | `OUT_OF_SCOPE` | Violates RD7/RD9/RD15. |
| Convenience dashboard or trace framework | Reject | `OPTIONAL_CONVENIENCE` | Not required to recompute Contract metrics. |

Only the rows marked `ESSENTIAL_FOR_CONTRACT` remain in the proposed work.

## 5. Minimal code-delta proposal

1. Add a strict `MIA_C6_SUPPRESSION_CONFIG` parser and a small
   `_C6SuppressionSidecar` in the existing runtime. It calls the unchanged C5
   predicate using the existing treatment-state snapshot provider, records one
   decision per ID-State reaching TRUE first-service, and raises on any
   integrity error.
2. Add one gate-enabled branch in `_start_next()` immediately after `popleft()`
   and before ordinary `service_start`/positive-byte service. A suppression
   marks the current item, emits its distinct evidence, clears `_in_service`,
   and lets the existing `_serve()` loop continue with untouched budget.
3. Extend existing lifecycle/conservation validation with a third byte
   partition, `suppressed_service_obligation_bytes`. Passing and disabled-gate
   behavior remains byte-for-byte on the prior path.
4. Add a read-only Run004 baseline-derivation CLI and a C6 authorization-bound
   runner/validator. Reuse the existing ledger, identity, exclusive-output, and
   seal patterns.
5. Add focused tests plus one tiny subprocess fixture for complete synthetic
   E2E qualification. Do not modify existing C4/C5 tests.

No refactor, new semantic channel, new scheduler, proactive removal, or general
trace platform is proposed.

## 6. Per-file implementation map

### 6.1 Runtime

```text
FILE = src/tracking/mdmt_mia_async_deadline_runtime.py
CHANGE_CATEGORY = INTERVENTION_CORE / LIFECYCLE_STATE / EVIDENCE_ACCOUNTING / RUNNER_CONFIG
CURRENT_BEHAVIOR = selected FIFO head always emits service_start and receives baseline service; C5 is observer-only
PROPOSED_MINIMAL_CHANGE = parse the C6 enablement object; add fail-closed C6 decision/evidence sidecar; branch once in _start_next before normal service; represent SUPPRESSED and its byte partition; extend existing seal invariants
CONTRACT_CLAUSE_SERVED = Sections 4, 5.1, 5.2, 5.4, G2–G11
RD_SERVED = RD1–RD11, RD14, RD16
WHY_THIS_FILE = it owns selection, receiver snapshot, service budget, completion, lifecycle, and ledger
WHY_NO_SMALLER_LOCATION = any external wrapper would decide before FIFO selection or after service and would violate the boundary
```

### 6.2 Baseline derivation

```text
FILE = scripts/derive_mdmt_mia_c6_run004_serviceable_baseline.py
CHANGE_CATEGORY = BASELINE_DERIVATION
CURRENT_BEHAVIOR = no sealed Run004 serviceable-ID-State serviced-byte derivation exists
PROPOSED_MINIMAL_CHANGE = read only the exact frozen four Shadow/ledger/manifest/summary sets; perform the canonical packet join and reconciliation; exclusively write context/result/seal/report to a new evidence-only directory
CONTRACT_CLAUSE_SERVED = Sections 3.2, 5.2, 5.3, G0, G1, G11
RD_SERVED = RD12, RD14 secondary, RD15, RD16
WHY_THIS_FILE = an independent CLI can be authorized, audited, and completed before treatment output exists
WHY_NO_SMALLER_LOCATION = embedding derivation in the treatment runner risks late derivation and baseline-label exposure to the treatment process
```

### 6.3 C6 runner and validator

```text
FILE = scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py
CHANGE_CATEGORY = VALIDATION_GATE / RUNNER_CONFIG / EVIDENCE_ACCOUNTING
CURRENT_BEHAVIOR = the C5 runner authorizes an observational Shadow census and validates C5-specific outputs
PROPOSED_MINIMAL_CHANGE = new C6-only authority schema, exact cells/order, generated-source binding, preexisting baseline-seal verification before output creation, controlled gate environment, per-cell independent validator, run aggregation, and reproducible result seal
CONTRACT_CLAUSE_SERVED = Sections 3.4–3.7, 5.4–5.7, 6, G0–G13
RD_SERVED = RD3, RD4, RD7, RD8, RD12–RD17
WHY_THIS_FILE = intervention authorization and evidence meanings differ from C5; modifying the frozen C5 runner would corrupt its authority
WHY_NO_SMALLER_LOCATION = the runner is the smallest boundary that can deny invalid authority before scientific process launch
```

The C6 runtime config must contain only enablement, run identity, and output
location. Scientific cell `role` must not be passed to or read by runtime
control flow.

### 6.4 Focused tests

```text
FILE = tests/test_mdmt_mia_c6_pre_service_semantic_suppression.py
CHANGE_CATEGORY = TEST_ONLY
CURRENT_BEHAVIOR = C4/C5 cover observation but not service-controlling suppression
PROPOSED_MINIMAL_CHANGE = T1–T15 unit/integration cases, independent evidence recomputation, baseline-derivation corruption cases, and opaque disabled-gate parity
CONTRACT_CLAUSE_SERVED = all intervention and measurement gates
RD_SERVED = RD1–RD16 plus the non-adaptive mechanics of RD17
WHY_THIS_FILE = keeps C6 assertions separate while reusing public/runtime test fixtures
WHY_NO_SMALLER_LOCATION = changing frozen C4/C5 tests would weaken regression provenance
```

### 6.5 Tiny E2E fixture

```text
FILE = tests/fixtures/run_mdmt_mia_c6_tiny_runtime.py
CHANGE_CATEGORY = TEST_ONLY
CURRENT_BEHAVIOR = no subprocess fixture emits a mechanically predetermined suppress/pass/reuse chain
PROPOSED_MINIMAL_CHANGE = emit a tiny deterministic PacketRuntime workload and no tracking metrics, for invocation through the production C6 launch/validate/seal functions
CONTRACT_CLAUSE_SERVED = mandatory pre-MVE E2E and G2, G3, G5, G6, G11, G12, G13
RD_SERVED = RD1–RD11, RD14 accounting
WHY_THIS_FILE = a subprocess boundary catches environment, path, persistence, and exit-code failures hidden by in-process unit tests
WHY_NO_SMALLER_LOCATION = placing synthetic behavior in the production runner would create an unauthorized runtime mode
```

No change is planned for the Contract, C5 runner, generic author shell launcher,
variant builder, existing C4/C5 tests, detector/tracker code, packet schema, or
scientific result files.

## 7. Contract → Code → Test → Evidence traceability matrix

| Contract / RD | Code location | Planned behavior | Planned test | Runtime evidence | Failure interpretation |
| --- | --- | --- | --- | --- | --- |
| RD1 | runtime `_start_next()` + C6 sidecar | Suppress selected whole-non-applicable ID-State before service | T1 | decision + `suppressed` ledger/census terminal | `MEASUREMENT_INVALID` |
| RD2 | runtime `_serve()` | Keep budget unchanged and continue loop | T2 | same-frame budget before/after and next slice | invalid immediate reuse |
| RD3 | existing `_c5_context_provider()` + exact predicate | Re-evaluate current treatment state; accept no baseline label input | T4 | decision snapshot digest/source plus absence of label source | causality/leakage failure |
| RD4 | `_start_next()` channel guard | Gate ID-State only | T9 | decisions contain only `id_state` | scope violation |
| RD5 | exact predicate result | Any applicable effect, including mixed, passes whole | T5 | decision class `SERVICEABLE_MIXED`; full original wire size serviced | invalid over-suppression |
| RD6 | item lifecycle + census terminal schema | `SUPPRESSED` distinct from completion/drop/failure | T1, T15 | exclusive terminal state and location | lifecycle invalid |
| RD7 | existing deque/loop | Released budget serves current next FIFO head of either constrained channel | T3 | selection ordinals and ledger slices | scheduler/FIFO violation |
| RD8 | existing Supplement/Local/H paths | No new gate or consumer semantics | T9 | channel event digests and Supplement ledger | non-target parity failure |
| RD9 | `_start_next()` only | Never scan queued packets | T7 | no decision until selection event | proactive pruning violation |
| RD10 | `_in_service` continuation | Passed packet decision sticky across frames | T6 | one decision, multiple slices, one completion | mid-service recheck violation |
| RD11 | decision sidecar observed-key scope | Suppression affects current packet ID only | T8 | independent decisions for later packet IDs | blacklist/cache violation |
| RD12 | baseline derivation CLI + runner `validate()` | Reuse and seal Run004; zero baseline launches | T12 | baseline context/result/seal and input hashes | baseline invalid / stop |
| RD14 primary | sidecar + independent validator | Sum original bytes of terminally suppressed packets | T10 | per-packet bytes and recomputed `B_avoided` | metric invalid |
| RD14 secondary | sticky class on item + baseline seal | Sum positive ID service slices by own first-service class; subtract sealed baseline | T11, T12 | ledger, decisions, baseline seal, delta | metric invalid |
| RD15 | cell aggregation only | System-level totals; no cross-run matched-work causal requirement | T12, validator test | cell result tables; no lineage artifact | scope/design violation |
| RD16 | result schema/decision evaluator | Report mechanism and redistribution separately | evaluator table test | separate `B_avoided`, treatment/baseline/delta fields | decision invalid |
| RD17 | post-run decision evaluator only | Apply frozen graded gate; never authorize C7 | evaluator table test | sealed decision enum | governance violation |
| G1 | baseline derivation CLI | Unique, reproducible, reconciled baseline sealed first | T12 | baseline context/result/seal timestamps and hashes | block treatment launch |
| G2 | predicate direct import + fingerprints | Exact source and behavior | C5 replay + mutation denial | predicate authority fields | block qualification |
| G3 | `_start_next()` assertions | Decision after selection with served=0 and remaining=original | T1, T15 | decision boundary fields | measurement invalid |
| G5 | suppression branch and validators | No positive slice/completion/delivery/update/feedback | T1, T10, T15 | joined ledger/census/runtime events | measurement invalid |
| G6 | `_serve()` loop | Immediate unchanged-budget reuse | T2 | frame budget reconciliation | measurement invalid |
| G7 | deque head selection | Treatment-internal FIFO only | T3, T7 | packet sequence/selection ordinals | measurement invalid |
| G10 | runtime invariants + runner forbidden-field checks | No future/GT/outcome/source-bypass reads | leakage/corruption cases | zero invariant counters; no forbidden keys | measurement invalid |
| G11 | extended service/census validators | Byte, frame, lifecycle, denominator, aggregate conservation | T10, T11, T15 | validation table and recomputed totals | measurement invalid |
| G13 | disabled conditional path + existing opaque digests | Frozen packet/service/consumer/feedback integrity when gate off | T13 | canonical ledger/event digests and pre-existing feedback digests only | block qualification |
| MVE non-adaptation | C6 runner authorization schema | MVE validity may block; scientific values cannot alter Formal config/code | T14 + authorization mutation denials | separate validity and sealed-result fields | governance failure |

Every frozen requirement therefore has an executable code boundary, test, and
evidence source; none relies only on prose.

## 8. Baseline derivation design

### 8.1 Inputs and stable join

For each frozen cell, read its C5 Shadow JSONL and C4 service ledger from the
same Run004 output root. The stable packet join key is canonical JSON over:

```text
(census_run_id, sequence_name, runtime_instance_id, emission_ordinal)
```

The inspected schemas expose all four fields on both sides. Shadow requires
exactly one classification row per started ID-State packet; the ledger may have
many `service_slice` rows per packet. Thus the intended cardinality is one
classification to zero-or-more positive service slices. Existing census
emission uniqueness and C5 duplicate-first-service rejection support this
identity, but the derivation must revalidate uniqueness rather than assume it.
`wire_digest`, `channel`, `JSON_WIRE_BYTES`, `sequence_name`, and run/cell
identity are mandatory reconciliation fields, not substitutes for the join
key.

### 8.2 Deterministic algorithm

1. Refuse any output path inside Run004. Verify exact Contract, Run004
   authorization, `RUN_END`, four Shadow-seal hashes, complete cell set, and
   status before opening treatment outputs (which must not yet exist).
2. Hash every consumed Shadow record/seal, C4 ledger/summary, packet census
   emission/terminal/validation, and runtime manifest into the derivation
   context.
3. Parse JSON with duplicate-key rejection. Validate schemas, cell/sequence
   identity, terminal completion, and existing C4/C5 seals.
4. Build a unique map from canonical packet key to C5 classification. Reject a
   duplicate key, non-ID-State Shadow row, or inconsistent wire byte/digest.
5. Read ledger events once. For every positive `service_slice` on ID-State,
   require exactly one classification and sum `bytes_served` under the sticky
   first-service class. A record with
   `whole_packet_currently_non_applicable=false` is serviceable. This includes
   every mixed packet; no effect-level split is allowed.
6. Reject a Shadow record without the corresponding first-service/start
   evidence, a service slice without a classification, negative/zero malformed
   slices, duplicate event ordinal, or inconsistent packet metadata.
7. Reconcile grouped slices to packet summaries; reconcile all packet slices to
   `logical_bytes_served`; reconcile offered/served/remaining totals, frame
   budgets, census identity, C5 checked count/bytes, and manifest status.
8. Emit context, result, seal, and a non-interpretive report using exclusive
   creation. Re-running over identical inputs in a fresh temporary destination
   must produce identical canonical context/result payload digests; volatile
   path/time fields stay outside the sealed payload.

Proposed evidence-only location:

```text
summary_md/communication/c6_run004_serviceable_baseline_derivation/
  C6_RUN004_BASELINE_DERIVATION_CONTEXT.json
  C6_RUN004_BASELINE_DERIVATION_RESULTS.json
  C6_RUN004_BASELINE_DERIVATION_SEAL.json
  C6_RUN004_BASELINE_DERIVATION_REPORT.md
```

This stage is separately authorized after implementation review, performed
read-only against Run004, independently audited, and sealed before any C6
treatment output may be inspected. It runs no baseline workload. Missing or
non-unique identity, hash mismatch, or reconciliation failure blocks treatment
with `NEEDS_RESEARCH_DECISION` where the Contract requires it.

```text
SAME_SEALED_RUN004_EVIDENCE_UNIVERSE = REQUIRED
BASELINE_RERUN = NO
NEW_MATCHED_WORK_INFRASTRUCTURE = NO
NEW_GENERAL_TRACE_INFRASTRUCTURE_REQUIRED = NO
```

## 9. Intervention control-flow plan

```text
while budget permits and (_in_service exists or queue nonempty):
    if no _in_service:
        item = queue.popleft()                 # only current FIFO head

        if C6 gate enabled and item.channel == "id_state":
            assert item has never been classified
            assert item.bytes_served_total == 0
            assert item.remaining_service_bytes == item.JSON_WIRE_BYTES

            snapshot = current treatment receiver-state snapshot
            result = exact frozen C5 predicate(item.wire, snapshot)
            persist one fail-closed first-service decision

            if result.whole_packet_currently_non_applicable:
                item.terminal_disposition = "suppressed"
                item.suppressed_service_obligation_bytes = item.JSON_WIRE_BYTES
                item.remaining_service_bytes = 0
                emit SUPPRESSED lifecycle/census evidence
                assert no service/completion/delivery/consumer/feedback action
                _in_service = None
                continue                       # same budget, next FIFO head

            item.c6_first_service_class = "serviceable"
            # mixed is serviceable as a whole; decision is now sticky

        execute frozen service_start and baseline _serve path
    else:
        continue frozen partial service        # never re-check
```

The gate has no queue iterator and receives only the selected item and an
invocation-scoped current treatment snapshot. It cannot look ahead. Neither
the runner nor runtime loads C5 Shadow classification files, so baseline label
replay is structurally unavailable. Only `_start_next()` calls the gate, so an
in-service packet cannot be rechecked. The observed-ID set detects duplicate
classification of the same instance but is not consulted for semantic
decisions about later instances. The channel guard excludes Supplement, Local,
and Homography. Selection remains `popleft()` and the next head gets no
semantic priority.

## 10. Lifecycle-state plan

The existing item dict and paired service-ledger/census records remain the
authoritative lifecycle representation. Add only:

- item `c6_first_service_class`: empty, `serviceable`, or `suppressed`;
- item `suppressed_service_obligation_bytes`: zero normally, original
  `JSON_WIRE_BYTES` only when suppressed;
- terminal disposition/class `SUPPRESSED` with location
  `selected_pre_service` and frozen predicate reason flags;
- one `suppression` service event, never a `completion` event;
- a corresponding packet-census terminal whose class is `SUPPRESSED`.

Allowed terminal partition becomes exactly:

```text
completed_delivered
completed_expired_or_rejected
pending_at_end
suppressed
```

For each constrained packet exactly one terminal disposition is required.
Suppressed packets remain in `_items` for audit but not in `_queue`,
`_in_service`, `_completed`, or runtime arrival heaps. They have no
`service_start_frame`, `service_completion_frame`, or `availability_frame`,
zero `bytes_served_total`, zero `remaining_service_bytes`, and suppressed bytes
equal to original wire bytes. Passing packets set their sticky class before
the pre-existing `service_start` event and otherwise use the frozen lifecycle.

The extended byte equation is:

```text
JSON_WIRE_BYTES
  = bytes_served_total
  + remaining_service_bytes
  + suppressed_service_obligation_bytes
```

Disabled-gate output must omit C6-only evidence and reproduce the prior
normalized event/ledger digests. No broader lifecycle refactor is allowed.

## 11. Evidence/accounting plan

### 11.1 Minimal per-packet evidence

One decision record for every treatment ID-State packet reaching TRUE
first-service contains schema/run/cell/sequence identity, canonical packet ID,
wire digest, original `JSON_WIRE_BYTES`, selected frame, zero-byte boundary
assertions, predicate source fingerprint, whole-packet decision, existing C5
reason flags/effect classifications, and terminal class. It contains no GT or
tracking metric.

The existing ledger remains authoritative for service slices. Its only new
event is the suppression transition and its only new packet accounting is the
suppressed byte partition. Existing frame summaries prove immediate reuse and
idle bytes.

### 11.2 Recomputable aggregates

The independent validator computes, never trusts, the following:

```text
B_avoided
  = sum(decision.JSON_WIRE_BYTES where terminal == SUPPRESSED)

suppressed_id_state_packet_count
  = count(unique suppressed packet_id)

serviceable_id_state_serviced_bytes_treatment
  = sum(positive ledger service_slice.bytes_served for ID-State packet_ids
        whose own sticky treatment decision is serviceable)

serviceable_id_state_serviced_bytes_baseline
  = exact field from the separately sealed Run004 derivation

delta_serviceable_id_state_serviced_bytes
  = treatment - baseline
```

It also recomputes total ID-State serviced bytes, total Supplement serviced
bytes, per-frame/total idle bytes, end-of-horizon pending bytes by channel,
checked counts/bytes, and suppression reason composition. Supplement is named
only `supplement_serviced_bytes`, never useful/serviceable bytes.

Mandatory invariants are:

- every suppressed packet has zero positive service slices, no completion,
  availability, delivery, consumer application, or feedback consequence;
- per-packet extended byte conservation and per-frame
  `R = served + unused`;
- unused budget implies no remaining treatment backlog at frame close;
- exactly one lifecycle terminal per emitted packet and exactly one C6
  decision per started ID-State packet;
- all serviceable bytes belong to a sticky first-service classification;
- aggregate values reproduce from raw decision/ledger/census records;
- complete/exclusive run and cell seals bind all raw-file hashes.

Proposed treatment root and minimum files are:

```text
outputs/20260915_mdmt_mia_c6_pre_service_semantic_suppression/<exact-run-id>/
  RUN_START.json
  RUN_END.json
  C6_RUN_CONTEXT.json
  C6_RUN_RESULTS.json
  C6_RUN_SEAL.json
  runtime/<cell>/ATTEMPT_START.json
  runtime/<cell>/ATTEMPT_END.json
  runtime/<cell>/.../c4_service_ledger_<sequence>.jsonl
  runtime/<cell>/.../c4_service_summary_<sequence>.json
  runtime/<cell>/.../packet_census_*.json[l]
  decisions/<cell>/c6_first_service_decisions_<sequence>.jsonl
  decisions/<cell>/c6_suppression_seal_<sequence>.json
```

This is a bounded extension of existing evidence, not a trace platform.

## 12. Focused test plan

| ID | Deterministic setup | Required assertion |
| --- | --- | --- |
| T1 | Selected ID-State is wholly non-applicable | One `SUPPRESSED`; zero slices; no start/completion/delivery/application/feedback; distinct census terminal. |
| T2 | Suppressible head plus work smaller than remaining frame budget | Budget before/after suppression identical and the next packet receives service in the same frame. |
| T3 | ID-State and Supplement interleaved in known admission order | Selection order is exactly treatment `popleft()` order after removing suppressed heads; capacity is not reserved by channel. |
| T4 | Same wire evaluated against two different current treatment snapshots; decoy C5 label file exists | Decisions follow only current snapshots; opening the decoy is denied/detected. |
| T5 | One packet has non-applicable and applicable effects | Whole packet is sticky serviceable, original wire unchanged, no effect pruning. |
| T6 | Serviceable packet size exceeds `R` | Exactly one classification, multiple cross-frame slices, no abort/recheck. |
| T7 | Suppressible packet waits behind an in-service packet | No decision/removal while waiting; decision occurs only after head selection. |
| T8 | Later packet repeats semantic content with a new packet ID | It receives an independent current-state decision; no blacklist or lineage memory. |
| T9 | Supplement plus Local/Homography fixtures | Supplement uses baseline shared service; Local/H bypass; disabled/enabled differences are only causal timing after released capacity. |
| T10 | Multiple known suppressed wire sizes | Recomputed `B_avoided` equals exact original-byte sum; tampered byte/slice fails closed. |
| T11 | Serviceable packet spans frames alongside suppressed work | Every positive slice is counted under its one sticky class; treatment aggregate reproduces exactly. |
| T12 | Tiny duplicate/missing/corrupt Run004-shaped fixtures and two clean derivations | Unique many-slice-to-one-class join, reconciliation, and deterministic seal; corruptions deny before treatment launch. |
| T13 | Same synthetic input with C6 config absent/disabled | Canonical packet/service/completion/consumer/feedback integrity digests equal frozen reference; only opaque pre-existing digests are compared and no tracking values are opened or printed. |
| T14 | Identical runtime config under different runner cell-role labels | Runtime decision/service evidence is identical; role affects metadata/aggregation only. |
| T15 | Predicate exception, duplicate decision, positive suppressed slice, completion of suppressed item, bad lifecycle, bad seal | Every case fails closed and yields no valid scientific result. |

Before C6 tests pass, run syntax/import checks only. After focused tests pass,
replay the unchanged C4/C5 suites named in Section 3. Test failures may trigger
a bounded implementation correction but never a Contract/RD change.

## 13. E2E qualification plan

This is a mandatory, separately authorized, non-scientific stage before MVE.
Use the tiny subprocess fixture through the production C6 launch function,
controlled environment, actual `PacketRuntime`, production validator, result
aggregation, and seal writer. The fixture contains:

1. a known suppressible ID-State head;
2. a known serviceable or mixed ID-State after it;
3. a Supplement after that item;
4. a finite budget chosen so the suppressed obligation would have consumed
   capacity but the next FIFO item instead receives a same-frame slice.

The expected chain is mechanically precomputed from fixture inputs:

```text
runner authorization accepted
→ exclusive root/start record
→ FIFO selects suppressible ID-State
→ exact known predicate decision
→ SUPPRESSED, zero service bytes
→ unchanged budget immediately serves next FIFO item
→ exact ledger/census/decision records
→ B_avoided independently recomputed
→ all validator gates pass
→ context/result/seal digests reproduce in a fresh root
→ terminal run record COMPLETE
```

Negative E2E cases corrupt each boundary in turn: wrong source/predicate hash,
stale baseline seal, output collision, wrong matrix/rate, missing decision,
positive suppressed slice, completion/delivery of suppressed work, missing
cell end, duplicate identity, and seal mismatch. Each must stop downstream
launch or mark the qualification invalid.

The fixture emits no detector/tracker result values. G13 compares canonical
runtime/service event digests and existing feedback-chain digests only. No MOTA,
IDF1, IDSW, per-object identity value, result JSON trajectory, or derived
tracking outcome may be opened, recomputed, logged, or surfaced.

```text
E2E_QUALIFICATION_DESIGNED = YES
SCIENTIFIC_INTERPRETATION = NONE
```

## 14. Real-path MVE plan

Only after implementation, focused regression, baseline seal, E2E
qualification, independent audit, generated-source qualification, GPU/runtime
preflight, and a separate exact-MVE authorization may the real-path canary run:

```text
REAL_PATH_MVE = YES
CELL = P23 / FIFO-strong
BASELINE_EXECUTIONS = 0
UNIQUE_OUTPUT_ROOT = REQUIRED
MVE_VALIDITY_STATUS = PASS / FAIL
MVE_SCIENTIFIC_RESULT = SEALED_NOT_ADAPTIVE
SCIENCE_ADAPTATION_ALLOWED = NO
```

It uses the actual governed author entry, C6 generated runtime, frozen input,
checkpoint, horizon, environment, and rate. Authority, causality, lifecycle,
accounting, completion, isolation, or seal failure blocks Formal. If validity
passes, the scientific values are sealed without changing code, config,
predicate, cell matrix/order, rates, metrics, thresholds, or the Formal
decision rule. No branch condition may read `B_avoided` or its delta to decide
whether or how Formal runs.

## 15. Pre-Formal audit plan

Team B receives a read-only packet containing:

- exact Contract, Plan, implementation, test/qualification, baseline seal,
  generated-source, preflight, and MVE authority hashes;
- source-span and behavioral predicate identity;
- focused and unchanged C4/C5 regression results;
- clean E2E positive/negative evidence and reproducible seals;
- real-path MVE validity status with scientific result still
  `SEALED_NOT_ADAPTIVE`;
- formal runner dry-run matrix, isolated destination, storage/GPU checks, and
  no-launch proof;
- an explicit first-use inventory for gate, lifecycle, ledger, baseline join,
  validator, runner, generated source, author entry, failure handling, and
  seal reproduction.

The audit asks:

> If Formal begins now, is any critical mechanism, evidence path, validator,
> baseline derivation, runner, generated-source binding, or seal path being
> exercised for the first time?

Required answer:

```text
CRITICAL_PATH_FIRST_EXERCISED_IN_FORMAL = NO
```

Any `YES` blocks Formal and sends only the unexercised mechanical path back to
qualification. Formal must be fresh scientific execution, never integration
testing.

## 16. Qualification and authorization boundaries

The stages are strictly ordered and independently authorized:

```text
Plan Team B PASS
→ implementation authorization
→ minimal implementation commit
→ focused tests + unchanged C4/C5 regressions
→ Run004 baseline derivation and independent seal
→ generated-author C6 variant/source binding
→ synthetic E2E qualification and evidence seal
→ independent experiment audit
→ GPU/runtime preflight
→ exact P23/FIFO-strong MVE authorization
→ real-path MVE validity audit (science remains sealed/non-adaptive)
→ pre-Formal audit
→ fresh exact four-cell Formal authorization
```

No earlier artifact authorizes a later stage. Baseline derivation launches no
workload. Qualification launches only synthetic/tiny non-scientific work. MVE
authorization covers one real cell only. Formal requires a new run ID and does
not reuse MVE. No stage authorizes baseline re-execution, tracking evaluation,
C7, C8, scheduler/RL work, pushing, or publication claims.

## 17. Risk register

| Risk | Trigger | Prevention | Detection | Severity |
| --- | --- | --- | --- | --- |
| Wrong first-service insertion point | decision before `popleft()` or after a slice | only call from `_start_next()` after selected head, before normal start/decrement | T1/G3 boundary fields and code audit | Critical |
| Predicate duplication/drift | copied/reimplemented predicate or changed source span | direct call; frozen runtime and exact-span hashes | G2 fingerprint plus independent behavioral replay | Critical |
| `SUPPRESSED` still triggers completion | item enters `_completed`/arrival heap | suppression clears `_in_service` and bypasses `_complete_current()` | T1/T15 joined event absence | Critical |
| C5 label replay | runtime/runner opens Shadow decisions | treatment interface accepts no baseline path/label | file-open denial test and source audit | Critical |
| FIFO look-ahead | queue scan chooses later semantic item | only `popleft()`; no iterator/priority structure | T3/T7 selection ledger | Critical |
| Baseline-minus-suppressed misconception | matched packets imposed across trajectories | system-level totals and current treatment population | schema/audit rejects matched-work causal claims | High |
| Non-unique baseline join | duplicate/missing packet identity | canonical four-field key and fail-closed cardinality checks | T12 plus derivation report | Critical |
| Mixed packet overclaim | mixed effect pruned or bytes called individually useful | exact whole-packet predicate; serviceable terminology | T5 and result-schema audit | High |
| Supplement mislabeled useful | Supplement bytes included in serviceable metric | separate neutral Supplement field | aggregator unit tests | High |
| MVE outcome accidentally gates Formal | code/config reads sealed scientific field | authorization validates only MVE validity, not value | T14 and pre-Formal diff/audit | Critical |
| Opaque parity opens tracking values | test serializes result arrays or metrics | compare existing integrity/feedback digests only | test source audit and forbidden-key scan | Critical |
| Formal is first integration test | real runner/path/seal skipped earlier | E2E plus real-path MVE and first-use inventory | pre-Formal audit | Critical |
| Failure-isolated C5 observer reused for control | predicate exception silently allows service | separate fail-closed C6 sidecar | injected exception T15 | Critical |
| Suppressed bytes counted pending | original remaining bytes left in pending aggregate | explicit suppressed byte partition and zero remaining | conservation tests | High |
| Runtime behavior depends on role | role passed into gate | omit role from runtime config | T14 environment/config comparison | High |
| Generated C5 source overwritten | C6 copies into existing variant path | exclusive new variant root and hash binding | collision denial/source audit | Critical |

## 18. Explicit non-goals

- No modification of RD1–RD17 or the frozen Contract.
- No baseline execution or treatment execution during planning/implementation.
- No tracking metric, trajectory analysis, GT-based evaluation, C7, or C8.
- No Supplement/Local/Homography applicability predicate.
- No effect-level pruning, repacketization, compression, or wire-schema change.
- No proactive queue scan, deadline/TTL, priority, reservation, scheduler,
  optimizer, RL, or MARL.
- No persistent blacklist, lineage ban, cross-packet semantic cache, or
  matched-work causal infrastructure.
- No new general-purpose trace, dashboard, or observability platform.
- No detector/tracker/checkpoint/config/threshold/dataset/horizon/rate tuning.
- No inference that C6 improves tracking, physical bandwidth, or optimality.

## 19. Stop conditions

Stop and do not create/accept an implementation candidate if any of the
following occurs:

- Contract commit, parent, path, or raw digest differs from Section 1;
- C5 implementation/Q5/Run004/generated-source authority cannot be verified;
- Run004 or its frozen seal hashes changed, or the baseline join is missing,
  non-unique, unreconciled, or unreproducible;
- exact predicate reuse or TRUE-first-service placement cannot be proven;
- input/config/checkpoint fingerprints or frame horizons cannot be bound to the
  same Run004 universe before code modification;
- implementation needs queue look-ahead, label replay, matched-work lineage,
  new tracing infrastructure, a non-ID-State gate, or a Contract/RD change;
- suppressed work receives positive service or any normal completion,
  delivery, update, or feedback consequence;
- disabled-gate opaque parity, focused tests, existing C4/C5 regressions, E2E,
  generated-author binding, or seal reproduction fails;
- MVE validity fails, a scientific MVE value is used adaptively, or any
  critical path would first execute in Formal;
- tracking outcomes must be opened to complete qualification.

Scientific values unfavorable to `H_M` or `H_R` are not implementation failure
and do not authorize adaptation. Governance-significant design changes require
`NEEDS_RESEARCH_DECISION`.

## 20. Proposed next authorization boundary

This Plan authorizes no code or test change. The only next stage is an
independent Team B delta review of this document against the frozen Contract
and actual architecture.

```text
C6_IMPLEMENTATION_PLAN_STATUS = COMPLETE
TRUE_FIRST_SERVICE_HOOK_FOUND = YES
BASELINE_DERIVATION_PATH_FOUND = YES
MINIMAL_IMPLEMENTATION_PATH_FOUND = YES
CONTRACT_TO_CODE_TRACEABILITY_COMPLETE = YES
CONTRACT_TO_TEST_TRACEABILITY_COMPLETE = YES
CONTRACT_TO_EVIDENCE_TRACEABILITY_COMPLETE = YES
NEW_GENERAL_TRACE_INFRASTRUCTURE_REQUIRED = NO
E2E_QUALIFICATION_DESIGNED = YES
REAL_PATH_MVE_DESIGNED = YES
PRE_FORMAL_AUDIT_DESIGNED = YES
RD1_RD17_CHANGED = NO
CONTRACT_CHANGED = NO
PRODUCTION_CODE_MODIFIED = NO
TEST_CODE_MODIFIED = NO
SCIENTIFIC_EXECUTION_PERFORMED = NO
TRACKING_OUTCOME_READ = NO
NEXT_AUTHORIZED_STAGE = TEAM_B_C6_IMPLEMENTATION_PLAN_REVIEW
BLOCKERS = NONE AT PLAN GENERATION; ALL SECTION 19 CONDITIONS REMAIN FAIL-CLOSED
```
