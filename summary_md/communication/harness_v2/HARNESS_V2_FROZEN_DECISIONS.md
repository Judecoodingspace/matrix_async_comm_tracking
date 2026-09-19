HARNESS_V2_FROZEN_DECISIONS
Project: MDMT / MIA Async Collaborative Tracking
Artifact type: Frozen engineering-governance decisions
Status: FROZEN FOR IMPLEMENTATION PLANNING
Date: 2026-09-17

0. Purpose
Harness v2 exists because C6 exposed a structural process problem:

Formal execution became the first true end-to-end integration test for multiple production-path behaviors.

This caused repeated failures unrelated to the scientific hypothesis, including attempt/run-root collisions, quarantine-state confusion, cwd-relative path rebasing, producer/validator evidence-root mismatch, relative environment paths, and synthetic tests that bypassed real subprocess/cwd semantics.

Harness v2 must reduce engineering attention cost while preserving scientific rigor.

The governing goal is:

Scientific questions should determine experiment pace; Harness should become stable, reusable infrastructure that catches mechanical failures before Formal.

1. Scope
Harness v2 governs:

authority boundaries;
execution-platform qualification;
attempt identity and isolation;
path handling;
exact production-path rehearsal;
pre-Formal readiness;
mechanical regression;
risk-proportionate delta review;
reuse of qualified platform infrastructure.
Harness v2 does not decide scientific hypotheses, treatments, metrics, schedulers, tracking interpretation, or whether future work uses FIFO, supersession, AoI, EDF, RL, or another scientific method.

2. Governing principle
NO_NEW_GATE_WITHOUT_FAILURE_MODE

A new Gate may be introduced only if it protects against a concrete observed failure or a clearly documented threat/failure mode that can invalidate execution or evidence.

Prefer:

fewer boundaries
+
stronger end-to-end invariants

over more documents, more seals, and nested authorities.

3. D1 — Three-layer authority model
Harness v2 SHALL use only three primary authority layers:

Science Authority
      ↓
Platform Authority
      ↓
Formal Run Authorization

Science Authority
Binds the scientific question, treatment, baseline, hypotheses, metrics, cells, and frozen research decisions.

Platform Authority
Binds the reusable execution infrastructure: Operator, Launcher, Real Child, Wrapper, canonical path contract, attempt lifecycle, evidence/validator contract, failure propagation, and production-path rehearsal behavior.

Formal Run Authorization
Binds one Science Authority + one qualified Platform Authority + one exact Attempt identity.

Nested authority-of-authority / seal-of-seal / qualification-of-qualification structures are prohibited by default unless a concrete failure mode requires them.

4. D2 — Formal is not an integration test
Mandatory invariant:

NO_EXECUTION_PATH_FIRST_EXERCISED_IN_FORMAL = YES

Formal may be the first run of the full scientific workload, but may not be the first time the real Operator, Launcher, Child, subprocess boundary, Wrapper, cwd change, env propagation, evidence writer, validator, progress/status path, logging, or failure propagation are exercised.

5. D3 — Exact Production-Path Rehearsal
Before every Formal authorization, Harness v2 SHALL execute:

EXACT_PRODUCTION_PATH_REHEARSAL

The rehearsal must traverse:

REAL Operator
→ REAL Launcher
→ REAL Child
→ REAL subprocess
→ REAL Wrapper
→ REAL cwd transition
→ REAL env propagation
→ REAL evidence writer
→ REAL validator

The only substituted component may be the final scientific workload, replaced with a fake/tiny/non-scientific author.

The rehearsal must not qualify the critical path by mocking the core subprocess boundary, using absolute-only tmp paths, bypassing the real wrapper, or using a validator stub.

It SHALL intentionally exercise a relative logical experiment root.

6. D4 — Canonical Path Contract
Logical paths may be relative above the execution boundary.

At the Real Child execution boundary:

logical relative root
→ resolve exactly once
→ canonical absolute execution root

