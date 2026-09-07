# Locked d1 Holdout Implementation Plan

## 0. Status, authority, and plan-only boundary

```text
DOCUMENT_CLASS = IMPLEMENTATION_PLAN
IMPLEMENTATION_PLAN_STATUS = DRAFT_FOR_INDEPENDENT_REVIEW
RESEARCH_DECISION_AUTHORITY = 42c1306ea4f454db5e01503b3ea58052046abfa8
EXPERIMENT_CONTRACT_AUTHORITY = aa2e081f506e2da8b493e8bc876b8437a23dcd03
FROZEN_EXECUTION_BASE = 47ce0fd35f1d9e7c10465297f5dcaf6b69117fab
DEVELOPMENT_ANALYSIS_AUTHORITY = 6c57e15fcf00f2a4c939ad98bcb203e1f958a5a3

AUTHORIZED_NOW = IMPLEMENTATION_PLAN_DRAFTING
IMPLEMENTATION_AUTHORIZED = NO
QUALIFICATION_AUTHORIZED = NO
TRAIN_HOLDOUT_EXECUTION_AUTHORIZED = NO
VAL_EXECUTION_AUTHORIZED = NO
SCIENTIFIC_OUTCOME_ACCESS_AUTHORIZED = NO
```

This plan translates the authoritative Contract into future file boundaries,
interfaces, ordering, and fail-closed checks. It does not revise R1--R9,
create an implementation authority, render a formal package, run a detector,
or authorize scientific execution. Contract language is referenced rather
than reproduced except where an implementation choice must be unambiguous.

The exact Research Decision and Contract were read from their authoritative
commits before this plan was drafted. Repository runtime surfaces, the frozen
development executor/cache implementation, Pair53/66 MVE implementation
records, and existing manifest schemas were inspected only to map future
implementation boundaries. No Train or Val scientific outcome was read.

## 1. Team B MINOR F1 closure

```text
TEAM_B_MINOR_F1_RESOLUTION = CLOSED_IN_IMPLEMENTATION_PLAN

TRAIN_PHYSICAL_VERDICT_FILE = analysis/primary_verdict.json
VAL_PHYSICAL_VERDICT_FILE = analysis/external_verdict.json
primary_or_external_verdict.json = DOCUMENTATION_SHORTHAND_ONLY
THIRD_PHYSICAL_VERDICT_FILE = PROHIBITED
SCIENTIFIC_RULE_CHANGED = NO
```

All future renderers, analyzers, manifests, tests, and auditors must reject a
physical file named `primary_or_external_verdict.json`. The generic Contract
Section 6 name denotes the population-specific slot; Contract Section 13.5
supplies its two canonical physical realizations.

## 2. Base, branch, worktree, and authority strategy

```text
CONTRACT_REFERENCE = Sections 0, 4, 8, and 22
IMPLEMENTATION_ACTION = Create a future isolated implementation worktree from
  the exact frozen execution base, not from the documentation tip.
PROPOSED_IMPLEMENTATION_BRANCH = impl/20260907-locked-d1-holdout
PROPOSED_IMPLEMENTATION_WORKTREE =
  /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/locked_d1_holdout_implementation
BRANCH_POINT = 47ce0fd35f1d9e7c10465297f5dcaf6b69117fab
FILES = Future orchestration, validation, analysis, storage, and tests only.
ENTRYPOINT = git worktree creation by a separately authorized operator.
INPUT = Frozen base plus exact decision/Contract commit identifiers.
OUTPUT = A future auditable implementation commit descended from 47ce0fd.
VALIDATION = rev-list ancestry; clean worktree; frozen file SHA-256 checks;
  documentation commit identifiers embedded as data, not runtime ancestry.
FAILURE_MODE = Refuse implementation when branch point, ancestry, or a frozen
  runtime fingerprint differs.
DEPENDENCIES = Independent approval to begin implementation.
```

The recommended base is the execution code state. Later commits contain
scientific analysis and governance documentation; making those commits the
runtime branch point would blur execution provenance. The implementation will
therefore record `42c1306...` and `aa2e081...` in `AUTHORITY_MANIFEST.json` and
read their documents by exact commit during review, without treating either
documentation commit as runtime authority. No Research Decision or Contract
commit is to be cherry-picked merely to make it an ancestor of runtime code.

## 3. Existing implementation surfaces and minimal-diff rule

The future implementation should wrap the existing behavior. These frozen
outcome-affecting surfaces must remain byte-identical to the hashes recorded in
Contract Section 4 unless a new scientific-authority review explicitly says
otherwise:

| Existing surface | Frozen role | Planned use | Modification policy |
| --- | --- | --- | --- |
| `src/tracking/mdmt_mia_onset_executor.py` | execution specs, hard gates, Y00 byte parity | read-only behavioral reference and reusable primitive | `FROZEN_MUST_NOT_CHANGE` |
| `src/tracking/mdmt_mia_cascade_runtime.py` | candidate/shadow/write-in trace semantics | frozen runtime copied into composed variant | `FROZEN_MUST_NOT_CHANGE` |
| `src/tracking/mdmt_mia_async_deadline_runtime.py` | packet timing/deadline semantics | frozen runtime copied into composed variant | `FROZEN_MUST_NOT_CHANGE` |
| `scripts/run_mdmt_mia_onset_development.py` | explicit-manual orchestration precedent | read-only pattern; never used directly for holdout | `FROZEN_MUST_NOT_CHANGE` |
| `scripts/run_mdmt_mia_author_sync.sh` | author path adapter and symlink input staging | reused unchanged | `FROZEN_MUST_NOT_CHANGE` |
| `src/evaluation/mdmt_mia_paper.py` | Source-MDA evaluator core | called only by authorized analyzer | `FROZEN_MUST_NOT_CHANGE` |
| packetized composed variant | author scientific runtime | referenced by exact path/tree digest | external read-only authority |
| reference composed variant | synchronous Y00 reference | referenced by exact path/tree digest | external read-only authority |
| `scripts/analyze_mdmt_mia_onset_development.py` at `6c57e15...` | registered bootstrap/contrast precedent | exact algorithmic reference and synthetic regression oracle | read-only analysis authority |

```text
MINIMAL_DIFF_STRATEGY = NEW_THIN_ORCHESTRATION_AND_GUARD_MODULES
CORE_RUNTIME_MODIFICATION_PLANNED = NO
WRAPPER_SUFFICIENT = YES
```

No existing outcome-affecting runtime modification is planned. If future
implementation discovers that a wrapper is insufficient, work stops before
editing the file and records:

```text
WHY_NECESSARY
WHY_WRAPPER_NOT_ENOUGH
SCIENTIFIC_SEMANTICS_IMPACT
QUALIFICATION_REQUIRED = YES
```

That discovery requires a revised independently reviewed implementation plan.

## 4. Proposed file-level impact map

These are proposed future files; none is created by this plan.

