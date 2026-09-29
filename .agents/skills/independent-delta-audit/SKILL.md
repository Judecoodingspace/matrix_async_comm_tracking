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

Run `scripts/audit_governance_v2_delta.py --base <BASE_SHA> --target <TARGET_SHA> [--unknown-scope-review <EXACT_REVIEW_JSON>]` as a candidate cross-check. Per-diff scope review is separate evidence and must never be inferred from the long-lived dependency map. Its output is not the independent verdict. Recompute source-symbol and dynamic-dispatch coverage yourself; selectors and AST containment are conservative aids, not a complete Python call graph.

## Derive impact

1. Verify the real diff and the exact source bytes. A changed HEAD proves a change occurred, not that every invariant changed.
2. Verify mapping identity, digest, and source-byte applicability. Equivalent source rename may retain semantic identity only with an auditable new applicability claim; changed behavior-to-invariant edges, protected coverage, or dynamic status require a new identity. A map anchored after a historical base cannot be treated as prospectively applicable to that base.
3. For each changed hunk, identify its behavior unit, protected invariant, and L0/L1/L2/L3 validation scope. Unmatched hunks are not GREEN: `SCOPED_UNKNOWN` blocks intersecting protected closures; `UNBOUNDED_UNKNOWN` fails closed across plausible closures. Verify exact per-diff review against map identity/digest, base/target SHA, raw diff SHA, path, hunk header, hunk digest, and scope basis. The explicit zero-existing-impact introduction case below is distinct from ordinary unknowns and test-only L0.
4. Traverse declared consumer → dependency edges and downstream impact through reverse edges. Check importlib, reflection, monkeypatching, dynamic dispatch, C extensions, generated source, config, and runtime environment within the protected closure, including unchanged nodes. Keep any older relevant dynamic `UNMAPPED` node unresolved even when an unrelated new hunk has zero old-graph impact; do not build a whole-repository call graph.
5. Classify each **actual prior evidence receipt**: `INHERITABLE` if its protected closure is unchanged; `CONDITIONALLY_INHERITABLE` if only an upstream prerequisite changed and a named qualification must PASS; `NON_INHERITABLE` if the proved behavior changed; `UNMAPPED` if closure/applicability or relevant unknown scope cannot be established. Keep infrastructure and scientific evidence separate when their closures are disjoint. A family-level CIM classification without a receipt hash is not authorization to reuse an artifact.
6. Verify that Team A's proposed static, mechanism, real-slice, or orchestration checks are sufficient and not excessive; identify any missing required gate as a correction. Team B does not originate frozen policy. A new Formal attempt still needs its exact rehearsal and separate authorization; hand production-path mechanics to `$execution-path-qualification`. Do not treat historical Formal results as qualification of a new candidate.

## Historical introduction and prospective registration

For `INTRODUCTION_ZERO_EXISTING_PROTECTED_IMPACT`, independently confirm the path was **added** in this exact diff, the semantic was explicitly selected, and `potential_behavior_units`, `potential_invariants`, and `potential_evidence_families` are all explicitly empty. Recompute the map identity/digest, base and target SHA, raw diff SHA, path, hunk header and hunk SHA bindings; judge whether the non-empty `scope_basis` credibly excludes impact on the pre-existing protected graph. A valid `SCOPED_ZERO_EXISTING_PROTECTED_IMPACT` review may preserve unrelated old evidence, but does not prove or authorize the new behavior or add it to the map. Missing or implausible closure remains `BLOCK`.

For historical introduction, use the map applicable to that historical base and its exact-bound per-diff review. For future descendants, verify the separate prospective map registration is anchored only after the new source exists. Prospective registration does not retroactively qualify historical execution authority.

Return `BASE_SHA`, `TARGET_SHA`, `DIFF_SHA256`, `MAP_IDENTITY`, `MAP_DIGEST`, `MAPPING_APPLICABILITY`, changed behavior units, affected invariant closure, unknown paths, evidence decisions with conditions, and verified minimum requalification. Include `UNKNOWN_SCOPE_KIND`, `INTRODUCTION_REVIEW_STATUS`, and `REGISTRATION_STAGE` when relevant. Distinguish `IMPLEMENTATION_FAILURE`, `GOVERNANCE_REVIEW_BLOCKER`, and `SCIENTIFIC_EVIDENCE_INVALIDATION`; issue an independent audit `PASS` or `BLOCK`, not Formal authorization. If Team A's CIM disagrees, return `CORRECTION_REQUIRED` or `BLOCK` with exact contrary evidence.

Never repair, retry, authorize, modify historical artifacts, or read tracking outcomes to complete this audit. Verify frozen governance rules; if they cannot express a legitimate case, report the tooling limitation rather than silently weakening semantics or adding a map-of-map, new layer, or new skill. Preserve the three primary authority layers: Science, Platform, and Formal Run Authorization.
