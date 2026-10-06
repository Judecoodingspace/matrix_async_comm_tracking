# V2-4 H_R Formal authorization prospective map registration

Status: **Team A registration candidate; independent Team B review pending**.

THIS REGISTRATION DOES NOT ACCEPT THE PRODUCTION CANDIDATE.

THIS REGISTRATION ONLY DEFINES PROSPECTIVE SEMANTIC COVERAGE.

FORMAL_AUTH_INFRA_CANDIDATE_SHA = `4de4e5a00abbd6c5b4205364738751a73c53c9f7`

PRODUCTION_CANDIDATE_CHANGED = NO

REAL_FORMAL_AUTHORIZATION_ISSUED = NO

H_R_FORMAL_EXECUTED = NO

## Authorities and applicability

- Registration base / accepted V2-1 inputs: `92c05753d869318bff246b1d32e28be8f4703236`.
- Exact production delta under classification: `6fe1183fbd412a0f5284cb40e0c4ef3fcd187a8e` to `4de4e5a00abbd6c5b4205364738751a73c53c9f7`.
- Original V2-4 accepted source remains `935ddcb7bba9b9894f495d84982cc310eb959c79`.
- Proposed map identity: `56c95e90942b73b7b59d87795320a743e452c7426d26c8e4af3efb2089dedd08`.
- Proposed map digest: `24e9226c67a2725769e67dd028d60913558717a8e9c40a78c7035c1f8a0429cb`.
- Proposed applicability canonical SHA-256, computed with `tracking.governance_v2.digest`: `1244b3a36231125314b8665b35ea75144e7c2cb06fe6ac6a621c48e168b802e7`.

`MAP_APPLICABILITY.json` must change with the map: the accepted
`check_applicability()` requires the claim's map identity and digest to match.
The proposed claim anchors the new locators to source bytes at the frozen
candidate commit, where their symbols actually exist. An applicability anchor
is a source-byte claim, not production acceptance. For the exact historical
base-to-candidate diff, the resulting applicability status is
`RETROSPECTIVE`; that classification cannot retroactively authorize an
execution. Independent review must judge this anchor and registration before
any reliance on it.

## Ownership

The new L1 `v2_4.hr_formal_authorization` unit protects Formal-support
consumer-record binding, Formal authorization identity, qualification/Formal
separation, fail-closed admission, and outcome blindness. It locates:

- Formal issuer imports, `issue_formal_authorization()`, `formal_launch()`,
  and the `formal-launch` CLI registration and dispatch;
- Formal-support pins, `validate_formal_support_consumer()`,
  `formal_config_expectation()`, and the Formal-specific
  `load_authorization()` branch.

Its dependencies are the existing execution authorization, preissue consumer,
qualification protocol, and runtime composition units. The new
`V2_4_H_R_FORMAL_AUTHORIZATION` evidence family proves this unit and requires
`V2_4_H_R_FORMAL_AUTHORIZATION_REVIEW`. This is a governance review gate; it
does not claim a scientific result or a completed H_R Formal run.

The existing `v2_4.hr_communication_evidence` locator now recognizes only
the Formal effective-config comparison inside real-child `execute()`.
The existing L0 `tests.v2_4_hr_production_path` unit recognizes the exact
Formal authorization test file and proves no production family. The broad
`AUTHORIZATION_` match token in the shared loader locator was narrowed to
the existing authorization error statements. This preserves the old
qualification/current-source owner while allowing a future Formal-only branch
edit to map solely to the new unit. No existing behavior unit's dependencies,
invariants, validation level, or evidence-family membership changed.

## Exact audit classification

The accepted old map/applicability reproduce `BLOCK`: seven
`UNBOUNDED_UNKNOWN` hunks and no scoped unknowns. The proposed map classifies
all nine changed hunks, including Formal functions that the old hunk-level
matcher had obscured through co-location with existing behavior.

| Item | Proposed-map result |
| --- | --- |
| Applicability for exact old-base to candidate diff | `RETROSPECTIVE` |
| Candidate classification | `CANDIDATE_REVIEWABLE_TEAM_B_PENDING` |
| Unmapped / unbounded / scoped unknowns | `0 / 0 / 0` |
| `V2_4_H_R_PRODUCTION_PATH` | `NON_INHERITABLE` |
| `V2_4_H_R_PREISSUE_CONSUMER` | `INHERITABLE` |
| `V2_4_H_R_QUALIFICATION_PROTOCOL` | `CONDITIONALLY_INHERITABLE` |
| `V2_4_H_R_FORMAL_AUTHORIZATION` | `NON_INHERITABLE` |

The computed minimum gate set is:

1. `V2_4_H_R_FORMAL_AUTHORIZATION_REVIEW`;
2. `V2_4_H_R_PRODUCTION_PATH_QUALIFICATION`;
3. `V2_4_H_R_TEST_REVIEW`.

`INDEPENDENT_DEPENDENCY_CLOSURE_REVIEW` drops from the computed set because
no unknown hunk remains. None of these gates was run by this registration.
The preissue consumer remains inheritable because its producer and historical
authorization behavior are unchanged; the qualification protocol is
conditional on the changed upstream runtime/evidence behavior. A future edit
confined to Formal issuer/admission symbols maps to the new unit and leaves
those upstream families inheritable, subject to exact source and receipt review.

## Falsification checks

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest -q \
  tests/test_governance_v2.py \
  tests/test_governance_v2_v23_registration.py \
  tests/test_governance_v2_v24_registration.py \
  tests/test_governance_v2_v24_formal_auth_registration.py
77 passed
```

The new tests reproduce the old-map block, assert exact candidate hunk
coverage, verify each new locator against candidate source bytes, and make
synthetic future edits to Formal issuance/admission, preissue, qualification,
runtime/service, real-child reconciliation, and test-only paths. Historical
V2-2/V2-3/V2-4 test fixtures remain pinned to their accepted map eras.

This Team A package is not an independent registration review, Formal
authorization, H_R qualification, C7 rerun, real preissue consumption, or
H_R Formal execution.
