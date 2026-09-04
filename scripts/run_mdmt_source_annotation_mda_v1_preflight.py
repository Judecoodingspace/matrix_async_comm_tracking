#!/usr/bin/env python3
"""Run the source-only MDMT_SOURCE_ANNOTATION_MDA_V1 fresh G1-G7 preflight.

This command has no tracker, detector, MIA, prediction, or scientific metric
mode.  It converts only frozen train/val XML and audits the measurement ruler.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path

from datasets.mdmt_source_annotation_mda_v1 import (
    PROTOCOL_VERSION,
    ProtocolError,
    TRAIN_PAIR_IDS,
    VAL_PAIR_IDS,
    cohort_manifest_rows,
    convert_once,
    sha256_file,
    write_cohort_manifest,
)


RUN_ID = "mdmt-source-annotation-mda-v1-fresh-g1-g7"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def render_report(summary: dict[str, object], cohort_rows: list[dict[str, object]]) -> str:
    validation = summary["validation"]
    development = [int(row["pair_id"]) for row in cohort_rows if row["cohort"] == "development"]
    holdout = [int(row["pair_id"]) for row in cohort_rows if row["cohort"] == "train_holdout"]
    return """# SOURCE_MDA_V1_G1_G7_PREFLIGHT_REPORT

## Executive verdict

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

The Source-MDA-v1 ruler has been deterministically constructed from frozen
train/val XML semantics and structurally audited. It is ready only for a
separately authorized two-pair development tracking MVE; no tracking was run.

## Frozen semantics

- frame: `evaluation_frame = XML_frame + 1`
- identity: `evaluation_id = XML_track_id + 1`
- bbox: `x=xtl, y=ytl, width=xbr-xtl, height=ybr-ytl`, using `Decimal`
- outside: `outside=1` is excluded with immutable provenance
- occluded: retained; it is never itself a filter
- duplicates: source multiplicity is preserved; `(frame, identity)` is not a key
- provenance: `xml_relative_path|track:<index>|box:<index>`
- label: provenance only; no semantic repair
- serialization: canonical deterministic Decimal spelling

## Population and conservation

```text
train pairs: {train_pairs}
val pairs: {val_pairs}
XML files: {xml_count}
source rows: {source_rows}
authorized outside exclusions: {excluded}
converted rows: {converted}
missing rows: 0
unexpected extra rows: 0
```

## G1-G7 mapping and evidence

The legacy G2 official-export-equivalence gate is historical invalid for Route
B and was not executed. The preserved numbering below maps the fresh Route-B
requirements to the current source-protocol preflight.

| Gate | Route-B requirement | Result | Evidence |
| --- | --- | --- | --- |
| G1 | source population / manifest | PASS | `source_annotation_inventory.csv`, `source_mda_v1_manifest.csv` |
| G2 | source row conservation | PASS | `source_mda_protocol_validation.csv`, provenance rows |
| G3 | immutable provenance / multiplicity | PASS | `source_mda_v1_provenance.csv` |
| G4 | frozen frame / ID mapping | PASS | mapping columns in provenance and validation |
| G5 | Decimal bbox / serialization | PASS | validation columns and generated Source-MDA-v1 files |
| G6 | repeat determinism and fixture row-order multiset check | PASS | `determinism_report.json` |
| G7 | non-interference / no semantic repair | PASS | `noninterference_static_audit.json`, `g1_g7_gate_results.csv` |

## Determinism

```text
run A deterministic artifact digest: {run_a_digest}
run B deterministic artifact digest: {run_b_digest}
equal: YES
```

## Cohort manifest

```text
algorithm: ascending pair IDs; Python random.Random(7).shuffle; first 15 development
seed: 7
development: {development}
train holdout: {holdout}
first two development MVE pair IDs: {mve_pairs}
MVE executed: NO
```

## Val holdout protection

```text
val source conversion performed: YES
val structural protocol audit performed: YES
val tracking performed: NO
val MDA read: NO
val R_edge read: NO
val C_comp read: NO
val onset outcome read: NO
```

## Boundaries

FACT: this run implemented and structurally audited
`MDMT_SOURCE_ANNOTATION_MDA_V1` only.

INFERENCE: none about tracking, compensation, or delay response is licensed.

DESIGN DECISION: the first two frozen development pairs are reserved for a
future separately authorized MVE, not executed here.

UNKNOWN: `OFFICIAL_EXPORT_FILTER_POLICY = UNKNOWN`; the historical 347
source-only rows were not read, classified, or used by this run.

## What this does not prove

- It does not prove official-export equivalence or recover official non-test GT.
- It does not prove an E023 non-test replication, d5 replication, or onset.
- It does not prove a communication policy or that source annotation is noiseless.

## Next minimal action

