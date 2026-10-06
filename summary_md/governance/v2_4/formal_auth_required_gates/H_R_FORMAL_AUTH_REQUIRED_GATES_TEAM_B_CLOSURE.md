# H_R Formal authorization required gates — independent Team B closure

REVIEW_ROLE = INDEPENDENT_TEAM_B
DECISION = ACCEPT
INDEPENDENT_V2_4_H_R_FORMAL_AUTH_REQUIRED_GATES_REVIEW = PASS

ACCEPTED_MAP_AUTHORITY = ca42bde13f06017e74504156965f62474c878bd1
FORMAL_AUTH_INFRA_PRODUCTION_CANDIDATE_SHA = 4de4e5a00abbd6c5b4205364738751a73c53c9f7
FORMAL_SUPPORT_BASE_SHA = 6fe1183fbd412a0f5284cb40e0c4ef3fcd187a8e
TEAM_A_SUPPORT_SHA = 52d4ec3faa64e7cddca9425197a043b6b06c392c
TEAM_A_PACKAGE_SHA256 = 71b03c246efa98c5e0a7286d61c273ffff7f651ce05feff3ec008f25d7150a78
CIM_SHA256 = 0f8440c945c979685b60d8c0bd2069a5957f71590838208772c69630cae65c19

The Team A support commit adds only its package and CIM. The package and CIM byte hashes match the stated identities. The CIM equals an independent `audit_diff()` recomputation using the accepted map at `ca42bde...`: `CANDIDATE_REVIEWABLE_TEAM_B_PENDING`, `RETROSPECTIVE` applicability, nine changed hunks, zero unknowns, and exactly the three gates below. The map, production candidate, and scientific evidence were not changed by the support commit.

## Gate 2 — production-path qualification

QUALIFICATION_ATTEMPT_ID = v2_4_hr_qual_004
QUALIFICATION_AUTHORIZATION_SHA256 = 17f4753c8b5ce07339eac69f6faff5ff45bfc65273ac18cb417c888d706363c8
RAW_SHA256 = 4a2c54265e23b629c8b5f628c8a1db7f169fee2def79e6c9b803abac007c7fb9
NORMALIZED_SHA256 = ab3c56833a707b8cbb55e92de9ca20c5242cbee0708c18bbab48da6176aebea0
EFFECTIVE_CONFIG_SHA256 = fec449c99f8a38c6d765a850e267ae671bf8bbbeeb82ad6191ab37add476294d
MANIFEST_SHA256 = 068c28d68b24714d34ef35e7edede6e916c749c60b76f84af93346324fd81640
VALIDATION_RECEIPT_SHA256 = dc5053a6f4a4529e034ae50226f7df61b74f129b46f81487ce30085b0730ad5c
FINALIZATION_RECEIPT_SHA256 = 4c19c51f70228c69bf6ce73b0e14eefe5fbcb3d88f8f5d6424ce9db5391f1af7

All seven hashes were recomputed from attempt-local files. The authorization is `H_R_PRODUCTION_AUTHORIZATION_V1`, binds `v2_4_hr_qual_004` and source `4de4e5a...`, sets `qualification_only=true` and three frames, and selects `P66__P20` at 16649 bytes. The sole launch record names the real H_R child; V2-2 terminal state is `COMPLETED` with child return code 0. The child reports real generated-runtime execution and a structural `PASS`, both outcome blind. V2-3 `inspect()` returns `FINALIZED`, and manifest, validation, and finalization receipt references agree. Read-only `load_authorization()` and RAW-to-NORMALIZED/effective-config replay passed against the actual files.

`v2_4_hr_qual_003` is historical failed environment evidence, not gate evidence. It used the same source SHA and three-frame qualification mode, but terminated before RAW, normalization, or finalization. Its author log reports `torch.cuda.is_available() is False` while loading the checkpoint; `qual_004` subsequently completed under the CUDA-visible environment. No production-source correction is implied by `qual_003`.

V2_4_H_R_PRODUCTION_PATH_QUALIFICATION = PASS

## Gate 1 — Formal authorization implementation

The exact `6fe1183...` to `4de4e5a...` source diff was inspected. `issue_formal_authorization()` requires the fixed content-verified Formal-support consumer before issuing a separate `H_R_FORMAL_AUTHORIZATION_V1` object. The existing consumer record has SHA-256 `45cb1631497311fa416840ec84fd55b90b13b42c3a8cb7386e8f52ad94e71fc9`, purpose `H_R_FORMAL_PREISSUANCE`, class `FORMAL_AUTHORIZATION_SUPPORT`, `REUSE_ADMISSIBLE`, `CONTENT` verification, and six passing checks. The loader rechecks that byte hash, purpose, corrective-child lineage, and bound V2-1 CIM/attestation identities.

Qualification `launch` accepts only qualification schema and mode; `formal_launch` accepts only Formal schema. The Formal loader binds authorization hash, attempt ID and root, output root, selected cell and capacity, source HEAD and current operator/child/runtime bytes, frozen wrapper/preparer, service and suppression configs, effective-config expectation, and the consumer-record hash. The real child compares Formal expected versus observed effective config. Authorization writing uses exclusive `xb` creation and refuses an occupied target. The issuer and admission path do not read tracking outcomes or result metrics.

V2_4_H_R_FORMAL_AUTHORIZATION_REVIEW = PASS

## Gate 3 — tests and decision

Independent focused reruns:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_mdmt_mia_hr_production_path.py tests/test_mdmt_mia_hr_formal_authorization.py
58 passed

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q -p no:cacheprovider tests/test_governance_v2_v24_formal_auth_registration.py
17 passed
```

The tests cover qualification/Formal separation, consumer tampering, attempt/output/source/config/schema failure, occupied-target refusal, and accepted-map locator classification. The actual `qual_004` evidence was separately verified read-only.

V2_4_H_R_TEST_REVIEW = PASS
ALL_THREE_REQUIRED_GATES_CLOSED = YES
P0_COUNT = 0
P1_COUNT = 0
P2_COUNT = 0

This record closes the three required review gates for the frozen candidate. It does not issue a real Formal authorization or execute H_R Formal.

REAL_FORMAL_AUTHORIZATION_ISSUED = NO
H_R_FORMAL_EXECUTED = NO
TRACKING_OUTCOME_READ = NO