| File | Current role | Proposed action | New/modify/read-only | Outcome-affecting? | Contract requirement | Qualification required? |
| --- | --- | --- | --- | --- | --- | --- |
| `src/tracking/mdmt_mia_onset_executor.py` | frozen execution primitive | reuse/import only; fingerprint at preflight | `READ_ONLY / FROZEN_MUST_NOT_CHANGE` | yes | §§4, 8, 9, 11 | yes, parity against base |
| `src/tracking/mdmt_mia_cascade_runtime.py` | frozen cascade semantics | hash and reuse only | `READ_ONLY / FROZEN_MUST_NOT_CHANGE` | yes | §§4, 11, 12, 17 | yes |
| `src/tracking/mdmt_mia_async_deadline_runtime.py` | frozen packet semantics | hash and reuse only | `READ_ONLY / FROZEN_MUST_NOT_CHANGE` | yes | §§4, 11, 12 | yes |
| `scripts/run_mdmt_mia_author_sync.sh` | frozen author adapter | invoke unchanged | `READ_ONLY / FROZEN_MUST_NOT_CHANGE` | yes | §§4, 8, 9 | yes |
| `src/evaluation/mdmt_mia_paper.py` | frozen evaluator | import only after unblinding authorization | `READ_ONLY / FROZEN_MUST_NOT_CHANGE` | yes | §§4, 10, 13 | yes |
| `src/tracking/mdmt_mia_locked_d1_package.py` | absent | render population plans, manifests, immutable IDs, authority checks | `NEW` | indirectly | §§2--8, 18, 20 | yes |
| `src/tracking/mdmt_mia_locked_d1_cache.py` | absent | population-specific seed/seal/verify wrapper | `NEW` | indirectly | §§5, 8, 17 | yes |
| `src/tracking/mdmt_mia_locked_d1_validity.py` | absent | outcome-blind schema/hash/parity/attempt audit | `NEW` | no scientific computation | §§9--12, 15, 20 | yes |
| `src/evaluation/mdmt_mia_locked_d1_analysis.py` | absent | guarded one-batch registered analysis | `NEW` | yes | §§10, 12--14, 18 | yes |
| `src/tracking/mdmt_mia_locked_d1_storage.py` | absent | storage inventory, projection, reserve monitoring | `NEW` | no | §§16--17 | yes |
| `scripts/render_mdmt_mia_locked_d1_package.py` | absent | package dry-render CLI only | `NEW` | no | §§6, 8 | yes |
| `scripts/run_mdmt_mia_locked_d1_holdout.py` | absent | explicit population executor CLI | `NEW` | yes, orchestration | §§7--11, 15, 18 | yes |
| `scripts/seed_mdmt_mia_locked_d1_detector_cache.py` | absent | explicit cache CLI | `NEW` | indirectly | §§5, 8, 17 | yes |
| `scripts/audit_mdmt_mia_locked_d1_validity.py` | absent | validity-only CLI | `NEW` | no scientific computation | §§10--12, 20 | yes |
| `scripts/analyze_mdmt_mia_locked_d1_holdout.py` | absent | authorization-gated analyzer CLI | `NEW` | yes | §§13--14, 18 | yes |
| `scripts/qualify_mdmt_mia_locked_d1_implementation.py` | absent | mechanics-only qualification CLI | `NEW` | no formal outcome | §§8, 11, 17, 21 | yes |
| `tests/test_mdmt_mia_locked_d1_package.py` | absent | synthetic manifest/cohort/condition tests | `NEW` | no | §§2--8, 18, 20 | n/a |
| `tests/test_mdmt_mia_locked_d1_cache.py` | absent | synthetic cache key/seal/miss tests | `NEW` | no | §§5, 17 | n/a |
| `tests/test_mdmt_mia_locked_d1_validity.py` | absent | forbidden-field and audit tests | `NEW` | no | §§9--12, 15, 20 | n/a |
| `tests/test_mdmt_mia_locked_d1_analysis.py` | absent | authorization, atomicity, frozen-math fixtures | `NEW` | no real outcome | §§13--14, 18 | n/a |
| `tests/test_mdmt_mia_locked_d1_storage.py` | absent | byte-precision reserve/budget tests | `NEW` | no | §§16--17 | n/a |
| `tests/test_mdmt_mia_locked_d1_failures.py` | absent | Type I/II state-machine tests | `NEW` | no | §15 | n/a |

## 5. U-I2 package roots and immutable batch IDs

This plan closes the engineering naming convention while leaving actual batch
allocation to future exclusive creation.

```text
CONTRACT_REFERENCE = Sections 6, 7, 15, and 18
IMPLEMENTATION_ACTION = Allocate monotonically increasing, population-specific
  batch IDs under disjoint roots.

TRAIN_BATCH_ID_PATTERN = locked_d1_train_batch_NNN
TRAIN_PACKAGE_ROOT_PATTERN =
  outputs/locked_d1_holdout/train/locked_d1_train_batch_NNN/

VAL_BATCH_ID_PATTERN = locked_d1_val_batch_NNN
VAL_PACKAGE_ROOT_PATTERN =
  outputs/locked_d1_holdout/val/locked_d1_val_batch_NNN/

QUALIFICATION_PACKAGE_ROOT_PATTERN =
  outputs/locked_d1_holdout/qualification/qualification_NNN/

ATTEMPT_ROOT_PATTERN =
  <package>/<reference|packetized>/<pair>/<condition>/attempts/attempt_NNN/
```

`NNN` is the next unused zero-padded positive integer discovered while holding
an exclusive allocator lock. A root is created with exclusive-create
semantics. Type I retries advance only the nested attempt index. Type II
invalidation permanently seals the current population package as `INVALID`
and requires the next full population batch ID. Train and Val counters are
independent; paths never use result labels. No directory is created now.

## 6. U-I1 holdout-only executor and package renderer

```text
CONTRACT_REFERENCE = Sections 2--11, 15, 18, and 20
IMPLEMENTATION_ACTION = Add a holdout-only specification builder and explicit
  executor that minimally wrap frozen development/MVE primitives.
FILES = src/tracking/mdmt_mia_locked_d1_package.py;
  scripts/render_mdmt_mia_locked_d1_package.py;
  scripts/run_mdmt_mia_locked_d1_holdout.py
ENTRYPOINT =
  render_mdmt_mia_locked_d1_package.py --population train|val --batch-id ID
    --package-root ROOT
  run_mdmt_mia_locked_d1_holdout.py --package-root ROOT --execute
INPUT = Exact population enum, d1 condition enum, authority manifest, sealed
  population cache, qualification authority, storage preflight record.
OUTPUT = Dry-rendered package manifests or immutable attempts; never analysis.
VALIDATION = Exact Cartesian sets (Train 50 plus 10 references; Val 25 plus 5
  references), authority hashes, exclusive roots, no analysis directory,
  embargo marker, storage reserve, and cache completeness.
FAILURE_MODE = Nonzero exit before author launch on any mismatch; terminal
  Type I/II record after launch; no automatic fallback or next-pair advance
  after Type II.
DEPENDENCIES = P1 package schema, P3 cache, P7 storage, P8 state machine, and
  P11 qualification authority.
```

Responsibilities are deliberately narrow:

- render only the exact frozen population and five d1 conditions;
- render a separate same-pair Y00 reference plan;
- invoke the unchanged author wrapper with an environment generated from the
  sealed condition record;
- allocate attempts exclusively and update state atomically;
- enforce reference-first/Y00 byte-parity ordering;
- expose only outcome-blind progress counts and identifiers;
- never call `cross_view_mda`, parse effect direction, or create `analysis/`;
- stop before a new attempt when the storage monitor cannot preserve reserve.

The wrapper may reuse these read-only primitives from
`mdmt_mia_onset_executor.py`: `ExecutionSpec`, `ReferenceArtifacts`,
`tree_digest`, `digest`, `run`, `prediction_paths`, `evidence_root`,
`verify_y00_parity`, `accept_attempt`, and `GATE_ARTIFACTS`. The new package
module owns the exact Train/Val pair and condition enumeration because the
inherited `resolve()`, `plan()`, and `qualification_plan()` correctly remain
restricted to Pair53/66 MVE. The holdout executor must not reuse
`execute_and_accept()` or `evaluate_private()`: both invoke the evaluator and
are therefore incompatible with the pre-unblinding embargo. It also must not
call the development launcher or analyzer. The unchanged author shell wrapper
is the only process-launch adapter.

CLI population selection is not a free-form cohort input. `--population`
selects one compile-time enum whose ordered pair IDs are checked against the
Contract. Pair, delay, logical condition, evaluator, variant, cache, and seed
cannot be overridden from the command line. The `--execute` flag is necessary
but never sufficient: an independently signed authorization/preflight record
must also pass.

Planned exit classes are: `0` success, `2` configuration/authorization refusal
before launch, `20` terminal Type I interruption recorded, and `30` batch-wide
Type II invalidation recorded. Exit numbers are engineering interface values;
failure classification still comes only from Contract Section 15 predicates.

## 7. U-I3 manifest production and sealing plan

