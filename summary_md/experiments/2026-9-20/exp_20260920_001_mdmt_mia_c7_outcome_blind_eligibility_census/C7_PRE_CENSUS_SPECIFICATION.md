# C7 Pre-Census Specification

```text
DOCUMENT_ROLE = C7_PRE_CENSUS_SPECIFICATION
EXPERIMENT_ID = exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census
CORRECTIVE_REVISION = 2
SPEC_STATUS = READY_FOR_TEAM_B_DELTA_AUDIT
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
| Threshold authority recovery audit | `C7_THRESHOLD_CALIBRATION_AUTHORITY_RECOVERY_AUDIT.md`, SHA-256 `95064461a4bab68d1c38e2b941f94dd9f3a928df2c10697ce54563ef0fba4d78`, commit `86cc2ca38a0ad6bdca3dfe3046132289cc071497` |
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
HISTORICAL_P20_THRESHOLD_ARCHITECTURE = SUPERSEDED
HISTORICAL_P20_THRESHOLD_ARCHITECTURE_STATUS = SUPERSEDED_BY_CSD_C7_01_THROUGH_CSD_C7_08
```

## 7. Corrective threshold derivation and qualification rule

### 7.1 Superseded historical architecture and corrective trigger

The historical P20 calibration inventory above and its original blocker remain
part of the revision history. The Threshold Calibration Authority Recovery
Audit recovered `D_count` and `D_den`, partially recovered `D_global`, and
could not recover `D_cond` from existing lawful pre-C7 authority. Therefore the
historical architecture could not be completely instantiated.

For provenance, the superseded architecture required four compatible
distributions, each processed by
`numpy.quantile(D_x, 0.20, method="linear")`, followed by `ceil(Q20)` for
count-like thresholds and canonical unrounded storage for rates. Comparison
was `metric >= threshold`. Its required support was:

| Historical distribution | Required support |
| --- | --- |
| `D_count` | historical recurring structural-event count compatible with C7 eligible-window support |
| `D_den` | historical stale-present window support |
| `D_global` | historical trajectory-level structural frequency compatible with C7 eligibility |
| `D_cond` | historical valid antecedent-to-consequent structural frequency compatible with C7 conditional eligibility |

At the superseded Specification SHA
`f120a75088910524b1c268bc7258f8386800ed1c1d1caf015c342f22ca5b5797`,
all four current-threshold fields and threshold calibration were blocked:

```text
HISTORICAL_SUPERSEDED_T_count = BLOCKED
HISTORICAL_SUPERSEDED_T_den = BLOCKED
HISTORICAL_SUPERSEDED_T_global = BLOCKED
HISTORICAL_SUPERSEDED_T_cond = BLOCKED
HISTORICAL_SUPERSEDED_THRESHOLD_CALIBRATION_STATUS = BLOCKED
```

C5's cited aggregate values had no established safe authority. C6 strict
recipient coexistence was definition-incompatible with the required recipient
completion-flip relation, and C4 workload bytes could not be converted to
event counts or rates. No implementation, qualification, dry run, partial
census, C7 result, or tracking/treatment outcome was permitted to remove that
historical block.

```text
HISTORICAL_D_COUNT_AUTHORITY_STATUS = RECOVERED
HISTORICAL_D_DEN_AUTHORITY_STATUS = RECOVERED
HISTORICAL_D_GLOBAL_AUTHORITY_STATUS = PARTIALLY_RECOVERED
HISTORICAL_D_COND_AUTHORITY_STATUS = NOT_RECOVERABLE_FROM_EXISTING_PRE_C7_AUTHORITY
HISTORICAL_THRESHOLD_CALIBRATION_AUTHORITY_RECOVERED = PARTIAL
HISTORICAL_FROZEN_CALIBRATION_ARCHITECTURE_INSTANTIABLE = NO
HISTORICAL_P20_THRESHOLD_ARCHITECTURE = SUPERSEDED_BY_CSD_C7_01_THROUGH_CSD_C7_08
```

This supersession is not an empirical falsification by P20 or by any C7
outcome. Existing lawful pre-C7 authority could not fully instantiate the
frozen historical calibration architecture, so a separately governed,
outcome-blind corrective derivation was required. The historical derivation,
Recovery Audit, and original blocker remain provenance evidence; they are not
deleted or rewritten.

### 7.2 Frozen corrective decisions

`CSD-C7-01` through `CSD-C7-09` are frozen and introduce no change to the
Contract's scientific scope. `CSD-C7-01` through `CSD-C7-08` retain the
Revision #1 threshold derivation, while `CSD-C7-09` clarifies its logical
interpretation:

- Exposure is used only for fairness and feasibility; different registered
  trajectory lengths are not structurally penalized by one high raw-count
  threshold.
- `T_count` remains an explicit minimum-recurrence invariant: fewer than five
  eligible redistribution opportunities can never qualify. It is not
  `alpha * trajectory_length`. Its semantic role is explicit and traceable,
  but it is mathematically redundant over the current frozen registered
  domain.
