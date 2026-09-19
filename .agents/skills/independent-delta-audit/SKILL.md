---
name: independent-delta-audit
description: Independently audit a Git BASE_SHA-to-HEAD_SHA delta and determine the smallest justified Harness v2 requalification scope. Use for review independent of the implementing agent; do not modify the audited repository.
---

# Independent Delta Audit

Audit Git and byte-level evidence directly. Do not accept an implementer’s summary in place of `git diff`, artifact hashes, or the current Platform Authority. This is a review aid, not an authority layer and not a repair workflow.

## Audit

1. Verify `BASE_SHA`, `HEAD_SHA`, branch, and exact changed paths with Git. Inspect the relevant hunks and bytes, including uncommitted changes when they are in scope.
2. Classify every changed file: `RED` for science semantics (treatment, baseline, metric, predicate, scheduler/service/runtime behavior); `YELLOW` for platform mechanics (Operator, Launcher, Real Child, Wrapper, path/attempt/evidence/validator/failure propagation); `GREEN` for non-semantic docs/comments/presentation. Escalate uncertainty by one level.
3. Map affected frozen invariants and identify unrelated changes. Compare changed production component bytes to the Platform Authority and verify that tests or rehearsal evidence do not enter `PLATFORM_V2_SHA`.
4. Return the smallest justified scope. A science-only delta can reuse the platform but needs a fresh exact rehearsal before Formal. A wrapper/runtime byte delta requires a new platform SHA and affected platform-delta qualification. A test-only change or new rehearsal evidence alone must not change the platform SHA. Docs-only needs static review only.

Use this output schema:

```text
BASE_SHA =
HEAD_SHA =
CHANGED_FILES =
RISK_CLASS_BY_FILE =
AFFECTED_INVARIANTS =
P0 =
P1 =
P2 =
P3 =
SCIENCE_AUTHORITY_IMPACT =
PLATFORM_V2_SHA_IMPACT =
QUALIFICATION_EVIDENCE_IMPACT =
REQUALIFICATION_SCOPE =
DELTA_REVIEW =
VERDICT =
```

## Boundaries

Do not modify files, normalize historical artifacts, silently waive unrelated changes, issue authorization, or replace real diff evidence with claims. Preserve attempt/evidence immutability and the three primary authority layers. If a proposed new governance Gate has no cited regression/failure mode or documented execution/evidence threat, report it as rejected rather than adding it.
