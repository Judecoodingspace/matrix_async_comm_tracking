# C7 Pre-Census Specification

```text
DOCUMENT_ROLE = C7_PRE_CENSUS_SPECIFICATION
EXPERIMENT_ID = exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census
SPEC_STATUS = DRAFT
SPECIFICATION_EXECUTION_AUTHORIZATION = NOT_AUTHORIZED
IMPLEMENTATION_AUTHORIZATION = NOT_AUTHORIZED
QUALIFICATION_AUTHORIZATION = NOT_AUTHORIZED
CENSUS_EXECUTION_AUTHORIZATION = NOT_AUTHORIZED
TRACKING_OUTCOME_READ_AUTHORIZATION = NOT_AUTHORIZED
```

## 1. Purpose

This document operationalizes only the frozen C7 Contract and frozen C7
Specification Decisions for an outcome-blind eligibility census. It does not
implement a runtime, authorize a census, assess H_R, or read tracking outcomes.
C7 qualification is testability evidence for a later independently authorized
H_R Formal; it is not causal H_R evidence.

## 2. Authority and frozen inputs

| Input | Authority |
| --- | --- |
| C7 Contract | `131bc41d22f919be24f63ae5f963ba94538daa19` |
| Contract SHA-256 | `044fe9d3538704bace3faa692ddb24d8bff9b0dd0541ed8ac145dbeaed897ec9` |
| Approval record | `6a8a802828731f20fcfa55a88c8419ca7a72926c` |
| Input evidence audit | `C7_PRE_CENSUS_INPUT_EVIDENCE_AUDIT.md` in this directory |
| Capacity derivation | `COMMUNICATION_C4_U1_U2_WORKLOAD_DERIVATION.md`, commit `24778f49ec9c913aadf95199343b12a75fd4078d` |
| C6 forensic context | `af98328b4bb7779afa7750e1a2cc3836b5df9f23` |

## 3. Scientific scope and non-goals

C7 exhaustively censes each registered realized trajectory once. It makes no
claim of CUDA replay identity, stochastic population inference, replicates, or
run-level confidence intervals. Its pair set is exactly `P23`, `P44`, and
`P66`. It neither adds a pair nor introduces a suppression treatment arm.

The census does not measure tracking improvement, IDF1, IDSW, MOTA, HOTA,
association quality, realized suppression benefit, or H_R support.

## 4. Frozen research and specification decisions

- One frame is the effective service window. Capacity resets each frame and
  can be reused only later in that same frame.
- The scientific service unit is logical-packet completion. Partial bytes do
  not commit semantics; an incomplete packet at window close has a
  within-window completion loss even if it later completes.
- TRUE-first-service stale classification is per packet, after FIFO selection
  and before its first byte. It is evaluated once and persists on the same
  unfinished logical packet; no future reclassification is permitted.
- Primary recipients are serviceable ID-State packets only. Supplement, Local
  Track, Homography, and arbitrary packets cannot satisfy the recipient gate.
- Conditional accounting holds observed baseline state, arrivals, FIFO,
  serviceability, event order, and frame budget fixed, and removes only
  authorized stale logical capacity accounting. It is not causal replay.
- Qualification is absolute and conjunctive. Zero qualified cells is valid.

## 5. Capacity-grid derivation and frozen manifest

`SD-C7-01` fixes quantiles `P20,P30,P40,P50,P60,P70,P80` over the frozen
25-pair `W_comm` distribution using `numpy.quantile(method="linear")` and the
C4 nearest-integer logical-byte convention.

| Capacity ID | Exact quantile | Decimal bytes/frame | Frozen bytes/frame |
| --- | --- | ---: | ---: |
| CAP_P20 | `203952879/12250` | 16649.214612244898 | 16649 |
| CAP_P30 | `453307079/22500` | 20146.981288888889 | 20147 |
| CAP_P40 | `995316829/39100` | 25455.673375959079 | 25456 |
| CAP_P50 | `1176644/45` | 26147.644444444446 | 26148 |
| CAP_P60 | `780030721/27750` | 28109.215171171170 | 28109 |
| CAP_P70 | `3311524393/111800` | 29620.075071556352 | 29620 |
| CAP_P80 | `43981789/1375` | 31986.755636363636 | 31987 |

The derived P20, P50, and P80 values exactly reproduce C4's frozen anchors.
The seven values are diagnostic coordinates created by SD-C7-01, not a claim
that the historical C4 envelope is an engineering capacity domain.

| Pair | Workload class | Expected frames | Registered cells |
| --- | --- | ---: | --- |
| P23 | Low | 700 | `P23__CAP_P20` through `P23__CAP_P80` |
| P44 | Median | 360 | `P44__CAP_P20` through `P44__CAP_P80` |
| P66 | High | 300 | `P66__CAP_P20` through `P66__CAP_P80` |

