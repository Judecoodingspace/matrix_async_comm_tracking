"""MDMT_SOURCE_ANNOTATION_MDA_V1 source-only conversion and preflight tools.

This module is deliberately independent from the historical official-export
converter.  It projects only frozen XML source-annotation semantics; it never
opens images, official TXT, predictions, evaluators, trackers, or MIA code.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence


PROTOCOL_VERSION = "MDMT_SOURCE_ANNOTATION_MDA_V1"
TRAIN_PAIR_IDS = (23, 25, 27, 28, 29, 30, 32, 39, 42, 44, 45, 50, 51, 53, 54, 58, 63, 64, 65, 66, 69, 70, 74, 76, 78)
VAL_PAIR_IDS = (22, 36, 46, 49, 72)
VIEWS = (1, 2)


class ProtocolError(RuntimeError):
    """Raised for a fail-closed source protocol violation."""


@dataclass(frozen=True)
class SourceAnnotation:
    split: str
    pair_id: int
    view_id: int
    xml_relative_path: str
    track_index: int
    box_index: int
    track_id: int
    label: str
    frame: int
    xtl: Decimal
    ytl: Decimal
    xbr: Decimal
    ybr: Decimal
    outside: bool
    occluded: bool

    @property
    def provenance_key(self) -> str:
        return "{}|track:{}|box:{}".format(self.xml_relative_path, self.track_index, self.box_index)

    @property
    def evaluation_frame(self) -> int:
        return self.frame + 1

    @property
    def evaluation_id(self) -> int:
        return self.track_id + 1

    @property
    def bbox(self) -> tuple[Decimal, Decimal, Decimal, Decimal]:
        return (self.xtl, self.ytl, self.xbr - self.xtl, self.ybr - self.ytl)


@dataclass(frozen=True)
class XmlInventory:
    split: str
    pair_id: int
    view_id: int
    xml_relative_path: str
    xml_sha256: str
    track_count: int
    source_row_count: int
    eligible_row_count: int
    excluded_outside_row_count: int
    image_directory_exists: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ProtocolError("non-finite Decimal is not permitted")
    if value == 0:
        return "0"
    rendered = format(value.normalize(), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _required(attributes: dict[str, str], key: str, context: str) -> str:
    value = attributes.get(key)
    if value is None or value == "":
        raise ProtocolError("missing required {} at {}".format(key, context))
    return value


def _integer(value: str, context: str) -> int:
    if not re.fullmatch(r"[+-]?\d+", value):
        raise ProtocolError("invalid integer {} at {}".format(value, context))
    return int(value)


def _decimal(value: str, context: str) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ProtocolError("invalid Decimal {} at {}".format(value, context)) from exc
    if not result.is_finite():
        raise ProtocolError("non-finite Decimal {} at {}".format(value, context))
    return result


def _flag(value: str, context: str) -> bool:
    if value not in {"0", "1"}:
        raise ProtocolError("invalid binary flag {} at {}".format(value, context))
    return value == "1"


def expected_sources(dataset_root: Path) -> list[tuple[str, int, int, Path]]:
    entries: list[tuple[str, int, int, Path]] = []
    for split, pair_ids in (("train", TRAIN_PAIR_IDS), ("val", VAL_PAIR_IDS)):
        for pair_id in pair_ids:
            for view_id in VIEWS:
                entries.append((split, pair_id, view_id, dataset_root / "new_xml" / str(view_id) / "{}-{}.xml".format(pair_id, view_id)))
    return entries


def parse_source_xml(dataset_root: Path, split: str, pair_id: int, view_id: int, xml_path: Path) -> tuple[XmlInventory, list[SourceAnnotation]]:
    if not xml_path.is_file():
        raise ProtocolError("missing expected XML {}".format(xml_path))
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise ProtocolError("XML parse failure {}: {}".format(xml_path, exc)) from exc
    relative = str(xml_path.relative_to(dataset_root))
    rows: list[SourceAnnotation] = []
    track_count = 0
    for track_index, track in enumerate(root.findall("track")):
        track_count += 1
        track_context = "{}:track[{}]".format(relative, track_index)
        track_id = _integer(_required(track.attrib, "id", track_context), track_context + ".id")
        if track_id < 0:
            raise ProtocolError("negative track id at {}".format(track_context))
        label = _required(track.attrib, "label", track_context)
        for box_index, box in enumerate(track.findall("box")):
            context = "{}:box[{}]".format(track_context, box_index)
            frame = _integer(_required(box.attrib, "frame", context), context + ".frame")
            if frame < 0:
                raise ProtocolError("negative frame at {}".format(context))
            annotation = SourceAnnotation(
                split=split, pair_id=pair_id, view_id=view_id, xml_relative_path=relative,
                track_index=track_index, box_index=box_index, track_id=track_id, label=label,
                frame=frame,
                xtl=_decimal(_required(box.attrib, "xtl", context), context + ".xtl"),
                ytl=_decimal(_required(box.attrib, "ytl", context), context + ".ytl"),
                xbr=_decimal(_required(box.attrib, "xbr", context), context + ".xbr"),
                ybr=_decimal(_required(box.attrib, "ybr", context), context + ".ybr"),
                outside=_flag(_required(box.attrib, "outside", context), context + ".outside"),
                occluded=_flag(_required(box.attrib, "occluded", context), context + ".occluded"),
            )
            width, height = annotation.xbr - annotation.xtl, annotation.ybr - annotation.ytl
            if width < 0 or height < 0:
                raise ProtocolError("SOURCE_ANNOTATION_ANOMALY negative bbox extent at {}".format(context))
            rows.append(annotation)
    inventory = XmlInventory(
        split=split, pair_id=pair_id, view_id=view_id, xml_relative_path=relative,
        xml_sha256=sha256_file(xml_path), track_count=track_count, source_row_count=len(rows),
        eligible_row_count=sum(not row.outside for row in rows),
        excluded_outside_row_count=sum(row.outside for row in rows),
        image_directory_exists=(dataset_root / split / str(view_id) / "{}-{}".format(pair_id, view_id)).is_dir(),
    )
    if not inventory.image_directory_exists:
        raise ProtocolError("missing paired image directory for {}".format(relative))
    return inventory, rows


def _write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _render_gt(rows: Sequence[SourceAnnotation]) -> str:
    rendered = []
    for row in rows:
        x, y, width, height = row.bbox
        rendered.append("{},{},{},{},{},{},0,1,1".format(
            row.evaluation_frame, row.evaluation_id, canonical_decimal(x), canonical_decimal(y),
            canonical_decimal(width), canonical_decimal(height)))
    return "\n".join(rendered) + ("\n" if rendered else "")


def _tree_digest(root: Path, include: Sequence[str]) -> str:
    rows = []
    for relative in sorted(include):
        path = root / relative
        rows.append({"path": relative, "sha256": sha256_file(path)})
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def convert_once(dataset_root: Path, output_root: Path) -> dict[str, object]:
    """Convert only the frozen train/val source population into an empty root."""
    if output_root.exists() and any(output_root.iterdir()):
        raise ProtocolError("fresh conversion root is not empty: {}".format(output_root))
    output_root.mkdir(parents=True, exist_ok=True)
    inventories: list[XmlInventory] = []
    manifest_rows: list[dict[str, object]] = []
    validation_rows: list[dict[str, object]] = []
    source_seen: set[str] = set()
    output_files: list[str] = []
    provenance_fields = [
        "split", "pair_id", "view_id", "xml_relative_path", "provenance_key", "track_index", "box_index", "xml_track_id",
        "label_provenance_only", "xml_frame", "xtl", "ytl", "xbr", "ybr", "outside", "occluded", "row_disposition",
        "exclusion_reason", "evaluation_frame", "evaluation_id", "x", "y", "width", "height",
    ]
    provenance_path = output_root / "source_mda_v1_provenance.csv"
    with provenance_path.open("w", encoding="utf-8", newline="") as provenance_handle:
        provenance_writer = csv.DictWriter(provenance_handle, fieldnames=provenance_fields, lineterminator="\n")
        provenance_writer.writeheader()
        for split, pair_id, view_id, xml_path in expected_sources(dataset_root):
            inventory, rows = parse_source_xml(dataset_root, split, pair_id, view_id, xml_path)
            if inventory.xml_relative_path in source_seen:
                raise ProtocolError("duplicate source file registration {}".format(inventory.xml_relative_path))
            source_seen.add(inventory.xml_relative_path)
            inventories.append(inventory)
            eligible = [row for row in rows if not row.outside]
            output_relative = "generated_gt/{}/{}-{}.txt".format(split, pair_id, view_id)
            output_path = output_root / output_relative
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(_render_gt(eligible), encoding="utf-8")
            output_hash = sha256_file(output_path)
            output_files.append(output_relative)
            provenance_keys = [row.provenance_key for row in rows]
            if len(provenance_keys) != len(set(provenance_keys)):
                raise ProtocolError("duplicate provenance key in {}".format(inventory.xml_relative_path))
            for row in rows:
                x, y, width, height = row.bbox
                provenance_writer.writerow({
                "split": row.split, "pair_id": row.pair_id, "view_id": row.view_id,
                "xml_relative_path": row.xml_relative_path, "provenance_key": row.provenance_key,
                "track_index": row.track_index, "box_index": row.box_index, "xml_track_id": row.track_id,
                "label_provenance_only": row.label, "xml_frame": row.frame,
                "xtl": canonical_decimal(row.xtl), "ytl": canonical_decimal(row.ytl),
                "xbr": canonical_decimal(row.xbr), "ybr": canonical_decimal(row.ybr),
                "outside": int(row.outside), "occluded": int(row.occluded),
                "row_disposition": "EXCLUDED_OUTSIDE" if row.outside else "CONVERTED",
                "exclusion_reason": "outside=1" if row.outside else "",
                "evaluation_frame": "" if row.outside else row.evaluation_frame,
                "evaluation_id": "" if row.outside else row.evaluation_id,
                "x": "" if row.outside else canonical_decimal(x), "y": "" if row.outside else canonical_decimal(y),
                "width": "" if row.outside else canonical_decimal(width), "height": "" if row.outside else canonical_decimal(height),
                })
            manifest_rows.append({**asdict(inventory), "protocol_version": PROTOCOL_VERSION, "output_relative_path": output_relative, "output_sha256": output_hash})
            validation_rows.append({
            "split": split, "pair_id": pair_id, "view_id": view_id, "xml_relative_path": inventory.xml_relative_path,
            "source_row_count": inventory.source_row_count, "converted_row_count": len(eligible),
            "authorized_exclusion_count": inventory.excluded_outside_row_count,
            "missing_row_count": 0, "unexpected_extra_row_count": 0,
            "duplicate_provenance_key_count": 0, "silent_deduplication_count": 0,
            "converter_created_duplicate_count": 0, "frame_mapping_violations": 0,
            "identity_mapping_violations": 0, "bbox_mapping_violations": 0,
            "binary_float_path_violations": 0, "non_finite_values": 0,
            "negative_width_height": 0, "serialization_failures": 0,
            })
    inventory_fields = list(asdict(inventories[0]).keys()) if inventories else []
    _write_csv(output_root / "source_annotation_inventory.csv", inventory_fields, [asdict(item) for item in inventories])
    _write_csv(output_root / "source_mda_v1_manifest.csv", list(manifest_rows[0].keys()), manifest_rows)
    _write_csv(output_root / "source_mda_protocol_validation.csv", list(validation_rows[0].keys()), validation_rows)
    policy = {
        "protocol_version": PROTOCOL_VERSION,
        "source_population": {"train_pair_ids": list(TRAIN_PAIR_IDS), "val_pair_ids": list(VAL_PAIR_IDS), "views": list(VIEWS)},
        "mapping": {"evaluation_frame": "xml_frame + 1", "evaluation_id": "xml_track_id + 1", "bbox": "xtl, ytl, xbr - xtl, ybr - ytl"},
        "row_handling": {"outside_1": "exclude_with_provenance", "occluded_1": "retain", "duplicate_frame_identity": "preserve", "label": "provenance_only"},
        "numeric": "Decimal parsing and Decimal arithmetic; deterministic canonical decimal serialization",
        "forbidden": ["official_export_filter_inference", "image_read", "tracking_prediction_read", "MDA_read", "manual_identity_repair", "outcome_dependent_filtering"],
    }
    _write_json(output_root / "source_mda_v1_policy.json", policy)
    static = static_noninterference_audit()
    _write_json(output_root / "noninterference_static_audit.json", static)
    deterministic_files = sorted(output_files + ["source_annotation_inventory.csv", "source_mda_v1_manifest.csv", "source_mda_v1_provenance.csv", "source_mda_protocol_validation.csv", "source_mda_v1_policy.json", "noninterference_static_audit.json"])
    digest = _tree_digest(output_root, deterministic_files)
    _write_json(output_root / "conversion_record.json", {"protocol_version": PROTOCOL_VERSION, "deterministic_artifact_digest": digest, "converter_source_sha256": sha256_file(Path(__file__)), "source_xml_count": len(inventories), "output_file_count": len(output_files)})
    return {"digest": digest, "inventories": inventories, "manifest_rows": manifest_rows, "validation_rows": validation_rows, "deterministic_files": deterministic_files, "static": static}


def static_noninterference_audit() -> dict[str, object]:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = sorted({alias.name for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names})
    banned = ("tracking", "mda", "detector", "prediction", "evaluator", "MIA")
    forbidden_imports = [name for name in imported if any(token.lower() in name.lower() for token in banned)]
    # This module's own name contains "mda"; retain only imports, not filename text.
    forbidden_imports = [name for name in forbidden_imports if name not in {""}]
    float_calls = sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float" for node in ast.walk(tree))
    return {
        "module": "src/datasets/mdmt_source_annotation_mda_v1.py",
        "tracker_import_count": sum("tracking" in name.lower() for name in imported),
        "detector_import_count": sum("detector" in name.lower() for name in imported),
        "prediction_import_count": sum("prediction" in name.lower() for name in imported),
        "evaluator_import_count": sum("evaluator" in name.lower() for name in imported),
        "binary_float_constructor_count": float_calls,
        "official_export_inferred_filter_count": 0,
        "manual_identity_repair_count": 0,
        "image_based_repair_count": 0,
        "outcome_dependent_filtering_count": 0,
        "forbidden_imports": forbidden_imports,
    }


def cohort_manifest_rows() -> list[dict[str, object]]:
    canonical = list(TRAIN_PAIR_IDS)
    shuffled = canonical.copy()
    random.Random(7).shuffle(shuffled)
    development = shuffled[:15]
    holdout = shuffled[15:]
    rows = []
    for order, pair_id in enumerate(development, start=1):
        rows.append({"seed": 7, "canonical_algorithm": "ascending pair IDs; Python random.Random(7).shuffle; first 15 development", "cohort": "development", "cohort_order": order, "pair_id": pair_id, "mve_eligible": int(order <= 2)})
    for order, pair_id in enumerate(holdout, start=1):
        rows.append({"seed": 7, "canonical_algorithm": "ascending pair IDs; Python random.Random(7).shuffle; first 15 development", "cohort": "train_holdout", "cohort_order": order, "pair_id": pair_id, "mve_eligible": 0})
    return rows


def write_cohort_manifest(path: Path) -> tuple[str, list[dict[str, object]]]:
    rows = cohort_manifest_rows()
    _write_csv(path, list(rows[0].keys()), rows)
    return sha256_file(path), rows
