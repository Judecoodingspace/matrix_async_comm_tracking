# GT Protocol Gate Report

## G7 decision

```text
GT_PROTOCOL_GATE_FAIL
```

The source-only GT protocol gate failed at G2. Two-pair MVE, development,
holdout, Formal, recovery implementation, MIA execution, and all tracking runs
remain unauthorized. This is a measurement-protocol failure, not a scientific
claim about the candidate-compensation mechanism.

Raw, ignored artifacts are rooted at:

```text
outputs/20260817_mdmt_non_test_mda_gt_protocol/
```

The raw G7 record is
`outputs/20260817_mdmt_non_test_mda_gt_protocol/records/g7_final_decision.json`.

## Gate outcomes

| Gate | State | Evidence | Result |
| --- | --- | --- | --- |
| G1 | `PASS` | `records/g1_source_audit.json` | All 88 XML files parsed with strict required fields and unique split resolution. |
| G2 | `FAIL` | `records/g2_validation_run_a.json`; official-test exact reports | 5/28 test files were exact; 23/28 failed duplicate-preserving Decimal multiset equivalence. |
| G3 | `BLOCKED_BY_UNKNOWN` | No artifact generated | Not run after G2 hard failure. |
| G4 | `BLOCKED_BY_UNKNOWN` | No artifact generated | Not run after G2 hard failure; the pre-registered identity evidence input was not admitted as a passed gate. |
| G5 | `BLOCKED_BY_UNKNOWN` | No artifact generated | Not run after G2 hard failure. |
| G6 | `BLOCKED_BY_UNKNOWN` | No artifact generated | Not run after G2 hard failure. |
| G7 | `GT_PROTOCOL_GATE_FAIL` | `records/g7_final_decision.json` | Fail-closed result; repair-and-continue is forbidden. |

## G2 observed facts

- The official test reference contains 28 sequence-view files.
- Strict conversion produced no missing reference rows but 347 additional
  source-derived rows across the 23 mismatching files.
- The report's frame/ID/bbox projection-mismatch columns are consequences of
  those unmatched multiset rows; they do not independently diagnose a mapping
  cause.
- Test XML has zero `outside=1` boxes, so the required outside-exclusion rule
  has no official-test witness. The same audit retained 158,301 eligible
  occluded boxes, so the occlusion rule did have coverage.
- No rounding, IoU tolerance, row de-duplication, source-row filtering, or
  semantic repair was applied.

## Required next action

If work resumes, it must be a separately approved protocol investigation of the
347 source-derived extra rows and of the absent `outside=1` official-test
witness. It must establish the official annotation/export semantics before any
non-test GT derivation is retried. It may not use tracking/MVE outcomes to
choose or justify a repair.

## Verification

```text
PYTHONPATH=src python -m pytest tests/test_mdmt_non_test_mda_gt_protocol.py -q
6 passed

PYTHONPATH=src python -m py_compile \
  src/datasets/mdmt_mda_gt_protocol.py \
  scripts/prepare_mdmt_non_test_mda_gt.py
passed

git diff --check
passed
```
