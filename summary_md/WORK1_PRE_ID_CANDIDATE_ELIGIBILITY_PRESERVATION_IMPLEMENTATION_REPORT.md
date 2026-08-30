# Work 1 Pre-ID Candidate Eligibility Preservation — M1–M2 Implementation Report

## Status

`M2_SYNTHETIC_PARITY_PASS__DYNAMIC_NON_INTERFERENCE_NOT_RUN`

```text
GOVERNANCE_AMENDMENT_AND_PREEXECUTION_GATES_IMPLEMENTED_FOR_REVIEW
M2_SYNTHETIC_PARITY = PASS
M2_DYNAMIC_NON_INTERFERENCE = NOT_RUN
M2_DYNAMIC_NON_INTERFERENCE_NOT_RUN
MVE = NOT_RUN
FORMAL = NOT_RUN
HELDOUT = NOT_ACCESSED
GT_SAFETY = UNGRADED
```

This implementation adds only observer, derivative-preparation, orchestration,
and unit-test infrastructure. The fixed non-GT synthetic parity fixture and a
temporary derivative structure/restoration audit passed (`16 passed`). It does
not access development/held-out inputs or execute an MVE.

## Files

- `src/tracking/mdmt_mia_work1_eligibility_observer.py`
- `scripts/prepare_mdmt_mia_work1_eligibility_variant.py`
- `scripts/run_mdmt_mia_work1_eligibility_mve.py`
- `tests/test_mdmt_mia_work1_eligibility_mve.py`
- `src/tracking/mdmt_mia_work1_xml_governance.py`
- `scripts/audit_mdmt_mia_work1_xml_governance.py`
- `tests/test_mdmt_mia_work1_xml_governance.py`
- `summary_md/WORK1_AUTHOR_RUNTIME_XML_GOVERNANCE_AMENDMENT.md`
- `summary_md/WORK1_DYNAMIC_M2_PREEXECUTION_GATE_SPEC.md`
- `summary_md/ABC_INITIALIZATION_EQUALITY_AUDIT_SCHEMA.json`

## XML governance writeback

```text
GOVERNANCE_DECISION_ALREADY_FROZEN_BEFORE_WRITEBACK
WORK1_DECISION_GT_INDEPENDENT
THIS IS AN EXPLICIT GOVERNANCE AMENDMENT
```

The old full-runtime XML ban is retained as superseded history. Frozen
original-MIA first-frame initialization is now an allowed held-constant author
control, subject to fail-closed `G-XML1` through `G-XML5`. Work 1 direct oracle
access and GT grading remain prohibited.

The new gate code validates only pre-frozen hashes, audit records, event
ordering, runtime counters, and output schemas. It cannot generate an expected
XML hash baseline and does not open XML/GT data. The passive initialization
marker is emitted only in a temporary/future isolated derivative; its return
is ignored and frozen parent source remains unchanged.

## Governance gate verification

Allowed synthetic/static verification completed:

```text
existing Work 1 synthetic parity: 16 passed
new XML-governance gate tests: 8 passed
combined focused suite: 24 passed
G-XML3 static CLI audit: PASS
ABC equality JSON schema parse: PASS
frozen parent entrypoint SHA-256: MATCH
frozen XML-reader source SHA-256: MATCH
frozen initialization-region SHA-256: MATCH
```

No real `ABC_INITIALIZATION_EQUALITY_AUDIT.json` or
`WORK1_RUNTIME_ORACLE_FIREWALL_AUDIT.json` was generated. Those require a
future separately authorized A/B/C execution.

## Boundary confirmation

- Parent E023 v8 source is not modified.
- The derivative generator is fail-closed on all frozen hashes and refuses an
  existing destination.
- Hooks are one-way (`None` return), copy/hash inputs, and write only
  observer-ledger artifacts.
- `POST_ID_MEMBERSHIP_DISAPPEARED_ONLY` is diagnostic; it never invalidates a
  token.
