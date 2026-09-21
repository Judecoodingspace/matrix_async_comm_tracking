# C7 Outcome-Blind Eligibility Census Implementation Plan

Status: `READY_FOR_INDEPENDENT_PLAN_AUDIT`

This document is an implementation plan only. It does not authorize or contain an implementation, qualification execution, census execution, outcome read, or scientific decision revision.

## 1 Purpose and authority

The purpose of this plan is to translate the frozen C7 corrective pre-census specification into an auditable implementation path for an outcome-blind, observational eligibility census. The implementation must determine whether an authorized suppressible stale ID-State packet creates a same-window, same-packet-residual opportunity for a later serviceable ID-State packet to complete under conditional accounting, while leaving the real baseline runtime unchanged.

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

## 2 Frozen scientific boundary

The following requirements are immutable implementation inputs.

### 2.1 Fixed census grid

- Pair IDs: `P23`, `P44`, `P66`.
- Frame counts: `700`, `360`, `300`, respectively.
- Binding capacities: `16649`, `20147`, `25456`, `26148`, `28109`, `29620`, `31987`.
- The census manifest is the immutable Cartesian product of the three pair/frame definitions and seven capacities: exactly 21 cells.
- Cell identity is a stable tuple `(pair_id, capacity_bytes_per_frame, frame_count)` plus a deterministic `cell_id`.

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

### 2.4 Qualification and selection separation

Per-cell qualification is evaluated independently. Cross-cell selection is forbidden until all 21 manifest cells are present, valid, and qualification-complete. Selection then uses this exact ordering:

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

