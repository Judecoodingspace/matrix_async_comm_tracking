# C7 Outcome-Blind Eligibility Census Implementation Plan

Status: `READY_FOR_INDEPENDENT_CORRECTIVE_REVISION_2_DELTA_AUDIT`

This document is an implementation plan only. It does not authorize or contain an implementation, qualification execution, census execution, outcome read, or scientific decision revision.

## 1 Purpose and authority

The purpose of this plan is to translate the frozen C7 corrective pre-census specification into an auditable implementation path for an outcome-blind, observational eligibility census. The implementation must determine whether an authorized suppressible stale ID-State packet creates a same-window, same-packet-residual opportunity for a later serviceable ID-State packet to complete under conditional accounting, while leaving the real baseline runtime unchanged.

C7 is a testability/mechanistic-opportunity census, not a causal test of `H_R`. Its downstream evidentiary chain is frozen as:

```text
C7 census
  -> absolute qualification and selection
  -> one mechanistic H_R test candidate, if any
  -> separately governed real-suppression Formal
  -> only that later Formal may evaluate causal H_R
```

If zero cells qualify, the current frozen workload family provides no qualified `H_R` test regime: emit `NO_CELL_SELECTED`, stop, and do not expand the grid in the same census. If one or more cells qualify, select exactly one under the frozen hierarchy and request separate governance for a later real-suppression Formal. The selected cell is only a candidate for that later Formal.

```text
C7_CENSUS_EVALUATES_H_R = NO
C7_QUALIFICATION_ROLE = TESTABILITY / MECHANISTIC-OPPORTUNITY EVIDENCE
SELECTED_CELL_ROLE = CANDIDATE_FOR_LATER_REAL_H_R_FORMAL
SELECTED_CELL_IS_H_R_EVIDENCE = NO
C7_QUALIFIED != H_R_SUPPORTED
C7_SELECTED != REAL_REDISTRIBUTION_DEMONSTRATED
```

The exact authority chain for this plan is:

| Authority role | Binding identity |
| --- | --- |
| Plan base / corrective freeze commit | `0eda32c58871c1ec4b5b194c0c33608d7dd2a777` |
| Frozen specification content authority | `67f9b07a00141d380952f6a6cc9ae23f34c1cd7d` |
| Corrective freeze record SHA-256 | `5ab6ddc8b98796692cfa045456c62956af3a9ff1a0cbed24dd55ed319f3fcbb0` |
| Final corrective specification SHA-256 | `37733d47553ef9cd36fb9fef56bf6450bb800d83f69a4eea706cbee9df038299` |
| Corrective Revision 2 record SHA-256 | `70db89e502a9c9a3ae4322a2387b5693ca2c1600663ade39d947c3c11525fbbb` |
| Specification provenance SHA-256 | `7d2d08e3c868e38161428dfb84817e0f239b87f5860763bc1b4c53a6074db079` |
| Independent specification audit | Team B `PASS`; P0/P1/P2 findings all zero |

The dedicated plan branch is `plan/20260921-c7-outcome-blind-eligibility-census-implementation-plan`, created at the exact corrective freeze commit. The only authorized change on this branch is this plan artifact.

The required `experiment-governance-core` and `execution-path-qualification` skills were not available in the session skill registry. Their absence does not require reinterpretation of the frozen scientific decision. This plan therefore applies their required roles explicitly: change classification, authority locking, execution-path mapping, fail-closed evidence validation, production-path parity, and independent-audit handoff. `research-planner` and `independent-delta-audit` are prohibited in this authoring context and were not invoked.

Change classification for all future work described here:

| Class | Treatment |
| --- | --- |
| Frozen scientific authority | Immutable; no edits and no semantic reinterpretation |
| Engineering implementation | Future, separately authorized code/schema/test work |
| Validation and qualification | Future, separately authorized; qualification remains distinct from census selection |
| Documentation and provenance | This plan now; later manifests, seals, and audit records only under explicit authorization |

### 1.1 Corrective Revision 1 disposition

Revision parent: `73c8a2b555e6f99ec0d2f431ccf77f43697f5953`. Previous Plan SHA-256: `3d3ab6a349afa4058da4a9138d17acd57aa3c2a6afc420df94319e2e2e8e4a4f`. This revision dispositions exactly the eight third-party findings without a new research decision.

| FINDING_ID | ORIGINAL_ISSUE | DISPOSITION | PLAN_SECTIONS_CHANGED | NEW_RD_REQUIRED | SCIENTIFIC_SEMANTICS_CHANGED | TEST_ADDED_OR_CHANGED | STATUS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1-1 | Whether C7 itself evaluates `H_R` was not explicit. | Propagate the frozen upstream chain: C7 supplies mechanistic testability only; a separately governed real-suppression Formal alone may evaluate causal `H_R`. | 1, 10, 20, 23 | NO | NO | Claim-boundary documentation checks | RESOLVED_BY_UPSTREAM_AUTHORITY_PROPAGATION |
| P1-2 | No adversarial test prevented future baseline information from entering recipient serviceability intervals. | Add raw-evidence future-state injection negatives independently of source sticky-classification testing. | 4, 6, 8, 11, 12, 17 | NO | NO | `recipient_interval_future_state_injection` and four required fault variants | RESOLVED |
| P2-1 | Effective service window lacked an exact mechanical boundary. | Define one window as exactly one frame index from frame-open ordinal through frame-close boundary. | 2, 6, 8 | NO | NO | Frame-boundary/domain tests | RESOLVED |
| P2-2 | Stale removable interval start/end and cross-frame behavior were ambiguous. | Encode governed per-frame start/end rules, persistent classification, and no cross-frame capacity credit. | 2, 4, 6, 11, 17 | NO | NO | Same-frame and persisted-residual interval-boundary tests | RESOLVED |
| P2-3 | Downstream estimand/claim caveat was insufficiently explicit. | State that qualified/selected C7 opportunity is neither causal `H_R` evidence nor demonstrated real redistribution/tracking improvement. | 1, 20, 23 | NO | NO | Claim-boundary documentation checks | RESOLVED |
| P2-4 | Real-input MVE embargo did not explicitly cover internal artifacts and logs. | Extend embargo to intermediate/temp/debug/cache/log/exception channels and allow only structural operator-visible status. | 11, 13, 16, 17 | NO | NO | MVE artifact/log/stdout/stderr leakage negatives | RESOLVED |
| P2-5 | Later MVE slice choice lacked an explicit outcome-blind selection rule. | Require a pre-execution engineering/availability-only selection rationale and forbid prevalence/opportunity-based choice. | 13, 22 | NO | NO | Authorization-schema allowlist/forbidden-rationale tests | RESOLVED |
| P2-6 | Aggregate nested-count invariants were implicit. | Require `0 <= N_eligible <= N_stale <= N_all` before qualification and add fail-closed mutations. | 6, 8, 11, 17 | NO | NO | Negative/over-nested/duplicate/domain/invalid-window tests | RESOLVED |

### 1.2 Corrective Revision 2 disposition

```text
CORRECTIVE_REVISION = #2
PARENT_PLAN_COMMIT = 56966b9256f761983870c2b1db285a050ba62a57
PARENT_PLAN_SHA256 = e7136af31310bccc4b163920e5c67d0552041c47ff179638868c7107876b32aa
TRIGGER = TEAM_B_CORRECTIVE_PLAN_DELTA_AUDIT
P0_FIXED = 0
P1_FIXED = 1
P2_FIXED = 0
FINDING = P1-CR1-01
RESOLUTION = SEPARATE_SOURCE_REMOVABLE_WORK_FROM_RELEASED_CAPACITY_CREDIT
NEW_RESEARCH_DECISION = NO
OQ1_REOPENED = NO
SCIENTIFIC_SEMANTICS_CHANGED = NO
FROZEN_SPEC_CHANGED = NO
```

This correction restores fidelity to the already-frozen rule: capacity released inside one frame may be reused by later legal FIFO work in that same frame, but never carried across frames. Source removable-work bounds answer which stale work is legally removable; they do not define the lifetime of capacity credit already released from that work.

## 2 Frozen scientific boundary

The following requirements are immutable implementation inputs.

### 2.1 Fixed census grid