All JSON is canonical UTF-8 (`sort_keys=true`, compact separators for digests),
written to a same-filesystem temporary name, fsynced where supported, and
atomically renamed. A sealed manifest is never edited; a later state is a new
manifest or a separately named terminal state record.

| Manifest | Producer and timing | Required content/source authority | Seal timing and consumer | Fail-closed behavior |
| --- | --- | --- | --- | --- |
| `AUTHORITY_MANIFEST.json` | authority sealer after cache and pre-binding plan/condition cores exist | all Contract §6.1 fields; exact decision/Contract/base/runtime/variant/evaluator/Source-MDA/detector identities | seal after the non-cyclic digest graph below recomputes; consumed by every later tool | missing/extra drift or bundle mismatch: no launch |
| `EXECUTION_PACKAGE_MANIFEST.json` | package sealer after every other package authority is final | schema, population, batch, expected counts, plan/condition/authority/cache hashes, embargo state, implementation identity | seal last before qualification binding | any referenced digest mismatch: package ineligible |
| `EXECUTION_PLAN_MANIFEST.json` | renderer | exact reference and packetized specs, argv/env, expected artifact paths, runtime gates, attempt templates | seal before cache seed | rerender inequality: no launch |
| `condition_manifest.json` | renderer constructs a pre-binding core, then the authority sealer writes the final records | exactly Contract §6.2 records plus separately classified reference records | seal after `authority_bundle_sha256` is known | duplicate/foreign/missing row or digest-graph drift: Type II before launch |
| `detector_cache/cache_manifest.json` | cache seeder after full staging verification | population, ordered physical images, resolved paths, source hashes, cache keys/hashes, config/checkpoint/hook, seed, state | atomically promoted with read-only cache; consumed by authority rebinder, preflight, auditor | partial/foreign/symlink cache file or key mismatch: no promotion |
| `attempt_manifest.json` | executor at exclusive attempt allocation; terminal copy sealed at completion | all Contract §7 fields and condition/authority record hashes | running state references append-only state snapshots; final manifest seals once terminal | pre-existing root or inconsistent transition: stop and classify |
| `attempt_state.json` | executor, each allowed transition | attempt ID, state, timestamps, last completed state, parity flags where applicable | atomic replacement; terminal state made read-only | illegal regression/skip: Type II semantic acceptance failure |
| `failure_manifest.json` | failure classifier immediately after terminal evidence capture | exact Contract §15.1 fields and allowed reason code | seal before any retry or batch invalidation | incomplete class/evidence: conservatively Type II unclassified |
| `validity/MEASUREMENT_VALIDITY_MANIFEST.json` | validity auditor after the whole population is terminal | every Contract §20 validity boolean, selected attempt IDs, authority digests, counts, auditor identity, no-outcome attestation | seal only on all-pass; consumed by authorization creator | any false/missing key: no authorization |
| `STORAGE_MANIFEST.json` | storage module at render, launch, after each terminal attempt, and package seal | Contract §17.6 inventory plus filesystem/projection snapshot lineage | each snapshot is immutable and hash-linked; launch snapshot consumed by executor | forbidden field or reserve/budget failure: no next attempt |
| `embargo/UNBLINDING_AUTHORIZATION.json` | separate authorization command after validity pass and human approval | population-specific Contract §14 fields, exact validity and authority hashes, authorized identity/time | seal once; consumed only by analyzer | absent/mismatch/invalid batch: analyzer refuses before reads |
| `analysis/ANALYSIS_MANIFEST.json` | analyzer in one atomic transaction after all outputs exist in staging | selected attempts, population/cohort/conditions, authority, analyzer commit/hash, frozen math parameters, output hashes, authorization hash | promoted last with the complete analysis directory | any computation/output failure leaves staging ineligible and no canonical analysis root |

Actual SHA-256 values for future files/manifests remain `UNKNOWN_UNTIL_BUILT`;
the plan does not invent them.

### 7.1 Non-cyclic manifest digest graph

Contract §6.1 places `condition_manifest_sha256` inside the authority bundle,
while §6.2 places `authority_bundle_sha256` inside every condition record. A
naive full-file hash in both directions is a cryptographic cycle and is not an
implementable seal order. The implementation must not hide this with a mutable
placeholder or an unverifiable self-reference.

The proposed engineering serialization is:

```text
1. condition_core_sha256 = SHA-256 of canonical condition/reference records
   excluding only the back-reference field authority_bundle_sha256.
2. cache_manifest_sha256 = SHA-256 of the sealed population cache manifest,
   which binds batch_id, condition_core_sha256, and static detector authority,
   but does not claim an authority-bundle back-reference.
3. authority_bundle_sha256 = Contract §6.1 canonical digest, with its
   condition_manifest_sha256 slot defined as condition_core_sha256.
4. final condition_manifest.json = the identical core records plus the now-
   known authority_bundle_sha256 in every record.
5. condition_manifest_file_sha256 = SHA-256 of that final physical file and is
   recorded by EXECUTION_PLAN_MANIFEST.json and EXECUTION_PACKAGE_MANIFEST.json.
6. EXECUTION_PACKAGE_MANIFEST.json is sealed last and references every final
   physical-file digest; no earlier manifest references its own final digest.
```

This changes no cohort, condition, authority value, outcome, or scientific
rule. Because the Contract uses the name `condition_manifest_sha256` without
spelling out a back-reference projection, independent implementation-plan
review must explicitly accept or replace this serialization before P1 code is
written. Until then:

```text
MANIFEST_DIGEST_GRAPH_STATUS = PROPOSED_NON_CYCLIC_CLOSURE_PENDING_PLAN_REVIEW
SILENT_HASH_CONVENTION = PROHIBITED
BLOCKS_P1_IMPLEMENTATION = YES_UNTIL_PLAN_REVIEW
```

## 8. U-I4 outcome-blind validity auditor

```text
CONTRACT_REFERENCE = Sections 9--12, 15, 17, and 20
IMPLEMENTATION_ACTION = Implement a dedicated process and import boundary that
  validates bytes/schema/provenance without importing the scientific analyzer
  or evaluator function.
FILES = src/tracking/mdmt_mia_locked_d1_validity.py;
  scripts/audit_mdmt_mia_locked_d1_validity.py
ENTRYPOINT = audit_mdmt_mia_locked_d1_validity.py --package-root ROOT
INPUT = Explicit allowlist of manifests, raw prediction bytes, and trace files
  permitted by Contract §10.2.
OUTPUT = MEASUREMENT_VALIDITY_MANIFEST.json and a value-free audit report.
VALIDATION = Static import test, forbidden-key scan, monkeypatch trap proving
  `cross_view_mda` cannot be imported/called, exact schema/type/domain checks,
  dual-view hash parity, and population completeness.
FAILURE_MODE = Any absent or unknown predicate is false; no unblinding file is
  created; ambiguity becomes Type II unclassified unless interruption evidence
  proves Type I.
DEPENDENCIES = Sealed manifests, terminal attempts, cache, and failure records.
```

The auditor module may import hashing, JSON/schema helpers, path/manifest
types, and a byte-level prediction schema validator. It must not import
`src/evaluation/mdmt_mia_paper.py` or the analyzer module. Its result schema has
an allowlist and rejects the Contract §10.1 forbidden names, including
mechanism aggregates. Candidate/packet/frame traces are streamed only for row
types, required fields, frame/view domains, and consistency constraints that
are validity predicates; the auditor does not count delay-only rows, completed
events, or mechanism-positive pairs.

## 9. Authorization-gated one-batch scientific analyzer