The current C4 ledger proves many byte and identity invariants but does not yet record every ordered FIFO snapshot or complete event-local serviceability evidence for every possible later ID-State recipient. This is the principal implementation gap. It must be closed observationally without changing the binding server's scheduling or state transitions.

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
| Ordered event and FIFO snapshot | C4 event ordinal and queue | `src/tracking/mdmt_mia_async_deadline_runtime.py` passive `PROPOSED_NEW: _notify_c7_event` | Immutable event data and queue view | Ordered per-event snapshots | Check ordinal continuity and transition legality | Queue corruption negatives | Window/cell invalid |
| True first service after select/before byte | `_start_next` then `_serve`; C5 timing pattern | Passive callback to `PROPOSED_NEW: C7CensusObserver.observe_true_first_service` | Packet, pre-byte residual, receiver snapshot | Once-only classification record | Verify no prior served bytes; uniqueness; packet digest | Timing boundary unit tests | Cell invalid on absent/duplicate/late record |
| Sticky authorized stale proof | Existing pure applicability concepts | `src/tracking/mdmt_mia_c7_census.py` `PROPOSED_NEW: classify_authorized_stale_once` | ID-State payload, event-local state, authority rule ID | Predicate inputs, booleans, reason code | Recompute from raw fields; ignore producer label | stale/non-stale/future-state mutation cases | Invalid evidence, never inferred zero |
| Same-packet residual linkage | C4 `remaining_service_bytes`, packet ID/digest | `PROPOSED_NEW: derive_same_packet_release` | True-first record and baseline service events | source packet ID/digest, pre/post residual, released bytes | Cross-check all bytes against that packet's ledger | cross-packet substitution negative | Window invalid |
| Recipient type and serviceability | Packet type; baseline state snapshots | `PROPOSED_NEW: evaluate_recipient_serviceability` | Later immutable FIFO entry and event-local baseline snapshot | packet type, reason-coded serviceability proof | Recompute type and predicate fields | Supplement/local/homography rejection; serviceability cases | Window invalid if proof absent |
| Baseline incomplete due binding capacity | Frame budget, residual, queue, completion ledger | `PROPOSED_NEW: prove_capacity_caused_incompletion` | Frame close ledger and recipient residual | budget exhaustion, bytes needed, baseline completion=false | Check capacity conservation and distinguish waiting-only | capacity exhausted vs waiting-only cases | Predicate false or invalid if evidence incomplete |
| Conditional accounting only | No existing treatment-safe C7 evaluator | `src/tracking/mdmt_mia_c7_census.py` `PROPOSED_NEW: evaluate_window_accounting` | Frozen baseline ledger/snapshots only | accounting steps, released/allocated bytes, no mutation proof | Independently recompute from raw baseline evidence | determinism, no replay, no state mutation tests | Window invalid on non-conservation or changed order |
| Same-window completion flip | C4 logical completion semantics | `PROPOSED_NEW: evaluate_completion_flip` | Baseline residual and conditional allocation | baseline complete=false, conditional complete=true, exact logical boundary | Recompute residual arithmetic; partial is false | exact/one-byte-short/partial cases | Predicate false; invalid on inconsistent arithmetic |
| Conservation completeness | `seal_evidence` | Existing seal plus C7 validator invariants | Per-event and per-window bytes/work | baseline and conditional conservation blocks | Full independent sum/reconciliation | missing/duplicate/corrupt event negatives | Cell invalid |
| Valid zero vs invalid | Strict reader patterns | `PROPOSED_NEW: aggregate_cell` | Complete validated window set | validity enum, counts including zero, invalid reason list | Require complete expected frame domain before counts | valid-zero and missing-evidence tests | Invalid never serialized as zero-qualified |
| Exact thresholds | None C7-specific | `PROPOSED_NEW: qualify_cell` | integer `N_all`, `N_stale`, `N_eligible` | four gate booleans, including `T_count` and `T_den`, and exact cross-products | Recompute integer formulas | boundary vectors for 4/5, 19/20, 59/60, 3/4 and exact passes | Qualification invalid on bad denominators/schema |
| Qualification before selection | Existing packaging pattern only | `PROPOSED_NEW: validate_all_cells_qualified` | frozen manifest and 21 cell qualification records | completeness record | Exact manifest bijection | missing/extra/duplicate cell tests | No selection artifact written |
| Count/Pareto/stable selection | None C7-specific | `PROPOSED_NEW: select_qualified_cell` | 21 valid qualification records | separate `C7_SELECTION.json` with comparison trace | Independent sort/Pareto recomputation | count, Pareto, incomparable/stable tie cases | Fail closed on ambiguity or weights |
| Outcome firewall | Communication-only C6 path pattern | launcher allowlist plus `PROPOSED_NEW: reject_forbidden_schema_fields` | configs, environment, artifacts | firewall attestation and schema key inventory | Static recursive forbidden-key/path scan | injected outcome key/path negatives | Abort/delete incomplete temp output; no seal |
| Atomic writes and resume | `_atomic_write`, exclusive writes | C7 writer `PROPOSED_NEW: write_cell_transaction` | validated staged artifacts | temp-to-final commit marker, digest inventory | Verify marker last and all digests | interruption/resume tests | Quarantine/recompute incomplete cell |
| Authority/config/provenance sealing | Generated/runtime manifests and C6 packaging pattern | `PROPOSED_NEW: seal_census_package` | source/config/input/output/schema/validator hashes | canonical inventory and seal | Independent seal reproduction | tamper every binding class | Package invalid |