- Pair IDs: `P23`, `P44`, `P66`.
- Frame counts: `700`, `360`, `300`, respectively.
- Binding capacities: `16649`, `20147`, `25456`, `26148`, `28109`, `29620`, `31987`.
- The census manifest is the immutable Cartesian product of the three pair/frame definitions and seven capacities: exactly 21 cells.
- Cell identity is a stable tuple `(pair_id, capacity_bytes_per_frame, frame_count)` plus a deterministic `cell_id`.
- `EFFECTIVE_SERVICE_WINDOW = EXACTLY_ONE_FRAME_INDEX`.
- Each window begins at that frame's frame-open event ordinal and ends at that frame's frame-close boundary. `N_all`, `N_stale`, and `N_eligible` count only these one-frame windows in the frozen authorized frame domain.

### 2.2 Exact thresholds

- `T_count = 5` eligible windows.
- `T_den = 20` stale-present windows.
- Global rate threshold: `N_eligible / N_all >= 1/60`.
- Conditional rate threshold: `N_eligible / N_stale >= 1/4`.
- Every comparison is inclusive (`>=`).
- Rate comparisons must use integer cross multiplication only:
  - global: `60 * N_eligible >= N_all`;
  - conditional: `4 * N_eligible >= N_stale`.
- `T_count` remains separately evaluated, persisted, and reported even where it is intentionally redundant, per `CSD-C7-09`.
- A zero numerator is a valid measured result when all required evidence is complete. Missing or inconsistent evidence is invalid, never zero.

### 2.3 Exact `WINDOW_ELIGIBLE` boundary

A window is eligible only when all of the following are proven from baseline evidence:

1. An ID-State packet is classified as authorized suppressible stale at its true first service event.
2. The stale proof is complete and bound to that packet.
3. The conditional accounting release is linked to residual bytes of that same stale packet; bytes from another packet cannot satisfy the predicate.
4. A later recipient is an ID-State packet and is serviceable at the relevant event. Supplement, local, homography, or arbitrary packets cannot be recipients.
5. The recipient is incomplete in the real baseline window because binding capacity is exhausted; merely waiting in FIFO is insufficient.
6. Conditional accounting removes only authorized stale accounting.
7. Baseline descendants, receiver state, FIFO order, arrivals, serviceability, and event order remain fixed.
8. Under that accounting-only change, the recipient changes from incomplete to complete in the same window.
9. All predicate evidence and byte/work conservation evidence are complete and mutually consistent.

Packet completion is logical whole-packet completion. Partial bytes do not count as completion.

The true first service event is defined after FIFO selection and before the first byte of the selected packet is served. Classification is computed exactly once per packet, persisted, and never recomputed from future state. Conditional accounting is not replay: it cannot invoke tracking, reschedule packets, mutate AoI, add predictive logic, add RL, or apply treatment.

### 2.4 Governed temporal mechanics

OQ-1 is closed by governance clarification. For a candidate ID-State recipient resident in the real baseline FIFO but not yet at its own true first service, serviceability is represented over its FIFO residence by event-bounded intervals derived exclusively from the observed baseline receiver-state trajectory:

```text
[e_i, e_(i+1)) uses receiver_state after real baseline event e_i
until the next real baseline receiver-state transition
```

A real baseline state transition changes serviceability immediately for subsequent query points. No synthetic true-first-service event, permanent arrival-time classification, frame-end-only state, future event, counterfactual receiver state, or conditional replay may supply an interval state.

A stale source is classified only at its own true first-service event after FIFO selection and before its first service byte. Once classified `SUPPRESSIBLE_STALE`, the classification persists with that same unfinished logical packet. Conditional accounting represents two distinct states.

State A, `SOURCE_REMOVABLE_WORK`, answers which stale logical work is legally removable. Its source-side accounting interval is per frame:

- if classification occurs in the current frame, `SOURCE_REMOVABLE_WORK_START` is the valid true-first-service stale-classification event;
- if classification occurred in an earlier frame and its unfinished residual obligation exists in the current-frame baseline trajectory, the start is current frame open or the first current-frame presence of that persisted residual obligation;
- the removable amount is limited to authorized stale logical work belonging to the current-frame frozen baseline service trajectory;
- `SOURCE_REMOVABLE_WORK_END` is the earlier of exhaustion/completion of that relevant stale baseline obligation or frame close.

State B, `RELEASED_CAPACITY_CREDIT`, is created when authorized stale work is removed from conditional accounting. Credit creation is byte-conservative:

```text
released_capacity_credit += authorized_stale_work_removed_bytes
```

This credit has an independent lifetime. It does not expire when the source reaches its real baseline exhaustion/completion event. Once created in a frame, unused credit remains available to subsequent legal FIFO work until it is fully consumed or that frame closes. Only `FULLY_CONSUMED` and `FRAME_CLOSE` are valid expiration reasons; `SOURCE_BASELINE_COMPLETED` is forbidden. Remaining credit expires unused at frame close and never seeds the next frame.

```text
STALE_CLASSIFICATION_CAN_PERSIST_ACROSS_FRAMES = YES
SOURCE_BASELINE_COMPLETION != RELEASED_CREDIT_EXPIRATION
INTRA_FRAME_UNUSED_RELEASED_CREDIT_REUSABLE = YES
INTER_FRAME_RELEASED_CREDIT_CARRYOVER = NO
CURRENT_FRAME_REMOVABLE_WORK = only unfinished stale logical obligation present in the current-frame frozen baseline service trajectory
```

Credit propagates strictly through subsequent valid work in frozen baseline FIFO order. At every FIFO step, `consumed = min(credit_before, valid_fifo_work)` and `credit_after = credit_before - consumed`. Every preceding valid obligation consumes first; there is no preferred-recipient assignment, FIFO skip, reranking, or rescheduling.

An opportunity therefore requires temporal overlap of the recipient serviceability interval with the released-credit-available interval and FIFO reachability, with enough remaining credit for logical completion. It does not require overlap with the source removable-work interval after credit has already been created. Baseline recipient completion must be `NO`, conditional completion must be `YES`, and the baseline receiver-state/serviceability trajectory, arrivals, FIFO/event order, and frame budget remain fixed.

Mechanical example:

```text
same frame
e10: A reaches true first service, is classified SUPPRESSIBLE_STALE,
     60 bytes of authorized work are removed, credit = 60
e20: A reaches real baseline completion; unused credit remains 60
e25: B becomes FIFO-reachable and serviceable; B needs 40 bytes
e30: frame close

SOURCE_REMOVABLE_WORK_INTERVAL = [e10, e20]
RELEASED_CREDIT_AVAILABLE_INTERVAL = [e10, e30) or until consumed
B_SERVICEABLE_INTERVAL includes e25 onward
```

The source interval and B's serviceable interval need not intersect. Because the released-credit interval and B's serviceable interval do intersect and `60 >= 40`, B is not rejected merely because A's source removable-work interval ended at `e20`. This remains same-frame accounting; no credit crosses `e30`.

### 2.5 Qualification and selection separation

Per-cell qualification is evaluated independently. Cross-cell selection is forbidden until all 21 manifest cells are present, valid, and qualification-complete. The selector reconstructs the qualified subset itself. If that subset is empty, it emits `NO_CELL_SELECTED`, emits no ranking winner, does not expand the grid, and stops. Otherwise selection uses this exact ordering inside the qualified subset:

1. maximum `N_eligible`;
2. on count ties, Pareto comparison of the exact global and conditional rates;
3. if still tied, stable pair order, then stable capacity order, then stable `cell_id`.

No weighted score is permitted.

## 3 Existing architecture findings

### 3.1 Reusable production architecture

