# V2-4 / H_R prospective dependency-map registration

Status: **Team A registration candidate; independent registration review pending**. The accepted production-source authority is `935ddcb7bba9b9894f495d84982cc310eb959c79`. This registration starts from `f0687193ed720c3732e1c656dcda8d284b34ae80`; its commit will carry map, applicability, this note, and tests, without changing production source. It classifies future H_R changes only. The historical V2-4 introduction and `6da670a` → `935ddcb` consumer-corrective reviews retain their original exact-bound evidence and independent closure.

All 20 old behavior rows, seven old evidence rows, and 32 old protected invariants are exact prefixes of the new map. Every previously audited non-L0 source path has identical bytes at the new source anchor. `harness.resolve_dynamic_modules` and `C6_HARNESS_DYNAMIC_BOUNDARY` remain `UNMAPPED`; H_R has no dependency edge to the C6 Formal harness.

## Registered behavior

Edges point from consumer to dependency. All new production/qualification units are `L1` and `CLOSED`; the test unit is `L0`, `CLOSED`, has no protected invariant, and proves no production family. Locators name actual functions and behavior-specific tokens at the accepted source SHA. An atomic function uses `*` only when the entire function owns that registered behavior.

| Unit | New protected invariants | Dependency edges | Gate |
| --- | --- | --- | --- |
| `v2_4.hr_execution_authorization` | `h_r_selected_cell_identity`, `h_r_current_source_identity`, `h_r_frozen_wrapper_preparer_identity` | none | `V2_4_H_R_PRODUCTION_PATH_QUALIFICATION` |
| `v2_4.hr_suppression_service_binding` | `h_r_suppression_before_first_byte`, `h_r_fifo_suppression_coexistence`, `h_r_suppression_seal_integrity` | `runtime.fifo_frame_service`, `runtime.parse_registered_capacity` | `V2_4_H_R_PRODUCTION_PATH_QUALIFICATION` |
| `v2_4.hr_runtime_composition` | `h_r_attempt_local_runtime`, `h_r_real_wrapper_execution`, `h_r_generated_source_integrity`, `h_r_outcome_quarantine` | `v2_4.hr_execution_authorization`, `v2_4.hr_suppression_service_binding`, `v2_2.execution_lifecycle` | `V2_4_H_R_PRODUCTION_PATH_QUALIFICATION` |
| `v2_4.hr_communication_evidence` | `h_r_raw_normalized_provenance`, `h_r_effective_config_reconciliation`, `h_r_structural_verdict_boundary` | `v2_4.hr_execution_authorization`, `v2_4.hr_suppression_service_binding`, `v2_4.hr_runtime_composition`, `v2_3.artifact_finalization` | `V2_4_H_R_PRODUCTION_PATH_QUALIFICATION` |
| `v2_4.hr_historical_authorization` | `h_r_historical_git_source_identity`, `h_r_historical_authorization_fail_closed` | `v2_4.hr_execution_authorization` | `V2_4_H_R_PREISSUE_CONSUMER_QUALIFICATION` |
| `v2_4.hr_preissue_consumer` | `h_r_corrective_child_pin`, `h_r_child_receipt_anchor`, `h_r_formal_support_reuse_gate` | `v2_4.hr_historical_authorization`, `v2_3.artifact_finalization`, `v2_3.corrective_lineage`, `v2_3.receipt_consumption` | `V2_4_H_R_PREISSUE_CONSUMER_QUALIFICATION` |
| `v2_4.hr_qualification_protocol` | `h_r_tiny_qualification_boundary`, `h_r_qualification_outcome_blind` | `v2_4.hr_execution_authorization`, `v2_4.hr_runtime_composition`, `v2_4.hr_communication_evidence`, `v2_3.artifact_finalization` | `V2_4_H_R_QUALIFICATION_PROTOCOL_REVIEW` |
| `tests.v2_4_hr_production_path` | none | none | `V2_4_H_R_TEST_REVIEW` |

The production evidence family `V2_4_H_R_PRODUCTION_PATH` proves only execution authorization, suppression/service binding, real-child composition, and communication evidence. `V2_4_H_R_PREISSUE_CONSUMER` separately proves historical-Git authorization and the fixed corrective-child receipt consumer. `V2_4_H_R_QUALIFICATION_PROTOCOL` proves only non-scientific qualification orchestration. A future preissue-only or historical-Git-only edit therefore does not make the real runtime production family non-inheritable; a current-worktree authorization edit does reach it.

## Identities and source applicability

- New `dependency_mapping_identity`: `78c539edd5cab75e83ea97410d606eecf50efda970a8c5781f80669a80da7a70`.
- New `mapping_digest`: `8dba7c8e5f861728f80e4b178991748189a734346332db4d72c0971bbd425868`.
- Both were computed by `make_mapping()`. `make_applicability()` anchors at the accepted production-source commit `935ddcb7bba9b9894f495d84982cc310eb959c79`, not at this registration commit.
- New non-L0 audited source paths are `scripts/qualify_mdmt_mia_hr_production_path.py`, `scripts/run_mdmt_mia_hr_formal.py`, `scripts/run_mdmt_mia_hr_real_child.py`, and `src/tracking/mdmt_mia_hr_evidence.py`. The H_R-relevant `src/tracking/mdmt_mia_async_deadline_runtime.py` was already audited. The L0 test path is excluded from applicability.

For a future Formal-support V2-1 package against the accepted unchanged implementation, `v2_1_inputs_commit` must identify the accepted registration commit containing the new map/applicability, while the CIM implementation base and target are both `935ddcb7bba9b9894f495d84982cc310eb959c79`. The registration commit is not substituted as the implementation target.

## Registration checks

Focused registration tests: **11 passed**. Synthetic future Git diffs separately exercise real-child runtime composition, first-service suppression, raw/evidence validation, preissue-only changes, historical-Git-only authorization, current-worktree authorization, qualification-only changes, and test-only changes. They verify the runtime/preissue/qualification evidence-family separation and unchanged legacy C7/V2-2/V2-3 classifications. `C6_HARNESS_DYNAMIC_BOUNDARY` remains `UNMAPPED` without becoming an H_R blocker.

Governance regression: **110 passed** across Governance v2 core, V2-2 execution, V2-3 artifacts, V2-3 registration, and V2-4 registration. The 9 historical V2-3 registration tests use the small registration-only fixture in `tests/conftest.py` to read their accepted V2-3 map/applicability snapshot at `f068719`, since those tests assert that V2-3 was the last registered domain. The new V2-4 tests read the current extended map directly. H_R production-path regression: **30 passed**.

`POST_REGISTRATION_FORMAL_SUPPORT_V21_SYNTHETIC_CHECK = PASS`: a temporary Git commit pinned the proposed map/applicability, and a synthetic no-delta CIM with implementation base/target both at `935ddcb` yielded `CANDIDATE_REVIEWABLE_TEAM_B_PENDING`, no unmapped unknown paths, and non-blocked applicability. A temporary exact independent attestation for `H_R_FORMAL_PREISSUANCE` with only relied `V2_4_H_R_PREISSUE_CONSUMER` evidence and all actual minimum requalification obligations closed passed `artifacts._v21_check()`. An old V2-1 map/applicability Git pin also passed the historical compatibility regression after the current map changed.

The synthetic attestation is a test fixture, not new authority. Real `FORMAL_AUTHORIZATION_SUPPORT` reuse was **not run**, no real consumer record was written, and H_R Formal remains unauthorized and unexecuted. Independent review of this registration candidate remains pending.
