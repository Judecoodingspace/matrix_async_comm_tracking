# Harness v2 Minimal Implementation Plan

**Status:** `PLAN ONLY — NO IMPLEMENTATION OR QUALIFICATION PERFORMED`

**Date:** 2026-09-18

**Planning base:** `e752f251e8619c88824237c48e9a392012b609c6`

**Frozen input:** `HARNESS_V2_FROZEN_DECISIONS` dated 2026-09-17

**Reviewed corrective status:**

```text
P1_PLATFORM_IDENTITY_QUALIFICATION_SEPARATED = YES
PLATFORM_V2_SHA_BINDS_RUNTIME_IDENTITY_ONLY = YES
TEST_DIGEST_INCLUDED_IN_PLATFORM_V2_SHA = NO
REHEARSAL_IDENTITY_INCLUDED_IN_PLATFORM_V2_SHA = NO
HARNESS_CORE_STATELESS_PRIMITIVES = YES
HARNESS_IS_WORKFLOW_ENGINE = NO
FORMAL_READY_IS_AUTHORIZATION = NO
FORMAL_READY_MUTATES_AUTHORITY = NO
FORMAL_READY_REPAIRS_STATE = NO
PRIMARY_AUTHORITY_LAYER_COUNT = 3
```

## 1. Objective

Implement the smallest reusable platform harness that:

1. keeps Science Authority, Platform Authority, and Formal Run Authorization as the only authority layers;
2. exercises the real production path with a fake scientific payload before Formal;
3. resolves a logical root exactly once at the real-child boundary;
4. derives all run/cell/evidence/status paths from one attempt identity;
5. reports one machine-readable `FORMAL_READY` verdict;
6. permanently covers C6 regressions R13–R21;
7. reuses Platform Authority when only science changes.

This plan changes no scientific question, treatment, predicate, scheduler, service semantics, metric, baseline, or tracking interpretation.

## 2. Current-to-v2 authority mapping

No fourth authority layer is introduced.

| Harness v2 layer | C6 retrospective mapping | Future form |
| --- | --- | --- |
| Science Authority | Frozen C6 contract plus the scientific subset of `C6_FORMAL_EXECUTION_PACKAGE.json` | One machine-readable science artifact binding question, cells, treatment, baseline, and metrics |
| Platform Authority | Existing platform manifest plus exact Operator/Launcher/Child/Wrapper/path/validator component digests | One `PLATFORM_AUTHORITY_V2.json` containing only stable production runtime identity and contract versions |
| Formal Run Authorization | Existing C6 Formal authorization is historical input only | One authorization binding exactly one Science Authority, one Platform Authority, and one attempt ID/root |

The historical C6 package, authorization, issuance, attempts, and evidence remain immutable. Harness v2 does not rewrite them into the new layout.

Readiness output and retrospective qualification output are evidence, not additional authorities. They must not be wrapped in issuance-of-issuance or seal-of-seal structures.

## Corrective Revision — Platform Identity / Qualification Separation

Harness v2 separates stable production platform identity from the evidence showing that a particular identity was qualified.

`PLATFORM_V2_SHA` binds only the canonical stable payload formed from:

- Formal Operator digest;
- Production Launcher digest;
- Real Child digest;
- Wrapper digest;
- Harness runtime/core digest;
- validator-owning production source digests;
- canonical path contract version;
- attempt layout contract version;
- failure propagation contract version.

The stable identity payload must not contain test digests, test commit identity, rehearsal identity/output, C6 retrospective evidence, readiness evidence, environment observations, qualification commit, or evidence commit. If the listed production bytes and contract versions do not change, running new tests, producing a new rehearsal, or recording new qualification evidence leaves `PLATFORM_V2_SHA` unchanged.

At most one separate qualification evidence artifact/schema concept, `PLATFORM_QUALIFICATION_EVIDENCE_V2`, records:

- the exact `PLATFORM_V2_SHA` that was qualified;
- test identities and the test commit;
- R13–R21 results;
- C6 retrospective results;
- exact-production-path rehearsal identity and results;
- qualification environment observations;
- qualification/evidence commit identity.

