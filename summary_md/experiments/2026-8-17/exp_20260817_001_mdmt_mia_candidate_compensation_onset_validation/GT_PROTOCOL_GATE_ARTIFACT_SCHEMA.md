# GT Protocol Gate Artifact Schema

## Scope

This schema covers only the source-only XML-to-MDA ground-truth protocol gate
for `exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation`. It
does not contain predictions, tracker outputs, MVE metrics, development
selection, holdout confirmation, Formal conclusions, or recovery analysis.

## Raw artifact root

```text
outputs/20260817_mdmt_non_test_mda_gt_protocol/
```

`run_a/` and `run_b/` contain deterministic generated GT only.  Their hashes
are compared by G6.  `records/` contains provenance and gate state; timestamps
in provenance records are intentionally not part of the deterministic equality
claim.

## Required artifacts and gate meaning

| Gate | Artifact(s) | PASS condition |
| --- | --- | --- |
| G1 | `manifests/source_annotation_manifest.csv`, `audits/field_completeness_report.csv`, `policy/mapping_rule_manifest.json`, `records/g1_source_audit.json` | Exactly 88 parseable, uniquely split-resolved XML sources; strict fields and policy recorded. |
| G2 | `manifests/official_test_reference_manifest.csv`, `audits/official_test_exact_equivalence_report.csv`, `audits/official_test_equivalence_differences.csv`, `audits/official_test_outside_occluded_audit.csv`, `records/g2_validation_run_a.json` | All 28 official test files match as Decimal-normalized duplicate-preserving multisets. |
| G3 | `audits/non_test_row_conservation_report.csv`, `audits/frame_image_integrity_report.csv`, `audits/dual_view_timeline_integrity_report.csv`, `audits/bbox_boundary_audit.csv`, `manifests/derived_gt_manifest.csv` | Row conservation, no duplicate identity keys, valid image mapping, and matched dual-view timelines. |
| G4 | `evidence/cross_view_identity_semantics_evidence.json`, `audits/per_pair_cross_view_identity_audit.csv` | Authoritative identity evidence plus every non-test pair being measurable under the fixed protocol. |
| G5 | `audits/class_conflict_manifest.csv`, `policy/primary_sensitivity_manifest.json` | Primary full-derived-GT and class-consistent sensitivity populations are both declared; no source-row mutation is permitted. |
| G6 | `determinism/deterministic_repeat_run_report.csv`, `manifests/artifact_manifest.csv`, `records/g6_repeat_verify.json` | Run A and B generated GT and deterministic audits are byte-identical. |
| G7 | `GT_PROTOCOL_GATE_REPORT.md`, `records/g7_final_decision.json`, generation records | Only `PASS`, `FAIL`, or `BLOCKED_BY_UNKNOWN`; no repair-and-continue state. |

## Mapping and comparison invariants

```text
output_id    = XML track id + 1
output_frame = XML box frame + 1
x, y         = xtl, ytl
width, height = xbr - xtl, ybr - ytl
outside=0     = include
outside=1     = exclude
occluded      = retained when outside=0
```

Equivalence uses the duplicate-preserving multiset key
`(frame, id, x, y, width, height)`. Decimal spelling differences such as
`26` and `26.0` are normalized, while a numeric difference such as `100` and
`100.01` fails. No rounding, tolerance, IoU matching, row de-duplication, or
automatic repair is allowed.