| Existing component / symbol | Finding | Planned disposition |
| --- | --- | --- |
| `src/tracking/mdmt_mia_packets.py` packet dataclasses and JSON wire helpers | Stable packet identities, types, sizes, and digests exist without tracking-evaluation outcomes. | `REUSE_UNCHANGED` |
| `src/tracking/mdmt_mia_async_deadline_runtime.py::_C4SharedLogicalServer` | Owns the binding finite-capacity FIFO, in-service residual, event ordinal, frame budget, byte ledger, completion, and terminal conservation checks. | `EXTEND_EXISTING` with passive C7 observation hooks only |
| `_C4SharedLogicalServer._start_next` and `_serve` | `_start_next` selects the FIFO head; observer notification can occur after selection and before `_serve` deducts the first byte. | Exact true-first-service hook |
| `_C4SharedLogicalServer._complete_current` | Provides logical completion boundary and packet identity. | Baseline completion evidence hook |
| `_C4SharedLogicalServer.begin_frame` / `finalize_pending` / `seal_evidence` | Provide frame budget boundaries, terminalization, and existing conservation invariants. | Extend evidence, preserve behavior |
| `_C5ShadowOpportunitySidecar.observe_first_service` | Demonstrates a once-per-packet observational callback at the required timing. | Reuse the timing pattern, not C5 semantics |
| `_C6SuppressionSidecar.classify` | Demonstrates sticky classification but is connected to treatment. | Do not reuse as C7 logic |
| `_classify_whole_packet_currently_non_applicable` | Existing pure current-state predicate supplies evidence concepts for ID-State applicability. | Reuse only if frozen stale proof fields and timing are reproduced exactly |
| `PacketRuntime` C4 admission/service path | ID-State and Supplement share the production binding server; state and trace manifests are already generated. | Preserve as real baseline; attach passive observer |
| `scripts/prepare_mdmt_mia_async_packet_variant.py::patch_variant` | Copies the selected runtime source into the generated author tree and hashes changed files in a generated manifest. | `REUSE_UNCHANGED` unless later path qualification proves a cachebuster is required |
| `scripts/run_mdmt_mia_author_sync.sh` | Existing operator wrapper provides stage/pair, path isolation, generated source invocation, and logs. | `REUSE_UNCHANGED` |
| `scripts/run_mdmt_mia_c6_real_child.py` | Demonstrates a child-to-wrapper production boundary and controlled environment. | Pattern only; create a C7 child that never sets C6 treatment config |
| `scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py` | Demonstrates exclusive root creation, launch authorization, subprocess execution, disk reread, validation, inventory, and seal. | Packaging pattern only; no C6 treatment semantics or result constants |
| `src/tracking/packet_census_run_tools.py` | Provides strict JSON/JSONL read patterns, canonical hashing, atomic writes, manifest freeze/verify, and pollution checks. | Reuse/refactor generic utilities only; do not reuse historical manifest constants |

The current C4 ledger proves many byte and identity invariants but does not yet record every ordered FIFO snapshot, receiver-state transition, or governed serviceability interval for every possible later ID-State recipient. This is the principal implementation gap. Governance has fixed the required representation as observed-baseline trajectory intervals; implementation must add that evidence observationally without changing the binding server's scheduling or state transitions.

### 3.2 Paths inspected during plan authoring

No experiment output, tracking outcome, C7 outcome, or C6 formal scientific outcome was opened. Inspection was limited to authority documents and source/test structure.

| Path | Inspection scope |
| --- | --- |
| `src/tracking/mdmt_mia_packets.py` | Full source |
| `src/tracking/mdmt_mia_packet_runtime.py` | Full source; historical zero-delay structure only |
| `src/tracking/mdmt_mia_active_packet_runtime.py` | Full source; active packet boundary and integrity structure |
| `src/tracking/mdmt_mia_async_deadline_runtime.py` | Targeted C4/C5/C6 parsers, sidecars, logical server, runtime send/frame/finalize paths |
| `src/tracking/mdmt_mia_cascade_runtime.py` | Symbol/search-level inspection only |
| `src/tracking/packet_census_run_tools.py` | Targeted hashing, atomic I/O, manifest, validation, and pollution controls |
| `scripts/prepare_mdmt_mia_async_packet_variant.py` | Symbol/search-level inspection of generated runtime copy and manifest binding |
| `scripts/run_mdmt_mia_author_sync.sh` | Full source |
| `scripts/run_mdmt_mia_c6_real_child.py` | Full source as a path-boundary example |
| `scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py` | Targeted launcher, validation, reconciliation, disk validation, inventory, and seal paths |
| `scripts/run_mdmt_mia_c6_e2e_qualification.py` | Symbol map only |
| `scripts/qualify_mdmt_mia_c6_pre_formal.py` | Symbol/search-level packaging pattern only; no result artifact opened and no embedded scientific value adopted |
| `scripts/run_mdmt_mia_c6_real_mve.py` | Repository-search match only |
| `tests/fixtures/run_mdmt_mia_c6_tiny_runtime.py` | Full source as synthetic production-subprocess example |
| `tests/test_mdmt_mia_c4_service_runtime.py` | Targeted FIFO, partial-service, completion, pending, invalid-config, and deterministic-ledger tests |
| `tests/test_mdmt_mia_c6_pre_service_semantic_suppression.py` | Targeted first-service, sticky-classification, corruption, and reconciliation tests; no historical Git command executed |
| `tests/test_mdmt_mia_c6_canonical_path_contract.py` | Targeted production-path parity structure only |
| `tests/test_mdmt_mia_packet_interface.py` | Test-name/symbol inspection only |
| `tests/test_mdmt_mia_c6_real_cell_launcher.py` | Test-name/symbol inspection only |
| `tests/test_mdmt_mia_c6_evidence_shape_profile.py` | Test-name/symbol inspection only |
| `configs/m3ot_oosm_smoke.yaml` | Filename discovery only; contents not opened |

## 4 Specification-to-code mapping

`PROPOSED_NEW` names below are planned APIs, not claims that those symbols already exist.

