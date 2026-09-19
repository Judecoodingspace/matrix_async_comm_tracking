---
name: experiment-governance-core
description: Classify a proposed experiment or repository change and select the minimum science, platform, and Formal-authorization path. Use before implementing or authorizing experiment changes; do not use to decide scientific conclusions.
---

# Experiment Governance Core

Use this skill to route a proposed change through the qualified Harness v2 model. It is an operational reasoning aid, not an authority and not an authorization mechanism.

## Read first

Establish the actual `BASE_SHA`, `HEAD_SHA` (or working-tree delta), affected files, current Science Authority, `PLATFORM_AUTHORITY_V2`, and qualification evidence. Read the applicable science contract before classifying a scientific change. Treat an unknown change as one risk level higher.

The only primary authority layers are: Science Authority, Platform Authority, and Formal Run Authorization. Qualification evidence reports a platform check; it is never a parent authority.

## Classify and route

Classify each affected behavior, then use the highest class:

- `RED`: treatment, baseline, metric, predicate, scheduler/service semantics, scientific runtime behavior, or another scientific semantic. Require scientific review/new or amended Science Authority as applicable. Reuse an unchanged platform, but require a fresh exact rehearsal and a fresh Formal authorization before a Formal run.
- `YELLOW`: Operator, Launcher, Real Child, Wrapper, canonical paths, attempt layout, production evidence/validator behavior, or failure propagation. Identify the affected platform component, compute the resulting platform identity, and require only its affected delta qualification plus exact rehearsal.
- `GREEN`: documentation, comments, or presentation/non-semantic wording. Require static delta review only.

Return exactly these fields, with concrete values rather than a generic checklist:

```text
RISK_CLASS =
AFFECTED_AUTHORITY =
AFFECTED_INVARIANTS =
REQUIRED_GATES =
PROHIBITED_EXTRA_GATES =
PLATFORM_REQUALIFICATION_REQUIRED =
EXACT_REHEARSAL_REQUIRED =
FORMAL_AUTHORIZATION_REQUIRED =
BLOCKERS =
NEXT_STAGE =
```

## Guardrails

- Preserve `NO_EXECUTION_PATH_FIRST_EXERCISED_IN_FORMAL`: every Formal attempt needs a fresh exact production-path rehearsal, with only its final scientific payload eligible for non-scientific substitution.
- Preserve `FORMAL_READY_IS_AUTHORIZATION = NO`, `FORMAL_READY_MUTATES_AUTHORITY = NO`, and `FORMAL_READY_REPAIRS_STATE = NO`.
- Never add a Gate unless it cites a concrete existing regression/failure mode or a documented threat to execution or evidence validity. Otherwise return it in `PROHIBITED_EXTRA_GATES` and reject it.
- Do not decide treatment outcomes, scientific conclusions, or Formal authorization. Do not introduce a fourth primary authority layer.

For a proposed implementation delta, compose this skill with `$independent-delta-audit`; for pre-Formal mechanical readiness, hand off to `$execution-path-qualification`.
