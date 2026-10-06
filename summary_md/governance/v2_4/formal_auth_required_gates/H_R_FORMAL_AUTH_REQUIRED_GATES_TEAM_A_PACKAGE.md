# H_R Formal authorization: required gates, Team A support package

Status: **ready for one combined independent Team B review; no gate self-accepted**.

This package supports only `V2_4_H_R_FORMAL_AUTHORIZATION_REVIEW`,
`V2_4_H_R_PRODUCTION_PATH_QUALIFICATION`, and `V2_4_H_R_TEST_REVIEW`.
It does not issue Formal authorization or report tracking outcomes.

## Frozen authority and classification

| Identity | Exact value |
| --- | --- |
| Accepted V2-1 map inputs commit | `ca42bde13f06017e74504156965f62474c878bd1` |
| Formal-support comparison base | `6fe1183fbd412a0f5284cb40e0c4ef3fcd187a8e` |
| Unchanged Formal-auth production candidate | `4de4e5a00abbd6c5b4205364738751a73c53c9f7` |
| Live `github` production branch SHA, read back with `ls-remote` | `4de4e5a00abbd6c5b4205364738751a73c53c9f7` |
| Accepted mapping semantic identity | `56c95e90942b73b7b59d87795320a743e452c7426d26c8e4af3efb2089dedd08` |
| Accepted mapping digest | `a93a9c292ec6e1a56ed8d628eb110c58828a32cf2623b875fa6bbede82723fb7` |
| Raw Git diff SHA-256 | `3d138626af6c1bab117285842c6a7a662a53defbbcb46e026ccaa936d0a4a5fe` |

The adjacent `H_R_FORMAL_AUTH_REQUIRED_GATES_CIM.json` was emitted by
`scripts/audit_governance_v2_delta.py` using the accepted map and applicability
files at the exact inputs commit. It classifies the unchanged base-to-candidate
delta as `CANDIDATE_REVIEWABLE_TEAM_B_PENDING`, with applicability
`RETROSPECTIVE`, nine changed hunks, and **zero unmapped, unbounded, and scoped
unknowns**. Its minimum gate set is exactly the three gates above. The
applicability anchor is source-byte coverage, not acceptance of this candidate.

## Gate 2: one replacement production-path qualification

`v2_4_hr_qual_003` remains an immutable, failed environment-only pre-RAW
attempt. Its authorization SHA-256 is
`dbb93c448587285cdb82faed87dc93a6f2faaae10933e55b2e5032568609d184`.
The author-side checkpoint loader could not see CUDA devices inside the
restricted sandbox; no RAW, normalized, or effective-config evidence was
produced by that attempt. Nothing in `qual_003` was reused or finalized.

Before creating its replacement, a read-only preflight used the exact author
interpreter `/mnt/data/yzm/experiments/mdmt_mia_official/.conda-env/bin/python`
with `PYTHONNOUSERSITE=1` outside the GPU-restricted sandbox. PyTorch
`1.10.0+cu113` reported CUDA available, two devices, device 0
`NVIDIA GeForce RTX 3090`, and successfully allocated a tensor on `cuda:0`.
The frozen production worktree was clean at the exact candidate SHA, and the
`qual_004` attempt and authorization paths were absent before launch.

Exactly one new qualification launch was made:

```text
PYTHONDONTWRITEBYTECODE=1 YOLO_CONFIG_DIR=/tmp python scripts/qualify_mdmt_mia_hr_production_path.py \
  --attempts-root /tmp/mdmt_mia_v2_4_qualification_20261006 \
  --attempt-id v2_4_hr_qual_004
```

The launch used the CUDA-visible execution environment. The authorization is
`H_R_PRODUCTION_AUTHORIZATION_V1`, `qualification_only=true`,
`qualification_frame_count=3`, source SHA `4de4e5a...`, and frozen cell
`P66__P20` / pair `P66` / capacity `P20` / `16649` bytes. It is not a Formal
authorization. The child completed, the accepted structural verdict was
`PASS`, and V2-3 state was `FINALIZED`. The qualification report states
`tracking_outcome_read=false` and `h_r_formal_executed=false`.

| Immutable attempt-local object | Path below `/tmp/mdmt_mia_v2_4_qualification_20261006/` | SHA-256 |
| --- | --- | --- |
| Qualification authorization | `v2_4_hr_qual_004_authorization.json` | `17f4753c8b5ce07339eac69f6faff5ff45bfc65273ac18cb417c888d706363c8` |
| RAW evidence | `v2_4_hr_qual_004/output/hr/H_R_RAW_EVIDENCE.jsonl` | `4a2c54265e23b629c8b5f628c8a1db7f169fee2def79e6c9b803abac007c7fb9` |
| NORMALIZED evidence | `v2_4_hr_qual_004/output/hr/H_R_NORMALIZED_EVIDENCE.json` | `ab3c56833a707b8cbb55e92de9ca20c5242cbee0708c18bbab48da6176aebea0` |
| Effective config | `v2_4_hr_qual_004/output/hr/H_R_EFFECTIVE_CONFIG.json` | `fec449c99f8a38c6d765a850e267ae671bf8bbbeeb82ad6191ab37add476294d` |
| Manifest | `v2_4_hr_qual_004/v2_3/manifest.json` | `068c28d68b24714d34ef35e7edede6e916c749c60b76f84af93346324fd81640` |
| Validation receipt | `v2_4_hr_qual_004/v2_3/validation_receipt.json` | `dc5053a6f4a4529e034ae50226f7df61b74f129b46f81487ce30085b0730ad5c` |
| Finalization receipt | `v2_4_hr_qual_004/v2_3/finalization_receipt.json` | `4c19c51f70228c69bf6ce73b0e14eefe5fbcb3d88f8f5d6424ce9db5391f1af7` |