| Frozen requirement | Existing hook | Planned code location / function | Inputs | Evidence output | Independent validation | Test | Failure behavior |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Authority lock and 21-cell immutable manifest | Launcher patterns; canonical hash utilities | `scripts/run_mdmt_mia_c7_outcome_blind_census.py` `PROPOSED_NEW: build_frozen_manifest`, `verify_launch_authorization` | Frozen authority hashes, pair/frame table, capacities | `C7_CENSUS_MANIFEST.json` | Rebuild Cartesian product and hash; reject additions/omissions/order drift | Manifest unit + mutation negatives | Abort before child launch |
| Binding finite FIFO baseline | `_C4SharedLogicalServer` | Existing `admit`, `_start_next`, `_serve`, `_complete_current` | Real packet arrivals and capacity | Baseline event ledger | Reconcile bytes, order, sequence, digest, budget | Existing C4 tests plus C7 path contract | Cell invalid |
| Ordered event, FIFO, and receiver-state trajectory | C4 event ordinal and queue | `src/tracking/mdmt_mia_async_deadline_runtime.py` passive `PROPOSED_NEW: _notify_c7_event` | Immutable event data, queue view, and real baseline state transitions | Ordered per-event snapshots and event-bounded receiver-state intervals | Check ordinal continuity, transition legality, and no-lookahead interval bounds | Queue corruption and future-state injection negatives | Window/cell invalid |
| True first service after select/before byte | `_start_next` then `_serve`; C5 timing pattern | Passive callback to `PROPOSED_NEW: C7CensusObserver.observe_true_first_service` | Packet, pre-byte residual, receiver snapshot | Once-only classification record | Verify no prior served bytes; uniqueness; packet digest | Timing boundary unit tests | Cell invalid on absent/duplicate/late record |
| Sticky authorized stale proof | Existing pure applicability concepts | `src/tracking/mdmt_mia_c7_census.py` `PROPOSED_NEW: classify_authorized_stale_once` | ID-State payload, event-local state, authority rule ID | Predicate inputs, booleans, reason code | Recompute from raw fields; ignore producer label | stale/non-stale/future-state mutation cases | Invalid evidence, never inferred zero |
| Same-packet residual and source removable-work linkage | C4 `remaining_service_bytes`, packet ID/digest | `PROPOSED_NEW: derive_source_removable_work` | True-first record, persisted stale identity, frame-open presence, and baseline service events | source packet/digest, stale event, removable bytes/start/end, baseline completion event | Cross-check legal removable work and source-side interval against that packet's current-frame baseline ledger | cross-packet, early-start, overrun, and source-bound negatives | Window invalid |
| Released-capacity-credit ledger | C4 event ordinal, service bytes, FIFO order, and frame close | `PROPOSED_NEW: propagate_released_capacity_credit` | Authorized removed bytes plus subsequent frozen FIFO obligations | creation event/amount, per-step before/consumer/consumed/after, expiration reason/event | Independently reconstruct credit without using source completion as expiration; enforce same-frame conservation | source-completion-survival, intervening-consumer, premature/late creation, negative/over-credit, frame-carry negatives | Window invalid |
| Recipient type and trajectory serviceability | Packet type; baseline state snapshots/transitions | `PROPOSED_NEW: evaluate_recipient_serviceability` | Later immutable FIFO entry and event-bounded observed baseline receiver-state trajectory | ID-State type, interval bounds, source event ordinals, raw applicability/serviceability fields | Recompute intervals from real transitions; reject future/counterfactual/synthetic-event evidence | type cases plus `recipient_interval_future_state_injection` variants | Window invalid if proof absent or temporally invalid |
| Baseline incomplete due binding capacity | Frame budget, residual, queue, completion ledger | `PROPOSED_NEW: prove_capacity_caused_incompletion` | Frame close ledger and recipient residual | budget exhaustion, bytes needed, baseline completion=false | Check capacity conservation and distinguish waiting-only | capacity exhausted vs waiting-only cases | Predicate false or invalid if evidence incomplete |
| Conditional accounting only | No existing treatment-safe C7 evaluator | `src/tracking/mdmt_mia_c7_census.py` `PROPOSED_NEW: evaluate_window_accounting` | Frozen baseline ledger/FIFO/state intervals, source removable-work records, and independent credit ledger | stepwise FIFO credit propagation, recipient overlap with credit availability, and no-mutation proof | Recompute every FIFO hop; require credit-availability/recipient overlap rather than source-interval/recipient overlap, and accept later same-frame use of existing credit | two corrective tiny-E2E cases, no-skip, determinism, no-replay, no-state-mutation tests | Window invalid on non-conservation, changed order, direct assignment, or incorrect credit lifetime |
| Same-window completion flip | C4 logical completion semantics | `PROPOSED_NEW: evaluate_completion_flip` | Baseline residual and conditional allocation | baseline complete=false, conditional complete=true, exact logical boundary | Recompute residual arithmetic; partial is false | exact/one-byte-short/partial cases | Predicate false; invalid on inconsistent arithmetic |
| Conservation completeness | `seal_evidence` | Existing seal plus C7 validator invariants | Per-event and per-window bytes/work | baseline and conditional conservation blocks | Full independent sum/reconciliation | missing/duplicate/corrupt event negatives | Cell invalid |
| Valid zero, nested counts, and invalid | Strict reader patterns | `PROPOSED_NEW: aggregate_cell` | Complete validated one-frame window set | validity enum, counts including zero, nesting attestation, invalid reason list | Require expected frame-domain bijection and `0 <= N_eligible <= N_stale <= N_all` before qualification | valid-zero, negative/over-nested/duplicate/domain/invalid-window tests | Invalid never serialized as zero-qualified |
| Exact thresholds | None C7-specific | `PROPOSED_NEW: qualify_cell` | integer `N_all`, `N_stale`, `N_eligible` | four gate booleans, including `T_count` and `T_den`, and exact cross-products | Recompute integer formulas | boundary vectors for 4/5, 19/20, 59/60, 3/4 and exact passes | Qualification invalid on bad denominators/schema |
| Qualification before selection | Existing packaging pattern only | `PROPOSED_NEW: validate_all_cells_qualified` | frozen manifest and 21 cell qualification records | completeness record | Exact manifest bijection | missing/extra/duplicate cell tests | No selection artifact written |
| Count/Pareto/stable selection | None C7-specific | `PROPOSED_NEW: select_qualified_cell` | 21 valid qualification records | separate `C7_SELECTION.json` with comparison trace | Independent sort/Pareto recomputation | count, Pareto, incomparable/stable tie cases | Fail closed on ambiguity or weights |
| Outcome firewall | Communication-only C6 path pattern | launcher allowlist plus `PROPOSED_NEW: reject_forbidden_schema_fields` | configs, environment, artifacts | firewall attestation and schema key inventory | Static recursive forbidden-key/path scan | injected outcome key/path negatives | Abort/delete incomplete temp output; no seal |
| Atomic writes and resume | `_atomic_write`, exclusive writes | C7 writer `PROPOSED_NEW: write_cell_transaction` | validated staged artifacts | temp-to-final commit marker, digest inventory | Verify marker last and all digests | interruption/resume tests | Quarantine/recompute incomplete cell |
| Authority/config/provenance sealing | Generated/runtime manifests and C6 packaging pattern | `PROPOSED_NEW: seal_census_package` | source/config/input/output/schema/validator hashes | canonical inventory and seal | Independent seal reproduction | tamper every binding class | Package invalid |

The mapping is complete at plan level: every frozen predicate, aggregation rule, qualification rule, selection rule, and firewall constraint has an implementation point, evidence field family, validator action, test family, and fail-closed behavior. The former OQ-1 event-timing issue is closed by the governed observed-baseline trajectory-interval model in Sections 2 and 22.

## 5 Proposed implementation architecture

The planned data flow is:

```text
operator entry
  -> C7 parent launcher (authority + manifest + exclusive root)
  -> C7 real child (controlled outcome-blind environment)
  -> existing author-sync wrapper
  -> generated real runtime
  -> existing C4 baseline FIFO + passive C7 observer
  -> staged raw evidence
  -> independent validator
  -> atomic cell commit + inventory/seal
  -> later, separate 21-cell qualification
  -> later, separate cross-cell selection
```

Planned component boundaries:

| File | Change | Responsibility |
| --- | --- | --- |
| `src/tracking/mdmt_mia_async_deadline_runtime.py` | `EXTEND_EXISTING` | Emit passive immutable observation callbacks and evidence snapshots; preserve all baseline scheduling/state transitions |
| `src/tracking/mdmt_mia_c7_census.py` | `NEW` | Frozen constants, typed evidence records, once-only stale classifier, pure accounting evaluator, aggregate, exact qualification, and selection logic |
| `src/tracking/mdmt_mia_c7_validator.py` | `NEW` | Independent raw-evidence recomputation, schema/ordering/conservation/firewall checks; must not trust producer eligibility labels |
| `scripts/run_mdmt_mia_c7_outcome_blind_census.py` | `NEW` | Operator/parent launcher, authority binding, manifest, subprocess orchestration, atomic packaging, resume, inventory, seals |
| `scripts/run_mdmt_mia_c7_real_child.py` | `NEW` | Controlled child adapter into the existing real wrapper; sets C4 and observational C7 config only |
| `scripts/run_mdmt_mia_author_sync.sh` | `REUSE_UNCHANGED` | Production execution wrapper |
| `scripts/prepare_mdmt_mia_async_packet_variant.py` | `REUSE_UNCHANGED` initially | Install and hash the updated runtime into the generated source tree |
| `src/tracking/mdmt_mia_packets.py` | `REUSE_UNCHANGED` | Wire packet definitions and integrity |
| `src/tracking/packet_census_run_tools.py` | `REUSE_OR_REFACTOR_GENERIC_ONLY` | Canonical hashing/atomic I/O patterns; no historical manifest constants |

The producer and validator may share only declarative schema version/constants and canonical serialization. The validator must independently implement predicate recomputation and reconciliation; it must not call the producer's `evaluate_window_accounting`, `qualify_cell`, or `select_qualified_cell` functions.

## 6 Evidence and schema design

All schemas are versioned, strict, and reject unknown fields unless a future version is separately authorized. JSON integers represent bytes, frame indexes, counts, event ordinals, and cross-products; no floating point is used for qualification.

### 6.1 Raw per-window evidence

Each window record must include:

- schema version, run/cell/pair/capacity/frame identities;
- the exact one-frame window identity, frame-open event ordinal, and frame-close boundary;
- binding budget, bytes served, unused bytes, and backlog/residual totals;
- ordered arrivals and ordered FIFO/in-service snapshots with packet ID, packet sequence, packet type, sender/recipient, wire digest, wire bytes, residual bytes, and event ordinal;
- baseline service events with bytes before/served/after, true-first-service flag, completion flag, and logical completion event;
- true-first-service stale proof with raw predicate inputs, rule/version identity, classification event, and a once-only persistence key;
- source removable-work proof with `source_packet_id`, `source_wire_digest`, `stale_classification_event`, `source_removable_work_bytes`, `source_removable_start_event`, `source_removable_end_event`, `source_baseline_completion_event`, classification frame, and current-frame presence;
- a distinct released-credit ledger with `released_credit_created`, `credit_creation_event`, and, for each frozen FIFO step, `credit_balance_before_fifo_step`, `fifo_consumer_packet_id`, `credit_consumed_by_step`, and `credit_balance_after_step`, followed by `credit_expiration_reason` and `credit_expiration_event`;
- every real baseline receiver-state transition needed to derive event-bounded recipient serviceability intervals, including source event ordinal and raw applicability fields;
- later recipient proof with ID-State type, ordering relation, queried interval/event, event-local serviceability inputs/reason, baseline residual, and baseline logical completion state;
- capacity-caused-incompletion proof distinguishing exhausted binding capacity from mere FIFO waiting;
- conditional-accounting steps over immutable baseline order, with every intervening packet, recipient overlap with the released-credit-available interval, consumed/released/remaining bytes, and recipient residual bytes;
- the individual `WINDOW_ELIGIBLE` predicates, an evidence-complete bit, and reason-coded failure/invalid states;
- baseline and conditional conservation equations;
- a recursive key inventory attesting that forbidden outcome fields are absent.