```text
CONTRACT_REFERENCE = Sections 10, 12--14, and 18
IMPLEMENTATION_ACTION = Implement a separate analyzer whose first operation is
  authorization validation and whose only complete output is an atomic whole-
  population analysis directory.
FILES = src/evaluation/mdmt_mia_locked_d1_analysis.py;
  scripts/analyze_mdmt_mia_locked_d1_holdout.py
ENTRYPOINT = analyze_mdmt_mia_locked_d1_holdout.py --package-root ROOT
INPUT = Exact authority bundle, validity manifest, unblinding authorization,
  all selected prediction/trace artifacts, frozen Source-MDA files.
OUTPUT = Contract §13.5 files; Train `primary_verdict.json` or Val
  `external_verdict.json`, never both and never the generic shorthand.
VALIDATION = Authorization hash and population identity before opening any
  scientific input; exact all-pair/all-condition set; deterministic synthetic
  regression against analysis authority `6c57e15...`; output hash closure.
FAILURE_MODE = Before authorization: refuse without touching scientific files.
  During analysis: preserve an ineligible staging root, publish no partial
  canonical analysis directory, and never retry from outcome direction.
DEPENDENCIES = Population validity PASS and separately granted one-batch
  unblinding authorization.
```

The future bootstrap helper will reproduce the algorithm from
`scripts/analyze_mdmt_mia_onset_development.py` at `6c57e15...`: one fresh
`default_rng(7)` stream per registered aggregate as specified by the Contract,
10,000 pair resamples, arithmetic pair mean, and percentile endpoints. It is
verified with synthetic fixed fixtures and source/hash review rather than by
reading formal outcomes.

The analyzer stages all output beneath
`analysis.staging.<authorization-sha256>/`, computes all registered metrics,
contrasts, direction counts, CIs, mechanism states, component verdicts, and
the population verdict within one invocation, then writes
`ANALYSIS_MANIFEST.json` last and atomically renames staging to `analysis/`.

## 10. U-I5 detector cache, static-input deduplication, and reference role

### 10.1 Population caches

```text
CONTRACT_REFERENCE = Sections 5, 8, 11, and 17.4
IMPLEMENTATION_ACTION = Generalize the existing shared-canonical development
  cache seeder into a population-bound wrapper without changing the hook.
FILES = src/tracking/mdmt_mia_locked_d1_cache.py;
  scripts/seed_mdmt_mia_locked_d1_detector_cache.py
ENTRYPOINT = seed_mdmt_mia_locked_d1_detector_cache.py seed|status|verify
  --package-root ROOT
INPUT = Exact population image enumeration, detector/config/checkpoint/hook
  identities, and package authority.
OUTPUT = One sealed cache per Train package and one separate sealed cache per
  Val package, each with `cache_manifest.json`.
VALIDATION = expected key set equals actual key set; every NPZ schema/hash;
  source image/config/checkpoint/hook fingerprints stable before and after.
FAILURE_MODE = staging attempt retained; no partial promotion; packetized read
  miss raises; no `auto` or live-inference fallback.
DEPENDENCIES = Dry-rendered package and storage preflight.
```

The frozen cache key remains exactly:

```text
sha256(str(Path(image_filename).expanduser().resolve())) + ".npz"
```

The seeder enumerates both physical views of every exact population pair,
including frame zero as the author loop does. It seeds into
`cache_seed/attempt_NNN/detector_cache/`, verifies the whole population, writes
the manifest, makes files read-only, and atomically promotes once. Train and
Val caches, manifests, and cache-seed attempts are never shared. The
`REFERENCE` role receives no detector-cache environment key and retains its
frozen live-inference semantics. All packetized conditions use `read` only.

### 10.2 Static-input deduplication

The current author wrapper already builds a lightweight `run_inputs` tree of
symlinks to the immutable image and XML sources. The proposed formal executor
will use one package-level, population-specific, read-only staging namespace
and condition-local symlinks/references to it rather than five physical image
tree copies.

```text
PROPOSED_MECHANISM = SHARED_READ_ONLY_SOURCE_WITH_SYMLINK_STAGING
FINAL_DEDUP_MECHANISM_STATUS = QUALIFICATION_REQUIRED
```

Qualification must prove that every author-visible image resolves to the same
canonical dataset path used during cache seeding. If condition-local path
construction changes `Path(filename).resolve()`, the cache key, author path
semantics, source provenance, or condition behavior, the optimization fails
closed and cannot enter a formal package. Bind mounts are not the default
because they add host lifecycle/privilege state; they remain a reviewed
fallback only if symlink semantics fail qualification. Physical copies are a
last-resort `TEMPORARY_STAGING` exception requiring the Contract §17.4
necessity record.

## 11. Minimal mechanism trace and formal debug policy

### 11.1 Field mapping

No frozen writer is modified. A new post-run projection step copies only the
required row fields into minimal immutable formal trace files. The frozen raw
writer files remain `TEMPORARY_STAGING` during the active batch and are not
automatically deleted by this implementation; any later cleanup needs separate
storage-retention authorization under Contract Section 17.5. Formal acceptance
binds the projection algorithm and its source hashes; historical development
traces remain untouched.

| Contract required semantic | Existing source field | Source module | Write location | Keep in formal trace? | Rationale |
| --- | --- | --- | --- | --- | --- |
| pair | condition record / sequence prefix | package renderer | minimal trace header/manifest | yes | provenance and fixed denominator |
| logical condition | `logical_condition` | package renderer | minimal trace header/manifest | yes | binds Y10 primary and Yec diagnostic roles |
| authority identity | `authority_bundle_sha256` | package renderer | minimal trace manifest | yes | mixed-authority prevention |
| candidate time | `capture_frame` | `mdmt_mia_cascade_runtime.py` | `<attempt>/evidence/cascade_edge_candidates_<pair>-1.jsonl` | yes | candidate-to-Supplement linkage |
| view identity | `view_id` | `mdmt_mia_cascade_runtime.py` | `<attempt>/evidence/cascade_edge_candidates_<pair>-1.jsonl` | yes | stable event identity |
| stable candidate reference | `pre_branch_row_index` | `mdmt_mia_cascade_runtime.py` | `<attempt>/evidence/cascade_edge_candidates_<pair>-1.jsonl` | yes | deterministic within-attempt identity |
| candidate availability | `delay_membership` | `mdmt_mia_cascade_runtime.py` | `<attempt>/evidence/cascade_edge_candidates_<pair>-1.jsonl` | yes | delay-only predicate |
| counterfactual membership | `cf_membership` | `mdmt_mia_cascade_runtime.py` | `<attempt>/evidence/cascade_edge_candidates_<pair>-1.jsonl` | yes | delay-only predicate |
| trigger opportunity consistency | `high_score_triggered` | `mdmt_mia_cascade_runtime.py` | `<attempt>/evidence/cascade_edge_candidates_<pair>-1.jsonl` | yes | completed-event validity check |
| successful write-in | `high_score_bbox_written` | `mdmt_mia_cascade_runtime.py` | `<attempt>/evidence/cascade_edge_candidates_<pair>-1.jsonl` | yes | complete-event predicate |
| packet channel | `kind` | `mdmt_mia_async_deadline_runtime.py` | `<attempt>/evidence/async_packet_trace_<pair>-1.jsonl` | yes | Supplement identification |
| delivery terminal | `packet_action` | `mdmt_mia_async_deadline_runtime.py` | `<attempt>/evidence/async_packet_trace_<pair>-1.jsonl` | yes | timely predicate |
| packet time | `capture_frame` | `mdmt_mia_async_deadline_runtime.py` | `<attempt>/evidence/async_packet_trace_<pair>-1.jsonl` | yes | same-frame linkage |
| frame/view membership audit | `frame_id`, `identifiable`, `views` membership/high-score summaries | `mdmt_mia_cascade_runtime.py` | `<attempt>/evidence/cascade_edge_trace_<pair>-1.jsonl` | yes, restricted schema | Contract §12 frame audit and reproducibility |
| hard runtime guards | manifest counters and `shadow_export_fields` | both frozen runtime modules | unchanged compact manifests | yes | attempt validity |
| low-score diagnostic details | `low_score.*` | `mdmt_mia_cascade_runtime.py` | omitted from candidate/packet minimal projections; retain only if frame schema requires | conditional | not a Gate E/F predicate |
| payload arrays, images, corners, centers, tracker snapshots | in-memory prebranch state, not required final row fields | frozen author/cascade runtime | no new persistent dump | no | debug-only, high footprint |
| wire payload bodies/digests beyond hard guards | packet runtime events | `mdmt_mia_async_deadline_runtime.py` | omitted from minimal packet projection unless validity test requires | conditional | debug-only outside provenance/guard need |