The mapping is complete at plan level: every frozen predicate, aggregation rule, qualification rule, selection rule, and firewall constraint has an implementation point, evidence field family, validator action, test family, and fail-closed behavior. One event-timing issue remains explicitly governed in Section 22; it is not silently resolved here.

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
- frame-open and frame-close event ordinal bounds;
- binding budget, bytes served, unused bytes, and backlog/residual totals;
- ordered arrivals and ordered FIFO/in-service snapshots with packet ID, packet sequence, packet type, sender/recipient, wire digest, wire bytes, residual bytes, and event ordinal;
- baseline service events with bytes before/served/after, true-first-service flag, completion flag, and logical completion event;
- true-first-service stale proof with raw predicate inputs, rule/version identity, classification event, and a once-only persistence key;
- same-packet release proof with the stale source packet ID/digest and exact residual/service arithmetic;
- later recipient proof with ID-State type, ordering relation, event-local serviceability inputs/reason, baseline residual, and baseline logical completion state;
- capacity-caused-incompletion proof distinguishing exhausted binding capacity from mere FIFO waiting;
- conditional-accounting steps over immutable baseline order, with released, allocated, remaining, and recipient residual bytes;
- the individual `WINDOW_ELIGIBLE` predicates, an evidence-complete bit, and reason-coded failure/invalid states;
- baseline and conditional conservation equations;
- a recursive key inventory attesting that forbidden outcome fields are absent.

Producer-derived booleans are conveniences, not authority. Raw evidence sufficient for independent recomputation is mandatory.

### 6.2 Aggregate, qualification, and selection separation

Four artifact families remain distinct:

1. `windows.jsonl`: raw per-window baseline and accounting evidence.
2. `cell_aggregate.json`: validity, expected/observed frame domain, `N_all`, `N_stale`, `N_eligible`, exact numerator/denominator pairs, and conservation totals.
3. `cell_qualification.json`: `T_count`, global, and conditional threshold booleans plus integer cross-products and overall qualification.
4. `C7_SELECTION.json`: written only after all 21 cells validate and qualify; includes the ordered comparison trace and no weighted score.

Required denominator handling:

- `N_all` is the count of complete, valid census windows in the authorized cell frame domain.
- `N_stale` is the count of those windows containing the exact authorized stale predicate.
- `N_eligible` is the count satisfying every frozen eligibility predicate.
- If `N_stale == 0`, the conditional rate is recorded as `N/A`, its gate is false, and the separately evaluated `T_den` gate is also false. The cell remains a valid measured cell if all evidence is complete.

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
6. independent stale, same-packet, recipient type/serviceability, capacity-cause, and completion-flip recomputation;
7. baseline and conditional byte/work conservation;
8. independent `N_all`, `N_stale`, `N_eligible`, threshold, and cross-product recomputation;
9. valid-zero versus invalid separation;
10. forbidden outcome field/path/environment/static-schema scans;
11. atomic terminal marker, inventory, digest, and seal verification;
12. for package selection, independent all-21 completeness and exact count/Pareto/stable-order recomputation.

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

1. retain the maximum `N_eligible` set;
2. compare tied cells using exact rational cross multiplication on global and conditional numerator/denominator pairs;
3. remove a tied cell only when another is no worse on both rates and strictly better on at least one;
4. if a Pareto set remains, apply stable pair order `P23`, `P44`, `P66`, then the frozen ascending capacity order, then lexical stable `cell_id`;
5. emit the full comparison trace, candidate set after each step, and selected manifest identity.

The implementation contains no weight parameter, score field, normalization, or configurable tie-break. Static tests reject those schema keys.

## 11 Test architecture

The required four-layer pyramid is:

### Layer 1: unit tests

- exact stale predicate and once-only persistence;
- true-first-service timing boundary;
- same-packet residual linkage;
- permitted recipient type and serviceability proof;
- capacity-caused incomplete versus waiting-only;
- logical completion versus partial bytes;
- accounting conservation and immutable ordering/state inputs;
- valid zero versus invalid;
- exact qualification integer boundaries;
- count/Pareto/stable selection;
- manifest, hash, schema, and forbidden-key validation.

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
- future-state mutation: sticky first-service class is unchanged;
- fault injection: missing event, duplicate classification, altered digest, cross-packet release, reordered FIFO, partial-as-complete, outcome-key injection, and interrupted write;
- resume: an already sealed matching cell is verified and skipped; an incomplete staged cell is quarantined and recomputed.

The fixture must demonstrate that the exact same launcher/child/wrapper/runtime/writer/validator components are used by later production execution. Only the synthetic packet source and tiny frame domain differ.