Producer-derived booleans are conveniences, not authority. Raw evidence sufficient for independent recomputation is mandatory.

The source removable-work record and released-credit ledger are independently reconstructable. Credit creation cannot precede authorized removal and cannot exceed removed stale work. Its only permitted expiration reasons are `FULLY_CONSUMED` and `FRAME_CLOSE`; `SOURCE_BASELINE_COMPLETED` is invalid. Source baseline completion may end source-side removability but cannot erase credit already created.

### 6.2 Aggregate, qualification, and selection separation

Four artifact families remain distinct:

1. `windows.jsonl`: raw per-window baseline and accounting evidence.
2. `cell_aggregate.json`: validity, expected/observed frame domain, `N_all`, `N_stale`, `N_eligible`, nested-count attestation, exact numerator/denominator pairs, and conservation totals.
3. `cell_qualification.json`: the four named booleans `count_pass`, `denominator_pass`, `global_pass`, and `conditional_pass`, their exact threshold identities and integer cross-products, plus overall qualification.
4. `C7_SELECTION.json`: written only after all 21 cells validate and are qualification-evaluated; selection then operates only on the independently reconstructed qualified subset and includes the ordered comparison trace with no weighted score.

Required denominator handling:

- `N_all` is the count of complete, valid census windows in the authorized cell frame domain.
- `N_stale` is the count of those windows containing the exact authorized stale predicate.
- `N_eligible` is the count satisfying every frozen eligibility predicate.
- If `N_stale == 0`, the conditional rate is recorded as `N/A`, its gate is false, and the separately evaluated `T_den` gate is also false. The cell remains a valid measured cell if all evidence is complete.
- Before any qualification gate runs, aggregation and independent validation must prove `0 <= N_eligible <= N_stale <= N_all`, an exact bijection with the authorized one-frame domain, no duplicate contributing window, and no invalid window included in valid counts. Negative counts, `N_stale > N_all`, `N_eligible > N_stale`, frame-domain mismatch, duplication, or invalid-window inclusion makes the cell invalid.

## 7 Manifest / provenance / sealing

The top-level frozen manifest binds:

- all authority hashes listed in Section 1;
- implementation commit and dirty-state rejection;
- source hashes for runtime, producer, validator, child, wrapper, packet definitions, and generated author source;
- schema version and schema hash;
- validator version and hash;
- pair identity, frame count, input paths/digests, and permitted communication-only input classes;
- each capacity and deterministic cell ID;
- config hashes, controlled environment allowlist, output root, and expected artifact inventory;
- outcome-firewall forbidden paths/keys and operational-log policy.

Each cell seal binds the manifest hash, cell launch spec, raw evidence digest, aggregate digest, qualification digest, operational-log digests, validator report digest, source/config/input hashes, and a terminal status. The package seal binds the exact 21-cell inventory and is written only after independent validation succeeds for every cell.

Canonical JSON is UTF-8, sorted keys, compact separators, and a final newline only where the file contract requires it. SHA-256 is used throughout. Seal reproduction is a mandatory qualification check.

## 8 Validator design

The validator is fail closed and operates on files reread from disk, not in-memory producer objects. It performs:

1. strict schema/type/range/unknown-field validation;
2. authority, implementation, generated-source, config, pair, capacity, input, output-root, schema, and validator binding checks;
3. exact manifest bijection and authorized frame-domain checks;
4. packet identity, wire digest, sequence, and event ordinal reconciliation;
5. FIFO transition and true-first-service timing/uniqueness checks;
6. independent stale, same-packet, recipient type/serviceability-interval, source removable-work, released-credit availability, FIFO reachability, capacity-cause, and completion-flip recomputation;
7. independent credit-ledger validation rejecting credit disappearance at source completion, credit before authorized removal, credit greater than removed work, FIFO skipping, negative credit, direct preferred-recipient assignment, insufficient-credit completion, credit after frame close, or next-frame carryover;
8. baseline and conditional byte/work conservation using a non-double-counting ledger: before close, `total released = total consumed + current balance`; at close, the terminal balance is reclassified once as `expired unused`, so `total released = total consumed + expired unused` and post-close balance is zero;
9. no-lookahead validation that every recipient interval state comes from the latest real baseline transition at or before its query point, with event ordinal continuity and rejection of future snapshot/applicability/transition evidence;
10. independent `N_all`, `N_stale`, `N_eligible`, frame-domain bijection, nesting, threshold, and cross-product recomputation before qualification;
11. valid-zero versus invalid separation;
12. forbidden outcome field/path/environment/static-schema scans;
13. atomic terminal marker, inventory, digest, and seal verification;
14. for package selection, independent all-21 completeness, reconstruction of the qualified subset, zero-qualified stop behavior, and exact count/Pareto/stable-order recomputation.

The validator rejects producer labels that disagree with raw evidence. A missing record, duplicate packet classification, unknown packet type, discontinuous ordinal, changed FIFO order, cross-packet byte release, partial-as-complete claim, outcome key, stale digest, extra cell, or unexpected file invalidates the affected cell or whole package as appropriate.

## 9 Exact qualification implementation

Qualification consumes only a validated `cell_aggregate.json`. Planned pseudocode:

```text
count_pass       = (N_eligible >= 5)
denominator_pass = (N_stale >= 20)
global_lhs       = 60 * N_eligible
global_rhs       = N_all
global_pass      = (global_lhs >= global_rhs)
conditional_lhs  = 4 * N_eligible
conditional_rhs  = N_stale
conditional_pass = (N_stale > 0 and conditional_lhs >= conditional_rhs)
qualified        = count_pass and denominator_pass and global_pass and conditional_pass
```

The record persists all counts, both sides of both cross-products, all four gate booleans, the explicit `T_count` and `T_den` rule/version identities, validity, and the overall boolean. It never computes a floating-point rate for authority. Human-readable decimal rates, if ever displayed, are non-authoritative derived presentation and cannot enter selection.

Boundary tests include exact equality, one below, and one above for `T_count=5` and `T_den=20`, both rate boundaries, zero denominators, very large integers, and mutation of each persisted cross-product.

## 10 Selection implementation

Selection is a separate command/function and cannot run until the validator proves a bijection between the frozen 21-cell manifest and 21 valid, qualification-complete records.

Algorithm:

1. assert exactly 21 authorized cells are present and every cell is valid and qualification-evaluated;
2. independently reconstruct `qualified_candidates = [cell for cell in cells if CELL_QUALIFIED == YES]` from raw counts and the four gates;
3. if the qualified subset is empty, emit `NO_CELL_SELECTED`, emit no ranking winner, do not expand the grid, and stop;
4. otherwise retain only qualified candidates with the maximum `N_eligible`;
5. compare only that count-tied set using exact rational cross multiplication on global and conditional numerator/denominator pairs;
6. remove a count-tied cell only when another is no worse on both rates and strictly better on at least one;
7. if a Pareto tradeoff/tie remains, apply stable pair order `P23`, `P44`, `P66`, then the frozen ascending capacity order, then lexical stable `cell_id`;
8. emit the full comparison trace, qualified subset, candidate set after each step, and selected manifest identity.

The implementation contains no weight parameter, score field, normalization, or configurable tie-break. Static tests reject those schema keys.

## 11 Test architecture

The required four-layer pyramid is:

### Layer 1: unit tests

- exact stale predicate and once-only persistence;
- exact one-frame window boundaries from frame-open ordinal through frame-close and authorized-domain bijection;
- true-first-service timing boundary;
- observed-baseline recipient serviceability interval construction and transition boundaries;
- `recipient_interval_future_state_injection`, distinct from source sticky classification, covering future receiver-state snapshot, future applicability field, future serviceability transition, and event-ordinal mismatch/lookahead;
- same-packet residual linkage;
- source removable-work start/end and amount, independently from released-credit creation/balance/expiration;
- released credit surviving source baseline completion until consumption or frame close, plus forbidden source-completion expiration;
- credit creation only after authorized removal, byte upper bound, non-negativity, frame-close expiry, and no cross-frame carryover;
- permitted recipient type and serviceability proof;
- capacity-caused incomplete versus waiting-only;
- strict FIFO propagation through intervening packets and temporal-overlap gating;
- logical completion versus partial bytes;
- accounting conservation and immutable ordering/state inputs;
- valid zero versus invalid and `0 <= N_eligible <= N_stale <= N_all` with all fail-closed count/domain mutations;
- exact qualification integer boundaries;
- qualified-subset reconstruction, zero-qualified no-selection/stop, and count/Pareto/stable selection;
- manifest, hash, schema, and forbidden-key validation.
- MVE structural-status allowlist across artifacts/temp/debug/cache/log/stdout/stderr/exception/diagnostic channels, with injected count/rate/qualification/ranking leakage;
- MVE authorization rationale allowlist and rejection of outcome-informed slice-selection fields.