Qualification evidence reports what qualified a platform identity; it is not authoritative input to `PLATFORM_V2_SHA`, is not a fourth authority layer, and cannot serve as a parent authority. Harness v2 must not create a qualification authority, qualification issuance, qualification seal authority, or platform-authority parent.

```text
RUNNING_A_NEW_QUALIFICATION_MUST_NOT_CHANGE_PLATFORM_V2_SHA = YES
TEST_DIGEST_INCLUDED_IN_PLATFORM_V2_SHA = NO
REHEARSAL_IDENTITY_INCLUDED_IN_PLATFORM_V2_SHA = NO
PRIMARY_AUTHORITY_LAYER_COUNT = 3
NEW_PRIMARY_AUTHORITY_LAYER_ADDED = NO
NEW_PRODUCTION_MODULES_BEYOND_EXISTING_PLAN = 0
QUALIFICATION_EVIDENCE_ARTIFACT_SCHEMA_CONCEPT_COUNT = 1
```

## 3. Existing production path to reuse

| Role | Existing path/symbol | v2 action |
| --- | --- | --- |
| Formal Operator | `scripts/run_mdmt_mia_c6_formal.py:operator()` | Reuse the real cell loop and fail-closed progress behavior through a new rehearsal mode; do not copy the loop |
| Production Launcher | `scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py:launch_c6_stage()` | Reuse the subprocess, disk reread, real validator, aggregation, and terminal path |
| Real Child | `scripts/run_mdmt_mia_c6_real_child.py:_run()` | Reuse; extend only the explicit non-scientific rehearsal identity and canonical-root proof |
| Wrapper | `scripts/run_mdmt_mia_author_sync.sh` | Reuse unchanged unless a failing regression proves a required platform delta |
| Fake scientific payload | `tests/fixtures/fake_mdmt_mia_c6_author.py` | Reuse as the only substituted final workload |
| Real validator | `_validate_real_disk_cell()` plus existing Census/decision/ledger checks | Reuse unchanged for rehearsal evidence |
| Canonical path rehearsal | `tests/test_mdmt_mia_c6_canonical_path_contract.py` | Move its direct-launch proof behind the real Operator entry path |

Current gap: existing Formal qualification can use a synthetic child, while the canonical-path test reaches the real Launcher/Child/Wrapper without entering through the real Formal Operator. Neither alone proves D2/D3.

## 4. Minimal file delta

### 4.1 New reusable core

Create `src/tracking/harness_v2.py` with only these responsibilities:

- `AuthorityBinding`: validate the three direct authority identities.
- `AttemptLayout`: validate an attempt ID and derive `run/`, `cells/`, `progress/`, `aggregation/`, and `terminal/` below one canonical attempt root.
- `canonical_execution_root(repo_root, logical_root)`: resolve once and reject later relative rebasing.
- `classify_repository_state(...)`: return separate `SOURCE_STATE`, `AUTHORITY_STATE`, and `EXECUTION_ARTIFACT_STATE`.
- `compute_platform_identity(...)`: compute only the stable production runtime/contract payload and `PLATFORM_V2_SHA`.
- `classify_delta(base_sha, head_sha, platform_paths, science_paths)`: classify RED/YELLOW/GREEN and return the minimum requalification scope.
- `readiness_check(...)`: compose existing checks and return only a structured ready/block result.

Every primitive is deterministic input → validation/derivation → output. The module has no mutable global state, manager object, workflow lifecycle, or authority/artifact mutation methods. It must not expose `issue`, `repair`, `retry`, `recover`, `mutate`, `run_science`, `commit`, or equivalent manager operations. It must not import scientific runtime code or encode C6 suppression semantics.

```text
HARNESS_V2_CORE_IS_STATELESS = YES
HARNESS_V2_IS_WORKFLOW_ENGINE = NO
```

### 4.2 One command

Create `scripts/run_harness_v2.py` with one initial public operation:

```bash
python scripts/run_harness_v2.py qualify \
  --science-authority <path> \
  --platform-authority <path> \
  --formal-authorization-candidate <path> \
  --attempt-id <id>
```

Successful stdout:

```text
FORMAL_READY = YES
```

Failure stdout:

```text
FORMAL_READY = NO
BLOCKER = <stable blocker code>
```

`qualify` is strictly a read → validate → classify → rehearse → report operation. Detailed diagnostics may be written only beneath an exclusive temporary, non-scientific, non-authoritative rehearsal namespace that is separate from every Formal attempt namespace; stdout remains the single verdict interface. Qualification never launches a scientific payload, issues an authorization, converts an authorization candidate to `execution_authorized=true`, rewrites Science or Platform Authority, repairs an old attempt, deletes quarantine, moves prior artifacts, automatically retries, commits/pushes Git state, or mutates a scientific package.

```text
FORMAL_READY_IS_AUTHORIZATION = NO
FORMAL_READY_MUTATES_AUTHORITY = NO
FORMAL_READY_REPAIRS_STATE = NO
```

### 4.3 Exact rehearsal path

Extend `scripts/run_mdmt_mia_c6_formal.py` with an explicit `REHEARSAL` mode distinct from current `QUALIFICATION` and `LIVE` modes.

`REHEARSAL` must:

1. enter the same `operator()` cell loop used by `LIVE`;
2. create a repository-relative logical attempt root pointing to an exclusive temporary location;
3. derive every cell root from `AttemptLayout`;
4. build launch specs that select the real child, not the tiny/synthetic child;
5. route through `launch_c6_stage()` and its actual subprocess call;
6. run `run_mdmt_mia_c6_real_child.py`;
7. run `run_mdmt_mia_author_sync.sh` after its real `cd` transition;
8. substitute only the final author entry with `fake_mdmt_mia_c6_author.py` in an isolated generated-source tree;
9. produce the normal communication evidence shape;
10. use the real disk validator and propagate any process/evidence failure;
11. mark every result `synthetic_non_scientific=true` and forbid Formal/scientific aggregation.

Add the narrowly scoped `PLATFORM_REHEARSAL / REAL_CHILD_REHEARSAL` policy pair to the existing real-cell authorization validator. It must be impossible to use this pair with a live Formal authorization.

### 4.4 Real-child proof additions

Modify `scripts/run_mdmt_mia_c6_real_child.py` only as needed to:

- record the already-canonical absolute execution root received at the child boundary;
- prove `MIA_OUTPUT_ROOT`, `MIA_RUN_INPUT_ROOT`, `MPLCONFIGDIR`, runtime evidence, C6 evidence, status, logs, and finalizer paths are descendants of that root;
- mark rehearsal execution non-scientific without changing the real Wrapper command;
- fail when producer and validator normalized evidence roots differ.

Do not modify the C6 predicate, scheduler, ledger semantics, author command arguments, or scientific validator rules.

## 5. Single attempt namespace

New v2 authorizations contain one logical `experiment_root` and one `attempt_id`; they do not carry independently editable per-cell roots.

The harness derives:

```text
<experiment_root>/<attempt_id>/
├── run/
├── cells/<cell>/
├── progress/
├── aggregation/
└── terminal/
```

Required rules:

- attempt ID, run ID, cell roots, progress, aggregation, and terminal identity derive from the same object;
- an existing attempt root blocks launch regardless of its terminal state;
- a failed attempt receives `FAILED_QUARANTINED` and remains immutable;
- retry requires a new attempt ID;
- no cleanup, reuse, merge, or in-place repair is available through Harness v2.

## 6. State separation

`classify_repository_state()` must report three independent values:

```text
SOURCE_STATE = CLEAN / DIRTY
AUTHORITY_STATE = MATCH / DRIFT
EXECUTION_ARTIFACT_STATE = ABSENT / ACTIVE / COMPLETE / FAILED_QUARANTINED / COLLISION
```

Rules:

- tracked or untracked changes under registered source paths affect `SOURCE_STATE`;
- byte drift in the three bound authority artifacts affects `AUTHORITY_STATE`;
- registered attempt roots and quarantine markers affect only `EXECUTION_ARTIFACT_STATE`;
- untracked quarantined evidence must not dirty source or authority state;
- no classifier may delete, move, stage, or rewrite an artifact.

