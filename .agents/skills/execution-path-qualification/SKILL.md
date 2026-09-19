---
name: execution-path-qualification
description: Check a specific experiment attempt’s mechanical readiness with the qualified Harness v2 interface before Formal execution. Use for pre-Formal path qualification, not scientific review or authorization issuance.
---

# Execution-Path Qualification

Use the repository’s existing Harness v2 interfaces; do not recreate their validators or operator logic in prose or code. This skill reports readiness only. `FORMAL_READY` is not authorization and does not mutate authority or repair state.

## Preconditions and checks

Discover the active Platform Authority and current platform identity; do not use a literal SHA from a prior run. Check that `PLATFORM_QUALIFICATION_EVIDENCE_V2` exists, is `PASS`, and binds the computed current `PLATFORM_V2_SHA`. Check that the proposed attempt namespace is absent and distinct from historical attempts. Classify quarantined evidence as execution-artifact state, not source or authority dirt, unless source/authority bytes independently differ.

Use the qualified entry point with inactive input authority material:

```bash
PYTHONHASHSEED=0 PYTHONNOUSERSITE=1 <qualified-python> \
  scripts/run_harness_v2.py qualify \
  --science-authority <science-authority> \
  --platform-authority <platform-authority> \
  --formal-authorization-candidate <inactive-candidate> \
  --attempt-id <fresh-attempt-id>
```

When all read/validation checks pass, this command’s non-scientific rehearsal must traverse the real Operator → Launcher → Real Child → subprocess → Wrapper → cwd transition → environment propagation → evidence writer → validator path. Only its final scientific payload may be fake. Do not treat package validation, a mocked subprocess, or a direct child invocation as equivalent.

Return one machine-readable assessment:

```text
PLATFORM_V2_SHA =
QUALIFICATION_EVIDENCE_STATUS =
QUALIFICATION_EVIDENCE_BINDS_CURRENT_PLATFORM =
ATTEMPT_NAMESPACE_STATUS =
EXACT_REHEARSAL_STATUS =
FORMAL_READY =
BLOCKER =
FORMAL_AUTHORIZATION_ISSUED = NO
SCIENTIFIC_WORKLOAD_EXECUTED = NO
NEXT_STAGE =
```

## Hard boundary

Do not issue Formal authorization, repair or retry an attempt, delete quarantine evidence, auto-commit/push, run scientific work, or read tracking outcomes. A failed check is a blocker for a human or separately authorized workflow; it is not permission to mutate the repository or attempt.
