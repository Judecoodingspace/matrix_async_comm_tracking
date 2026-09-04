# EXEC_PLAN

## Current Frozen State

```text
EXPERIMENT: exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation
RESEARCH_DECISIONS_RESOLVED
CONTRACT_AMENDMENT_RECORDED
SOURCE_MDA_V1_IMPLEMENTATION_COMPLETE
FRESH_G1_G7_SOURCE_PROTOCOL_PREFLIGHT_PASS
G6_EVALUATOR_FIXTURE_AND_OUTSIDE_ACCOUNTING_CLOSED
PAIR53_PAIR66_MVE_DECISIONS_FROZEN
M2_M3_NON_TEST_MVE_INTEGRATION_NOT_IMPLEMENTED
PAIR53_PAIR66_MVE_PREFLIGHT_BLOCKED
TRACKING_MVE_NOT_EXECUTED
DEVELOPMENT_SWEEP_NOT_AUTHORIZED
HOLDOUT_CONFIRMATION_NOT_AUTHORIZED
VERSION_AWARE_RECOVERY_NOT_AUTHORIZED
```

R1/R2/R3 are closed and must not be reopened during this gate. This plan
inherits E023 R4-R6 semantics, does not reactivate the suspended joint-
transaction hypothesis and does not implement version-aware recovery.

The legacy M1 exact-official-export plan below is retained as historical design
evidence and is superseded for Route B by
`MDMT_SOURCE_ANNOTATION_MDA_V1`, its authority audit, and its fresh G1-G7
reports. The current authorized scope is contract synchronization and static
Pair53/66 execution-preflight only. No tracker, MIA runtime, detector, Pair53,
Pair66, or prediction/scientific outcome may be executed or consumed by this
preflight.

## Gate Research Contract

### Question

Can one globally frozen, deterministic and non-repairing XML-to-MDA conversion
protocol exactly reproduce all official-test MDA GT and then produce
structurally valid, cross-view-measurable derived non-test MDA GT?

### Evidence Classification

#### FACT

- The local dataset contains 88 source XML files and 28 official-test MDA GT
  files.
- A historical audit reconciled 600,923 official-test rows to XML and observed
  `official_id = xml_id + 1`.
- The historical audit used loaders and reconciliation logic that may round
  coordinates, collapse duplicate keys or infer mappings by vote; it is not
  the newly required exact multiset equivalence evidence.
- The G1-G6 artifact package, strict converter, repeat-run report and G7 report
  do not yet exist.
- Tracking, MVE, development, holdout and Formal remain blocked.

#### INFERENCE

- The historical reconciliation makes the frozen global mapping plausible,
  but cannot establish G2 PASS under the stricter comparison semantics.

#### ASSUMPTION

- Independent authoritative MDMT materials can establish the intended
  cross-view identity semantics for train/val in addition to source-only
  per-pair measurability evidence.

#### UNKNOWN

- Whether all 88 XML files contain every required field without relying on
  parser defaults.
- Whether the frozen `outside` and `occluded` rules exactly reproduce all 28
  official files.
- Whether exact duplicate-preserving semantic multisets match for every
  official-test file without rounding, tolerance or IoU matching.
- Whether an independent authoritative evidence chain establishes train/val
  cross-view identity semantics.
- Whether every candidate non-test pair contains measurable same-ID,
  same-frame, cross-view events.
- Whether bbox boundary anomalies exist and, if so, whether official-test
  evidence resolves their treatment without clipping or repair.
- Whether two isolated executions produce byte-identical deterministic
  artifacts and generated GT.

### Primary Gate Hypothesis

`H_protocol`: one global mapping with no sequence/view/ID exceptions exactly
reproduces the 28 official-test MDA GT files and yields deterministic,
row-conserving and cross-view-measurable train/val derived GT.

### Alternative Gate Hypothesis

`H_protocol_alt`: at least one exact-equivalence, structural, identity-
semantics or determinism requirement fails or remains unknown, so non-test MDA
evaluation is not scientifically authorized.

These hypotheses are separated only by the registered G1-G6 evidence. Tracking
outcomes cannot adjudicate this gate.

## Resolved Research Decisions