The exact manifest is the following 21 stable cells. Every row must bind the
listed identity plus capacity derivation authority, controlled constants,
Contract SHA, Specification SHA, and execution-authorization state.

| Cell ID | Pair | Capacity ID | Bytes/frame | Expected frames |
| --- | --- | --- | ---: | ---: |
| P23__CAP_P20 | P23 | CAP_P20 | 16649 | 700 |
| P23__CAP_P30 | P23 | CAP_P30 | 20147 | 700 |
| P23__CAP_P40 | P23 | CAP_P40 | 25456 | 700 |
| P23__CAP_P50 | P23 | CAP_P50 | 26148 | 700 |
| P23__CAP_P60 | P23 | CAP_P60 | 28109 | 700 |
| P23__CAP_P70 | P23 | CAP_P70 | 29620 | 700 |
| P23__CAP_P80 | P23 | CAP_P80 | 31987 | 700 |
| P44__CAP_P20 | P44 | CAP_P20 | 16649 | 360 |
| P44__CAP_P30 | P44 | CAP_P30 | 20147 | 360 |
| P44__CAP_P40 | P44 | CAP_P40 | 25456 | 360 |
| P44__CAP_P50 | P44 | CAP_P50 | 26148 | 360 |
| P44__CAP_P60 | P44 | CAP_P60 | 28109 | 360 |
| P44__CAP_P70 | P44 | CAP_P70 | 29620 | 360 |
| P44__CAP_P80 | P44 | CAP_P80 | 31987 | 360 |
| P66__CAP_P20 | P66 | CAP_P20 | 16649 | 300 |
| P66__CAP_P30 | P66 | CAP_P30 | 20147 | 300 |
| P66__CAP_P40 | P66 | CAP_P40 | 25456 | 300 |
| P66__CAP_P50 | P66 | CAP_P50 | 26148 | 300 |
| P66__CAP_P60 | P66 | CAP_P60 | 28109 | 300 |
| P66__CAP_P70 | P66 | CAP_P70 | 29620 | 300 |
| P66__CAP_P80 | P66 | CAP_P80 | 31987 | 300 |

`CELL_SET_MUTATION = FORBIDDEN` after freeze.

## 6. Historical calibration evidence eligibility and inventory

Only pre-C7, authoritative, outcome-blind, definition-preserving evidence can
enter a calibration distribution. Historical evidence is recurrence-scale
context only; C4/C5/C6 must not be retrospectively recounted as C7 eligible
windows.

| Evidence ID | Stage | Artifact | Measurement | Support dimension | Status |
| --- | --- | --- | --- | --- | --- |
| CE-01 | C4 | frozen workload derivation | `W_comm` quantiles | bytes/frame workload | Excluded: wrong dimension for all four threshold metrics |
| CE-02 | C5 | C5 Contract/plan | first-service denominator definition | semantic measurement convention | Included for definitions only; no aggregate calibration values established |
| CE-03 | C6 | frozen temporal forensic CSV | suppression epochs and coexistence observations | structural context | Excluded from numeric threshold calibration: it lacks C7-compatible recipient/flip support and contains zero strict coexistence |

```text
C5_AGGREGATE_CALIBRATION_AUTHORITY = NOT_ESTABLISHED
RETROSPECTIVE_CREATION_OF_NEW_C4_C5_C6_QUANTITIES = FORBIDDEN
```

## 7. Threshold-generation algorithm — BLOCKED

`SD-C7-02` requires four compatible distributions, each calibrated with the
single operator `numpy.quantile(D_x, 0.20, method="linear")`, then
`ceil(Q20)` for count-like thresholds and canonical unrounded storage for
rates. Comparison is `metric >= threshold`.

The required distributions cannot currently be built without violating the
frozen compatibility and outcome-firewall rules:

| Distribution | Required support | Status |
| --- | --- | --- |
| `D_count` | historical recurring structural-event count compatible with C7 eligible-window support | BLOCKED |
| `D_den` | historical stale-present window support | BLOCKED |
| `D_global` | historical trajectory-level structural frequency compatible with C7 eligibility | BLOCKED |
| `D_cond` | historical valid antecedent-to-consequent structural frequency compatible with C7 conditional eligibility | BLOCKED |

C5's cited aggregate values have no established safe authority. C6 strict
recipient coexistence is zero and lacks the required recipient completion-flip
definition; converting either fact into a C7 threshold would be direct
cross-stage rate copying or an invented scientific quantity. C4 workload bytes
cannot be converted to event counts or rates.