- Stale-present support remains a separate, substantively distinct criterion,
  with `T_den > T_count`, so a high conditional fraction on a thin denominator
  cannot qualify. This inequality does not establish that every gate is
  mathematically non-redundant.
- The two integer thresholds have distinct mechanical sources:
  `T_count` comes from minimum recurrence and `T_den` from conditional-rate
  resolution. The historical unified ruler is not restored.
- Minimum recurrence is `5`, hence `T_count = 5`.
- Conditional-rate discrete resolution is five percentage points, hence
  `T_den = 20`. This is not a confidence interval.
- With registered trajectory lengths `P23=700`, `P44=360`, and `P66=300`, the
  shortest trajectory has 300 frames. Therefore `T_global = 5/300 = 1/60`.
  The canonical comparison value is exactly `1/60`, not rounded `1.67%`.
- `T_cond = 5/20 = 1/4`, stored and compared canonically as exactly `1/4`.
- `CSD-C7-09` intentionally retains `T_count=5` as the visible
  minimum-recurrence invariant even though `G1` is implied both by `G3` and by
  `G2 AND G4` throughout the current frozen registered domain. Mathematical
  non-redundancy is not required.

The global gate mechanically implies minimum eligible counts of 5 for P66,
6 for P44, and 12 for P23. These are consequences of the single `1/60` gate,
not additional thresholds.

```text
T_count = 5
T_den = 20
T_global = 1/60
T_cond = 1/4
THRESHOLD_DERIVATION_STATUS = FROZEN_BY_CORRECTIVE_SPECIFICATION_DECISIONS
CSD_C7_09 = FROZEN
T_COUNT_ROLE = MINIMUM_RECURRENCE_INVARIANT
T_COUNT_MATHEMATICALLY_REDUNDANT_OVER_FROZEN_DOMAIN = YES
T_COUNT_REDUNDANCY_INTENTIONAL = YES
```

### 7.3 Four conjunctive criteria and their explanatory roles

Every valid cell qualifies only if all four gates pass:

```text
N_eligible_windows >= 5
AND N_stale_present_windows >= 20
AND N_eligible_windows / N_all_windows >= 1/60
AND N_eligible_windows / N_stale_present_windows >= 1/4
```

All comparisons use `>=`; equality passes. The criteria have distinct
scientific and explanatory roles. This does not mean that all four have
mathematically independent exclusion power over the current frozen domain:

1. `N_eligible_windows >= 5` states the explicit minimum-recurrence invariant:
   fewer than five opportunities are categorically insufficient. In the
   current domain it does not independently change PASS/FAIL.
2. `N_stale_present_windows >= 20` protects against a conditional rate built
   on extremely thin stale-context support.
3. `N_eligible_windows / N_all_windows >= 1/60` prevents a longer trajectory
   from qualifying on the same five sparse events alone.
4. `N_eligible_windows / N_stale_present_windows >= 1/4` requires genuine
   redistribution opportunities not to be only a tiny minority of
   stale-present contexts.

The four gates are conjunctive and unweighted. Ranking and Pareto comparison
occur only after qualification and cannot substitute for any gate.

#### 7.3.1 Gate redundancy audit

Within the frozen registered domain, `N_all_windows` is one of
`{300, 360, 700}`. The following outcome-free implications are exact:

```text
G2: N_stale_present_windows >= 20
G4: N_eligible_windows / N_stale_present_windows >= 1/4

G2 AND G4
=> N_eligible_windows >= 20 * 1/4
=> N_eligible_windows >= 5
=> G1
```

Independently, the global-frequency gate implies:

```text
G3 at N_all_windows = 300 => integer N_eligible_windows >= 5
G3 at N_all_windows = 360 => integer N_eligible_windows >= 6
G3 at N_all_windows = 700 => integer N_eligible_windows >= 12

therefore G3 => G1 for every frozen registered trajectory
```

```text
GATE_REDUNDANCY_AUDIT = PASS
T_COUNT_REDUNDANT_OVER_FROZEN_DOMAIN = YES
T_COUNT_REDUNDANCY_INTENTIONAL = YES
T_COUNT_RETAINED_AS_EXPLICIT_INVARIANT = YES
G2_AND_G4_IMPLIES_G1 = YES
G3_IMPLIES_G1_OVER_REGISTERED_DOMAIN = YES
```

Retaining `T_count=5` is deliberate: it preserves the frozen
minimum-recurrence scientific statement; makes the rule “fewer than five is
unacceptable” directly visible to reviewers; prevents that semantic invariant
from silently disappearing if a future registered domain or threshold is
changed through separate formal governance; and preserves traceability to
`CSD-C7-02` and `CSD-C7-05`. It remains explicitly evaluated and reported, but
no claim is made that it currently changes PASS/FAIL independently.

```text
THRESHOLD_VALUES_CHANGED = NO
QUALIFICATION_FUNCTION_CHANGED = NO
QUALIFICATION_BEHAVIOR_CHANGED = NO
BOUNDARY_OPERATOR_CHANGED = NO
```