- The only implemented execution subcommand is ledger summarization. `mve`
  deliberately exits with `MVE_EXECUTION_NOT_IMPLEMENTED` pending a separately
  frozen execution authorization.

## Not performed

`PERSISTENT_VARIANT_NOT_GENERATED`  
`RUNTIME_NON_INTERFERENCE_NOT_RUN`  
`DEVELOPMENT_NOT_RUN`  
`HELDOUT_NOT_RUN`  
`FORMAL_NOT_RUN`

## Passive full-core comparison instrumentation

```text
DYNAMIC_M2_COMPARISON_COVERAGE_BLOCKER_CLEARED_FOR_REVIEW
DYNAMIC_M2_EXECUTION_NOT_AUTHORIZED
```

The Dynamic M2 comparison gap is now covered by one exact canonical recorder
shared by an isolated A-traced derivative and one shared B/C derivative.
Detector/tracker rows and order, all three ID stages, post-ID recomputation,
High-/Low-score inputs and outputs, NMS, feedback, next-frame state, final
predictions, and complete packet state/counters have source-mapped passive
checkpoints. A/B/C use one schema and checkpoint sequence; no intersection-only
comparison or float tolerance is permitted.

Allowed verification completed:

```text
existing Work 1 synthetic parity: 16 passed
XML governance tests: 8 passed
new full-core synthetic/static tests: 13 passed
combined focused suite: 37 passed
full-core static audit: PASS
temporary A/BC derivative generation + AST/hash/isomorphism audit: PASS
frozen parent/protected helpers modified: NO
real A/B/C runtime: NOT RUN
```

New evidence and implementation:

- `src/tracking/mdmt_mia_work1_core_comparison.py`
- `scripts/audit_mdmt_mia_work1_core_comparison.py`
- `tests/test_mdmt_mia_work1_core_comparison.py`
- `summary_md/WORK1_FULL_CORE_COMPARISON_SOURCE_MAP.md`
- `summary_md/WORK1_FULL_CORE_COMPARISON_INSTRUMENTATION_SPEC.md`
- `summary_md/WORK1_FULL_CORE_COMPARISON_TRACE_SCHEMA.json`
- `summary_md/WORK1_FULL_CORE_COMPARISON_INSTRUMENTATION_MANIFEST.json`
- `summary_md/FULL_CORE_COMPARISON_COVERAGE_AUDIT.json`
- `summary_md/FULL_CORE_INSTRUMENTATION_PASSIVITY_AUDIT.json`

Persistent traced derivatives remain ungenerated. Real parent-vs-A-traced
parity, G-XML2/3/4, full-core equality and observer mutation remain future
runtime gates after a repeated authorization review.

## Dynamic M2 repeat-review repair

The repeat authorization review found and repaired six execution-validity
gaps without changing Work 1 scientific behavior:

- every A/B/C trace now independently passes exact schema, role, contiguous
  sequence, full externally supplied frame coverage, frame-0, standard-frame,
  and final checkpoint-profile validation before equality is computed;
- empty traces and a checkpoint omitted uniformly from all three roles fail
  closed;
- frozen-parent versus A-traced author prediction parity has an exact-byte
  machine gate;
- a condition-isolated B repeat and exact determinism gate are frozen;
- normalized A/B/B-repeat/C launch environment and argv differences are
  machine audited;
- G-XML2 initialization-state records, G-XML3 dynamic zero-counter evidence,
  and a validator-compatible G-XML4 ordering artifact now have passive runtime
  producers;
- observer mutation counting uses unique protected boundaries instead of
  adding overlapping counts, and `exact_canonical_equality` reflects the real
  comparison result.

Synthetic/static verification after repair:

```text
focused suite: 43 passed
machine launch-diff audit: PASS
AST parse: PASS
real parent/A/B/B-repeat/C runtime: NOT RUN
```

These repairs make the evidence path executable after a fresh authorization;
they do not themselves constitute Dynamic M2 evidence or authorization.
