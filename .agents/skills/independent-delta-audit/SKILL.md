---
name: independent-delta-audit
description: Independently audit an exact Git base-to-target delta against the versioned Governance v2 dependency map, evidence inheritance, and minimal requalification scope. Never modify the audited repository or issue Formal authorization.
---

# Independent Delta Audit — V2-1

This skill is a review procedure, not an authority layer. Team A may prepare a candidate CIM; an independent Team B reviewer must derive its own findings from the exact candidate SHA.

## Inputs

- Exact 40-character `BASE_SHA` and `TARGET_SHA`; inspect `git diff --binary --no-renames`, file modes, new/deleted files, and relevant working-tree state.
- Versioned `DEPENDENCY_MAP.json`, its recomputed semantic identity and full mapping digest, and `MAP_APPLICABILITY.json`.
- Actual source bytes at the map anchor and the candidate endpoint, plus prior evidence receipts when inheritance of a concrete artifact is proposed.
- Frozen scientific spec and current Platform Authority, only where affected.

Run `scripts/audit_governance_v2_delta.py --base <BASE_SHA> --target <TARGET_SHA>` as a candidate cross-check. Its output is not the independent verdict. Recompute source-symbol and dynamic-dispatch coverage yourself; selectors and AST containment are conservative aids, not a complete Python call graph.

## Derive impact

1. Verify the real diff and the exact source bytes. A changed HEAD proves a change occurred, not that every invariant changed.
2. Verify mapping identity, digest, and applicability. Equivalent source rename may retain the semantic map identity only with an auditable new applicability claim. Changed behavior-to-invariant edges, protected coverage, or dynamic status require a new map identity.
3. For each changed hunk, identify the semantic behavior unit and protected invariant. A single file may contain L0/L1/L2 behaviors. A path or hunk that cannot be mapped is `UNMAPPED`, never GREEN. Verify each unknown item's exact reviewed scope: `SCOPED_UNKNOWN` blocks only intersecting protected closures; absent an auditable scope, `UNBOUNDED_UNKNOWN` fails closed broadly.
4. Traverse declared dependency edges. Check importlib, reflection, monkeypatching, dynamic dispatch, C extensions, generated source, config, and runtime environment. Inspect the entire protected closure, including unchanged nodes. If any relevant dynamic path cannot be closed, mark its family `UNMAPPED` and block unsafe inheritance.
5. Classify each **actual prior evidence receipt**: `INHERITABLE` if its protected closure is unchanged; `CONDITIONALLY_INHERITABLE` if only an upstream prerequisite changed and a named qualification must PASS; `NON_INHERITABLE` if the proved behavior changed; `UNMAPPED` if closure/applicability cannot be established. A family-level CIM classification without a receipt hash is not authorization to reuse an artifact.
6. Specify only affected static, mechanism, real-slice, or orchestration checks. A new Formal attempt still needs an exact rehearsal and a new authorization. Do not treat historical Formal results as qualification of a new candidate.

Return `BASE_SHA`, `TARGET_SHA`, `DIFF_SHA256`, `MAP_IDENTITY`, `MAP_DIGEST`, `MAPPING_APPLICABILITY`, changed behavior units, affected invariant closure, unknown paths, evidence decisions with conditions, required requalification, and an independent `PASS` or `BLOCK`. If the Team A CIM disagrees, return `CORRECTION_REQUIRED` or `BLOCK` with exact contrary evidence.

Never repair, retry, authorize, modify historical artifacts, or read tracking outcomes to complete this audit. Preserve the three primary authority layers: Science, Platform, and Formal Run Authorization.
