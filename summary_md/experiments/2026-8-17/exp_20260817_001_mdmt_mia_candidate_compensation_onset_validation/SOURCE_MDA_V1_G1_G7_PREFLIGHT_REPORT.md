# SOURCE_MDA_V1_G1_G7_PREFLIGHT_REPORT

## A. EXECUTIVE VERDICT

```text
Converter implemented: YES
Fresh audit root: YES

G1: PASS
G2: PASS
G3: PASS
G4: PASS
G5: PASS
G6: PASS
G7: PASS

Overall: FRESH_G1_G7_SOURCE_PROTOCOL_PREFLIGHT_PASS
Tracking MVE authorized by this run: NO
Tracking MVE executed: NO
```

The all-pass preflight makes the protocol ready for separately authorized
tracking MVE only. It did not execute an MVE.

## B. 30-SECOND EXPLANATION

本轮先按已经冻结的 XML 标注语义制造并检查“尺子”：将所有 train/val XML 机械地投影为
Source-MDA-v1，逐行保留来源、检查没有漏行/重造行/重复键或映射漂移，并独立重复一遍确认结果
逐字节相同。全程没有运行 tracker、MIA 或 MDA 科学评价，因此它只证明测量尺子可以进入下一阶段，
不证明任何补偿机制或 tracking 结果。

## C. FILES CHANGED

Added:

- `src/datasets/mdmt_source_annotation_mda_v1.py`
- `scripts/run_mdmt_source_annotation_mda_v1_preflight.py`
- `tests/test_mdmt_source_annotation_mda_v1.py`
- this report and `SOURCE_MDA_V1_IMPLEMENTATION_REPORT.md`

Untouched frozen files:

```text
E023 v8 modified = NO
official GT modified = NO
source XML modified = NO
src/tracking/ modified = NO
```

Raw generated artifacts are ignored under:

```text
outputs/20260904_mdmt_source_annotation_mda_v1_preflight_retry3/
```

## D. CONVERTER SEMANTICS

| Item | Frozen implementation |
| --- | --- |
| frame | `XML_frame + 1` |
| identity | `XML_track_id + 1` |
| bbox | `(xtl, ytl, xbr-xtl, ybr-ytl)` |
| outside | `outside=1` is an explicit provenance-recorded exclusion |
| occluded | retained; no filter |
| duplicate | preserve source multiplicity; `(frame, identity)` is not unique |
| provenance | `xml_relative_path|track:<index>|box:<index>` |
| numeric type | `Decimal`, with no binary-float constructor path |
| serialization | canonical deterministic Decimal output |

## E. POPULATION MANIFEST

```text
train pairs: 25
val pairs: 5
XML count: 60
source rows: 1,610,691
authorized exclusions: 0
converted rows: 1,610,691
```

The population contains only frozen train/val XML. No test XML, official TXT,
prediction, tracking or scientific output was an input.

## F. G1-G7 TABLE

The legacy exact-official-export G2 is a historical invalid predecessor for
Route B. These preserve the G1-G7 numbering while mapping it to the current
Route-B source-protocol requirements.

| Gate | Requirement | Result | Violations | Machine-checkable evidence |
| --- | --- | --- | ---: | --- |
| G1 | source population / manifest | PASS | 0 | `run_a/source_annotation_inventory.csv`, `run_a/source_mda_v1_manifest.csv` |
| G2 | source row conservation | PASS | 0 | `run_a/source_mda_protocol_validation.csv` |
| G3 | provenance / multiplicity | PASS | 0 | `run_a/source_mda_v1_provenance.csv` |
| G4 | frozen frame / ID mapping | PASS | 0 | mapping and validation columns in run A |
| G5 | Decimal bbox / numeric / serialization | PASS | 0 | validation columns and generated Source-MDA-v1 files |
| G6 | repeat determinism / evaluator row-order invariance | PASS | 0 | `determinism_report.json`; `SOURCE_MDA_V1_G6_FIXTURE_CLOSURE_REPORT.md` |
| G7 | non-interference / no semantic repair | PASS | 0 | `run_a/noninterference_static_audit.json`, `g1_g7_gate_results.csv` |

The complete generated gate table has SHA-256:

```text
40f48231a767636357b8d5557db043090db334cf12941d447dc89f9ce00bddf6
```

## G. DETERMINISM

```text
run A hash: b9c09025ab775e8e4d2f343bd7634f7f3273b007f712d58bffe9adc5523b3a0e
run B hash: b9c09025ab775e8e4d2f343bd7634f7f3273b007f712d58bffe9adc5523b3a0e
equal: YES
```

`determinism_report.json` SHA-256:

```text
8545b1f3ace6001027f41af3d924856ad68e430bf332e6f899a3f69b54dd6472
```

The original repeat-run digest proves converter determinism. The separately
recorded G6 fixture closure invokes `load_mot_gt -> cross_view_mda` on fixed
synthetic predictions and GT files whose row multiset is identical but whose
same-frame order differs; its MDA/AAS outputs are exactly equal. No real
prediction-dependent evaluation was run.

## H. PROVENANCE / MULTIPLICITY

```text
source rows: 1,610,691
converted rows: 1,610,691
authorized exclusions: 0
missing: 0
unexpected extras: 0
duplicate provenance keys: 0
silent deduplications: 0
converter-created duplicates: 0
```

Run-A provenance manifest SHA-256:

```text
af61fe6c5fbcf76aae60357464b0c8a77f4fda83c63a2aa6c13470c15647a157
```

## I. COHORT MANIFEST

```text
canonical ordering algorithm:
ascending pair IDs; Python random.Random(7).shuffle; first 15 development

seed = 7
development = [53, 66, 30, 74, 76, 63, 39, 78, 44, 32, 58, 23, 65, 42, 54]
train holdout = [70, 50, 28, 64, 27, 25, 69, 51, 29, 45]
first two development MVE pair IDs = [53, 66]
MVE executed = NO
```

`cohort_manifest.csv` SHA-256:

```text
3e82deee04260c88ba637a00112f11b6604f2e1033c4b13174168b2180c14f03
```

## J. VAL HOLDOUT CHECK

```text
val source conversion performed: YES
val structural protocol audit performed: YES

val tracking performed: NO
val MDA read: NO
val R_edge read: NO
val C_comp read: NO
val onset outcome read: NO
```

## K. FACT / INFERENCE / DESIGN DECISION / UNKNOWN

- FACT: the isolated converter passed all structural G1-G7 checks on frozen
  train/val XML.
- INFERENCE: none about tracking, E023 replication, compensation or onset.
- DESIGN DECISION: seed-7 determines the immutable development/holdout split;
  `[53, 66]` are only reserved future MVE pairs.
- UNKNOWN: `OFFICIAL_EXPORT_FILTER_POLICY = UNKNOWN`. The historical 347
  source-only rows remain an uninspected divergence fingerprint.

## L. WHAT THIS RUN DOES NOT PROVE

- It does not prove official-export equivalence.
- It does not prove E023 non-test replication, d5 replication, or an onset.
- It does not prove a communication policy or a recovery method.
- It does not prove source annotation has no noise.

## M. NEXT MINIMAL ACTION

Request separate authorization for the two-pair development tracking MVE.
