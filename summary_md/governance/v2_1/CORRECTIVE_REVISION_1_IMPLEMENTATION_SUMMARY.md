# Governance v2 V2-1 — Corrective Revision #1

Status: Team A self-check complete; Team B independent delta review pending. Corrective baseline: `55adcec432dc824acfb17daeaf622ad38b2ce712`. This revision changes only V2-1 governance code, its map/evidence, tests, and directly related review text. It does not authorize V2-2 or H_R Formal execution.

## Findings closed

- **P1-1 scoped unknown:** The Q3 unmatched Harness hunks are bound to exact raw diff SHA256 and individual hunk digests in `DEPENDENCY_MAP.json`. Each scope records its exact path/hunk, conservative potential units, and review rationale. The bound scope includes Harness dynamic binding and C7 launch eligibility; it does not include the independent C7 FIFO, registered-capacity, or credit implementation closures. Any unmatched hunk without an exact reviewed rule is `UNBOUNDED_UNKNOWN`, blocks candidate acceptance, and marks every potentially affected mapped family `UNMAPPED`. A matched unresolved dynamic unit is also explicitly scoped to its declared downstream closure. The CIM records kind, basis, potential units/invariants/families, and changed-hunk references.
- **P1-2 unresolved closure:** Every evidence family checks all nodes in its protected dependency closure for `dynamic_dependency_status=UNMAPPED`, even when those nodes did not change. Q1 and Q2 now classify `C6_HARNESS_DYNAMIC_BOUNDARY` as `UNMAPPED`; there is no invented closure receipt.
- **P2 affected closure:** Dependency edges mean consumer → dependency. The implementation traverses reverse edges from changed units to all downstream consumers and reports both `affected_behavior_units` and their `affected_invariants`. A synthetic capacity-propagation change reaches FIFO, released-credit, and eligibility invariants through the declared graph.

## Map and real cases

The five exact Q3 hunk-scope rules change map semantics; therefore the dependency mapping identity changed to `5ad83a7d5b1fe20caae10dabe152d6d61160afa4e0d7be4f45dfac6c5b8b385d` and the full mapping digest changed to `76609323eb03373eb96d643c003cd147f1b76a1c6ddb3a97aab2653520705316`. The anchor implementation remains `89256787c93036fa1350a97a9832ae9a56c03cac`; `MAP_APPLICABILITY.json` was regenerated against the same source bytes. No existing behavior edge was changed.

Q1 remains a reviewable real L1 case: source cleanliness is affected; C7 FIFO, capacity, eligibility, and full-domain families remain inheritable within the declared closed map. Q2 remains a reviewable real L2 case: C7 eligibility reconstruction is non-inheritable; FIFO and capacity remain inheritable. In both, the unresolved C6 Harness family is `UNMAPPED`. Q3 remains `BLOCK`: C6 Harness and C7 full-domain path are `UNMAPPED`, while C7 FIFO, capacity, and eligibility remain inheritable as family-level classifications because the exact reviewed Q3 changes do not enter their declared protected closures.

These historical-case CIMs classify evidence *families*, not concrete receipt reuse or Formal readiness. Team B must independently check the exact Q3 scope rationale and the absence of any omitted path from the protected closures.

## Verification

The required regression suite reports **224 passed in 16.94s**. Python compile and `git diff --check` passed. A fresh qualification output was generated at `/tmp/v2_1_cr1_qualification_final_20260928` and copied into `candidate_evidence/`. No scientific Formal experiment ran.