| ID | Status | Decision |
| --- | --- | --- |
| R1 | `APPROVED / RESOLVED_CONDITIONAL` | Permit deterministic train/val MDA GT conversion only after exact official-test equivalence and a separate non-test identity-semantics audit; no semantic repair. |
| R2 | `APPROVED / RESOLVED` | Freeze 15 train development, 10 train holdout and 5 MDMT val holdout pairs using canonical pair ordering, a fixed algorithm and seed 7 before outcomes are read. |
| R3 | `APPROVED / RESOLVED_WITH_CONTRACT_AMENDMENT` | Freeze d1-d5 and the earliest delay passing Gate A-F; Gate F requires actual High-score write-in in at least 10/15 development pairs. |

Any change to dataset/split, primary contrasts, candidate membership semantics,
oracle boundary, evaluator identity definition or frozen GT mapping requires a
visible `NEEDS_RESEARCH_DECISION`; it is not an engineering cleanup.

## M0 — Research Decision Synchronization

Type: `LEARNING_CRITICAL`

Status: `COMPLETED`

- R1-R3 are resolved without reopening the research question.
- The R3 Gate F amendment is recorded in `EXPERIMENT_CONTRACT.md`.
- The d1-d5 condition matrix and earliest-onset semantics are frozen before
  implementation.
- The next blocking lifecycle stage is the G1-G7 GT Protocol Gate below.

## M1 — GT Protocol Gate

Type: `LEARNING_CRITICAL`

Status: `POLICY_FROZEN / BLOCKED_BY_UNKNOWN / ARTIFACT_EXECUTION_NOT_STARTED`

### M1.1 Frozen Authority And Mapping Rules

Authoritative source annotation:

```text
MDMT_ROOT/new_xml/{view_id}/{sequence_id}-{view_id}.xml
```

Frozen global conversion candidates to be tested on official test:

```text
output_mda_id    = source_xml_track_id + 1
output_mda_frame = source_xml_box_frame + 1
x                = xtl
y                = ytl
width            = xbr - xtl
height           = ybr - ytl
outside=0        -> include
outside=1        -> exclude
outside=0, occluded=0/1 -> retain without geometry or identity change
```

The converter has no authority to:

- create sequence-, view- or ID-specific mappings;
- use a lookup table or majority-vote repair;
- fill required source fields with defaults;
- round, clip, move, enlarge or shrink a bbox;
- match rows by IoU or numeric tolerance;
- inspect images to repair identity or geometry;
- inspect detector, tracker, MDA or other prediction outcomes;
- delete an unfavorable row, track, frame or pair;
- patch source XML or generated GT manually.

Semantic numeric comparison must preserve exact values and multiplicity. A
canonical decimal representation may treat `26` and `26.0` as equal, but must
treat `100` and `100.01` as different. G2 compares duplicate-preserving
multisets of:

```text
(frame, id, x, y, width, height)
```

No rounding, IoU matching or tolerance is allowed.

### M1.2 Inputs By Gate

| Gate | Required inputs |
| --- | --- |
| G1 | 88 `new_xml` files; train/val/test image directories; frozen mapping policy; Git/source metadata. |
| G2 | 28 local official-test MDA GT files; test XML; G1 mapping manifest; test-only generated GT. |
| G3 | G2-passed converter; train/val XML; both views' image names, counts, dimensions and timelines. |
| G4 | Official paper/dataset/annotation protocol/evaluator or author code; G2 evidence; train/val/test XML schema; source-only per-pair ID statistics. |
| G5 | Train/val frame, ID and label fields; frozen primary/sensitivity definitions; evaluator identity semantics. |
| G6 | Converter source; mapping manifest; all 88 XML files; all 28 official GT files; derived GT; two empty isolated run roots. |
| G7 | Every required G1-G6 artifact; hard-gate summary; unresolved UNKNOWN list. Tracking outcomes are forbidden. |

Official or author-controlled materials must provide the independent authority
for G4. Repository history is a discovery lead and supporting audit trail, not
by itself authoritative evidence.

### M1.3 Artifact Layout

Machine-generated raw artifacts remain under ignored `outputs/`:

```text
outputs/20260817_mdmt_non_test_mda_gt_protocol/
├── policy/
│   └── mapping_rule_manifest.json
├── manifests/
│   ├── source_annotation_manifest.csv
│   ├── official_test_reference_manifest.csv
│   ├── derived_gt_manifest.csv
│   └── artifact_manifest.csv
├── audits/
│   ├── field_completeness_report.csv
│   ├── official_test_exact_equivalence_report.csv
│   ├── official_test_equivalence_differences.csv
│   ├── official_test_outside_occluded_audit.csv
│   ├── official_test_duplicate_identity_audit.csv
│   ├── non_test_row_conservation_report.csv
│   ├── non_test_duplicate_identity_report.csv
│   ├── frame_image_integrity_report.csv
│   ├── dual_view_timeline_integrity_report.csv
│   ├── bbox_boundary_audit.csv
│   ├── per_pair_cross_view_identity_audit.csv
│   └── class_conflict_manifest.csv
├── evidence/
│   └── cross_view_identity_semantics_evidence.json
├── run_a/
│   └── generated_gt/{test,train,val}/
├── run_b/
│   └── generated_gt/{test,train,val}/
├── determinism/
│   └── deterministic_repeat_run_report.csv
├── records/
│   ├── generation_record_run_a.json
│   └── generation_record_run_b.json
└── GT_PROTOCOL_GATE_REPORT.md
```

Durable schemas, conclusions and links are tracked under the experiment
directory:

```text
GT_PROTOCOL_GATE_ARTIFACT_SCHEMA.md
GT_PROTOCOL_GATE_REPORT.md
```

Deterministic manifests must omit timestamps, absolute temporary paths and
other volatile fields. Actual runtime, environment and command information goes
in `generation_record_run_*.json`, so reproducibility comparison and provenance
recording do not conflict.

### G1 — Converter Authority And Input Provenance

Tasks:

- enumerate all 88 XML files without view-intersection filtering;
- record split, sequence, view, source path, SHA-256 and parser status;
- audit required track fields `id` and `label`, and required box fields
  `frame`, `xtl`, `ytl`, `xbr`, `ybr`, `outside` and `occluded`, without
  supplying defaults;
- freeze the global mapping-rule manifest and forbidden converter authority;
- inventory paired image directories and source XML coverage.

Required artifacts:

```text
policy/mapping_rule_manifest.json
manifests/source_annotation_manifest.csv
audits/field_completeness_report.csv
```

Hard gate:

- every expected XML is uniquely present and parseable;
- all required fields are present and valid;
- the mapping is global and exception-free;
- source and policy fingerprints are complete.

Stop on a parse/field/provenance failure. If the mapping cannot be stated
without an exception, fail closed; do not invent a repair table.

### G2 — Official-Test Exact Equivalence

Precondition: `G1=PASS`.

Tasks:

- create test-only generated GT using the G1 mapping;
- compare all 28 files against official-test GT as exact semantic multisets;
- preserve duplicate multiplicity and report every missing/extra/different row;
- explicitly audit `outside` exclusion and `occluded` retention against
  official-test evidence;
- audit duplicate `(frame, id)` keys in each official and generated file;
- fingerprint every official reference and generated test file.

Required artifacts:

```text
manifests/official_test_reference_manifest.csv
audits/official_test_exact_equivalence_report.csv
audits/official_test_equivalence_differences.csv
audits/official_test_outside_occluded_audit.csv
audits/official_test_duplicate_identity_audit.csv
run_a/generated_gt/test/
```

Hard gate:

```text
official_test_file_count = 28
official_test_missing_rows = 0
official_test_extra_rows = 0
official_test_frame_mismatch = 0
official_test_id_mismatch = 0
official_test_bbox_mismatch = 0
official_test_duplicate_identity_keys = 0
outside_rule_supported = 1
occluded_rule_supported = 1
```

Any nonzero mismatch yields `GT_PROTOCOL_GATE_FAIL`. Do not generate or promote
train/val derived GT after a G2 failure.

### G3 — Non-Test Structural Integrity

Precondition: `G2=PASS`.

Tasks:

- apply the same frozen converter to train/val XML without branching;
- preserve every eligible source row exactly once;
- audit duplicate identity keys, frame-to-image mapping and image ambiguity;
- audit both views' pair completeness and timeline alignment;
- report bbox boundary anomalies without clipping or repairing them;
- fingerprint all derived files and their source lineage.

Required artifacts:

```text
audits/non_test_row_conservation_report.csv
audits/non_test_duplicate_identity_report.csv
audits/frame_image_integrity_report.csv
audits/dual_view_timeline_integrity_report.csv
audits/bbox_boundary_audit.csv
manifests/derived_gt_manifest.csv
run_a/generated_gt/{train,val}/
```

Hard gate:

```text
non_test_missing_source_rows = 0
non_test_extra_derived_rows = 0
non_test_duplicate_identity_keys = 0
invalid_frame_image_mapping = 0
ambiguous_frame_image_mapping = 0
missing_pair_or_view = 0
dual_view_timeline_violation = 0
frame_offset = 0
```

An unresolved bbox-boundary treatment is `BLOCKED_BY_UNKNOWN`; clipping is
forbidden. Structural violations fail closed.

### G4 — Cross-View Identity Semantics

Precondition: `G2=PASS`; G3 structural artifacts must be available.

Tasks:

- freeze an independent authoritative evidence chain from official MDMT
  materials or author-controlled evaluation code;
- record exactly how equal IDs across paired views are interpreted;
- build duplicate-preserving source-only per-pair train/val/test ID statistics;
- verify each candidate non-test pair has same-ID, same-frame, cross-view events
  and can support MDA measurement;
- keep FACT, INFERENCE and UNKNOWN evidence explicitly separated.

Required artifacts:

```text
evidence/cross_view_identity_semantics_evidence.json
audits/per_pair_cross_view_identity_audit.csv
```

Hard gate:

```text
independent_authoritative_identity_evidence = 1
cross_view_ids_confirmed_non_view_local = 1
every_candidate_pair_mda_measurable = 1
```

If IDs are confirmed view-local, the gate fails. If an independent evidence
chain cannot be established, G7 remains `BLOCKED_BY_UNKNOWN`. If a frozen
candidate pair has zero same-ID/same-frame cross-view events, stop with
`NEEDS_RESEARCH_DECISION`; do not drop or exchange the pair.

### G5 — Annotation Inconsistency And Sensitivity Freeze

Precondition: G3/G4 evidence exists; no tracking outcome has been read.

Tasks:

- create a full source-only class-conflict manifest by pair/frame/ID/view;
- freeze full deterministic derived GT as the primary evaluation population;
- freeze a class-consistent sensitivity mask separately;
- prove the sensitivity definition changes only evaluation inclusion and does
  not modify source rows, identities, geometry or predictions;
- fingerprint both definitions before any MVE or outcome read.

Required artifact:

```text
audits/class_conflict_manifest.csv
```

Hard gate:

- primary GT remains the full deterministic conversion;
- sensitivity is separately reported and cannot replace primary GT;
- manifest construction has no tracking-outcome dependency;
- no source row, identity or bbox is rewritten.

Outcome-dependent masking or primary-row modification fails closed.

### G6 — Deterministic Repeatability And Provenance

Preconditions: G1-G5 completed without a hard failure.

Tasks:

- execute the complete conversion/audit pipeline twice from two empty,
  isolated roots using identical frozen inputs, rules and code;
- compare generated GT, deterministic manifests, class-conflict lists,
  per-pair statistics and artifact fingerprints;
- record SHA-256 for converter source, source XML, official references,
  generated files and key audit artifacts;
- record actual command, Git commit, Python/dependency versions and runtime
  environment separately for each run.

Required artifacts:

```text
run_b/generated_gt/{test,train,val}/
determinism/deterministic_repeat_run_report.csv
records/generation_record_run_a.json
records/generation_record_run_b.json
manifests/artifact_manifest.csv
```

Hard gate:

```text
generated_gt_checksum_mismatch = 0
deterministic_manifest_mismatch = 0
class_conflict_manifest_mismatch = 0
deterministic_statistic_mismatch = 0
required_fingerprint_missing = 0
```

Any mismatch yields `GT_PROTOCOL_GATE_FAIL`. Environment differences are
recorded but are not alone a scientific failure; identical frozen inputs,
rules and code must still yield identical deterministic output.

### G7 — Final Authorization

G7 adds no conversion rule and reads no tracking outcome. It aggregates G1-G6
evidence and must choose exactly one result:

```text
GT_PROTOCOL_GATE_PASS
GT_PROTOCOL_GATE_FAIL
GT_PROTOCOL_GATE_BLOCKED_BY_UNKNOWN
```

`GT_PROTOCOL_GATE_PASS` is allowed only when every G1-G6 hard gate passes,
every required artifact exists and every critical UNKNOWN is resolved.

`GT_PROTOCOL_GATE_FAIL` is required after any explicit hard-gate violation.
Repair-and-continue is forbidden.

`GT_PROTOCOL_GATE_BLOCKED_BY_UNKNOWN` is required when critical authority or
evidence remains unavailable. “Mostly passed” and “run MVE first” are not valid
states.

The report must be structured by G1-G7. For each gate it records:

```text
Gate
Policy
Evidence artifact
Observed facts
Unknowns
Hard-gate results
Status
```

Intermediate G1-G6 `Status` values are restricted to:

```text
PASS
FAIL
BLOCKED_BY_UNKNOWN
PASS_PENDING_ARTIFACT
```

The final G7 status remains restricted to the three `GT_PROTOCOL_GATE_*`
results above.

The durable report must also list authoritative inputs, frozen mapping rules,
forbidden converter authority, exact-equivalence results, non-test structural
results, identity-semantics evidence, annotation inconsistency statistics,
repeatability results, unresolved UNKNOWNs, fail-closed stops and the exact
authorization boundary.

G7 PASS authorizes only:

```text
GT/evaluation infrastructure
+ causal invariant implementation/check
-> two-pair MVE
```

It does not authorize development, holdout, Formal or version-aware recovery.

### M1.4 Minimal Tooling

Planned new files:

```text
src/datasets/mdmt_mda_gt_protocol.py
scripts/prepare_mdmt_non_test_mda_gt.py
tests/test_mdmt_non_test_mda_gt_protocol.py
```

`mdmt_mda_gt_protocol.py` must be a pure source/evaluation module that:

- parses required XML fields strictly without defaults;
- uses `Decimal` or equivalent lossless canonicalization;
- preserves duplicate multiplicity;
- implements only the frozen ID/frame/bbox/outside/occluded rules;
- performs exact multiset, image timeline, pair completeness, bbox boundary,
  cross-view ID and class-conflict audits;
- does not import tracker, MIA runtime, detector or prediction evaluation code.

`prepare_mdmt_non_test_mda_gt.py` must expose staged, fail-closed modes:

```text
audit-source
validate-official-test
derive-non-test
repeat-verify
finalize-gate
```

One uninterrupted command must not generate test/train/val together.
`derive-non-test` must require a valid G2 PASS artifact and compatible policy,
source and converter fingerprints.

Focused tests must cover at least:

- missing required fields are not hidden by defaults;
- `26` and `26.0` compare semantically equal;
- `100` and `100.01` mismatch;
- duplicate multiplicity is retained;
- `outside=1` is excluded and `occluded=1` retained;
- ID/frame `+1` mapping;
- bbox is neither clipped nor rounded;
- sequence/view exceptions are rejected;
- missing, ambiguous or out-of-range image mapping;
- dual-view timeline mismatch;
- primary/sensitivity manifests do not mutate source rows;
- policy/config/source fingerprint drift;
- two independent runs are deterministic;
- G2 not PASS blocks `derive-non-test`;
- incomplete G4/G5/G6 blocks G7 PASS.

No tracker or MIA runtime file may be added or changed during M1.

### M1.5 Existing Code Reuse Boundary

May be reused narrowly:

- `src/datasets/mdmt.py`: split/sequence path conventions and official-test ID
  constants;
- `scripts/prepare_mdmt_official_mda_gt.py`: official URL and filename
  conventions;
- `src/evaluation/mdmt_mia_paper.py`: evaluator trace showing that equal GT IDs
  form cross-view associations; it does not replace independent G4 authority;
- `scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py`: SHA-256,
  fingerprint, manifest compatibility and isolated-attempt patterns;
- `tests/test_mdmt_adapter.py`: synthetic XML and official-GT fixture patterns.

Must not be reused as strict Gate semantics:

- `discover_mdmt_sequence_ids()` returns a view intersection and can hide a
  missing side;
- `load_mdmt_view()` supplies defaults and rounds bbox coordinates;
- `load_official_mda_gt()` rounds official numeric values;
- `reconcile_xml_to_official_mda()` uses a bbox-keyed dictionary and majority
  votes, which can collapse duplicates and infer repairs;
- `audit_same_numeric_ids_across_views()` uses a dictionary keyed by
  `(frame,id)` and lacks the G4 evidence fields;
- `prepare_mdmt_official_mda_gt.py --resume` validates existence, not a frozen
  reference checksum manifest.

The strict Gate parser must therefore be isolated rather than changing the
existing runtime loader semantics.

### M1.6 Fail-Closed Stops