### 7.4 Boundary and zero-denominator handling

For complete evidence with `N_stale_present_windows = 0`:

```text
CELL_VALID = YES
CELL_QUALIFIED = NO
conditional_opportunity_frequency = N/A
```

Missing, incomplete, unverifiable, or internally inconsistent evidence yields
`CELL_INVALID`; it must never be converted to an observed zero.

### 7.5 Mechanical qualification fixtures

| Case | `N_all` | `N_stale` | `N_eligible` | Count | Denominator | Global | Conditional | Overall |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |
| A | 300 | 20 | 5 | PASS | PASS | PASS | PASS | PASS |
| B | 700 | 20 | 5 | PASS | PASS | FAIL | PASS | FAIL |
| C | 300 | 100 | 5 | PASS | PASS | PASS | FAIL | FAIL |
| D | 300 | 5 | 5 | PASS | FAIL | PASS | numerically PASS | FAIL |
| E | 300 | 0 | 0 | FAIL | FAIL | FAIL | N/A | valid but unqualified |

Case E assumes complete evidence. The exact global-gate consequences are
`ceil(300/60)=5`, `ceil(360/60)=6`, and `ceil(700/60)=12`.

No C7 implementation, qualification, dry run, partial census, C7 result, or
tracking/treatment outcome was used in this corrective derivation.

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
`CELL_QUALIFIED=NO`. For every other valid cell, qualification uses the four
frozen corrective thresholds in Section 7 conjunctively.

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

This corrective specification is not approved and cannot authorize
implementation. The historical calibration block has been resolved only by
the separately governed outcome-blind `CSD-C7-01` through `CSD-C7-08`; it was
not resolved from any C7 or tracking outcome. The document is ready for an
Team B delta audit of the `CSD-C7-09` gate-redundancy clarification, which
remains mandatory before any later authorization stage.

## 13. Provenance and validation checklist

```text
CONTRACT_PATH = summary_md/experiments/2026-9-20/exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census/EXPERIMENT_CONTRACT.md
CONTRACT_CONTENT_AUTHORITY_COMMIT = 131bc41d22f919be24f63ae5f963ba94538daa19
CONTRACT_SHA256 = 044fe9d3538704bace3faa692ddb24d8bff9b0dd0541ed8ac145dbeaed897ec9
INPUT_EVIDENCE_AUDIT_PATH = summary_md/experiments/2026-9-20/exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census/C7_PRE_CENSUS_INPUT_EVIDENCE_AUDIT.md
INPUT_EVIDENCE_AUDIT_SHA256 = d0074016e6a311b04e53c245e43f954f6c7fba764f5e0275555ed8eb6b4ad302
THRESHOLD_RECOVERY_AUDIT_PATH = summary_md/experiments/2026-9-20/exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census/C7_THRESHOLD_CALIBRATION_AUTHORITY_RECOVERY_AUDIT.md
THRESHOLD_RECOVERY_AUDIT_SHA256 = 95064461a4bab68d1c38e2b941f94dd9f3a928df2c10697ce54563ef0fba4d78
SUPERSEDED_PRE_CENSUS_SPEC_SHA256 = f120a75088910524b1c268bc7258f8386800ed1c1d1caf015c342f22ca5b5797
REVISION_1_CANDIDATE_COMMIT = 73386375eaccb2fdf6cb20ad8c3a5cced82ff714
REVISION_1_SPEC_SHA256 = 5b9321d1757934629873c9c1788a2067af8b9c0e3c4214563d18cd70445b5da1
REVISION_1_RECORD_SHA256 = 126f1e9a6a6b7d32fd0df7d8a1557689c66d7790ad77085cb16068351bde47f1
PRE_CENSUS_SPEC_PATH = summary_md/experiments/2026-9-20/exp_20260920_001_mdmt_mia_c7_outcome_blind_eligibility_census/C7_PRE_CENSUS_SPECIFICATION.md
PRE_CENSUS_SPEC_SHA256 = BOUND_BY_EXTERNAL_PROVENANCE_RECORD
CAPACITY_DERIVATION_AUTHORITY = 24778f49ec9c913aadf95199343b12a75fd4078d
THRESHOLD_DERIVATION_AUTHORITY = CSD_C7_01_THROUGH_CSD_C7_09
THRESHOLD_DERIVATION_STATUS = FROZEN_BY_CORRECTIVE_SPECIFICATION_DECISIONS
SPEC_STATUS = READY_FOR_TEAM_B_DELTA_AUDIT
```

Checklist: Contract identity verified; no Research Decision or frozen
Specification Decision changed; exact grid recomputed; no C7 outcome read; no
tracking outcome read; no historical quantity created; no rate copied across
definitions; historical P20 architecture retained as superseded provenance; no
adaptive grid/threshold action; no invalid evidence coerced to zero; no H_R
causal claim; and Revision #2 changes neither threshold values nor
qualification behavior.
