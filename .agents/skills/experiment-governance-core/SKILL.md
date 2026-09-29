---
name: experiment-governance-core
description: Classify a proposed experiment or repository change and select the minimum science, platform, and Formal-authorization path. Use before implementing changes or seeking authorization; do not use to decide scientific conclusions.
---

# Experiment Governance Core

Use this skill to select the minimum governance action for a proposed or observed change using the Governance v2 behavior-impact and evidence-inheritance model. It is an operational reasoning aid, not an authority or authorization mechanism.

## Read first

Establish exact `BASE_SHA` and `TARGET_SHA` for a committed candidate, or label a working-tree proposal provisional. Inspect changed hunks, the applicable dependency map and its source-byte claim, affected Science/Platform Authority, and existing qualification evidence. Read the science contract when scientific behavior may change. An unresolved unknown blocks the plausible affected inheritance claim; do not convert uncertainty into a color.

The only primary authority layers are: Science Authority, Platform Authority, and Formal Run Authorization. Qualification evidence reports a platform check; it is never a parent authority.

## Classify and route

For each exact change, attribute changed hunks through reviewed `source_locator` entries to behavior units. Follow `dependency_edges` from consumer to dependency; a changed dependency can affect downstream consumers through reverse edges. Determine the affected protected invariants and classify each evidence family before selecting gates:

- `INHERITABLE`: its protected dependency closure is unchanged; no rerun of that evidence is required.
- `CONDITIONALLY_INHERITABLE`: an upstream prerequisite changed; name the qualification that must PASS before reuse.
- `NON_INHERITABLE`: the behavior proved by that evidence changed; rerun only its applicable proof.
- `UNMAPPED`: relevant closure, unknown scope, or map applicability is unproven; block unsafe inheritance pending review.

Use the mapped `validation_level` (L0/L1/L2/L3) and `requalification_gate` only for affected behavior. These levels define validation scope, not global severity colors. A mapped L0 test-only change with no protected scientific invariant impact needs targeted test review only. Distinguish an implementation failure from a governance-review blocker and actual scientific-evidence invalidation. Do not rerun unrelated science when an infrastructure change is disjoint from its protected closure: for example, a mapped V2-2 execution-lifecycle change may require `V2_2_EXECUTION_RELIABILITY` requalification while unchanged C7 evidence remains inheritable.

RED/YELLOW/GREEN are optional summaries **after** this reasoning, never the routing algorithm:

- `RED`: scientific treatment, baseline, metric, predicate, scheduler/service, or runtime semantics changed. Review the affected Science Authority and evidence; an unchanged platform may be reused. A later Formal attempt still needs its required exact rehearsal and fresh authorization.
- `YELLOW`: execution, platform, or evidence-path behavior changed. Qualify the affected infrastructure closure; hand production-path mechanics to `$execution-path-qualification`.
- `GREEN`: an exact review found only non-semantic supporting change. Documentation or comments are not automatically GREEN: authority text and evidence metadata can carry governance meaning.

Return concrete values, using `NONE` or `PENDING` where appropriate:

```text
BASE_SHA =
TARGET_SHA =
CHANGED_BEHAVIOR_UNITS =
AFFECTED_INVARIANTS =
MAPPING_STATUS =
UNKNOWN_SCOPE_STATUS =
EVIDENCE_INHERITANCE =
MINIMUM_REQUALIFICATION =
AFFECTED_AUTHORITY =
PROHIBITED_EXTRA_GATES =
PLATFORM_REQUALIFICATION_REQUIRED =
EXACT_REHEARSAL_REQUIRED =
FORMAL_AUTHORIZATION_REQUIRED =
BLOCKER_CLASS =
BLOCKERS =
NEXT_STAGE =
RISK_SUMMARY =
```

Use `BLOCKER_CLASS` = `IMPLEMENTATION_FAILURE`, `GOVERNANCE_REVIEW_BLOCKER`, `SCIENTIFIC_EVIDENCE_INVALIDATION`, or `NONE`. This is a Team A candidate route, not Team B acceptance or Formal authorization.

## Guardrails

- Preserve `NO_EXECUTION_PATH_FIRST_EXERCISED_IN_FORMAL`: every Formal attempt needs a fresh exact production-path rehearsal, with only its final scientific payload eligible for non-scientific substitution.
- Preserve `FORMAL_READY_IS_AUTHORIZATION = NO`, `FORMAL_READY_MUTATES_AUTHORITY = NO`, and `FORMAL_READY_REPAIRS_STATE = NO`.
- Never add a Gate unless it cites a concrete existing regression/failure mode or a documented threat to execution or evidence validity. Otherwise return it in `PROHIBITED_EXTRA_GATES` and reject it.
- Do not decide treatment outcomes, scientific conclusions, or Formal authorization. Do not introduce a fourth primary authority layer.

Team A may propose the minimum route. When frozen governance requires independent closure, hand the exact candidate to `$independent-delta-audit` for Team B verification; Team B does not invent policy during that review. For pre-Formal production-path mechanics, hand off to `$execution-path-qualification`. Do not build a new governance layer when the existing map, exact-diff review, or targeted qualification expresses the risk; report a tooling limitation if they cannot.

## V2-1 mapping and introduction boundaries

Inspect the long-lived dependency map, per-diff CIM, and exact scope review separately. `dependency_mapping_identity` identifies behavior semantics; `mapping_digest` binds the full reviewed representation; `MAP_APPLICABILITY` binds mapped source locators to exact audited bytes. A later prospective anchor cannot govern an older base where its mapped source did not exist. The map is not Platform Authority; the CIM and Team A review are evidence, not authorization.

`UNBOUNDED_UNKNOWN` blocks all plausibly affected protected closures. `SCOPED_UNKNOWN` blocks only intersecting closures. `SCOPED_ZERO_EXISTING_PROTECTED_IMPACT` may preserve unrelated old evidence only after a valid exact-bound `INTRODUCTION_ZERO_EXISTING_PROTECTED_IMPACT` review explicitly establishes no effect on existing protected behavior units, invariants, and evidence families. This is not L0, ignored, or safe by default. Per-diff review stays outside long-lived map identity; a relevant dynamic `UNMAPPED` node remains unresolved even when another hunk has zero old-graph impact.

Historical introduction review determines a newly added path's impact on the old graph. It neither proves the new behavior nor registers it for future diffs. Prospective registration is a separate later map update, anchored after the source exists. Never retrofit that map to claim prospective authority over the historical introduction diff.