| Condition | Required result |
| --- | --- |
| Required XML field missing, parse error or incomplete provenance | Stop; classify as `FAIL_CLOSED` or `BLOCKED_BY_UNKNOWN` from recorded facts. |
| Official reproduction requires any sequence/view/ID exception | `GT_PROTOCOL_GATE_FAIL`. |
| Any G2 missing/extra/frame/ID/bbox mismatch | `GT_PROTOCOL_GATE_FAIL`. |
| Official duplicate identity key is nonzero | Stop and report; do not invent a rule. |
| `outside`/`occluded` behavior differs from official GT | `GT_PROTOCOL_GATE_FAIL`. |
| G3 missing/extra/duplicate row, frame/image violation or incomplete pair/timeline | `FAIL_CLOSED`. |
| Bbox boundary treatment is not resolved by frozen policy and official evidence | `GT_PROTOCOL_GATE_BLOCKED_BY_UNKNOWN`; no clipping. |
| IDs are confirmed view-local | `GT_PROTOCOL_GATE_FAIL`. |
| Independent identity-semantics authority cannot be established | `GT_PROTOCOL_GATE_BLOCKED_BY_UNKNOWN`. |
| A frozen pair has zero measurable cross-view identity events | `NEEDS_RESEARCH_DECISION`; no pair replacement. |
| Sensitivity depends on outcomes or modifies primary rows | `FAIL_CLOSED`. |
| Any deterministic artifact/checksum differs | `GT_PROTOCOL_GATE_FAIL`. |
| Required artifact missing or critical UNKNOWN unresolved | G7 cannot PASS. |

### M1.7 Explicit M1 Execution Order

```text
1. Freeze artifact and mapping-rule schemas.
2. Implement strict pure functions and synthetic tests.
3. Run focused tests; stop on failure.
4. Run G1 over all source XML/image inventories.
5. If G1 passes, generate test-only GT.
6. Run G2 over all 28 official files; stop on any mismatch.
7. Only after G2 PASS, derive train/val GT and run G3.
8. Build independent identity authority and per-pair evidence for G4.
9. Freeze primary/sensitivity definitions and run G5 before outcomes.
10. Repeat the complete pipeline from a second empty root and run G6.
11. Aggregate only G1-G6 evidence and perform G7.
12. Only after GT_PROTOCOL_GATE_PASS, update lifecycle status and consider M2.
```

## M2 — Isolated Variant, Cohort Manifest And CLI Wiring

Type: `PLUMBING`

Status: `AUTHORIZED_ONLY_AS_FUTURE_ENGINEERING / NOT_IMPLEMENTED /
BLOCKS_PAIR53_PAIR66_MVE`

Tasks after G7 PASS:

- preserve E023 v8 unchanged;
- create an isolated onset-validation variant that changes only split/data
  routing, not R4-R6 semantics;
- canonically order the 25 train pair IDs and generate the 15/10 split once
  using the frozen algorithm and `seed=7` before any metric read;
- retain all five val pairs as a separate MDMT-split holdout;
- add `mve`, `development` and `confirm` CLI modes;
- fingerprint source, checkpoint, split manifest, delays and conditions.

Gate:

```text
FRESH_G1_G7_SOURCE_PROTOCOL_PREFLIGHT_PASS = 1
official_test_pairs_selected = 0
cohort_overlap = 0
cohort_manifest_determinism_mismatch = 0
condition/source/config drift = 0
```

## M3 — Logging, Checkpoint And Output Serialization

Type: `PLUMBING`

Status: `AUTHORIZED_ONLY_AS_FUTURE_ENGINEERING / NOT_IMPLEMENTED /
BLOCKS_PAIR53_PAIR66_MVE`

Tasks after G7 PASS:

- reuse immutable detector caches per pair;
- use isolated attempt roots and clean-restart manifests;
- serialize E023 R5d per-frame/candidate traces;
- add explicit development-selection and holdout-lock files;
- ensure `--resume` skips only passed attempts.

Gate:

```text
partial_attempt_promoted = 0
checkpoint_fingerprint_mismatch = 0
logging_prediction_mismatch = 0
```

## M4 — Two-Pair MVE

Type: `LEARNING_CRITICAL`

Status: `DECISIONS_FROZEN / EXECUTION_PREFLIGHT_BLOCKED / NOT_EXECUTED`

Pairs and delays:

```text
pairs = 53, 66
delays = 1, 3, 5
conditions = Y00, Y01, Y10/Y11/Yec per delay
per_pair = 11 accepted conditions
total = 22 accepted pair-condition runs
```