## 13 Outcome-blind MVE

The MVE is a separately authorized path qualification step, not a scientific census or selection. Before it runs, its launch record must bind one registered pair, an explicitly authorized tiny frame prefix, one frozen capacity, all source/schema/validator hashes, and an isolated `MVE_ONLY` output root. Its cell identity is forbidden from the 21-cell manifest.

Success criteria:

- real generated author source and real wrapper used;
- no C6 suppression treatment environment present;
- C4 baseline trace unchanged except additive passive evidence;
- C7 evidence complete enough for independent recomputation;
- static and dynamic outcome-firewall scans pass;
- two clean executions are byte/digest deterministic except explicitly normalized run/timestamp fields;
- validator and seal reproduction pass;
- deliberate negative controls fail closed.

The exact real pair/frame prefix must be named by the later MVE authorization; this plan does not silently choose it.

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
- selection consumes only validated C7 count/rate records.

## 17 Risk register

| Risk | Prevention | Detection | Fail-closed response | Required test |
| --- | --- | --- | --- | --- |
| 1. Wrong first-service timing | Hook after FIFO select, before byte deduction | Residual equals full pre-service packet; no prior service event | Invalidate cell | boundary instrumentation test |
| 2. Future-state reclassification | Once-only packet key and immutable record | duplicate/classification-event scan | Invalidate cell | future-state mutation test |
| 3. Cross-packet residual attribution | Bind release to packet ID + wire digest | Ledger reconciliation | Invalidate window/cell | substituted packet negative |
| 4. Ineligible recipient type | Explicit ID-State enum allowlist | Independent packet decode | Predicate false or invalid on unknown | Supplement/local/homography cases |
| 5. Serviceability timing ambiguity | Persist event-local raw state and rule ID; governance gate in Section 22 | Validator recomputation and audit | Block milestone M3 | queued-unserved recipient timing cases |
| 6. Waiting mistaken for capacity loss | Require exhausted budget plus exact residual/cause proof | Budget/work equation | Predicate false | waiting-only case |
| 7. Conditional accounting becomes replay/treatment | Pure function over frozen evidence; no runtime callback/import | dependency/static scan and baseline digest comparison | Abort qualification | mutation/reordering spies |
| 8. Partial bytes counted complete | Logical residual must reach exactly zero | Independent arithmetic | Predicate false/invalid | one-byte-short test |
| 9. Valid zero confused with missing evidence | Explicit validity enum and expected frame bijection | completeness scan | Invalid, never zero | valid-zero vs missing-window test |
| 10. Threshold drift/float error | Literal frozen integers and cross multiplication | independent recomputation | Qualification invalid | exact boundary vectors |
| 11. Premature/weighted selection | Separate command gated on all 21; schema forbids weights | manifest bijection and key scan | No selection output | missing-cell/weight-key tests |
| 12. Provenance or generated-source drift | Bind all source/config/input/schema/validator hashes | disk reread + seal reproduction | Reject launch/package | one-hash-at-a-time tamper matrix |
| 13. Outcome contamination | allowlists, strict schema, dependency/key/path/environment scans | static + runtime firewall validator | Abort, no authoritative seal | injected outcome field/path/env/import cases |

## 18 Milestones

| Milestone | Objective | Exit criterion |
| --- | --- | --- |
| M0 | Authority and change-boundary lock | Independent plan audit accepts authority chain and classifications |
| M1 | Declarative schema, manifest, and frozen constants | Schema review proves every required field and exact rule is representable |
| M2 | Passive runtime observation hooks | Existing C4 behavior tests unchanged; hook timing/immutability proven |
| M3 | Predicate and sticky classification core | All predicate unit tests pass; Section 22 governance item resolved |
| M4 | Conditional accounting and conservation | Pure accounting and independent recomputation agree on exhaustive fixtures |
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
| M3 | C7 predicate functions/tests | accounting replay; outcome imports | exhaustive predicate cases | NO | NO | governance item resolved and tests pass |
| M4 | Pure conditional-accounting functions/tests | packet reschedule, AoI/predictive/RL, treatment | conservation/determinism/mutation tests | NO | NO | accounting semantics proven |
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
- No independent audit performed by the plan author.

