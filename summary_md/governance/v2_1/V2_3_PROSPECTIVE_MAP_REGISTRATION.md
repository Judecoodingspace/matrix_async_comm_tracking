# V2-3 prospective dependency-map registration

Status: Team A registration candidate; independent registration review pending. Source implementation authority: a174dc5d718ccc73b412d0ead9554ba7d8a857d2.

This registration is prospective. It classifies future changes to the accepted V2-3 implementation. It does not retroactively reclassify the historical a13acde8f48dbfb88c009d3d6def7a49e4506ed3 → a174dc5d718ccc73b412d0ead9554ba7d8a857d2 introduction diff, which retains its exact-bound INTRODUCTION_ZERO_EXISTING_PROTECTED_IMPACT review.

The pre-existing C7, C6, and V2-2 behavior units, invariants, edges, validation levels, dynamic statuses, and evidence rows are unchanged. C6_HARNESS_DYNAMIC_BOUNDARY remains UNMAPPED.

## Registered behavior

Edges point from a consumer to behavior it depends on. All six production/qualification units are L1 and CLOSED; the test unit is L0, CLOSED, and has no protected invariants.

| New behavior unit | New protected invariants | Dependency edges |
| --- | --- | --- |
| v2_3.artifact_finalization | authoritative_artifact_identity, atomic_finalization, mechanical_science_separation, reconstructible_artifact_binding | v2_2.execution_lifecycle |
| v2_3.v21_evidence_binding | historical_v2_1_input_identity, v2_1_applicability_reuse, independent_closure_binding | None |
| v2_3.corrective_lineage | corrective_parent_immutability, purpose_scoped_supersession, sticky_verified_mismatch, raw_a2_lineage_block, retention_lineage_safety | v2_3.artifact_finalization, v2_3.v21_evidence_binding |
| v2_3.receipt_consumption | receipt_reuse_admissibility, c1_c6_fail_close, verification_depth_boundary, current_lineage_consumption | v2_3.artifact_finalization, v2_3.v21_evidence_binding, v2_3.corrective_lineage |
| v2_3.cli_interface | artifact_cli_delegation | v2_3.artifact_finalization, v2_3.receipt_consumption, v2_3.corrective_lineage |
| v2_3.qualification_protocol | v2_3_artifact_qualification_semantics | v2_3.artifact_finalization, v2_3.v21_evidence_binding, v2_3.corrective_lineage, v2_3.receipt_consumption, v2_3.cli_interface |
| tests.v2_3_artifact_qualification | None | None |

The single new evidence family is V2_3_ARTIFACT_ARCHITECTURE. It proves the six L1 V2-3 units above and uses V2_3_ARTIFACT_ARCHITECTURE_QUALIFICATION as its minimum gate. The L0 test unit has its own test-review gate and is not a proven unit of that evidence family.

## Exact identities and applicability

- dependency_mapping_identity: a6d8f572b1f41fa8607743d03bb7cd4e8b479bfbf7f36a4b909926fa8c89641c
- mapping_digest: 0b61884bbf137cb8cec5e3c5ef5fc19dc958250b817078e8d9fc8e52f8bec286
- MAP_APPLICABILITY.json anchor: a174dc5d718ccc73b412d0ead9554ba7d8a857d2
- Audited non-L0 source set: 12 paths, comprising all nine previously mapped paths plus src/tracking/governance_v2_artifacts.py, scripts/governance_v2_artifacts.py, and scripts/qualify_governance_v2_3.py.

The identities were generated with make_mapping(). The applicability claim was generated with make_applicability() at the accepted implementation SHA and exactly reproduces under that function.

## Qualification

Focused command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_governance_v2_v23_registration.py → 9 passed. Synthetic future Git commits separately changed finalization, historical V2-1 binding, sticky A2 correction, C1–C6 consumption, CLI delegation, and qualification protocol. Each change targets V2_3_ARTIFACT_ARCHITECTURE and its gate while all C7/V2-2 evidence stays inheritable and C6 stays unmapped. A V2-3 test-only change remains L0 and leaves the production evidence inheritable.

Regression command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_governance_v2.py tests/test_governance_v2_execution.py tests/test_governance_v2_artifacts.py tests/test_governance_v2_v23_registration.py → 99 passed. The new focused regression verifies that a historical V2-1 CIM still validates through its pre-registration Git-pinned map and applicability inputs after the current map changes.

No production source, scientific runtime, C7 execution, or H_R execution was changed or run. H_R Formal is not authorized.