MVE validates non-test protocol consumption, synchronous equivalence, E023
shadow quarantine, row conservation, logger invariance, condition parity and
deterministic restart. It cannot select onset or support a mechanism claim.

Gate:

```text
FRESH_G1_G7_SOURCE_PROTOCOL_PREFLIGHT_PASS = 1
Pair53 = 11/11 accepted
Pair66 = 11/11 accepted
total = 22/22 accepted
all MVE measurement gates pass
Y00 synchronous equivalence passes
Y10/Yec sole intended difference is membership source
future/GT/source-bypass/history-rewrite counts are zero
two repeated MVE conditions are byte-identical
scientific values suppressed from the MVE summary
```

Development remains blocked until an explicit MVE audit writes
`development_allowed=1`.

### PAIR53_PAIR66_TRACKING_MVE_FROZEN_DECISIONS

The authoritative full wording is in `EXPERIMENT_CONTRACT.md`. This execution
plan implements it as follows:

| Decision | Execution rule | State |
| --- | --- | --- |
| MVE-R0 | Validate mechanism-field connectivity and valid-zero distinguishability; never require nonzero occurrence or a favorable direction. | `FROZEN` |
| MVE-R1 | Build one frozen non-test synchronous reference per pair and require strict prediction, feedback, evaluator, packet, read-boundary, alias, logger, and shadow parity before delayed-outcome consumption. | `FROZEN / NOT_IMPLEMENTED` |
| MVE-R2 | Accept only Pair53 `11/11`, Pair66 `11/11`, total `22/22`; no partial promotion. | `FROZEN` |
| MVE-R3 | Preserve failed attempts and retry unchanged conditions in new roots; any outcome-capable semantic repair stops for amendment/successor and impact assessment. | `FROZEN / INHERITED_MACHINERY_NOT_INTEGRATED` |
| MVE-R4 | Determine MVE validity solely from execution/measurement gates, independently of scientific outcomes. | `FROZEN` |
| MVE-R5 | Until `22/22` accepted, consume only execution/measurement status and never use partial scientific values for design choices. | `FROZEN / SUPPRESSION_NOT_IMPLEMENTED` |
| MVE-R6 | Check contrast inputs, formulas, alignment, finiteness, and schema; publish only computability booleans, never Pair53/66 contrast values or interpretation. | `FROZEN / SUPPRESSION_NOT_IMPLEMENTED` |
| MVE-R7 | Once all execution/measurement gates pass, progression to the 15-pair development sweep is outcome-independent. | `FROZEN` |
| MVE-R8 | Never substitute Pair53/66 for difficult, sparse, zero, atypical, or unfavorable valid data; stop for bugs, unspecified semantics, or population/version corruption. | `FROZEN` |
| MVE-R9 | On MVE PASS, immediately freeze every outcome-capable implementation and registered development-analysis component before any 15-pair run. | `FROZEN / FREEZE_MECHANISM_NOT_IMPLEMENTED` |

All Y-condition semantics are inherited unchanged from frozen E023. Before a
separate execution authorization, M2/M3 must supply an isolated non-test
variant/runner that combines those semantics with the accepted Homography
successor and Source-MDA-v1 without modifying either frozen authority.

## M5 — Development Delay Sweep

Type: `LEARNING_CRITICAL`

Status: `NOT_AUTHORIZED`

- Run the frozen 15-pair development cohort at d1-d5.
- Compute pair-level-bootstrap contrasts, pair-direction counts and the
  registered mechanism-path evidence.
- Select the earliest delay passing Contract Gate A-F, including actual
  delay-only candidate to High-score Supplement write-in in at least 10/15
  development pairs.
- Write `onset_selection.json` once and make it immutable.

If no delay qualifies, stop before holdout and report the preregistered no-onset
result. Do not relax gates, search thresholds, remove pairs, extend to d6+ or
reopen official test. Any implementation change after development outcomes
invalidates selection and requires a fresh development run.

## M6 — Fifteen-Pair Holdout Confirmation

Type: `LEARNING_CRITICAL`

Status: `NOT_AUTHORIZED`

- Run 10 train-holdout plus 5 val pairs only at the locked onset and preceding
  delay.
- Compute pair-level bootstrap without refitting onset.
- Report pooled, train-holdout and val effects separately.
- Opposite train-holdout and val mean directions prohibit a cross-split
  reproducibility claim.

Gate:

```text
no development/holdout overlap
no official-test data access
R_edge and C_comp meet or fail the preregistered rules
process evidence reaches actual High-score write-in
```