## 7. Readiness check order

`qualify` performs these checks in this order and stops at the first blocker:

1. parse exactly three authority bindings;
2. verify authority files and bound hashes;
3. classify source, authority, and artifact state independently;
4. validate attempt ID and exclusive namespace;
5. scan current-user `/proc/*/cmdline` for the exact authorization/attempt identity; never kill a process;
6. check Python, cwd, environment, storage, and platform component hashes;
7. classify the delta against the previously qualified platform identity;
8. run only the requalification scope required by changed platform components;
9. execute the exact production-path rehearsal for the declared cell topology;
10. verify producer/validator roots, required log sinks, progress/finalizer roots, failure propagation, and evidence completeness;
11. validate that the Formal authorization candidate binds the same science, platform, and attempt identities and remains inactive;
12. return `FORMAL_READY = YES` only if every required check passes.

Package/schema validation alone can never satisfy step 9.

## 8. Risk and requalification rules

| Delta | Risk | Minimum action |
| --- | --- | --- |
| Science Authority only; platform component hashes unchanged | RED scientific, platform unchanged | Scientific review outside Harness plus fresh exact rehearsal for the new topology, readiness, and fresh Formal authorization; reuse `PLATFORM_V2_SHA` without full platform requalification |
| Operator/Launcher/Child/Wrapper/harness runtime/path/attempt/failure-propagation/validator production component change | YELLOW platform | Compute a new `PLATFORM_V2_SHA`; run affected tests, exact rehearsal, and the minimum platform qualification; record new qualification evidence without automatically rebuilding Science Authority |
| Predicate, scheduler, service, baseline, metric, or execution behavior changes | RED | New Science Authority and affected platform qualification; no automatic authorization |
| Documentation/comment/presentation only | GREEN | Static delta review; no platform rerun unless executable bytes changed |

Unknown classifications escalate one level. `NO_NEW_GATE_WITHOUT_FAILURE_MODE` is enforced by requiring every proposed check to cite an existing regression ID or a documented threat that can invalidate execution/evidence.

Every delta review returns the frozen interface:

```text
CHANGED_FILES = <exact BASE_SHA..HEAD_SHA paths>
RISK_CLASS_BY_FILE = <RED / YELLOW / GREEN>
AFFECTED_INVARIANTS = <frozen invariant IDs>
P0/P1/P2/P3 = <findings>
DELTA_REVIEW = PASS / BLOCK
REQUALIFICATION_SCOPE = <smallest affected scope>
VERDICT = <one verdict>
```

Requalification scenarios are fixed as follows:

- **A — Science-only delta:** production platform bytes/contracts remain unchanged, so `PLATFORM_V2_SHA` remains unchanged. Perform scientific review, a fresh exact rehearsal for the new topology, readiness, and a fresh Formal authorization. Do not perform full platform requalification or invent a new platform identity.
- **B — Wrapper/platform component delta:** compute a new `PLATFORM_V2_SHA`, run affected tests plus exact rehearsal and minimum qualification, and record new qualification evidence. Do not automatically rebuild Science Authority.
- **C — Test-only delta:** `PLATFORM_V2_SHA` remains unchanged. Updated test results belong only to qualification evidence.
- **D — New rehearsal only:** `PLATFORM_V2_SHA` remains unchanged. The new rehearsal identity/output belongs only to qualification evidence.

## 9. Permanent regression mapping

Create `tests/test_harness_v2.py` and reuse the existing focused tests rather than duplicating fixtures.

| Regression | Required proof |
| --- | --- |
| R13 | Package/dry-run validation without exact rehearsal returns `FORMAL_READY=NO` |
| R14 | Run, cells, progress, aggregation, and terminal all derive from one attempt root |
| R15 | Untracked quarantined artifacts leave source/authority clean and artifact state quarantined |
| R16 | A relative logical root is resolved once before Wrapper `cd`; no nested rebasing appears |
| R17 | author failure or required `tee`/evidence sink failure blocks readiness; grep no-match alone does not |
| R18 | Producer and validator normalized evidence roots are byte-for-byte equal |
| R19 | All execution-critical environment paths are absolute below the canonical root |
| R20 | Replacing the real subprocess/child/wrapper with a mock or tiny child blocks qualification |
| R21 | Status, progress, aggregation, terminal, and finalizer use the same canonical attempt root |