The exact projection filename will preserve the Contract-recognized families
or be referenced by an explicit schema-version mapping in the condition and
attempt manifests. Qualification must demonstrate that the minimal projection
recomputes all Section 12 predicates and three-state classifications from
synthetic fixtures, while the validity auditor still verifies every Section 11
guard. Until that passes, `MINIMAL_TRACE_AUTHORITY = NOT_QUALIFIED` and formal
execution remains blocked.

### 11.2 Debug suppression

```text
FORMAL_VERBOSE_DEBUG_TRACE = DISABLED
FORMAL_DEBUG_ONLY_PERSISTENCE = DISABLED_BY_DEFAULT
```

Formal specs must set or enforce a minimal-trace profile and reject unknown
debug environment variables. The author log is retained at normal operational
level, but full-state dumps, extra cascade candidate/frame diagnostics,
visualizations, rendered frames/video, tensor/array dumps, profiling hooks,
packet census, interactive plots, and verbose per-frame console persistence
are disabled. Existing controls include `MIA_CASCADE_LOGGING` and packet-census
environment state; because Gate E/F needs selected cascade evidence, formal
mode does not simply set logging to zero. It keeps the frozen writer behavior
needed to produce a qualified minimal projection, then admits only required
evidence to the formal package. Qualification may enable extra debug output in
its separate root; those files never migrate automatically into Train or Val.

| Existing control/surface | Formal setting | Qualification setting |
| --- | --- | --- |
| `MIA_CASCADE_LOGGING` | `1`, because frozen candidate/frame evidence is required; persistence is reduced by the qualified projection, not by changing runtime semantics | may additionally test the inherited logging-off invariance case |
| `MIA_CASCADE_SHADOW` | exact condition value from the sealed condition record; it is scientific state, not a debug switch | inherited shadow-off invariance test only |
| `MIA_PACKET_CENSUS_RUN_ID` | absent/empty; packet-census output is not admitted | may be enabled only in an isolated qualification root if explicitly needed |
| `author.log` | normal operational log, one immutable file per attempt; no added verbose level | additional verbosity may remain qualification-only |
| visualizations, rendered video, profile/tensor/full-state dumps | disabled or absent; any unexpected output fails artifact admission | allowed only when declared `DEBUG_ONLY` in the qualification manifest |

No separate visualization or profiling flag was found on the frozen formal
entry path during repository inspection. The implementation must therefore use
an output allowlist rather than assume that an unknown file is harmless.

## 12. Storage manifest, budget, and outcome-blind monitoring

```text
CONTRACT_REFERENCE = Sections 16 and 17
IMPLEMENTATION_ACTION = Inventory every persistent/staging root and enforce
  launch-time reserve plus audited peak-envelope review.
FILES = src/tracking/mdmt_mia_locked_d1_storage.py;
  STORAGE_MANIFEST.json snapshots in each package
ENTRYPOINT = internal preflight/monitor API plus a status-only CLI subcommand
INPUT = filesystem statvfs facts, package paths, artifact inventory, projected
  remaining attempts; never scientific values.
OUTPUT = immutable hash-linked storage snapshots and boolean preflight keys.
VALIDATION = byte/file counts independently recomputed; forbidden-key scan;
  boundary fixtures at threshold minus/at/plus one byte.
FAILURE_MODE = no population launch or next attempt; preserve all evidence;
  require separate storage governance.
DEPENDENCIES = Package root allocation and artifact-role registry.
```

Every storage row contains:

```text
path_or_root, artifact_class, bytes, file_count, retention_class,
attempt_identity, condition_identity, shared_or_unique,
scientific_analysis_dependency, validity_dependency,
reproducibility_dependency, authority_dependency,
formal_admission_purposes
```

Launch thresholds are implemented as byte-exact comparisons:

```text
TRAIN: available_bytes >= 200000000000
VAL:   available_bytes >= 150000000000

TRAIN_AUDITED_PEAK_ENVELOPE_BYTES = 120000000000
VAL_AUDITED_PEAK_ENVELOPE_BYTES = 65000000000
```

Projected footprint above the applicable envelope sets
`STORAGE_BUDGET_REVIEW_REQUIRED=true` and blocks launch even if current free
space exceeds reserve. During execution, monitoring reads only filesystem
capacity, current bytes/file count, and projected remaining volume. It runs
before each new attempt and after each terminal attempt. Falling below the
reserve prevents the next attempt; an active process interrupted by disk
exhaustion is classified from evidence under Section 15, never by deleting
files or inspecting outcomes.

## 13. Type I/Type II state machines and accepted-attempt selection

### 13.1 Type I retry

```text
attempt_NNN
  -> terminal FAILED_TYPE_I
  -> immutable failure_manifest.json
  -> equality check of every authority/condition/cache/seed field
  -> exclusive attempt_NNN+1 with retry_of=attempt_NNN
```

The classifier accepts only Contract §15.2 reason codes. A retry is eligible
only when `scientific_outcome_accessed=false`, the prior attempt is terminal,
the new attempt is byte-for-byte authority-equivalent in its sealed spec, and
no Type II evidence exists. The first increasing attempt index reaching
`ACCEPTED_VALIDITY` is authoritative. All predecessors remain. No metric,
direction, contrast, mechanism state, or gate can enter retry eligibility.

```text
U_I7_NUMERIC_RETRY_CAP = NON_BLOCKING_DEFERRED_ENGINEERING_GOVERNANCE
HARD_RETRY_CAP_INVENTED = NO
```

### 13.2 Type II fail-close

```text
Type II detected
  -> write batch_state/INVALID.json atomically
  -> seal current whole population batch INVALID
  -> prohibit new pair-local attempt, validity PASS, authorization, analysis
  -> keep embargo active
  -> return to implementation and qualification
  -> after new authority approval, allocate a new full batch ID
```

Every downstream tool checks the batch-invalid marker before opening its main
inputs. The marker binds failure record and authority hashes. There is no local
repair and no accepted-attempt import from the invalid batch.
`MIXED_AUTHORITY_CONFIRMATORY_BATCH` is rejected by set-equality checks over all
selected `authority_bundle_sha256` values.

## 14. U-I6 qualification package

```text
CONTRACT_REFERENCE = Sections 8, 9, 11, 15, 17, 20, and 21/U-I6
IMPLEMENTATION_ACTION = Build a separate mechanics-only qualification package
  using the already frozen Pair53/66 MVE population, never formal Train/Val.
FILES = scripts/qualify_mdmt_mia_locked_d1_implementation.py and synthetic
  unit/integration tests listed in Section 4.
ENTRYPOINT = qualify_mdmt_mia_locked_d1_implementation.py --package-root ROOT
  --execute (only after separate qualification authorization)
INPUT = Pair53/66 MVE authority, synthetic failure fixtures, frozen runtime and
  variants; no Train/Val scientific outcome.
OUTPUT = qualification manifest/report with boolean mechanics gates and hashes.
VALIDATION = Exact authority/rendering/layout/cache/parity/immutability/failure/
  embargo/trace/debug/dedup/storage tests below.
FAILURE_MODE = Qualification FAIL; no implementation authority and no formal
  Train/Val package authorization.
DEPENDENCIES = P1--P9 implementation complete and independently audited.
```

The qualification input is exactly the prior MVE pairs `[53, 66]`, because
that population and runtime role already have qualification authority. It is
not a newly selected scientific cohort, and qualification produces no
confirmatory scientific verdict.

Qualification gates cover:

1. exact base/runtime/variant/evaluator/Source-MDA/detector binding;
2. exact Train/Val dry-render sets without running those populations;
3. package layout and canonical verdict filename rejection;
4. cache seed, full-key verification, read hit, and deliberate miss fail-close;
5. REFERENCE live-inference role and exact Y00 dual-view byte parity checker;
6. manifest completeness, digest tamper detection, and seal immutability;
7. exclusive attempt allocation and first-accepted outcome-blind selection;
8. injected Type I interruption followed by same-authority fresh retry;
9. injected Type II mismatch followed by batch-wide invalidation;
10. validity auditor import/output blindness and forbidden-field rejection;
11. analyzer refusing absent, stale, wrong-population, or wrong-hash authority;
12. minimal trace sufficiency for synthetic no-opportunity,
    opportunity-no-completion, and complete-path cases;
13. debug suppression and absence of debug-only formal artifacts;
14. symlink staging preserves author-visible resolved image paths and cache keys;
15. storage inventory correctness, exact reserve boundaries, peak-envelope
    review trigger, and monitor stop-before-next-attempt behavior.

## 15. Train/Val separation and authorization state machine

Train and Val have separate roots, batch IDs, caches, authority/package/plan/
condition/storage manifests, attempts, validity audits, authorization files,
analysis directories, and canonical verdict files. Common static authorities
are referenced by path and hash, not copied for convenience. No scientific
analysis state is shared, and no bootstrap population is pooled.

```text
TRAIN_IMPLEMENTED
  -> TRAIN_QUALIFIED
  -> TRAIN_EXECUTION_AUTHORIZED
  -> TRAIN_VALIDITY_PASS
  -> TRAIN_UNBLINDING_AUTHORIZED
  -> TRAIN_VERDICT_FROZEN
  -> VAL_EXECUTION_AUTHORIZED
  -> VAL_VALIDITY_PASS
  -> VAL_UNBLINDING_AUTHORIZED
  -> VAL_VERDICT_FROZEN
```

Each arrow requires an immutable authorization/state record naming the prior
record's SHA-256. `VAL_EXECUTION_AUTHORIZED` is a separate human/governance
action after the Train verdict is frozen; it does not branch on Train PASS or
FAIL and cannot rewrite Val population, conditions, statistics, mechanism
rules, or interpretation.

## 16. Implementation phases

No phase below is executed by this plan.

### P0 — implementation branch/worktree creation

```text
PHASE = P0
GOAL = Establish an isolated descendant of frozen base 47ce0fd.
CONTRACT_REFERENCES = §§0, 4, 8, 22
FILES_TO_ADD = none at worktree creation
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = all frozen runtime, variants, docs, outputs
IMPLEMENTATION_ACTIONS = create proposed branch/worktree; record ancestry and
  exact decision/Contract references; verify clean status and fingerprints
TESTS = rev-parse, merge-base --is-ancestor, sha256 checks, git diff baseline
EXPECTED_ARTIFACTS = implementation bootstrap audit record
FAIL_CLOSE_CONDITIONS = wrong base, dirty worktree, fingerprint mismatch
DEPENDENCIES = separate implementation authorization
EXIT_CRITERIA = isolated clean worktree exactly rooted at 47ce0fd
```

### P1 — package and manifest scaffolding

```text
PHASE = P1
GOAL = Implement pure dry rendering, canonical schemas, and batch allocation.
CONTRACT_REFERENCES = §§2--8, 18, 20; Team B MINOR F1
FILES_TO_ADD = mdmt_mia_locked_d1_package.py, renderer CLI, package tests
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = frozen runtime/evaluator/wrapper and authority docs
IMPLEMENTATION_ACTIONS = encode population enums; exact d1 records; reference
  plans; exclusive batch IDs; canonical JSON/digests; verdict-name rejection
TESTS = exact Cartesian sets, Train/Val separation, schema and tamper fixtures
EXPECTED_ARTIFACTS = synthetic/dry-render manifests only
FAIL_CLOSE_CONDITIONS = extra pair/condition/override, reused root, bad digest
DEPENDENCIES = P0
EXIT_CRITERIA = deterministic renderer passes all synthetic/static tests
```

### P2 — holdout-only executor orchestration

```text
PHASE = P2
GOAL = Add explicit-manual execution wrapper without core-runtime edits.
CONTRACT_REFERENCES = §§7--11, 15, 18, 20
FILES_TO_ADD = run_mdmt_mia_locked_d1_holdout.py; orchestration helpers/tests
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = onset executor, cascade/deadline runtimes, author shell,
  evaluator, external variants
IMPLEMENTATION_ACTIONS = exclusive attempts; sealed spec dispatch; reference-
  first Y00 ordering; atomic state transitions; value-free progress
TESTS = fake-runner state transitions, launch guards, no evaluator import/call
EXPECTED_ARTIFACTS = synthetic attempt trees and state manifests
FAIL_CLOSE_CONDITIONS = authorization/storage/cache/schema/authority mismatch,
  illegal state transition, analysis root present
DEPENDENCIES = P1
EXIT_CRITERIA = wrapper-only path reproduces frozen spec semantics in fixtures
```

### P3 — detector-cache seeding and sealing support

```text
PHASE = P3
GOAL = Provide separate population cache lifecycle with no live fallback.
CONTRACT_REFERENCES = §§5, 8, 11, 17.4
FILES_TO_ADD = mdmt_mia_locked_d1_cache.py, cache CLI/tests
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = frozen cache hook, detector/config/checkpoint, reference
  role, development/MVE caches
IMPLEMENTATION_ACTIONS = enumerate resolved images; stage; verify NPZ/key/hash;
  atomically promote; seal read-only; bind manifest
TESTS = synthetic populations, frame-zero, collision/miss/foreign/tamper cases
EXPECTED_ARTIFACTS = synthetic cache fixtures only before qualification
FAIL_CLOSE_CONDITIONS = partial cache, changed input, symlink cache entry, miss
DEPENDENCIES = P1, P7 storage API for future real seed
EXIT_CRITERIA = cache behavior and no-fallback invariants pass tests
```

### P4 — minimal trace and artifact minimization

```text
PHASE = P4
GOAL = Project the minimum formal trace and suppress debug-only persistence.
CONTRACT_REFERENCES = §§11, 12, 17
FILES_TO_ADD = projection/schema helper and focused tests, preferably within
  mdmt_mia_locked_d1_validity.py rather than a new runtime writer
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = frozen cascade/deadline writers and historical traces
IMPLEMENTATION_ACTIONS = field allowlist projection; trace/source hash binding;
  artifact-role declarations; formal debug profile
TESTS = three mechanism-state fixtures, hard-gate sufficiency, forbidden dump
  absence, lossless required-field projection
EXPECTED_ARTIFACTS = synthetic minimal traces and schema manifest
FAIL_CLOSE_CONDITIONS = any Section 12 predicate/guard unreconstructable,
  unknown debug artifact admitted
DEPENDENCIES = P1, frozen writer schemas
EXIT_CRITERIA = minimal schema sufficient and debug policy mechanically enforced
```

### P5 — outcome-blind validity auditor

```text
PHASE = P5
GOAL = Validate whole-population measurement integrity without science access.
CONTRACT_REFERENCES = §§9--12, 15, 17, 20
FILES_TO_ADD = mdmt_mia_locked_d1_validity.py, audit CLI/tests
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = evaluator and future analyzer
IMPLEMENTATION_ACTIONS = allowlisted file access; schema/hash/parity/hard-gate/
  attempt/population checks; forbidden-field output scanner
TESTS = import isolation, evaluator-call trap, missing/foreign/mixed attempts,
  forbidden mechanism aggregation and output-key fixtures
EXPECTED_ARTIFACTS = synthetic validity PASS/FAIL manifests
FAIL_CLOSE_CONDITIONS = false/missing predicate, forbidden field, any authority
  mixture, invalid batch marker
DEPENDENCIES = P1--P4, P8 classification model
EXIT_CRITERIA = auditor can certify validity but cannot compute a science result
```

### P6 — one-batch analyzer guards

