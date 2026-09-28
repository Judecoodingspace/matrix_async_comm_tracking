# Governance v2 V2-1 — Corrective Revision #2

Status: Team A self-check complete; Team B independent delta review pending. Corrective baseline is `6828bebc74347e6c74d23060bb739aaa0534cab6`. No V2-2 or H_R Formal authority is issued.

## Structural correction

CR1 placed five exact Q3 hunk-review decisions in `DEPENDENCY_MAP.json` and hashed them into `dependency_mapping_identity`. Those decisions concern one historical diff, so CR2 moved them to `candidate_evidence/Q3_UNKNOWN_SCOPE_REVIEW.json`. The long-lived map now contains only behavior units, dependency edges, protected invariants, validation levels, dynamic status, evidence-family semantics, and source locators. Its schema rejects extra top-level records such as `reviewed_unknown_scopes`.

No behavior, dependency, invariant, or evidence-family semantics changed. Removing the per-diff records therefore naturally restored the original semantic identity `ae802ff343f82acdc4966bf497c6c96e5b2e1590c547c6cd174544637172d2d5`; it was not hard-coded. The full map digest also returned to `193f15657a853027658ee60d75bac4e6545a727c9fc89af931c7de18b123d307`. `MAP_APPLICABILITY.json` was regenerated from the same anchor `89256787c93036fa1350a97a9832ae9a56c03cac` and source bytes.

## Exact per-diff binding

`audit_diff()` accepts an optional, explicit scope-review object. The existing `scripts/audit_governance_v2_delta.py` CLI needed the matching `--unknown-scope-review` option so an operator can supply this separate evidence without any implicit map lookup. The Q3 artifact is Team A candidate evidence, not authority. It binds map identity/digest, exact base/target SHAs, raw diff SHA256, and each reviewed path, hunk header, and changed-line hunk digest. Each row also records potential behavior units, derived potential invariants/evidence families, and a review rationale. The auditor recomputes those closures from the current map. Any top-level mismatch or row identity/closure mismatch rejects the entire review. An unmatched hunk without a trusted exact row is `UNBOUNDED_UNKNOWN` and blocks unsafe inheritance.

With the valid Q3 artifact, all five unmatched hunks are `SCOPED_UNKNOWN`; C7 FIFO, capacity, and eligibility families stay `INHERITABLE`, while C7 full-domain and C6 Harness are `UNMAPPED`. Q3 remains `BLOCK` because its dynamic boundary is unresolved. Without the artifact, the five hunks become `UNBOUNDED_UNKNOWN` and C7 mechanism families also become `UNMAPPED`. A mismatched artifact is rejected and has the same conservative fail-close result. The dynamic boundary remains unresolved in every case.

Q1/Q2 receive no unrelated scope-review input and preserve their CR1 classifications: C6 Harness is `UNMAPPED` even though unchanged; Q1 C7 families stay inheritable; Q2 C7 eligibility is non-inheritable while FIFO/capacity/full-domain remain inheritable. The consumer → dependency edge direction and reverse downstream invariant propagation are unchanged.

## Verification and limits

The specified five-file regression suite reports **235 passed in 22.20s**. Python compile, `git diff --check`, and fresh qualification generation at `/tmp/v2_1_cr2_qualification_final_20260928` passed. The new committed CIMs match that fresh output. The exact Q3 review rationale still requires independent Team B scrutiny; family-level classifications do not authorize reuse of a concrete historical receipt or Formal execution.