Retain and invoke the existing tests in:

- `tests/test_mdmt_mia_c6_formal.py`
- `tests/test_mdmt_mia_c6_canonical_path_contract.py`
- `tests/test_mdmt_mia_author_sync_wrapper.py`
- `tests/test_mdmt_mia_c6_real_cell_launcher.py`

## 10. C6 retrospective qualification

Use fixture-only, non-scientific attempts to reproduce the pre-fix conditions:

| Historical failure | Retrospective mutation | Expected blocker |
| --- | --- | --- |
| Attempt2 relative `RUN_ROOT` | pass a relative logical root through Wrapper cwd change without canonical binding | `NON_CANONICAL_EXECUTION_ROOT` |
| Attempt3 producer/validator root split | point validator at the cwd-rebased path | `EVIDENCE_ROOT_MISMATCH` |
| Run-root collision | pre-create any part of the derived attempt namespace | `ATTEMPT_NAMESPACE_OCCUPIED` |
| Quarantine dirty-state confusion | create an untracked `FAILED_QUARANTINED` attempt tree | source/authority remain clean; new distinct attempt may qualify |

The retrospective passes only when all four failures are caught before any scientific workload and the positive rehearsal traverses the complete real path.

## 11. Platform Authority v2 identity and qualification evidence

Once the production runtime bytes and contract versions are fixed, write one direct stable-identity artifact:

```text
summary_md/communication/harness_v2/PLATFORM_AUTHORITY_V2.json
```

Its canonical identity payload contains only:

- schema version for the stable identity payload;
- direct SHA-256 for Operator, Launcher, Real Child, Wrapper, harness runtime/core, and validator-owning production sources;
- canonical path contract version;
- attempt layout contract version;
- failure propagation contract version;
- `PLATFORM_V2_SHA`, computed over exactly those canonical stable fields.

It must not claim qualification status and must not include test digests, rehearsal identity/output, retrospective result, readiness output, environment evidence, qualification commit, or evidence commit.

After tests, R13–R21, C6 retrospective, and exact production-path rehearsal pass, record them using the one separate `PLATFORM_QUALIFICATION_EVIDENCE_V2` artifact/schema concept. That evidence binds the qualified `PLATFORM_V2_SHA` and records test/test-commit identity, retrospective results, rehearsal identity/results, environment observations, and qualification/evidence commit. Repeating qualification may replace or append evidence records according to that single schema without changing the bound platform identity.

Neither artifact contains another authority, issuance, nested seal, or scientific decision. Qualification evidence is not an authority and Formal Run Authorization continues to bind the three primary layers directly.

## 12. Implementation sequence

1. **Core and unit tests:** add stateless authority binding, attempt layout, state separation, path normalization, platform-identity computation, and delta classification.
2. **Real rehearsal path:** add `REHEARSAL` to the existing Operator/Launcher/Child path and keep the Wrapper/validator real.
3. **One-command readiness:** compose read/validate/classify/rehearse/report checks in `run_harness_v2.py`; enforce the two-line verdict and all non-mutation boundaries.
4. **Stable platform identity:** after production runtime bytes and contract versions stabilize, create `PLATFORM_AUTHORITY_V2.json` from only the stable identity payload and compute `PLATFORM_V2_SHA`.
5. **Qualification and retrospective:** run the focused tests, R13–R21, C6 retrospective, and exact production-path rehearsal against that identity.
6. **Qualification evidence:** record the results in the single `PLATFORM_QUALIFICATION_EVIDENCE_V2` artifact/schema concept, bound to the already-computed `PLATFORM_V2_SHA`.

Each step is a separate reviewable commit. Qualification evidence never changes stable platform identity, and no step creates an additional authority layer.

## 13. Verification commands for the implementation phase

These commands are planned, not executed by this document:

```bash
PYTHONHASHSEED=0 PYTHONNOUSERSITE=1 \
/mnt/data/yzm/experiments/mdmt_mia_official/.conda-env/bin/python -m pytest -q \
  tests/test_harness_v2.py \
  tests/test_mdmt_mia_c6_formal.py \
  tests/test_mdmt_mia_c6_canonical_path_contract.py \
  tests/test_mdmt_mia_c6_real_cell_launcher.py \
  tests/test_mdmt_mia_author_sync_wrapper.py
```

Then run `scripts/run_harness_v2.py qualify` with an inactive retrospective C6 authorization candidate and a fresh attempt ID. No real scientific data or tracking result may be opened.

## 14. Acceptance output

Implementation is complete only when it produces:

```text
THREE_LAYER_AUTHORITY_MODEL = IMPLEMENTED_OR_UNAMBIGUOUSLY_MAPPED
CANONICAL_PATH_CONTRACT = PASS
SINGLE_ATTEMPT_NAMESPACE = PASS
SOURCE_AUTHORITY_ARTIFACT_STATE_SEPARATION = PASS
EXACT_PRODUCTION_PATH_REHEARSAL = PASS
REAL_SUBPROCESS_USED = YES
REAL_WRAPPER_USED = YES
REAL_CWD_CHANGE_EXERCISED = YES
REAL_EVIDENCE_WRITER_USED = YES
REAL_VALIDATOR_USED = YES
NO_EXECUTION_PATH_FIRST_EXERCISED_IN_FORMAL = YES
FORMAL_READY_SINGLE_VERDICT = PASS
C6_RETROSPECTIVE_QUALIFICATION = PASS
FULL_REQUALIFICATION_NOT_REQUIRED_FOR_SCIENCE_ONLY_DELTA = YES
NO_NEW_GATE_WITHOUT_FAILURE_MODE = ENFORCED
PLATFORM_V2_SHA_BINDS_RUNTIME_IDENTITY_ONLY = YES
TEST_DIGEST_INCLUDED_IN_PLATFORM_V2_SHA = NO
REHEARSAL_IDENTITY_INCLUDED_IN_PLATFORM_V2_SHA = NO
QUALIFICATION_EVIDENCE_IS_AUTHORITY = NO
HARNESS_V2_CORE_IS_STATELESS = YES
HARNESS_V2_IS_WORKFLOW_ENGINE = NO
FORMAL_READY_IS_AUTHORIZATION = NO
FORMAL_READY_MUTATES_AUTHORITY = NO
FORMAL_READY_REPAIRS_STATE = NO
```

Until then:

```text
PLATFORM_V2_SHA = NOT_IMPLEMENTED
PLATFORM_QUALIFICATION_EVIDENCE_V2 = NOT_RECORDED
FORMAL_READY = NO
```

## 15. Corrective self-audit

```text
Q1_NEW_REHEARSAL_CHANGES_PLATFORM_V2_SHA = NO
Q2_TEST_ONLY_CHANGE_CHANGES_PLATFORM_V2_SHA = NO
Q3_WRAPPER_BYTE_CHANGE_CHANGES_PLATFORM_V2_SHA = YES
Q4_FORMAL_READY_CAN_ISSUE_AUTHORIZATION = NO
Q5_FORMAL_READY_CAN_REPAIR_OR_DELETE_FAILED_ATTEMPT = NO
Q6_QUALIFICATION_EVIDENCE_IS_FOURTH_AUTHORITY_LAYER = NO
Q7_HARNESS_V2_IS_WORKFLOW_ENGINE = NO
```

## 16. Explicit non-goals and stop boundary

Do not implement a workflow engine, registry, database, dashboard, PKI, scheduler, scientific runtime, tracking evaluator, or Git replacement. Do not create final reusable skills yet.

The Skill Creator boundary remains:

```text
Harness v2 implementation
→ R13–R21 PASS
→ C6 retrospective PASS
→ HARNESS_V2_QUALIFIED_FOR_NEXT_EXPERIMENT = YES
→ only then consider Skill Creator
```

This document stops at the implementation plan. It performs no code change, qualification, rehearsal, Formal run, scientific workload, tracking-result read, authority issuance, or skill generation.