### Layer 2: tiny synthetic E2E

Runs through the real C7 parent launcher, C7 child, existing wrapper boundary, generated runtime, writer, disk reread, and independent validator. It is not a shortcut that calls the evaluator directly.

### Layer 3: outcome-blind MVE

Uses the real production path and a separately authorized minimal real input slice. It proves path identity, evidence sufficiency, schema/firewall behavior, deterministic rerun, and seal reproduction. It does not read or compute tracking outcomes and is not one of the 21 census cells.

### Layer 4: later qualification

Only after implementation authorization, unit/E2E/MVE success, and independent audit. It verifies exact sources/configs/inputs/output root, all negative controls, manifest completeness, and production path parity before any 21-cell census launch can be authorized.

No test may recover forbidden material from Git objects/history or depend on previous C6 result artifacts.

## 12 Tiny synthetic E2E

Planned fixture: `tests/fixtures/run_mdmt_mia_c7_tiny_runtime.py`. It generates only synthetic packet/state evidence and declares `synthetic_non_scientific=true`.

Required deterministic cases:

- valid zero: complete evidence, no eligible window;
- exact positive: stale ID-State consumes binding bytes and the same packet's released accounting permits a later serviceable ID-State logical completion in the same window;
- one-byte-short: conditional recipient remains incomplete;
- wrong recipient type: Supplement/local/homography cannot qualify;
- waiting-only: capacity-cause predicate remains false;
- source future-state mutation: sticky first-service stale class is unchanged;
- recipient future-state injection: a query at `e_k` rejects receiver-state, applicability, or serviceability-transition evidence from `e_(k+1)` or later, including ordinal mismatch/lookahead; eligibility is not derivable and the affected window/cell fails closed under the schema contract;
- source/credit boundaries: same-frame classification, prior-frame persisted residual, source-obligation exhaustion, independent credit lifetime, frame-close expiry, and forbidden cross-frame credit;
- `released_credit_survives_source_baseline_completion`: in one frame, at `e10` A is classified `SUPPRESSIBLE_STALE`, 60 authorized bytes are removed, and credit becomes 60; A reaches real baseline completion at `e20`; with no intervening consumer, at `e25` serviceable FIFO-reachable B needs 40 bytes before frame close `e30`. Assert source removable-work ends at `e20`, credit at `e25` remains 60, baseline B completion is `NO`, conditional B completion is `YES`, and B is not rejected because the source interval ended;
- `released_credit_consumed_by_intervening_fifo_work`: A creates 60 credit; later valid FIFO packet C needs and consumes 50 before B; credit reaching serviceable B is 10 while B needs 20. Assert no FIFO skip, conditional B completion is `NO`, completion flip is `NO`, and B cannot make the window eligible;
- fault injection: missing event, duplicate classification, altered digest, cross-packet release, reordered FIFO, partial-as-complete, outcome-key injection, and interrupted write;
- aggregate fault injection: negative count, `N_stale > N_all`, `N_eligible > N_stale`, duplicate window, frame-domain mismatch, and invalid window included as valid;
- resume: an already sealed matching cell is verified and skipped; an incomplete staged cell is quarantined and recomputed.

The fixture must demonstrate that the exact same launcher/child/wrapper/runtime/writer/validator components are used by later production execution. Only the synthetic packet source and tiny frame domain differ.

## 13 Outcome-blind MVE

The MVE is a separately authorized path qualification step, not a scientific census or selection. `MVE_IS_CENSUS_CELL=NO`, `MVE_SCIENTIFIC_INTERPRETATION=FORBIDDEN`, `MVE_SELECTION=FORBIDDEN`, and `MVE_CELL_QUALIFICATION=FORBIDDEN`. Before it runs, its launch record must bind one registered pair, an explicitly authorized tiny frame prefix, one frozen capacity, all source/schema/validator hashes, and an isolated `MVE_ONLY` output root. Its cell identity is forbidden from the 21-cell manifest.

Success criteria:

- real generated author source and real wrapper used;
- no C6 suppression treatment environment present;
- C4 baseline trace unchanged except additive passive evidence;
- C7 evidence complete enough for independent recomputation;
- static and dynamic outcome-firewall scans pass;
- two clean executions are byte/digest deterministic except explicitly normalized run/timestamp fields;
- validator and seal reproduction pass;
- deliberate negative controls fail closed.

The MVE embargo covers intermediate artifacts, temporary files, debug output, stdout/stderr, operator-visible logs, exception dumps, diagnostic tables, and cached intermediate summaries. Operator-visible output is allowlisted to structural/path status such as `PATH_VALID`, `SCHEMA_VALID`, `VALIDATOR_PASS`, `FIREWALL_PASS`, `SEAL_REPRODUCED`, and `DETERMINISTIC_RERUN_PASS`. It must not expose `N_eligible`, `N_stale`, either opportunity frequency, `would_qualify`, selected/not-selected state, cell ranking, or preliminary scientific interpretation. Mechanically necessary internal values must remain access-controlled, non-authoritative, and unavailable as an informal pre-census observation channel.

The exact real pair/frame prefix must be named by the later MVE authorization; this plan does not silently choose it. The authorization must record its selection criterion before execution. Permitted criteria are engineering/availability only: smallest available valid prefix, runtime affordability, input availability, path coverage, deterministic fixture compatibility, or operational convenience. Prior or preliminary stale prevalence, recipient coexistence, `N_stale`, `N_eligible`, opportunity/conditional rates, `would_qualify`, or scientific desirability are forbidden selection inputs.

## 14 Qualification path

Later qualification must verify, in order:

1. clean implementation commit and exact frozen authority chain;
2. source-to-generated-runtime digest binding;
3. exact 21-cell manifest and configs;
4. unit test suite;
5. tiny synthetic E2E including negative controls;
6. outcome-blind MVE and deterministic rerun;
7. producer/validator independence and disk-reread boundary;
8. schema/firewall scans over source, config, environment, and emitted artifacts;
9. atomicity/resume fault tests;
10. reproducible inventory and seals;
11. independent audit approval.

Qualification writes only a qualification package. It does not run any census cell. Census launch requires a later exact-run authorization bound to the qualified implementation commit and frozen manifest.

## 15 Resume / restart / atomicity

Output layout is immutable by `run_id/cell_id`. Each cell executes in a sibling staging directory created exclusively. The final cell directory appears only by atomic rename after the child exits successfully, all expected files are closed, the validator passes, digests are computed, and the terminal commit marker is written last.

Resume rules:

- matching sealed final cell: reread and fully validate, then skip;
- mismatched authority/config/source/input/schema/validator hash: hard fail, never overwrite;
- incomplete staging directory: quarantine under a reason-coded non-authoritative name, then recompute from scratch;
- final directory without valid last-written terminal marker: invalid and quarantined;
- failed child or validator: preserve only operational diagnostics outside the authoritative evidence inventory; no aggregate/qualification seal;
- package resume: rebuild the inventory from verified cell seals; never trust a cached cell list.

No append-in-place is allowed for authoritative JSON/JSONL. Window evidence is first written to a staged file, flushed and closed, then hashed and committed with the cell transaction.

## 16 Outcome-firewall controls

Allowed content is communication-path evidence: packet metadata/digests/types, frame and event indexes, FIFO/service bytes, finite-capacity accounting, event-local applicability/serviceability inputs, predicate proofs, conservation, authority/config/input/source hashes, validation results, and operational process status.

Forbidden content includes tracking outcomes, identity metrics, detection/tracking quality, ID switches, IDF1/MOTA-like fields, selected scientific result narratives, C6 formal scientific outcomes, or any field/path that reveals them.

Controls:

- parent launcher starts from an allowlisted environment and rejects forbidden variables;
- child receives only bound communication inputs and observational C7 config;
- no evaluator imports tracking metric/evaluation modules;
- strict schema rejects unknown fields;
- recursive key/path scan runs before validation and sealing;
- source-level dependency test rejects outcome readers and result-summary paths;
- operational logs are separated from authoritative evidence and limited to command identity, progress, return code, timings, paths, and digests;
- exception text is sanitized to avoid dumping arbitrary payloads;
- output root pollution and unexpected file checks fail closed;
- MVE and later launch preflight confirm forbidden outcome files are absent and never recover them through Git/history/other worktrees;
- MVE stdout/stderr, logs, temp/debug/cache artifacts, exception dumps, and diagnostic tables pass an allowlist scan that exposes structural/path status only and rejects census counts, rates, qualification/selection hints, rankings, or interpretation;
- MVE authorization validation rejects any slice-selection rationale based on stale prevalence, recipient coexistence, opportunity counts/rates, qualification likelihood, or scientific desirability;
- selection consumes only validated C7 count/rate records.

## 17 Risk register

| Risk | Prevention | Detection | Fail-closed response | Required test |
| --- | --- | --- | --- | --- |
| 1. Wrong first-service timing | Hook after FIFO select, before byte deduction | Residual equals full pre-service packet; no prior service event | Invalidate cell | boundary instrumentation test |
| 2. Source future-state reclassification | Once-only packet key and immutable record | duplicate/classification-event scan | Invalidate cell | source sticky-class future-state mutation test |
| 2a. Recipient interval lookahead | Construct intervals only from ordered real baseline state transitions at/before query | Independent raw ordinal/state provenance reconstruction | Invalidate affected window/cell | `recipient_interval_future_state_injection` with all four fault variants |
| 3. Cross-packet residual attribution | Bind release to packet ID + wire digest | Ledger reconciliation | Invalidate window/cell | substituted packet negative |
| 4. Ineligible recipient type | Explicit ID-State enum allowlist | Independent packet decode | Predicate false or invalid on unknown | Supplement/local/homography cases |
| 5. Serviceability interval misconstruction | Apply the governed observed-baseline trajectory-interval model in Section 2 | Validator recomputation from raw real transitions | Invalidate affected window/cell | queued-unserved recipient interval-boundary cases |
| 5a. Source work and credit lifetime conflation | Model source removable work and released credit as separate ledgers; source completion is not a credit expiry | Independent reconstruction across source completion | Invalidate window/cell | `released_credit_survives_source_baseline_completion` and forbidden expiry reason |
| 5b. Credit creation/consumption/carryover corruption | Bind creation to removed bytes, propagate every FIFO step, expire remainder only at close | Byte conservation, FIFO sequence, non-negativity, frame-bound checks | Invalidate window/cell | premature/over-credit, intervening-consumer, negative, direct-assignment, and cross-frame negatives |
| 6. Waiting mistaken for capacity loss | Require exhausted budget plus exact residual/cause proof | Budget/work equation | Predicate false | waiting-only case |
| 7. Conditional accounting becomes replay/treatment | Pure function over frozen evidence; no runtime callback/import | dependency/static scan and baseline digest comparison | Abort qualification | mutation/reordering spies |
| 8. Partial bytes counted complete | Logical residual must reach exactly zero | Independent arithmetic | Predicate false/invalid | one-byte-short test |
| 9. Valid zero confused with missing evidence | Explicit validity enum and expected frame bijection | completeness scan | Invalid, never zero | valid-zero vs missing-window test |
| 10. Threshold drift/float error | Literal frozen integers and cross multiplication | independent recomputation | Qualification invalid | exact boundary vectors |
| 10a. Count nesting/domain corruption | Validate one-frame domain bijection and nested counts before gates | Independent aggregate reconstruction | Cell invalid before qualification | negative, over-nested, duplicate, domain, invalid-window mutations |
| 11. Premature/weighted selection | Separate command gated on all 21; schema forbids weights | manifest bijection and key scan | No selection output | missing-cell/weight-key tests |
| 12. Provenance or generated-source drift | Bind all source/config/input/schema/validator hashes | disk reread + seal reproduction | Reject launch/package | one-hash-at-a-time tamper matrix |
| 13. Outcome contamination | allowlists, strict schema, dependency/key/path/environment scans | static + runtime firewall validator | Abort, no authoritative seal | injected outcome field/path/env/import cases |
| 13a. MVE informal outcome channel | Structural-status-only output allowlist across all internal/operator-visible channels | Scan artifacts/logs/stdout/stderr/temp/cache/exception content | Abort MVE qualification; no seal | forbidden count/rate/qualification/ranking leakage matrix |

## 18 Milestones

| Milestone | Objective | Exit criterion |
| --- | --- | --- |
| M0 | Authority and change-boundary lock | Independent plan audit accepts authority chain and classifications |
| M1 | Declarative schema, manifest, and frozen constants | Schema review proves every required field and exact rule is representable |
| M2 | Passive runtime observation hooks | Existing C4 behavior tests unchanged; hook timing/immutability proven |
| M3 | Predicate, sticky classification, and governed recipient-interval core | All source and recipient temporal predicate tests pass with OQ-1 closed |
| M4 | Separate source-removable-work and released-credit accounting plus conservation | Pure accounting and independent recomputation agree, including both corrective tiny-E2E cases |
| M5 | Aggregation and exact four-gate qualification | Valid-zero/invalid separation and all integer boundary vectors pass |
| M6 | Cross-cell selection | All-21 gate and count/Pareto/stable ordering pass exhaustive tie cases |
| M7 | Evidence writer, provenance, inventory, seals, and real launcher path | interruption/tamper/resume matrix and canonical path/source binding pass |
| M8 | Independent fail-closed validator | All producer-label, evidence, firewall, and provenance mutations detected |
| M9 | Focused unit/integration suite | Required Layer 1 suite and unchanged C4 regressions pass cleanly |
| M10 | Tiny synthetic E2E | Real-path positive/zero/negative/fault/resume cases pass |
| M11 | Outcome-blind MVE path | Separately authorized MVE and deterministic rerun qualify |
| M12 | Qualification package preparation | Exact qualification procedure and negatives are reproducible; census not run; audit bundle ready |

## 19 Per-milestone file/change boundaries

Every milestone requires separate implementation authorization. “Scientific read” and “outcome read” are `NO` for every milestone.

| Milestone | Permitted files / change | Forbidden | Verification | Scientific read | Outcome read | Exit |
| --- | --- | --- | --- | --- | --- | --- |
| M0 | Authority inventory and implementation branch metadata only | Frozen spec edits; runtime/code changes | hashes, clean base, audit checklist | NO | NO | authority accepted |
| M1 | New C7 schema/constants module and schema tests | runtime behavior; launcher execution | schema/manifest/threshold unit tests | NO | NO | representational completeness |
| M2 | Minimal additive edits to async deadline runtime; hook tests | C6 treatment reuse; FIFO/state changes | existing C4 regressions + timing tests | NO | NO | behavioral parity |
| M3 | C7 predicate and observed-trajectory interval functions/tests | accounting replay; synthetic first-service events; future/counterfactual state; outcome imports | exhaustive source/recipient temporal predicate cases | NO | NO | governed interval model and tests pass |
| M4 | Pure source-removable-work and released-credit ledger functions/tests | source-completion credit expiry, packet reschedule, AoI/predictive/RL, treatment | conservation/determinism, credit-lifetime, FIFO-consumption, and mutation tests | NO | NO | separate-state accounting semantics proven |
| M5 | Aggregate and qualification functions/tests | selection; launcher execution | valid-zero/invalid + four-gate exact boundaries | NO | NO | exact qualification complete |
| M6 | Selection function/schema/tests | selection before all 21 valid/qualified; weights | count/Pareto/stable-order exhaustive cases | NO | NO | deterministic selection contract |
| M7 | Writer/manifest/seal utilities, new C7 parent/child, path tests | census launch; overwrite; C6 treatment config | fault/tamper/resume + synthetic canonical path | NO | NO | atomic real path proven |
| M8 | Independent validator/tests | calls into producer-derived predicates | evidence/provenance/firewall mutation matrix | NO | NO | fail-closed coverage |
| M9 | C7 focused unit/integration tests only | real data execution | isolated suite + unchanged C4 suite | NO | NO | Layer 1 complete |
| M10 | C7 tiny fixture/E2E tests and synthetic temp outputs | real input, outcome files | full real-path synthetic E2E | NO | NO | Layer 2 complete |
| M11 | MVE authorization/config and isolated MVE artifacts | 21-cell outputs; tracking evaluation | firewall, deterministic rerun, seals | NO | NO | Layer 3 complete |
| M12 | Qualification scripts/records and read-only audit bundle | census execution, selection execution, author self-approval | exact qualification dry run, negatives, independent-review handoff | NO | NO | package ready; author stops |