These hashes reference the finalized attempt. This package did not copy
runtime evidence into Git or write to the attempt after finalization.

## Gate 3: focused test-review support

Both commands passed without modifying production tests:

```text
# Run at production candidate 4de4e5a...
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q \
  tests/test_mdmt_mia_hr_production_path.py \
  tests/test_mdmt_mia_hr_formal_authorization.py
58 passed

# Run at accepted map authority ca42bde...
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q \
  tests/test_governance_v2_v24_formal_auth_registration.py
17 passed
```

The candidate tests cover qualification-only and three-frame authorization,
qualification rejection at `formal_launch`, Formal issuance/admission
separation, tampered consumer SHA/decision/C1-C6, attempt ID, output root,
selected cell/capacity, operator/child/runtime/wrapper/preparer identities,
service/suppression/effective configs, schema/purpose, and occupied-target
fail-close. The accepted-map regression covers prospective Formal-only locator
ownership and negative shared-loader separation. One initial combined test
command named the registration file in the production worktree, where that
later map-registration file does not exist; pytest collected no tests from
that command. The two version-correct commands above passed.

## Gate 1: static Formal-auth review support

Review the frozen candidate with `git show 4de4e5a00abbd6c5b4205364738751a73c53c9f7:<path>`
and its exact base-to-candidate diff. Source-byte SHA-256 values are:

| Candidate source path | SHA-256 | Review focus |
| --- | --- | --- |
| `scripts/run_mdmt_mia_hr_formal.py` | `69c9bd8bcfb73520fa342dc34f8a0dac924920c5085897ac119f2ff4d445d38a` | `_auth` line 45; `issue_formal_authorization` line 55; qualification `launch` line 90; `formal_launch` line 100; CLI line 202 |
| `src/tracking/mdmt_mia_hr_evidence.py` | `84ca835fafa1d567ea13c873c4837359730856edc3e5ad57e30b75c2cf4d3592` | `validate_formal_support_consumer` line 371; `formal_config_expectation` line 417; `load_authorization` line 428 |
| `scripts/run_mdmt_mia_hr_real_child.py` | `741459c97b39dc280a8604b49f228289e1113647e5aa03dfa9e4273109c9dd0a` | qualification tiny input line 48; bounded environment line 70; child execution line 108; Formal-only effective-config reconciliation line 151 |
| `scripts/qualify_mdmt_mia_hr_production_path.py` | `f47a7fa99524c6d4d6e4006a929d0bf7bdfc2feeea6d13a28b24accd8c554002` | qualification authorization builder line 43; three-frame qualification and selected-cell binding |
| `tests/test_mdmt_mia_hr_formal_authorization.py` | `ec7b9d8be95b95c2b7224d7bbdad5ef6d2b78afe0e70d7a687ab3fc0eeab541d` | issue/admit separation line 67; qualification rejection line 85; identity fail-close line 103; consumer fail-close line 135; no-overwrite line 151 |

Specific admission boundaries for Team B to inspect:

- **Schema and separation:** `issue_formal_authorization` changes the
  qualification template into `H_R_FORMAL_AUTHORIZATION_V1`, with
  `qualification_only=false` and zero qualification frames. `launch` accepts
  only qualification schema; `formal_launch` accepts only Formal schema.
- **Consumer record:** issuance calls `validate_formal_support_consumer` before
  writing; `load_authorization` rechecks its content SHA and binding. The
  accepted upstream record is separately retained at SHA-256
  `45cb1631497311fa416840ec84fd55b90b13b42c3a8cb7386e8f52ad94e71fc9`.
- **Attempt/output and selected condition:** `load_authorization` binds
  `attempt_id`, `run_id`, resolved attempt root and Formal output root;
  `formal_launch` checks `P66__P20` and `16649` bytes. The accepted selection
  loader checks the frozen C7 selection/validation identities.
- **Source/config identities:** the loader binds source SHA and exact
  operator/child/runtime/wrapper/preparer hashes; the Formal branch validates
  service, suppression, and effective-config expectations. The child compares
  the Formal effective config after RAW collection.
- **No overwrite and fail-close:** the issuer rejects occupied authorization
  or attempt targets. Tests cover missing/tampered record and identity fields.
- **Outcome blindness:** qualification inspected structural/mechanical status
  only; no ID-switch result, tracking metric, or Formal outcome was read.

This is Team A review support, not an independent verdict or an execution
authorization.

## Upstream reuse and handoff

The real Formal-support consumer record was hash-checked at its existing path
`/tmp/mdmt_mia_v2_4_qualification_20260929/formal_support/v2_4_hr_qual_002__validator_cr1__formal_authorization_support.json`.
`V2_4_H_R_PREISSUE_CONSUMER`, `validator_cr1`, the Formal-support V2-1
reference, and C7 selected-cell evidence were not regenerated. The existing
consumer record was reused as upstream authority and not changed.

```text
REAL_FORMAL_AUTHORIZATION_ISSUED = NO
H_R_FORMAL_EXECUTED = NO
TRACKING_OUTCOME_READ = NO
PRODUCTION_CANDIDATE_CHANGED = NO
DEPENDENCY_MAP_CHANGED = NO
TEAM_B_ACCEPTANCE_WRITTEN = NO
```

Next step: one combined independent Team B closure review of the three gates.