## 21 Implementation authorization boundary

This plan does not authorize implementation. After its dedicated commit, the only permitted next step is `INDEPENDENT_C7_IMPLEMENTATION_PLAN_AUDIT`.

Implementation may begin only after an independent audit explicitly approves this exact plan commit or an audited corrective plan supersedes it. Implementation authorization must name the exact implementation base, allowed files, allowed milestone(s), verification commands, outcome-firewall preflight, and stopping condition. Authorization for one milestone does not imply authorization for later milestones, MVE, qualification, census, or selection.

Any implementation discovery classified as `POTENTIAL_SPEC_CONFLICT` must stop at the affected milestone and return to governance. An `IMPLEMENTATION_DETAIL` may be resolved inside the frozen semantics if documented, tested, and included in the independent audit delta.

## 22 Open engineering questions

| ID | Classification | Question | Required resolution / gate |
| --- | --- | --- | --- |
| OQ-1 | `POTENTIAL_SPEC_CONFLICT` / `NEEDS_GOVERNANCE_REVIEW` | For a later ID-State packet still queued and never selected by the baseline before same-window capacity exhaustion, which exact baseline event supplies its event-local serviceability proof? Existing code has no true-first-service event for it. | Independent plan audit/governance must bind the precise event and raw state fields before M3. The implementation must not infer from future state or invent a replay event. |
| OQ-2 | `IMPLEMENTATION_DETAIL` | Is the existing generated-runtime manifest/cache invalidation sufficient when the runtime digest changes, or is an explicit C7 cachebuster field needed? | Resolve during M7 path tests; bind generated source digest either way. |
| OQ-3 | `IMPLEMENTATION_DETAIL` | Which registered pair and exact tiny frame prefix will be used for the non-scientific MVE? | Later MVE authorization must name it; do not choose during implementation. |
| OQ-4 | `IMPLEMENTATION_DETAIL` | Exact CLI spelling for resume/quarantine/dry-run modes. | Freeze in M5/M7 interface tests without changing atomicity semantics. |

Open engineering item count: `4`.

Potential specification conflict count: `1`.

The potential conflict is localized and explicitly gates implementation; it does not alter or weaken the frozen specification in this plan.

## 23 Independent audit handoff

The independent auditor should receive:

- this exact plan commit and clean diff from `0eda32c58871c1ec4b5b194c0c33608d7dd2a777`;
- the frozen authority files and verified hashes from Section 1;
- the complete specification-to-code traceability table;
- the architecture and producer/validator separation;
- schema field families and all exact threshold/selection algorithms;
- the four-layer test plan, risk register, and M0–M12 boundaries;
- the complete inspected-path inventory;
- explicit confirmation that no forbidden outcome material was read;
- OQ-1 for an explicit governance disposition.

Audit questions:

1. Does every frozen requirement map to a concrete implementation/evidence/validator/test/failure path?
2. Is the proposed runtime hook purely observational and placed at the exact true-first-service boundary?
3. Can the validator recompute eligibility without trusting producer labels?
4. Is conditional accounting demonstrably distinct from replay or treatment?
5. Are valid zero, invalid evidence, qualification, and selection cleanly separated?
6. Are production-path parity, atomicity, resume, provenance, and outcome firewall sufficiently fail closed?
7. Is OQ-1 resolvable without changing frozen scientific semantics, or must governance issue a specification clarification?

The author must not perform this independent audit. After committing this plan, work stops.

Plan-author self-audit before commit:

```text
FROZEN_SPEC_CHANGED = NO
NEW_SCIENTIFIC_DECISION = NO
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