```text
T_count = BLOCKED
T_den = BLOCKED
T_global = BLOCKED
T_cond = BLOCKED
THRESHOLD_CALIBRATION_STATUS = BLOCKED
```

No C7 implementation, qualification, dry run, partial census, C7 result, or
tracking/treatment outcome may be used to remove this block.

## 8. Window, packet, stale, and recipient definitions

`WINDOW_ELIGIBLE = YES` only if all of the following are verifiable in one
frame: authorized stale logical obligation; complete event-local stale proof;
same-packet proof for any residual; serviceable ID-State recipient; baseline
finite-capacity completion loss; preserved baseline FIFO/arrival/state/event
order; authorized conditional accounting only; and a same-window recipient
completion flip from baseline incomplete to conditionally complete.

`N_all_windows`, `N_stale_present_windows`, and `N_eligible_windows` are
window counts. `conditional_opportunity_frequency` is `N/A`, not zero, when
`N_stale_present_windows = 0`; a complete such cell is valid but unqualified.

## 9. Required evidence and residual linkage

Future C7 evidence must bind cell/window identity; packet identity and channel;
arrival and true-first-service events; receiver-state projection; effects and
per-effect applicability; stale provenance; residual bytes; FIFO/event order;
frame budget; baseline service and completion; recipient serviceability;
conditional-accounting bytes and completion; and explicit stale-present and
eligible membership booleans.

Residual linkage must prove the same packet was earlier classified stale and
remains unfinished in the current baseline trajectory. Packet type or version
alone is insufficient.

## 10. Conservation, validity, and qualification

The future validator must fail closed on negative remaining bytes, capacity
creation, cross-frame capacity carryover, insufficient-byte completion,
semantic commit of an incomplete packet, FIFO violation, unstable packet ID,
invalid stale residual provenance, unauthorized removed work, reranking,
invented arrivals, or future-state reads.

Missing or unverifiable evidence yields `CELL_INVALID`, never a zero count.
Only a complete observed zero can yield `CELL_VALID=YES` and
`CELL_QUALIFIED=NO`. Qualification is unavailable until all four frozen
thresholds are mechanically calibrated.

## 11. Selection, outputs, and outcome firewall

After absolute qualification only: select maximum eligible count; resolve an
eligible-count tie through Pareto comparison of the two rates; resolve any
remaining trade-off/tie by `pair ID -> capacity ID -> cell ID`. Other passing
cells are `QUALIFIED_BUT_DEFERRED`. If none pass, select none and do not expand
the grid.

The future aggregate must include cell identity/validity, pair/capacity,
window counts, both rates, four thresholds and gate flags, qualification,
selection status, and runtime/specification provenance.

Forbidden reads include all tracking outcomes, IDF1, IDSW, MOTA, HOTA,
association metrics, C8/future Formal results, and C7 outcomes before freeze.

## 12. Freeze boundary and handoff

This draft is not approved and cannot authorize implementation. It must first
receive independent review. The calibration block must be resolved solely by
locating existing authoritative, compatible, pre-C7 outcome-blind evidence or
by a separately governed change; it cannot be filled with assumptions.

## 13. Provenance and validation checklist

```text
CONTRACT_PATH = summary_md/experiments/2026-9-20/exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census/EXPERIMENT_CONTRACT.md
CONTRACT_CONTENT_AUTHORITY_COMMIT = 131bc41d22f919be24f63ae5f963ba94538daa19
CONTRACT_SHA256 = 044fe9d3538704bace3faa692ddb24d8bff9b0dd0541ed8ac145dbeaed897ec9
INPUT_EVIDENCE_AUDIT_PATH = summary_md/experiments/2026-9-20/exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census/C7_PRE_CENSUS_INPUT_EVIDENCE_AUDIT.md
INPUT_EVIDENCE_AUDIT_SHA256 = d0074016e6a311b04e53c245e43f954f6c7fba764f5e0275555ed8eb6b4ad302
PRE_CENSUS_SPEC_PATH = summary_md/experiments/2026-9-20/exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census/C7_PRE_CENSUS_SPECIFICATION.md
PRE_CENSUS_SPEC_SHA256 = BOUND_BY_EXTERNAL_PROVENANCE_RECORD
CAPACITY_DERIVATION_AUTHORITY = 24778f49ec9c913aadf95199343b12a75fd4078d
THRESHOLD_CALIBRATION_AUTHORITY = NOT_ESTABLISHED
SPEC_STATUS = DRAFT
```

Checklist: Contract identity verified; no Research Decision or frozen
Specification Decision changed; exact grid recomputed; no C7 outcome read; no
tracking outcome read; no historical quantity created; no rate copied across
definitions; no adaptive grid/threshold action; no invalid evidence coerced to
zero; and no H_R causal claim.