No milestone may modify `EXPERIMENT_CONTRACT.md`, either corrective specification revision, either freeze record, or the provenance authority. Any proposed frozen-authority change terminates this plan path and requires new governance rather than an implementation patch.

## 20 Explicit non-goals

- No C7 implementation in this plan-authoring change.
- No test/schema/config/runtime creation or modification in this change.
- No qualification, MVE, census cell, 21-cell sweep, aggregation, or selection execution.
- No tracking evaluation or outcome access.
- No revision of thresholds, pairs, frames, capacities, predicates, tie-breaks, or authority hashes.
- No reuse of C6 suppression as conditional accounting.
- No intervention, replay, rescheduling, AoI mutation, predictive method, RL policy, adaptive selector, or full OOSM framework design.
- No scientific interpretation of whether C7 will pass.
- No claim that a qualified C7 cell supports causal `H_R`, demonstrates real intervention redistribution, improves tracking, decreases ID switches, or improves IDF1/MOTA/HOTA-like outcomes.
- No design or execution of the separately governed later real-suppression `H_R` Formal.
- No independent audit performed by the plan author.

## 21 Implementation authorization boundary

This plan does not authorize implementation. `IMPLEMENTATION_AUTHORIZED=NO`. After Corrective Revision 2, the only permitted next step is `INDEPENDENT_C7_CORRECTIVE_REVISION_2_DELTA_AUDIT`.

Implementation may begin only after an independent audit explicitly approves this exact plan commit or an audited corrective plan supersedes it. Implementation authorization must name the exact implementation base, allowed files, allowed milestone(s), verification commands, outcome-firewall preflight, and stopping condition. Authorization for one milestone does not imply authorization for later milestones, MVE, qualification, census, or selection.

Any implementation discovery classified as `POTENTIAL_SPEC_CONFLICT` must stop at the affected milestone and return to governance. An `IMPLEMENTATION_DETAIL` may be resolved inside the frozen semantics if documented, tested, and included in the independent audit delta.

## 22 Open engineering questions

OQ-1 is not open and is not a potential specification conflict:

```text
OQ1_STATUS = CLOSED_BY_GOVERNANCE_CLARIFICATION
OQ1_REQUIRES_NEW_RD = NO
RECIPIENT_SERVICEABILITY_MODEL = OBSERVED_BASELINE_TRAJECTORY_INTERVALS
SYNTHETIC_FIRST_SERVICE_EVENT = FORBIDDEN
FUTURE_STATE = FORBIDDEN
COUNTERFACTUAL_REPLAY = FORBIDDEN
```

| ID | Classification | Question | Required resolution / gate |
| --- | --- | --- | --- |
| OQ-2 | `IMPLEMENTATION_DETAIL` | Is the existing generated-runtime manifest/cache invalidation sufficient when the runtime digest changes, or is an explicit C7 cachebuster field needed? | Resolve during M7 path tests; bind generated source digest either way. |
| OQ-3 | `IMPLEMENTATION_DETAIL` | Which registered pair and exact tiny frame prefix will be used for the non-scientific MVE? | Later MVE authorization must name it before execution using documented engineering/availability-only selection criteria; do not choose during implementation. |
| OQ-4 | `IMPLEMENTATION_DETAIL` | Exact CLI spelling for resume/quarantine/dry-run modes. | Freeze in M5/M7 interface tests without changing atomicity semantics. |

Open engineering item count: `3`.

Potential specification conflict count: `0`.

The OQ-1 closure is a governance clarification of the frozen mechanics, not a new research decision or changed scientific semantic.

## 23 Independent audit handoff

The independent auditor should receive:

- this exact Corrective Revision 2 Plan commit, its clean delta from parent Plan commit `56966b9256f761983870c2b1db285a050ba62a57`, and the full Plan lineage from freeze `0eda32c58871c1ec4b5b194c0c33608d7dd2a777`;
- the frozen authority files and verified hashes from Section 1;
- the complete specification-to-code traceability table;
- the architecture and producer/validator separation;
- schema field families and all exact threshold/selection algorithms;
- the four-layer test plan, risk register, and M0–M12 boundaries;
- the complete inspected-path inventory;
- explicit confirmation that no forbidden outcome material was read;
- the eight-finding Corrective Revision 1 disposition table, the `P1-CR1-01` Corrective Revision 2 record, and OQ-1 closed-state encoding.

Audit questions:

1. Does every frozen requirement map to a concrete implementation/evidence/validator/test/failure path?
2. Is the proposed runtime hook purely observational and placed at the exact true-first-service boundary?
3. Can the validator recompute eligibility without trusting producer labels?
4. Is conditional accounting demonstrably distinct from replay or treatment?
5. Are valid zero, invalid evidence, qualification, and selection cleanly separated?
6. Are production-path parity, atomicity, resume, provenance, and outcome firewall sufficiently fail closed?
7. Does the corrected Plan faithfully encode the already-issued OQ-1 governance clarification without reopening it or creating a new RD?
8. Is the upstream `C7 -> candidate -> separately governed real Formal -> causal H_R evaluation` claim boundary explicit and preserved?
9. Are source removable work and released capacity credit independently reconstructable, with source completion unable to expire already released same-frame credit?
10. Do the credit ledger, validator, and two tiny-E2E cases prove strict FIFO consumption, sufficient-credit completion, frame-close expiry, and no cross-frame carryover?

The author must not perform this independent audit. After committing this plan, work stops.

Plan-author self-audit before commit:

```text
FROZEN_SPEC_CHANGED = NO
NEW_RESEARCH_DECISION = NO
SCIENTIFIC_SEMANTICS_CHANGED = NO
OQ1_REOPENED = NO
OQ1_STATUS = CLOSED_BY_GOVERNANCE_CLARIFICATION
OQ1_REQUIRES_NEW_RD = NO
THIRD_PARTY_FINDINGS_DISPOSITIONED = 8/8
P1_CR1_01_STATUS = RESOLVED
SOURCE_REMOVABLE_WORK_DISTINCT_FROM_RELEASED_CREDIT = YES
SOURCE_BASELINE_COMPLETION_EXPIRES_CREDIT = NO
RELEASED_CREDIT_PERSISTS_UNTIL_CONSUMED_OR_FRAME_CLOSE = YES
RELEASED_CREDIT_EXPIRES_AT = FULL_CONSUMPTION_OR_FRAME_CLOSE
CROSS_FRAME_CREDIT_CARRYOVER = NO
FIFO_PROPAGATION_PRESERVED = YES
DIRECT_RECIPIENT_ASSIGNMENT = NO
LATE_SAME_FRAME_RECIPIENT_CAN_USE_PREVIOUSLY_RELEASED_UNUSED_CREDIT = YES
TINY_E2E_CREDIT_SURVIVES_SOURCE_COMPLETION_PLANNED = YES
TINY_E2E_INTERVENING_FIFO_CONSUMES_CREDIT_PLANNED = YES
P1_1_INHERITED_FROM_UPSTREAM_AUTHORITY = YES
P1_1_REQUIRES_NEW_RD = NO
RECIPIENT_TRAJECTORY_FUTURE_STATE_NEGATIVE_TEST_PLANNED = YES
WINDOW_EXACTLY_ONE_FRAME = YES
REMOVABILITY_BOUNDARY_EXPLICIT = YES
C7_QUALIFIED_NOT_EQUAL_H_R_SUPPORTED = YES
MVE_INTERNAL_ARTIFACT_EMBARGO_PLANNED = YES
MVE_SLICE_SELECTION_OUTCOME_BLIND = YES
COUNT_NESTING_INVARIANTS_PLANNED = YES
QUALIFIED_SUBSET_SELECTION_EXPLICIT = YES
ZERO_QUALIFIED_BRANCH_EXPLICIT = YES
T_DEN_GATE_EXPLICIT = YES
THRESHOLDS_CHANGED = NO
PAIR_SET_CHANGED = NO
CAPACITY_GRID_CHANGED = NO
ELIGIBILITY_CHANGED = NO
SELECTION_CHANGED = NO
OUTCOME_FIREWALL_WEAKENED = NO
REAL_EXECUTION_PATH_PLANNED = YES
TINY_E2E_PLANNED = YES
OUTCOME_BLIND_MVE_PLANNED = YES
FAIL_CLOSED_VALIDATOR_PLANNED = YES
RESUME_SEMANTICS_PLANNED = YES
IMPLEMENTATION_STARTED = NO
```