```text
PHASE = P6
GOAL = Add authorization-first, atomic population analysis implementation.
CONTRACT_REFERENCES = §§10, 12--14, 18; Team B MINOR F1
FILES_TO_ADD = mdmt_mia_locked_d1_analysis.py, analyzer CLI/tests
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = mdmt_mia_paper.py, development analyzer authority
IMPLEMENTATION_ACTIONS = validate auth before input open; implement frozen math;
  whole-population staging transaction; canonical verdict names
TESTS = authorization denial, read-open spies, synthetic deterministic math,
  interrupted transaction, Train/Val filename and separation tests
EXPECTED_ARTIFACTS = synthetic analysis packages only
FAIL_CLOSE_CONDITIONS = absent/stale/wrong authorization, incomplete population,
  invalid batch, pre-existing analysis root, computation/write failure
DEPENDENCIES = P1, P4 schema, P5 authorization contract
EXIT_CRITERIA = unauthorized reads impossible in tests; authorized synthetic
  batch is atomic and deterministic
```

### P7 — storage preflight and monitoring

```text
PHASE = P7
GOAL = Implement outcome-blind inventory, reserve, projection, and monitoring.
CONTRACT_REFERENCES = §§16--17
FILES_TO_ADD = mdmt_mia_locked_d1_storage.py and storage tests
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = any scientific artifact or historical output
IMPLEMENTATION_ACTIONS = statvfs snapshot; artifact classification; byte/file
  inventory; peak review; pre-attempt monitor; hash-linked snapshots
TESTS = exact byte thresholds, projection envelopes, forbidden keys, disk-full
  simulation without deletion
EXPECTED_ARTIFACTS = synthetic STORAGE_MANIFEST snapshots
FAIL_CLOSE_CONDITIONS = below reserve, projection above envelope without review,
  unknown artifact role, forbidden scientific field
DEPENDENCIES = P1 schema
EXIT_CRITERIA = storage decisions depend only on engineering facts
```

### P8 — failure/retry and batch-invalid state machine

```text
PHASE = P8
GOAL = Enforce immutable Type I retry and batch-wide Type II invalidation.
CONTRACT_REFERENCES = §§7, 15, 18, 20
FILES_TO_ADD = state-machine helpers/tests in package module and failure test file
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = frozen runtime and prior attempts
IMPLEMENTATION_ACTIONS = allowed transitions/reason codes; failure manifests;
  authority equality; first-accepted selection; invalid-batch guard
TESTS = crash/host/incomplete-write fixtures; every Type II reason; overwrite,
  reuse, mixed-authority, outcome-driven retry rejection
EXPECTED_ARTIFACTS = synthetic immutable failure/batch-state records
FAIL_CLOSE_CONDITIONS = ambiguous class, incomplete record, illegal retry, mix
DEPENDENCIES = P1--P2
EXIT_CRITERIA = Type I and Type II paths are total, deterministic, fail-closed
```

### P9 — qualification harness assembly

```text
PHASE = P9
GOAL = Assemble all mechanics gates over Pair53/66 and synthetic failures.
CONTRACT_REFERENCES = §§8, 9, 11, 15, 17, 20, 21/U-I6
FILES_TO_ADD = qualification CLI and qualification tests/report template
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = formal Train/Val inputs, runtime, authority docs
IMPLEMENTATION_ACTIONS = bind P1--P8 tests/gates; render but do not execute formal
  populations; define qualification manifest schema
TESTS = complete 15-gate list in Section 14
EXPECTED_ARTIFACTS = dry qualification plan only
FAIL_CLOSE_CONDITIONS = any gate absent, result-dependent field, formal outcome use
DEPENDENCIES = P1--P8
EXIT_CRITERIA = independently reviewable qualification package definition
```

### P10 — independent implementation audit

```text
PHASE = P10
GOAL = Establish whether code may become a candidate implementation authority.
CONTRACT_REFERENCES = §§4, 8, 10, 17, 20, 22
FILES_TO_ADD = tracked implementation audit report only
FILES_TO_MODIFY = none except report
FILES_MUST_NOT_CHANGE = Research Decision, Contract, frozen runtime, outputs
IMPLEMENTATION_ACTIONS = full diff/hash review; leakage audit; coverage review;
  verify no orphan requirement and no core change
TESTS = all unit/static tests; py_compile/shell syntax/diff checks; no real run
EXPECTED_ARTIFACTS = independent audit verdict and candidate commit/hash list
FAIL_CLOSE_CONDITIONS = unaudited outcome-affecting change, authority drift,
  test/coverage failure
DEPENDENCIES = P1--P9 complete
EXIT_CRITERIA = explicit implementation-audit PASS; still no formal authorization
```

### P11 — qualification execution

```text
PHASE = P11
GOAL = Execute separately authorized mechanics qualification only.
CONTRACT_REFERENCES = §§8, 9, 11, 15, 17, 20, 21/U-I6
FILES_TO_ADD = no planned source files; immutable qualification output only
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = Train/Val package roots and frozen authorities
IMPLEMENTATION_ACTIONS = after separate authorization, allocate qualification
  root; run Pair53/66 mechanics and injected failures; seal manifest/report
TESTS = runtime qualification gates from Section 14
EXPECTED_ARTIFACTS = qualification_NNN manifest, logs, hashes, verdict
FAIL_CLOSE_CONDITIONS = any gate failure, formal pair access, outcome computation
DEPENDENCIES = P10 PASS and explicit qualification authorization
EXIT_CRITERIA = independently reviewed qualification PASS and frozen candidate
  implementation SHA-256 values
```

### P12 — formal Train authorization preparation

```text
PHASE = P12
GOAL = Prepare, but not self-grant, the formal Train launch authority package.
CONTRACT_REFERENCES = §§8, 16--20
FILES_TO_ADD = tracked authorization-request/checklist documentation only;
  future dry-rendered package after explicit approval
FILES_TO_MODIFY = none
FILES_MUST_NOT_CHANGE = implementation authority, qualification evidence,
  Research Decision, Contract, Train/Val scientific inputs
IMPLEMENTATION_ACTIONS = bind audited implementation and qualification hashes;
  run outcome-blind dry preflight/storage projection; request human authorization
TESTS = Contract §20 checklist except execution-dependent predicates remain false
EXPECTED_ARTIFACTS = authorization request, not execution authorization
FAIL_CLOSE_CONDITIONS = any unresolved execution blocker, failed storage check,
  absent qualification, authority mismatch
DEPENDENCIES = P11 PASS and independent plan/implementation/qualification reviews
EXIT_CRITERIA = explicit separate Train execution authorization is the only next
  possible state; no automatic launch
```

## 17. Dependency graph

```text
Research Decisions @ 42c1306
              |
              v
Experiment Contract @ aa2e081
              |
              v
This Implementation Plan
              |
              v
Implementation branch from 47ce0fd
      |          |             |
      |          |             +--> storage monitor/preflight
      |          +----------------> manifest/package authority
      +---------------------------> separate Train/Val detector caches
              |                         |
              +-----------+-------------+
                          v
              independent implementation audit
                          |
                          v
                    qualification
                          |
                          v
                 formal Train package
                          |
          +---------------+----------------+
          |                                |
          v                                v
  outcome-blind validity auditor     sealed manifests/cache
          |                                |
          +---------------+----------------+
                          v
             Train unblinding authorization
                          |
                          v
            one-batch scientific analyzer
                          |
                          v
                 frozen Train verdict
                          |
                          v
              separate Val authorization
                          |
                          v
       Val package -> Val validity auditor -> Val unblinding
                          |
                          v
                 frozen external verdict
```

The validity auditor never depends on the scientific analyzer. The analyzer
depends on the validity manifest and authorization hash, not the reverse.

## 18. Risk register

