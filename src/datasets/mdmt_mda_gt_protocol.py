"""Strict source-only MDMT XML-to-MDA GT protocol tooling.

This module deliberately does not import any tracker, MIA runtime, detector or
prediction evaluator.  It is a measurement-protocol implementation: source XML
is authoritative, official test GT is a fixed reference, and every comparison
preserves row multiplicity and Decimal precision.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
SPLITS = ("train", "val", "test")
VIEWS = (1, 2)
XML_NAME = re.compile(r"^(?P<sequence>[^-]+)-(?P<view>[12])\.xml$")
GT_NAME = re.compile(r"^(?P<sequence>[^-]+)-(?P<view>[12])\.txt$")
POLICY_VERSION = "mdmt_mda_gt_protocol_v1"


class ProtocolError(RuntimeError):
    """A fail-closed source or protocol violation."""


@dataclass(frozen=True)
class SourceBox:
    sequence_id: str
    split: str
    view_id: int
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
    def mda_frame(self) -> int:
        return self.frame + 1

    @property
    def mda_identity(self) -> int:
        return self.track_id + 1

    @property
    def mda_bbox(self) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        return (self.xtl, self.ytl, self.xbr - self.xtl, self.ybr - self.ytl)


@dataclass(frozen=True)
class MdaRow:
    frame: int
    identity: int
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal

    @property
    def key(self) -> Tuple[int, int, str, str, str, str]:
        return (
            self.frame,
            self.identity,
            canonical_decimal(self.x),
            canonical_decimal(self.y),
            canonical_decimal(self.width),
            canonical_decimal(self.height),
        )


@dataclass
class XmlAudit:
    path: Path
    split: Optional[str]
    sequence_id: str
    view_id: int
    boxes: List[SourceBox]
    issues: List[str]
    track_count: int
    box_count: int

    @property
    def eligible_boxes(self) -> List[SourceBox]:
        return [box for box in self.boxes if not box.outside]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_decimal(value: Decimal) -> str:
    """A lossless, deterministic spelling for a finite Decimal."""
    if not value.is_finite():
        raise ProtocolError("non-finite Decimal is not permitted")
    if value == 0:
        return "0"
    normalized = value.normalize()
    rendered = format(normalized, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def parse_decimal(value: str, *, context: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProtocolError("invalid Decimal {}: {}".format(context, value)) from exc
    if not parsed.is_finite():
        raise ProtocolError("non-finite Decimal {}: {}".format(context, value))
    return parsed


def parse_int(value: str, *, context: str) -> int:
    if not re.fullmatch(r"[+-]?\d+", str(value)):
        raise ProtocolError("invalid integer {}: {}".format(context, value))
    return int(value)


def parse_flag(value: str, *, context: str) -> bool:
    if value not in {"0", "1"}:
        raise ProtocolError("invalid binary flag {}: {}".format(context, value))
    return value == "1"


def _required(attributes: Mapping[str, str], name: str, context: str) -> str:
    if name not in attributes:
        raise ProtocolError("missing required {} at {}".format(name, context))
    value = attributes[name]
    if value == "":
        raise ProtocolError("empty required {} at {}".format(name, context))
    return value


def resolve_split(dataset_root: Path, sequence_id: str, view_id: int) -> Optional[str]:
    candidates = [
        split for split in SPLITS
        if (dataset_root / split / str(view_id) / "{}-{}".format(sequence_id, view_id)).is_dir()
    ]
    if len(candidates) == 1:
        return candidates[0]
    return None


def parse_xml_file(path: Path, *, dataset_root: Path, sequence_id: str, view_id: int) -> XmlAudit:
    split = resolve_split(dataset_root, sequence_id, view_id)
    issues: List[str] = []
    boxes: List[SourceBox] = []
    track_count = 0
    box_count = 0
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return XmlAudit(path, split, sequence_id, view_id, boxes, ["xml_parse_error:{}".format(exc)], 0, 0)

    if split is None:
        issues.append("split_resolution_not_unique_or_missing")
    for track_index, track in enumerate(root.findall("track")):
        track_count += 1
        track_context = "{}:track[{}]".format(path, track_index)
        try:
            track_id = parse_int(_required(track.attrib, "id", track_context), context=track_context + ".id")
            if track_id < 0:
                raise ProtocolError("negative track id at {}".format(track_context))
            label = _required(track.attrib, "label", track_context)
        except ProtocolError as exc:
            issues.append(str(exc))
            continue
        for box_index, box in enumerate(track.findall("box")):
            box_count += 1
            box_context = "{}:track[{}].box[{}]".format(path, track_index, box_index)
            try:
                frame = parse_int(_required(box.attrib, "frame", box_context), context=box_context + ".frame")
                if frame < 0:
                    raise ProtocolError("negative frame at {}".format(box_context))
                xtl = parse_decimal(_required(box.attrib, "xtl", box_context), context=box_context + ".xtl")
                ytl = parse_decimal(_required(box.attrib, "ytl", box_context), context=box_context + ".ytl")
                xbr = parse_decimal(_required(box.attrib, "xbr", box_context), context=box_context + ".xbr")
                ybr = parse_decimal(_required(box.attrib, "ybr", box_context), context=box_context + ".ybr")
                outside = parse_flag(_required(box.attrib, "outside", box_context), context=box_context + ".outside")
                occluded = parse_flag(_required(box.attrib, "occluded", box_context), context=box_context + ".occluded")
            except ProtocolError as exc:
                issues.append(str(exc))
                continue
            if split is not None:
                boxes.append(SourceBox(sequence_id, split, view_id, track_id, label, frame, xtl, ytl, xbr, ybr, outside, occluded))
    return XmlAudit(path, split, sequence_id, view_id, boxes, issues, track_count, box_count)


def discover_xml_audits(dataset_root: Path, include_splits: Optional[Sequence[str]] = None) -> List[XmlAudit]:
    xml_root = dataset_root / "new_xml"
    selected_splits = None if include_splits is None else set(include_splits)
    audits: List[XmlAudit] = []
    for view_id in VIEWS:
        directory = xml_root / str(view_id)
        if not directory.is_dir():
            audits.append(XmlAudit(directory, None, "", view_id, [], ["missing_xml_view_directory"], 0, 0))
            continue
        for path in sorted(directory.glob("*.xml"), key=lambda item: item.name):
            match = XML_NAME.fullmatch(path.name)
            if not match:
                audits.append(XmlAudit(path, None, "", view_id, [], ["invalid_xml_filename"], 0, 0))
                continue
            declared_view = int(match.group("view"))
            if declared_view != view_id:
                audits.append(XmlAudit(path, None, match.group("sequence"), view_id, [], ["filename_view_directory_mismatch"], 0, 0))
                continue
            split = resolve_split(dataset_root, match.group("sequence"), view_id)
            if selected_splits is not None and split not in selected_splits:
                continue
            audits.append(parse_xml_file(path, dataset_root=dataset_root, sequence_id=match.group("sequence"), view_id=view_id))
    return sorted(audits, key=lambda item: ((item.split or ""), item.sequence_id, item.view_id, item.path.name))


def dataset_source_fingerprint(dataset_root: Path) -> str:
    """Fingerprint all source XML bytes without retaining parsed annotations."""
    values = []
    for view_id in VIEWS:
        directory = dataset_root / "new_xml" / str(view_id)
        if not directory.is_dir():
            values.append({"view_id": view_id, "path": str(directory), "sha256": "MISSING"})
            continue
        for path in sorted(directory.glob("*.xml"), key=lambda item: item.name):
            values.append({"view_id": view_id, "path": str(path), "sha256": sha256_file(path)})
    return fingerprint_payload({"policy_version": POLICY_VERSION, "source": values})


def mda_rows_from_audit(audit: XmlAudit) -> List[MdaRow]:
    if audit.issues:
        raise ProtocolError("cannot convert invalid XML {}: {}".format(audit.path, " | ".join(audit.issues)))
    rows = []
    for box in audit.eligible_boxes:
        x, y, width, height = box.mda_bbox
        rows.append(MdaRow(box.mda_frame, box.mda_identity, x, y, width, height))
    return sorted(rows, key=lambda row: row.key)


def parse_official_mda(path: Path) -> List[MdaRow]:
    rows: List[MdaRow] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ProtocolError("cannot read official GT {}: {}".format(path, exc)) from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        fields = [field.strip() for field in line.split(",")]
        if len(fields) < 6:
            raise ProtocolError("official GT has fewer than six fields at {}:{}".format(path, line_number))
        context = "{}:{}".format(path, line_number)
        rows.append(MdaRow(
            parse_int(fields[0], context=context + ".frame"),
            parse_int(fields[1], context=context + ".id"),
            parse_decimal(fields[2], context=context + ".x"),
            parse_decimal(fields[3], context=context + ".y"),
            parse_decimal(fields[4], context=context + ".width"),
            parse_decimal(fields[5], context=context + ".height"),
        ))
    return rows


def write_mda_rows(path: Path, rows: Iterable[MdaRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda row: row.key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        for row in ordered:
            handle.write("{},{},{},{},{},{},0,1,1\n".format(
                row.frame, row.identity, canonical_decimal(row.x), canonical_decimal(row.y),
                canonical_decimal(row.width), canonical_decimal(row.height)))


def counter_difference(reference: Counter, generated: Counter) -> Tuple[Counter, Counter]:
    return reference - generated, generated - reference


def compare_multisets(reference: Sequence[MdaRow], generated: Sequence[MdaRow]) -> Dict[str, object]:
    reference_counter = Counter(row.key for row in reference)
    generated_counter = Counter(row.key for row in generated)
    missing, extra = counter_difference(reference_counter, generated_counter)
    exact = not missing and not extra
    # These projections are diagnostics; an exact comparison is the hard gate.
    reference_frames = Counter(row.frame for row in reference)
    generated_frames = Counter(row.frame for row in generated)
    reference_ids = Counter(row.identity for row in reference)
    generated_ids = Counter(row.identity for row in generated)
    reference_boxes = Counter((canonical_decimal(row.x), canonical_decimal(row.y), canonical_decimal(row.width), canonical_decimal(row.height)) for row in reference)
    generated_boxes = Counter((canonical_decimal(row.x), canonical_decimal(row.y), canonical_decimal(row.width), canonical_decimal(row.height)) for row in generated)
    return {
        "exact": int(exact),
        "reference_row_count": len(reference),
        "generated_row_count": len(generated),
        "missing_rows": sum(missing.values()),
        "extra_rows": sum(extra.values()),
        "frame_projection_mismatch": sum((reference_frames - generated_frames).values()) + sum((generated_frames - reference_frames).values()),
        "id_projection_mismatch": sum((reference_ids - generated_ids).values()) + sum((generated_ids - reference_ids).values()),
        "bbox_projection_mismatch": sum((reference_boxes - generated_boxes).values()) + sum((generated_boxes - reference_boxes).values()),
        "differences": [
            {"kind": kind, "frame": key[0], "identity": key[1], "x": key[2], "y": key[3], "width": key[4], "height": key[5], "count": count}
            for kind, collection in (("missing", missing), ("extra", extra))
            for key, count in sorted(collection.items())
        ],
    }


def duplicate_identity_stats(rows: Sequence[MdaRow]) -> Dict[str, int]:
    counts = Counter((row.frame, row.identity) for row in rows)
    duplicate_keys = [key for key, count in counts.items() if count > 1]
    return {
        "duplicate_identity_keys": len(duplicate_keys),
        "duplicate_identity_extra_rows": sum(counts[key] - 1 for key in duplicate_keys),
    }


def csv_write(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def json_write(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def json_read(path: Path) -> Dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ProtocolError("invalid JSON {}: {}".format(path, exc)) from exc
    if not isinstance(payload, dict):
        raise ProtocolError("JSON root must be an object: {}".format(path))
    return payload


def policy_payload() -> Dict[str, object]:
    return {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "authoritative_source": "MDMT_ROOT/new_xml/{view_id}/{sequence_id}-{view_id}.xml",
        "mapping": {
            "output_mda_id": "source_xml_track_id + 1",
            "output_mda_frame": "source_xml_box_frame + 1",
            "x": "xtl",
            "y": "ytl",
            "width": "xbr - xtl",
            "height": "ybr - ytl",
            "outside_0": "include",
            "outside_1": "exclude",
            "occluded_0": "retain",
            "occluded_1": "retain",
            "output_suffix_fields": [0, 1, 1],
        },
        "comparison": {
            "kind": "exact_duplicate_preserving_semantic_multiset",
            "key": ["frame", "id", "x", "y", "width", "height"],
            "canonical_numeric_type": "Decimal",
            "rounding": "forbidden",
            "tolerance": "forbidden",
            "iou_matching": "forbidden",
        },
        "forbidden_authority": [
            "sequence_view_or_id_specific_exception",
            "manual_identity_or_bbox_repair",
            "majority_vote_mapping",
            "image_based_judgement",
            "prediction_or_tracking_outcome_read",
            "bbox_clip_or_round",
        ],
    }


def source_manifest_rows(audits: Sequence[XmlAudit]) -> List[Dict[str, object]]:
    rows = []
    for audit in audits:
        boxes = audit.boxes
        rows.append({
            "split": audit.split or "",
            "sequence_id": audit.sequence_id,
            "view_id": audit.view_id,
            "xml_path": str(audit.path),
            "xml_sha256": sha256_file(audit.path) if audit.path.is_file() else "",
            "parser_status": "PASS" if not audit.issues else "FAIL",
            "issue_count": len(audit.issues),
            "track_count": audit.track_count,
            "box_count": audit.box_count,
            "valid_box_count": len(boxes),
            "eligible_box_count": len(audit.eligible_boxes),
            "outside_box_count": sum(int(box.outside) for box in boxes),
            "occluded_box_count": sum(int(box.occluded) for box in boxes),
            "issues": " | ".join(audit.issues),
        })
    return rows


def image_paths(image_dir: Path) -> List[Path]:
    if not image_dir.is_dir():
        return []
    return sorted(
        [path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES],
        key=lambda path: path.name,
    )


def image_dimensions(path: Path) -> Tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as image:
            return image.size
    except Exception as exc:  # Pillow reports several image-format exceptions.
        raise ProtocolError("cannot read image dimensions {}: {}".format(path, exc)) from exc


def repository_state(repo_root: Path) -> Dict[str, object]:
    git_dir = repo_root / ".gitstore"
    if not git_dir.is_dir():
        return {"git_commit": "unavailable", "git_branch": "unavailable", "worktree_clean": None}
    command = ["git", "--git-dir={}".format(git_dir), "--work-tree={}".format(repo_root)]
    try:
        commit = subprocess.check_output(command + ["rev-parse", "HEAD"], text=True).strip()
        branch = subprocess.check_output(command + ["branch", "--show-current"], text=True).strip()
        clean = int(not subprocess.check_output(command + ["status", "--porcelain"], text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": "unavailable", "git_branch": "unavailable", "worktree_clean": None}
    return {"git_commit": commit, "git_branch": branch, "worktree_clean": clean}


def runtime_environment() -> Dict[str, object]:
    try:
        from PIL import Image
        pillow_version = Image.__version__
    except Exception:
        pillow_version = "unavailable"
    return {
        "python_version": sys.version,
        "platform": sys.platform,
        "pillow_version": pillow_version,
    }


def fingerprint_payload(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit_identity_pairs(audits: Sequence[XmlAudit]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    by_pair: Dict[Tuple[str, str], Dict[int, XmlAudit]] = defaultdict(dict)
    for audit in audits:
        if audit.split is not None and audit.view_id in VIEWS:
            by_pair[(audit.split, audit.sequence_id)][audit.view_id] = audit
    pair_rows: List[Dict[str, object]] = []
    conflicts: List[Dict[str, object]] = []
    for (split, sequence_id), views in sorted(by_pair.items()):
        first, second = views.get(1), views.get(2)
        if first is None or second is None:
            pair_rows.append({"split": split, "sequence_id": sequence_id, "pair_complete": 0, "same_id_same_frame_cross_view_event_count": 0, "class_conflict_event_count": 0, "mda_measurable": 0})
            continue
        def indexed(audit: XmlAudit) -> Dict[Tuple[int, int], List[str]]:
            values: Dict[Tuple[int, int], List[str]] = defaultdict(list)
            for box in audit.eligible_boxes:
                values[(box.mda_frame, box.mda_identity)].append(box.label)
            return values
        one, two = indexed(first), indexed(second)
        shared = sorted(set(one) & set(two))
        event_count = 0
        conflict_count = 0
        for frame, identity in shared:
            labels_one = sorted(one[(frame, identity)])
            labels_two = sorted(two[(frame, identity)])
            event_count += min(len(labels_one), len(labels_two))
            if set(labels_one) != set(labels_two):
                conflict_count += 1
                conflicts.append({
                    "split": split,
                    "sequence_id": sequence_id,
                    "frame": frame,
                    "identity": identity,
                    "view_1_labels": "|".join(labels_one),
                    "view_2_labels": "|".join(labels_two),
                })
        pair_rows.append({
            "split": split,
            "sequence_id": sequence_id,
            "pair_complete": 1,
            "same_id_same_frame_cross_view_event_count": event_count,
            "class_conflict_event_count": conflict_count,
            "mda_measurable": int(event_count > 0),
        })
    return pair_rows, conflicts


def artifact_hashes(root: Path, relative_paths: Iterable[Path]) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for path in sorted(relative_paths, key=lambda item: str(item)):
        full = root / path
        values[str(path)] = sha256_file(full) if full.is_file() else "MISSING"
    return values


def find_gt_files(root: Path) -> Dict[Tuple[str, int], Path]:
    files: Dict[Tuple[str, int], Path] = {}
    if not root.is_dir():
        return files
    for path in sorted(root.glob("*.txt"), key=lambda item: item.name):
        match = GT_NAME.fullmatch(path.name)
        if not match:
            continue
        key = (match.group("sequence"), int(match.group("view")))
        if key in files:
            raise ProtocolError("duplicate GT filename key in {}: {}".format(root, key))
        files[key] = path
    return files