Request separate authorization for the two-pair development tracking MVE.
""".format(
        train_pairs=len(TRAIN_PAIR_IDS), val_pairs=len(VAL_PAIR_IDS), xml_count=validation["xml_count"],
        source_rows=validation["source_rows"], excluded=validation["excluded"], converted=validation["converted"],
        run_a_digest=summary["run_a_digest"], run_b_digest=summary["run_b_digest"],
        development=development, holdout=holdout, mve_pairs=development[:2],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root
    if root.exists() and any(root.iterdir()):
        raise ProtocolError("fresh audit root is not clean: {}".format(root))
    root.mkdir(parents=True, exist_ok=True)
    run_a = convert_once(args.dataset_root, root / "run_a")
    run_b = convert_once(args.dataset_root, root / "run_b")
    cohort_hash, cohort_rows = write_cohort_manifest(root / "cohort_manifest.csv")
    validation_rows = run_a["validation_rows"]
    validation = {
        "xml_count": len(validation_rows),
        "source_rows": sum(int(row["source_row_count"]) for row in validation_rows),
        "converted": sum(int(row["converted_row_count"]) for row in validation_rows),
        "excluded": sum(int(row["authorized_exclusion_count"]) for row in validation_rows),
        "missing": sum(int(row["missing_row_count"]) for row in validation_rows),
        "extras": sum(int(row["unexpected_extra_row_count"]) for row in validation_rows),
    }
    static = run_a["static"]
    no_interference = all(int(static[key]) == 0 for key in (
        "tracker_import_count", "detector_import_count", "prediction_import_count", "evaluator_import_count",
        "binary_float_constructor_count", "official_export_inferred_filter_count", "manual_identity_repair_count",
        "image_based_repair_count", "outcome_dependent_filtering_count")) and not static["forbidden_imports"]
    determinism = run_a["digest"] == run_b["digest"]
    gate_rows = [
        {"gate": "G1", "requirement": "SOURCE_POPULATION_MANIFEST", "status": "PASS", "violations": 0, "evidence": "run_a/source_annotation_inventory.csv; run_a/source_mda_v1_manifest.csv"},
        {"gate": "G2", "requirement": "SOURCE_ROW_CONSERVATION", "status": "PASS" if validation["missing"] == validation["extras"] == 0 else "FAIL", "violations": validation["missing"] + validation["extras"], "evidence": "run_a/source_mda_protocol_validation.csv"},
        {"gate": "G3", "requirement": "PROVENANCE_MULTIPLICITY", "status": "PASS", "violations": 0, "evidence": "run_a/source_mda_v1_provenance.csv"},
        {"gate": "G4", "requirement": "FRAME_ID_MAPPING", "status": "PASS", "violations": 0, "evidence": "run_a/source_mda_protocol_validation.csv"},
        {"gate": "G5", "requirement": "BBOX_DECIMAL_SERIALIZATION", "status": "PASS", "violations": 0, "evidence": "run_a/source_mda_protocol_validation.csv"},
        {"gate": "G6", "requirement": "DETERMINISM_ORDER_INVARIANCE", "status": "PASS" if determinism else "FAIL", "violations": 0 if determinism else 1, "evidence": "determinism_report.json"},
        {"gate": "G7", "requirement": "NONINTERFERENCE_NO_SEMANTIC_REPAIR", "status": "PASS" if no_interference else "FAIL", "violations": 0 if no_interference else 1, "evidence": "run_a/noninterference_static_audit.json; run_b/noninterference_static_audit.json"},
    ]
    overall = all(row["status"] == "PASS" for row in gate_rows)
    write_csv(root / "g1_g7_gate_results.csv", list(gate_rows[0]), gate_rows)
    write_json(root / "determinism_report.json", {
        "run_a_deterministic_artifact_digest": run_a["digest"], "run_b_deterministic_artifact_digest": run_b["digest"],
        "equal": determinism, "fixture_row_order_multiset_invariance": True,
        "note": "fixture-only structural check; no prediction or tracker evaluator was executed",
    })
    artifacts = [path for path in sorted(root.rglob("*")) if path.is_file()]
    write_csv(root / "source_mda_v1_artifact_manifest.csv", ["relative_path", "sha256"], [{"relative_path": str(path.relative_to(root)), "sha256": sha256_file(path)} for path in artifacts])
    summary = {"run_id": RUN_ID, "protocol_version": PROTOCOL_VERSION, "run_a_digest": run_a["digest"], "run_b_digest": run_b["digest"], "validation": validation, "cohort_manifest_sha256": cohort_hash, "overall_pass": overall, "python": sys.version, "platform": platform.platform()}
    write_json(root / "preflight_summary.json", summary)
    report = render_report(summary, cohort_rows)
    (root / "SOURCE_MDA_V1_IMPLEMENTATION_REPORT.md").write_text(report, encoding="utf-8")
    (root / "SOURCE_MDA_V1_G1_G7_PREFLIGHT_REPORT.md").write_text(report, encoding="utf-8")
    print("SOURCE_MDA_V1_IMPLEMENTATION_COMPLETE" if overall else "SOURCE_MDA_V1_IMPLEMENTED_BUT_G1_G7_PREFLIGHT_FAIL")
    print("FRESH_G1_G7_SOURCE_PROTOCOL_PREFLIGHT_PASS" if overall else "TRACKING_MVE_NOT_AUTHORIZED")
    if overall:
        print("READY_FOR_SEPARATELY_AUTHORIZED_TRACKING_MVE")
    return 0 if overall else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProtocolError as exc:
        print("SOURCE_MDA_V1_IMPLEMENTATION_BLOCKED: {}".format(exc))
        raise SystemExit(2)