| Risk | Mitigation | Detection | Fail-close action |
| --- | --- | --- | --- |
| `RISK-1 core runtime accidentally modified` | branch from base; frozen path allowlist; wrapper-only changes | file SHA-256 and diff against 47ce0fd in P0/P10/preflight | reject implementation authority; restore through a new reviewed branch, never rewrite |
| `RISK-2 cache key semantics changed by dedup` | preserve resolved dataset path; bind key function/hook hash | qualification compares resolved paths and keys for every fixture | disable proposed dedup; no formal cache/run |
| `RISK-3 minimal trace omits mechanism evidence` | explicit field mapping and synthetic state reconstruction | P4 recomputes all Section 12 predicates/states from projection | keep formal execution blocked; revise projection and requalify |
| `RISK-4 validity auditor leaks scientific outcome` | separate module/process, no evaluator import, output allowlist | import graph, monkeypatch call trap, forbidden-key scan | validity FAIL; no authorization; classify any actual breach per governance |
| `RISK-5 analyzer runs before authorization` | authorization validation before input discovery/open | filesystem open spy and stale/wrong-hash fixtures | exit before read/write; preserve embargo |
| `RISK-6 attempt overwrite` | exclusive mkdir, monotonic index, sealed terminal records | collision and inode/path inventory checks | stop; never reuse path; investigate/classify |
| `RISK-7 mixed-authority batch` | one authority bundle per batch and per attempt | set equality across selected manifests and recomputed bundle | Type II; invalidate whole batch |
| `RISK-8 input dedup changes author runtime semantics` | symlink design only after Pair53/66 qualification | author-visible path, prediction/parity, cache-key fixture comparison | reject dedup implementation; no formal launch |
| `RISK-9 storage explosion despite minimization` | artifact admission allowlist, projection, footprint forecast | STORAGE_MANIFEST and peak-envelope comparison | require storage-budget review; do not launch |
| `RISK-10 disk exhaustion during active attempt` | byte reserve and pre-attempt monitoring with projected remaining volume | statvfs snapshots and write/process failure evidence | stop next attempt; retain artifacts; classify interruption Type I only if Contract evidence permits |

## 19. Contract coverage matrix

| Contract requirement | Implementation phase | Future file/module | Qualification test | Unresolved? |
| --- | --- | --- | --- | --- |
| authority/base/provenance | P0, P1, P10 | package module; `AUTHORITY_MANIFEST.json` | ancestry/hash tamper | future hashes only |
| exact Train/Val cohorts | P1 | package module/condition manifest | exact ordered sets | no |
| d1-only five conditions and Yec role | P1, P2 | package module/executor | Cartesian set/env mapping | no |
| external variants/runtime/evaluator identity | P0, P1, P10 | authority manifest/preflight | tree/file digest mismatch | future implementation hash |
| population cache authority | P3 | cache module/manifest | seed/read/miss/tamper | entry counts/hashes until seed |
| package internal layout | P1 | renderer/package module | tree/schema snapshot | no |
| immutable attempts and selection | P2, P8 | executor/state helpers | overwrite/retry/first-accepted | no |
| fail-closed launch preflight | P1--P3, P7--P9 | executor/preflight | one failure per predicate | qualification identity |
| Y00 byte parity | P2, P5, P9 | validity module | ordered dual-view hash equality | no |
| outcome embargo | P2, P5, P6 | executor/auditor/analyzer | evaluator trap/open spy/forbidden keys | no |
| attempt acceptance/hard gates | P2, P4, P5 | executor/validity | counter/schema/conservation fixtures | no |
| population measurement validity | P5 | auditor/validity manifest | exact 50/10 and 25/5 dry fixtures | auditor hash |
| mechanism trace/schema/states | P4, P6 | projection/analyzer | three-state and trigger-consistency fixtures | projection hash |
| frozen statistics/contrasts/gates | P6 | analysis module | deterministic synthetic regression | analyzer hash |
| canonical verdict filenames/F1 | P1, P6 | renderer/analyzer | reject generic; Train/Val exact names | no |
| one-batch authorization/atomicity | P5, P6 | auth record/analyzer | partial/missing/stale/interruption | signer workflow review |
| Type I retry | P8 | failure/state helpers | allowed reasons/same authority/new root | numeric cap deferred |
| Type II batch invalidation | P8 | `batch_state/INVALID.json` guards | each reason/mixed authority/local repair rejection | no |
| storage reserve | P7 | storage module/manifest | threshold boundary | live capacity at launch |
| artifact minimization/debug policy | P4, P7 | projection/storage inventory | debug artifact rejection | qualification evidence |
| static-input dedup | P3, P4, P9 | cache/package staging | resolved-path/cache-key parity | final mechanism qualification |
| Train/Val separation | P1, P6, P12 state logic | package/analyzer | cross-root/cross-manifest rejection | no |
| Val sequencing independent of Train result | P12 and later authorization | authorization records | state transition fixtures | future Val authorization |
| machine-checkable checklist | P1, P5, P7, P12 | manifests/preflight | every key present and boolean | execution-dependent values |
| authorization boundary | every phase | CLI launch guards | default refusal | explicit future approvals |

```text
NO_ORPHAN_CONTRACT_REQUIREMENT = PLANNED_AND_AUDITABLE
```

## 20. Unresolved implementation items disposition

| ID | Current status | Plan to resolve | Phase | Blocks implementation? | Blocks execution? |
| --- | --- | --- | --- | --- | --- |
| `U-I1` | `PLAN_DEFINED; SHA_UNKNOWN` | add exact holdout-only executor paths in §6, audit and hash built files | P2, P10 | no after plan approval | yes until audited identity exists |
| `U-I2` | `ENGINEERING_NAMING_CLOSED_IN_PLAN` | use §5 population/batch/root patterns and exclusive allocator | P1 | no | no after implementation test |
| `U-I3` | `SCHEMAS_AND_PRODUCERS_PLANNED; NON_CYCLIC_DIGEST_CLOSURE_PENDING_PLAN_REVIEW; HASHES_UNKNOWN` | approve §7.1 serialization, implement producers, dry render, independently verify hashes | P1, P3, P5, P7 | yes until plan review accepts/replaces §7.1; no afterward | yes until sealed manifests exist |
| `U-I4` | `MODULE_BOUNDARIES_PLANNED; HASHES_UNKNOWN` | implement separate auditor/analyzer, prove isolation and guards | P5, P6, P10 | no after plan approval | yes until audited/qualified |
| `U-I5` | `LIFECYCLE_PLANNED; COUNTS/HASHES_UNKNOWN` | separately seed and seal Train, later Val, only after authorization | P3, P11, formal preflight | no | yes |
| `U-I6` | `QUALIFICATION_PLAN_DEFINED; IDENTITY_UNKNOWN` | build harness, independent audit, separately authorized Pair53/66 qualification | P9--P11 | no after plan approval | yes |
| `U-I7` | `NON_BLOCKING_DEFERRED` | separate operations/storage governance may add a non-outcome hard cap | outside current plan unless requested | no | no numeric cap required by science |

No future generated SHA, cache entry count, manifest digest, or qualification
verdict is invented here.

## 21. Review gates and authorization boundary

The implementation plan is ready for independent review only when:

```text
TEAM_B_MINOR_F1_RESOLUTION = CLOSED_IN_IMPLEMENTATION_PLAN
IMPLEMENTATION_PHASES_DEFINED = YES
FILE_IMPACT_MAP_INCLUDED = YES
CONTRACT_COVERAGE_MATRIX_INCLUDED = YES
RISK_REGISTER_INCLUDED = YES
MINIMAL_DIFF_STRATEGY = YES
CORE_RUNTIME_MODIFICATION_PLANNED = NO
ARTIFACT_MINIMIZATION_IMPLEMENTATION_PLANNED = YES
STORAGE_PREFLIGHT_IMPLEMENTATION_PLANNED = YES
OUTCOME_BLIND_VALIDITY_AUDITOR_PLANNED = YES
ONE_BATCH_ANALYZER_GUARD_PLANNED = YES
TYPE_I_TYPE_II_STATE_MACHINE_PLANNED = YES
QUALIFICATION_PLAN_INCLUDED = YES
NEW_SCIENTIFIC_DECISION_INTRODUCED = NO
```

This document does not authorize P0 or any later phase. After independent plan
review, the next possible governance action is a separate authorization to
begin implementation. Qualification, Train execution, outcome access, and Val
execution each remain separately blocked.
