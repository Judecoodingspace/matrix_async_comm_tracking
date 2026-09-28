# Governance v2 — V2-1 Foundation candidate

Status: `TEAM_A_SELF_CHECK`; independent Team B verdict pending. No Formal authority or historical artifact is changed.

## Base and scope

- Repository: `Judecoodingspace/matrix_async_comm_tracking`
- Base: `89256787c93036fa1350a97a9832ae9a56c03cac`, historical C7 execution harness. Dedicated branch: `impl/20260928-governance-v2-1-foundation`.
- Historical C7 scientific core: `9140104ca2bf3d395b3012dcae32506e5abfb9cf` (unchanged).
- V2-1 adds a **governance analysis tool** and refactors existing governance/delta-audit skill instructions. It does not enter the C7 runtime or change Harness v2 readiness/Platform Authority bytes.

## Implementation

- `src/tracking/governance_v2.py`: canonical semantic map identity and full map digest, exact SHA/diff validation, changed-hunk token plus AST symbol attribution, declared dependency closure, evidence-family inheritance decisions, and `UNMAPPED` fail-close.
- `scripts/audit_governance_v2_delta.py`: read-only per-diff CIM CLI. A `CANDIDATE_REVIEWABLE_TEAM_B_PENDING` result is never an independent PASS or Formal authorization.
- `scripts/qualify_governance_v2_1.py`: rerunnable Team A qualification against three real repository commits, with output to a **fresh** caller-specified directory. Committed results are under `candidate_evidence/`.
- `DEPENDENCY_MAP.json`: selected semantic C7/C6 behaviors; it is deliberately not a whole-repository call graph. `dependency_mapping_identity` hashes behavior IDs, protected invariants, edges, levels, dynamic status, and evidence-family dependency semantics. `mapping_digest` also hashes source locators/selectors. A symbol rename may preserve semantic identity only with a new auditable applicability claim.
- `MAP_APPLICABILITY.json`: one reviewed anchor implementation SHA and exact mapped **production source** hashes. A new Git SHA that changes only unrelated files need not clone the map. Historical Q cases are explicitly `RETROSPECTIVE`; future targets are applicable only to the audited base source bytes and require delta review of target changes. A target-source semantic alteration requires review, and a changed edge requires a new map identity.
- `tests/test_governance_v2.py`: schema/identity, applicability drift, three real Git diffs, and conditional inheritance checks. The machine-readable observed test result is `candidate_evidence/TEST_SUMMARY.json` (220 passed).

## Exact qualification cases

| Case | Real commit | Observed behavior | Candidate outcome |
| --- | --- | --- | --- |
| Q1 L1 | `ec8be0bc7098da015956b7e9fe56dbe21bb6a9f6` | `run_mdmt_mia_c7_real_child._build_wrapper_environment` adds `PYTHONDONTWRITEBYTECODE`; separate test hunk. | Source-cleanliness gate required; FIFO, capacity propagation, and eligibility evidence families remain `INHERITABLE`. |
| Q2 L2 | `f484ac5b886e68393c581936f1e764d4d08366d8` | `derive_source_removable_work`, `_evaluate_fifo_conditional_accounting`, and `validate_core_evidence` bind credit to displaced current-frame service. | C7 eligibility evidence family `NON_INHERITABLE`; FIFO and registered-capacity families remain `INHERITABLE`. |
| Q3 dynamic | `0aa88ea1d02d9cfe1d81f923cf4a73c2dd6062dc` | Real `run_harness_v2.py` platform component binding changes; same production module uses `importlib.util.spec_from_file_location` to load execution modules. Other affected hunks also lack reviewed mapping. | `UNMAPPED` and `BLOCK`; no false GREEN. |

These are retrospective classification proofs using real source commits, not authorization to reuse a historical qualification receipt. The `evidence_id` entries are *families*. Concrete old evidence requires an additional receipt digest, applicability closure, and independent review before inheritance is accepted.

## Historical evidence applicability

- C6 `PLATFORM_QUALIFICATION_EVIDENCE_V2.json` remains historical evidence for its exact C6 Platform Authority. Its `98c7e39d...` platform identity is not silently asserted for the C7 Full-21 launcher or this candidate. Reuse for another platform is `UNMAPPED` until component identity and execution-closure compatibility are proven.
- C5 Q3S/Q5 path qualification is historical evidence of C5 source/root bindings. It cannot directly qualify new C7 paths; no C5 evidence receipt is reused by V2-1.
- C7 MVE 003, Full-21 package, independent structural audit, and controlled release remain valid historical records. They are not inherited as qualification of a new implementation or a future Formal attempt. V2-1 does not read their tracking outcomes, alter them, or revalidate them.

## Requalification and limitations

`INHERITABLE` requires an unchanged protected closure; `CONDITIONALLY_INHERITABLE` names the upstream gate that must PASS; `NON_INHERITABLE` requires a new proof of changed behavior; `UNMAPPED` blocks reuse. Q1/Q2 show affected checks rather than full requalification by default.

Known limits: selected-map scope only (L3 scientific-specification changes have no reviewed behavior node and therefore fail closed as unknown); token/AST matching cannot prove complete Python dynamic dependency closure; C6 Harness dynamic loading remains explicitly `UNMAPPED`; map applicability is base-byte binding plus target delta review, not automatic endorsement of target semantics; candidate CIMs classify evidence families, not concrete historical receipt hashes. Integration with Formal readiness, process supervision, telemetry, artifact deduplication, and full production rehearsal belong to later phases. Team B must independently audit map completeness and every proposed inheritance.

## Reproduce

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /mnt/data/deeplearning_env/anaconda3/bin/python -m pytest -q tests/test_governance_v2.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qualify_governance_v2_1.py --output-dir /tmp/v2_1_review_fresh_output
```

The second command requires a fresh directory and does not execute scientific work. The committed `candidate_evidence/` JSON records exact base/target SHAs, raw diff SHA256, map identity/digest, hunk attribution, evidence-family classifications, and minimum requalification.