## M7 — Scientific Decision And Handoff

Type: `LEARNING_CRITICAL`

Status: `NOT_AUTHORIZED`

- Complete `RESULTS.md` and `DECISION.md`.
- Produce the seven-dimension analysis report and Mermaid result flow.
- Update the experiment index and current status.
- Decide whether a separate version-aware recovery contract is justified.

## Locked Invariants

```text
no old-bbox insertion
no historical/published rewrite
no future read
no runtime GT
no source bypass
no test-driven tuning
same detector/tracker/payload/evaluator after M1
same R4-R6 candidate-membership semantics
Yec remains oracle-only
official test is never used for onset selection
```

## Explicitly Forbidden During Pair53/66 Execution-Preflight

- run MIA tracking or read tracking outcomes;
- run Pair53/66 MVE;
- calculate MDA, `R_edge` or `C_comp`;
- select onset or run d1-d5;
- run development, holdout or Formal;
- modify the frozen cohort;
- modify E023 source semantics;
- implement version-aware recovery.

## Planned File Scope

Files expected during authorized M1 implementation:

```text
src/datasets/mdmt_mda_gt_protocol.py
scripts/prepare_mdmt_non_test_mda_gt.py
tests/test_mdmt_non_test_mda_gt_protocol.py
summary_md/experiments/2026-8-17/
  exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/
    GT_PROTOCOL_GATE_ARTIFACT_SCHEMA.md
    GT_PROTOCOL_GATE_REPORT.md
```

Lifecycle documents may be updated only after the corresponding evidence is
available. M1 must not modify:

```text
src/tracking/
MIA runtime
E023 generated source
detector/tracker/evaluator causal semantics
```

## Known Stale Mismatches To Resolve Later

These mismatches are recorded, not silently repaired by this plan update:

| File or implementation | Current mismatch | Required later action |
| --- | --- | --- |
| `current_experiment_stage.md`, `current_status.md` | Use the coarser `BLOCKED_PENDING_GT_PROTOCOL_GATE` state. | Synchronize to policy-frozen / artifact-not-run / blocked-by-unknown when lifecycle records are next updated. |
| `EXPERIMENT_CARD.md`, `EXPERIMENT_CONTRACT.md` | Describe the gate as pending without the full G1-G7 artifact state. | Add links/status after the artifact schema and report exist; do not claim PASS early. |
| `RUN_PLAN.md` | A single planned command requests train/val/test together. | Replace with staged `audit-source`, `validate-official-test`, `derive-non-test`, `repeat-verify`, `finalize-gate` interfaces before execution. |
| `RUN_PLAN.md` | References converter, variant, onset CLI and tests that do not yet exist. | During M1 implement only converter/audit/tests; keep MIA entries non-executable. |
| Existing Contract output list | Does not enumerate the complete G1-G7 package. | Link the durable artifact schema after it is created. |
| Historical 600,923-row audit | Uses rounded/dictionary/vote-based reconciliation rather than strict exact multisets. | Retain as historical FACT only; do not promote to G2 PASS. |
| `prepare_mdmt_official_mda_gt.py` | Resume checks existence but not frozen reference checksums. | Produce a separate official-reference manifest. |
| G4 authority | No vendored independent official evidence artifact has yet been frozen. | Keep `BLOCKED_BY_UNKNOWN` until an authoritative evidence chain is captured. |
| `experiment_validation_plan.md` | Required by `AGENTS.md` bootstrap but absent in this worktree. | Record as repository documentation debt; do not substitute a new research policy during M1. |

## Minimum-Discriminating Rationale And Decision Gate

G1-G7 is the minimum discriminating plan because it changes no tracking
variable and asks only whether the evaluation protocol needed by the approved
non-test experiment is valid. Running MVE first cannot resolve annotation
authority and would permit outcome-dependent GT repair.

The exact next decision gate is:

```text
IF all G1-G6 hard gates pass
AND all required artifacts exist
AND all critical UNKNOWNs are resolved
THEN GT_PROTOCOL_GATE_PASS
     -> authorize M2/M3 and, after their checks, two-pair MVE only
ELSE IF any hard gate explicitly fails
THEN GT_PROTOCOL_GATE_FAIL
     -> stop; no repair-and-continue
ELSE GT_PROTOCOL_GATE_BLOCKED_BY_UNKNOWN
     -> stop; obtain missing authority/evidence without reading outcomes
```
