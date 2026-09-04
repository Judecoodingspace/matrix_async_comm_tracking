# SOURCE_MDA_V1_G6_FIXTURE_CLOSURE_REPORT

## A. EXECUTIVE VERDICT

```text
G6 converter determinism: PASS (previously frozen)
G6 evaluator row-order invariance: PASS
outside=1 source rows: 0
outside accounting consistent: YES

G1-G5 rerun: NO
G7 rerun: NO
Tracking run: NO
MVE run: NO
```

## B. FIXTURE DESCRIPTION

Evaluator used:

```text
src/evaluation/mdmt_mia_paper.py
load_mot_gt -> cross_view_mda
source SHA-256: ea9805ad770e6278a2271b5c1d9d5c981eb44a3fe21f53472b82c4bd672bdfdb
```

The fixed synthetic fixture has two paired views, frames `0, 1`, identities
`101, 202, 303`, eight GT rows per variant, and eight static prediction rows.
Each frame contains two GT rows in each view. No detector, tracker, MIA process
or real MDMT prediction supplied the fixture.

## C. ROW-ORDER PERTURBATION

```text
GT_A SHA-256: ac3218a89c176d9fb09e5a7864a55e6f5766317e07b6f56e50bb5f03e3639eb7
GT_B SHA-256: 9682af62d92b789f83ace336ebfef8d8aae91e2e0980ac0bb162e0722b3c1146

row multiset equal: YES
row order equal: NO
prediction fixture SHA-256: a70e18c24e6f5a6c5201802ae3e6ceace3577047e08d06f3518989b101fb0134
```

GT_B reverses the two rows within each same-frame/view group. No frame, ID,
bbox, multiplicity or prediction changed.

## D. EVALUATOR OUTPUT COMPARISON

| Metric | GT_A | GT_B | Equal |
| --- | ---: | ---: | --- |
| MDA | 1.0 | 1.0 | YES, exact numeric equality |
| AAS | 1.0 | 1.0 | YES, exact numeric equality |

The two per-frame output records are also exactly equal. This fixture invokes
only the MDA/AAS core; it does not invoke the separate MOTMetrics path, so MOTA,
IDF1 and IDSW are not reported or inferred here.

## E. OUTSIDE COUNT

```text
XML files: 60
source rows: 1,610,691
outside=1: 0
outside=0: 1,610,691
train outside=1: 0
val outside=1: 0
XML files containing outside=1: 0
```

Thus the previously recorded `authorized exclusions = 0` is consistent.

## F. SCIENTIFIC BOUNDARY

This run does not validate E023, compensation, d5 replication or onset. It does
not run Pair 53/66, tracking, detector, ByteTrack, MIA or a real MDA scientific
evaluation; it does not inspect val outcomes or infer official export filtering.
`OFFICIAL_EXPORT_FILTER_POLICY` remains `UNKNOWN`.

## G. FINAL STATE

```text
G6_FIXTURE_CLOSURE_PASS
OUTSIDE_POPULATION_COUNT_CONSISTENT
FRESH_G1_G7_SOURCE_PROTOCOL_PREFLIGHT_PASS
READY_FOR_SEPARATELY_AUTHORIZED_TRACKING_MVE
TRACKING_MVE_EXECUTED = NO
```

Machine-readable evidence is ignored under:

```text
outputs/20260904_mdmt_source_mda_v1_g6_fixture_closure/g6_fixture_closure.json
SHA-256: 7003b2568dd9fe6c595964acaa75e396af24a05bb7c8f0d159a1e57d20e4649b
```