Every execution-critical downstream path must derive from that root, including cell/run roots, MIA_OUTPUT_ROOT, MIA_RUN_INPUT_ROOT, MPLCONFIGDIR, runtime evidence root, producer root, validator root, status/finalization root, logs, and results.

Invariant:

NO_RELATIVE_ARTIFACT_PATH_CROSSES_A_CWD_BOUNDARY

and:

PRODUCER_EVIDENCE_ROOT == VALIDATOR_EVIDENCE_ROOT

after normalization.

7. D5 — Single Attempt Namespace
Every Formal attempt SHALL have one attempt-scoped namespace, conceptually:

experiment/
└── attempt_N/
    ├── run/
    ├── cells/
    ├── progress/
    ├── aggregation/
    └── terminal/

Run-level and cell-level identity must derive from the same Attempt identity.

Failed attempts become:

FAILED_QUARANTINED

and are never deleted, repaired in place, reused, merged into later attempts, or retroactively upgraded to PASS. Retry requires a fresh Attempt identity.

8. D6 — Separate Source, Authority, and Execution Artifact State
Harness v2 SHALL distinguish:

SOURCE_STATE
AUTHORITY_STATE
EXECUTION_ARTIFACT_STATE

Quarantined evidence must not automatically make source or authority state dirty.

9. D7 — Platform Qualification is reusable
Once:

PLATFORM_AUTHORITY_V2 = QUALIFIED

future experiments SHALL reuse it if the platform components/invariants remain unchanged.

Science-only changes do not trigger full platform requalification. A platform component change triggers only the smallest affected delta qualification.

10. D8 — Risk-proportionate review
RED — scientific
Treatment, scientific runtime behavior, baseline, metric definitions, scheduler/service semantics, predicate semantics, or execution boundaries that change scientific behavior.

YELLOW — platform/mechanical
Launcher, Wrapper, Real Child, validator, path handling, artifact schema, attempt roots, production mechanics.

GREEN — non-semantic
Documentation, comments, presentation-only artifacts, and logging wording that cannot affect execution/evidence validity.

When uncertain, escalate one level. Full-system review is not the default.

11. D9 — Delta review replaces full re-review
Review:

BASE_SHA → HEAD_SHA

and answer:

Which files changed?
What risk class applies?
Which frozen invariant can be affected?
Which prior qualification becomes invalid?
What is the minimum requalification scope?
Expected output:

DELTA_REVIEW = PASS / BLOCK
REQUALIFICATION_SCOPE = <minimal scope>

12. D10 — One-command Formal readiness
Harness v2 SHALL converge to one entry point conceptually equivalent to:

harness qualify <experiment>

and return only:

FORMAL_READY = YES

or:

FORMAL_READY = NO
BLOCKER = ...

Internally it must check authority identity, source/authority state, attempt isolation, historical artifacts, root absence, active processes, canonical paths, environment, Python/runtime, storage, production rehearsal, producer/validator agreement, failure propagation, and package/authorization consistency.

13. D11 — Failure propagation must fail closed
The Harness must distinguish scientific process status, required evidence/log sink status, and display/filter status.

author/process failure → FAIL;
required evidence/log sink failure → FAIL;
display-only filter with no match must not create a false failure.
14. D12 — C6 failures become permanent regressions
Permanent reusable regressions:

R13 Package-validation dry-run != production operator-path qualification
R14 Formal run-level root must be attempt-scoped
R15 Quarantined artifacts != source/authority contamination
R16 Relative RUN_ROOT must not be reinterpreted after wrapper cd
R17 Required log/evidence sink failure must fail closed
R18 Producer/validator evidence roots must remain identical across cwd changes
R19 Env-carried output paths must be canonical absolute below execution boundary
R20 Mocked subprocess cannot qualify real cwd/path semantics
R21 Status/finalizer must share the canonical root contract

New regressions require a concrete failure mode.

15. D13 — Harness v2 lifecycle
Preferred lifecycle:

Research Decision Freeze
→ Scientific Implementation / MVE
→ Platform Delta Qualification (only if Platform changed)
→ Exact Production-Path Rehearsal
→ FORMAL_READY
→ Formal Run Authorization
→ Formal Run
→ Result Authority
→ Scientific Interpretation

16. D14 — Stable platform version
Harness v2 should expose one stable Platform Authority identity:

PLATFORM_V2_SHA

binding Operator, Launcher, Child, Wrapper, path contract, attempt lifecycle, evidence/validator contract, failure propagation, and rehearsal mechanism.

Future Formal identity becomes:

SCIENCE_AUTHORITY = <science SHA>
PLATFORM_AUTHORITY = <platform SHA>
ATTEMPT = <attempt id>

17. D15 — Reusable Skill architecture
Three reusable skills are frozen:

experiment-governance-core
Classifies the proposed change and returns:

RISK_CLASS
REQUIRED_GATES
PROHIBITED_EXTRA_GATES
AUTHORITY_IMPACT

and enforces:

NO_NEW_GATE_WITHOUT_FAILURE_MODE

execution-path-qualification
Qualifies the real production path using real Operator/Launcher/Child/subprocess/Wrapper/cwd/env/evidence writer/validator and a fake scientific payload.

Core outputs:

FORMAL_READY = YES / NO
NO_EXECUTION_PATH_FIRST_EXERCISED_IN_FORMAL = YES / NO

independent-delta-audit
Reviews BASE_SHA → HEAD_SHA and returns:

CHANGED_FILES
RISK_CLASS_BY_FILE
AFFECTED_INVARIANTS
P0/P1/P2/P3
REQUALIFICATION_SCOPE
VERDICT

18. D16 — What must not become a Skill
Do not create narrow skills such as:

c6-suppression-skill
attempt4-recovery-skill
wrapper-fix-skill
c7-aoi-skill

Experiment-specific failure knowledge belongs in the regression corpus. Reusable workflow/reasoning belongs in skills.

19. D17 — Skill Creator timing
Do not generate the final reusable skills from these frozen decisions alone.

A skill should encode a validated workflow, not a proposed workflow.

Required sequence:

HARNESS_V2_FROZEN_DECISIONS
→ small implementation plan
→ Harness v2 implementation
→ C6 retrospective qualification
→ HARNESS_V2_QUALIFIED_FOR_NEXT_EXPERIMENT
→ Skill Creator generates Skill v1
→ next experiment validates Skill v1 in real use

Draft skill specs may be written earlier, but the final Skill Creator pass happens only after the retrospective qualification passes.

20. D18 — C6 retrospective acceptance test
Before Harness v2 is qualified, prove retrospectively that it would have caught, before Formal:

Attempt2 relative RUN_ROOT bug
Attempt3 producer/validator cwd-relative root bug
run-root attempt collision
quarantine dirty-state confusion

Required result:

C6_RETROSPECTIVE_QUALIFICATION = PASS

Only then may Platform Authority v2 be frozen for reuse.

21. Non-goals for first implementation
Do not build:

a generic distributed experiment platform;
workflow engine;
database-backed registry;
web dashboard;
PKI/signature system;
new scheduler;
new scientific runtime;
replacement for Git.
Reuse the current repository and tooling wherever possible.

22. First implementation objective
The first version only needs to prove:

1. Platform qualification can be reused.
2. Production rehearsal is real.
3. Canonical path invariants are enforced.
4. Attempt identity is isolated.
5. FORMAL_READY is one machine-readable verdict.
6. Known C6 failures are caught before Formal.
7. Small platform changes require only delta qualification.

23. Acceptance criteria
Harness v2 is ready for next-experiment use only when:

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

24. Frozen next step
Immediate next task:

HARNESS_V2_MINIMAL_IMPLEMENTATION_PLAN

The plan must be small, implementation-oriented, non-scientific, create no new governance layer, and must not implement code yet.
