"""MDMT XML/image adapter with strict runtime/evaluation separation."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
import xml.etree.ElementTree as ET

from tracking.tracklet_packets import DetectionKey, LocalDetection


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
OFFICIAL_MDA_TEST_SEQUENCE_IDS = (
    "26", "31", "34", "48", "52", "55", "56", "57", "59", "61", "62", "68", "71", "73"
)


@dataclass(frozen=True)
class MDMTBoxAnnotation:
    """One XML box. ``local_identity`` is evaluation-only."""

    sequence_id: str
    split: str
    view_id: int
    frame_id: int
    image_path: Path
    local_identity: int
    label: str
    bbox_xyxy: tuple[int, int, int, int]
    occluded: bool
    outside: bool


@dataclass(frozen=True)
class MDMTViewData:
    sequence_id: str
    split: str
    view_id: int
    image_paths: tuple[Path, ...]
    annotations: tuple[MDMTBoxAnnotation, ...]
    orphan_image_count: int
    xml_path: Path

    @property
    def image_path_by_frame(self) -> dict[int, Path]:
        return {index: path for index, path in enumerate(self.image_paths)}


@dataclass(frozen=True)
class MDMTOfficialMDABox:
    sequence_id: str
    view_id: int
    frame_id: int
    global_identity: int
    bbox_xyxy: tuple[int, int, int, int]


def _image_paths(directory: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    )


def discover_mdmt_sequence_ids(root: Path, *, split: str) -> tuple[str, ...]:
    """Return base sequence IDs that have both view directories and XML files."""
    view_one = root / split / "1"
    view_two = root / split / "2"
    if not view_one.is_dir() or not view_two.is_dir():
        raise FileNotFoundError(f"missing paired MDMT split directories under {root / split}")
    ids_one = {path.name.rsplit("-", 1)[0] for path in view_one.iterdir() if path.is_dir()}
    ids_two = {path.name.rsplit("-", 1)[0] for path in view_two.iterdir() if path.is_dir()}
    return tuple(sorted(ids_one & ids_two, key=lambda value: int(value) if value.isdigit() else value))


def load_mdmt_view(
    root: Path,
    *,
    split: str,
    sequence_id: str,
    view_id: int,
) -> MDMTViewData:
    """Load one view and map zero-based XML frames to sorted image order."""
    sequence_id = str(sequence_id)
    view_id = int(view_id)
    image_dir = root / split / str(view_id) / f"{sequence_id}-{view_id}"
    xml_path = root / "new_xml" / str(view_id) / f"{sequence_id}-{view_id}.xml"
    if not image_dir.is_dir():
        raise FileNotFoundError(image_dir)
    if not xml_path.is_file():
        raise FileNotFoundError(xml_path)
    images = _image_paths(image_dir)
    if not images:
        raise ValueError(f"no images in {image_dir}")

    root_node = ET.parse(xml_path).getroot()
    annotations: list[MDMTBoxAnnotation] = []
    max_frame = -1
    for track in root_node.findall("track"):
        local_identity = int(track.attrib["id"])
        label = str(track.attrib.get("label", ""))
        for box in track.findall("box"):
            frame_id = int(box.attrib["frame"])
            max_frame = max(max_frame, frame_id)
            if frame_id < 0 or frame_id >= len(images):
                raise ValueError(
                    f"XML frame {frame_id} has no sorted image in {image_dir} ({len(images)} images)"
                )
            bbox = (
                int(round(float(box.attrib["xtl"]))),
                int(round(float(box.attrib["ytl"]))),
                int(round(float(box.attrib["xbr"]))),
                int(round(float(box.attrib["ybr"]))),
            )
            annotations.append(
                MDMTBoxAnnotation(
                    sequence_id=sequence_id,
                    split=split,
                    view_id=view_id,
                    frame_id=frame_id,
                    image_path=images[frame_id],
                    local_identity=local_identity,
                    label=label,
                    bbox_xyxy=bbox,
                    occluded=bool(int(box.attrib.get("occluded", "0"))),
                    outside=bool(int(box.attrib.get("outside", "0"))),
                )
            )
    annotations.sort(
        key=lambda row: (row.frame_id, row.bbox_xyxy, row.label, row.local_identity)
    )
    annotated_frame_count = max_frame + 1 if max_frame >= 0 else 0
    return MDMTViewData(
        sequence_id=sequence_id,
        split=split,
        view_id=view_id,
        image_paths=images,
        annotations=tuple(annotations),
        orphan_image_count=max(len(images) - annotated_frame_count, 0),
        xml_path=xml_path,
    )


def build_runtime_detections(
    view: MDMTViewData,
    *,
    frame_start: int = 0,
    frame_end: int | None = None,
    labels: Sequence[str] | None = None,
    include_occluded: bool = True,
    fps: float | None = None,
) -> tuple[dict[int, tuple[LocalDetection, ...]], dict[DetectionKey, MDMTBoxAnnotation]]:
    """Build GT-box detections while keeping XML identities in an evaluation map."""
    label_set = None if labels is None else {str(label) for label in labels}
    last_frame = len(view.image_paths) - 1 if frame_end is None else int(frame_end)
    indexed: dict[int, list[tuple[int, MDMTBoxAnnotation]]] = defaultdict(list)
    all_by_frame: dict[int, list[MDMTBoxAnnotation]] = defaultdict(list)
    for annotation in view.annotations:
        if annotation.outside or not int(frame_start) <= annotation.frame_id <= last_frame:
            continue
        all_by_frame[annotation.frame_id].append(annotation)
    for frame_id, rows in all_by_frame.items():
        stable_rows = sorted(rows, key=lambda row: (row.bbox_xyxy, row.label, row.local_identity))
        for source_index, annotation in enumerate(stable_rows):
            if label_set is not None and annotation.label not in label_set:
                continue
            if not include_occluded and annotation.occluded:
                continue
            indexed[frame_id].append((source_index, annotation))

    detections: dict[int, tuple[LocalDetection, ...]] = {}
    evaluation: dict[DetectionKey, MDMTBoxAnnotation] = {}
    for frame_id in range(int(frame_start), last_frame + 1):
        runtime_rows: list[LocalDetection] = []
        for detection_index, annotation in indexed.get(frame_id, []):
            key = DetectionKey(view.sequence_id, view.view_id, frame_id, detection_index)
            evaluation[key] = annotation
            runtime_rows.append(
                LocalDetection(
                    sensor_key=key,
                    frame_id=frame_id,
                    drone_id=view.view_id,
                    bbox_xyxy=annotation.bbox_xyxy,
                    world_xy=None,
                    embedding=None,
                    sequence_id=view.sequence_id,
                    capture_time_ms=None if fps is None else 1000.0 * frame_id / float(fps),
                    confidence=1.0,
                    class_name=annotation.label,
                )
            )
        detections[frame_id] = tuple(runtime_rows)
    return detections, evaluation


def audit_same_numeric_ids_across_views(
    first: MDMTViewData,
    second: MDMTViewData,
) -> dict[str, object]:
    """Test whether same-number XML IDs are even label-consistent across views."""
    if first.sequence_id != second.sequence_id:
        raise ValueError("cross-view audit requires the same sequence")
    first_rows = {
        (row.frame_id, row.local_identity): row
        for row in first.annotations
        if not row.outside
    }
    second_rows = {
        (row.frame_id, row.local_identity): row
        for row in second.annotations
        if not row.outside
    }
    shared = sorted(set(first_rows) & set(second_rows))
    mismatches = [key for key in shared if first_rows[key].label != second_rows[key].label]
    return {
        "sequence_id": first.sequence_id,
        "shared_numeric_id_frame_rows": len(shared),
        "label_mismatch_rows": len(mismatches),
        "label_mismatch_fraction": 0.0 if not shared else len(mismatches) / len(shared),
        "same_numeric_id_cross_view_status": "unverified" if mismatches else "not_disproven",
    }


def load_official_mda_gt(
    path: Path,
    *,
    sequence_id: str,
    view_id: int,
) -> tuple[MDMTOfficialMDABox, ...]:
    """Load the one-based-frame GT consumed by the official MDA evaluator."""
    rows: list[MDMTOfficialMDABox] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            fields = line.strip().split(",")
            if len(fields) < 6:
                raise ValueError(f"invalid official MDA row {path}:{line_number}")
            frame_one_based, identity, x, y, width, height = [
                int(round(float(value))) for value in fields[:6]
            ]
            rows.append(
                MDMTOfficialMDABox(
                    sequence_id=str(sequence_id),
                    view_id=int(view_id),
                    frame_id=frame_one_based - 1,
                    global_identity=identity,
                    bbox_xyxy=(x, y, x + width, y + height),
                )
            )
    return tuple(rows)


def reconcile_xml_to_official_mda(
    view: MDMTViewData,
    official_rows: Sequence[MDMTOfficialMDABox],
) -> tuple[dict[int, int], dict[str, object]]:
    """Recover local-XML to official-global IDs through exact frame/bbox matches."""
    xml_by_box = {
        (row.frame_id, row.bbox_xyxy): row.local_identity
        for row in view.annotations
        if not row.outside
    }
    identity_votes: dict[int, Counter[int]] = defaultdict(Counter)
    unmatched = 0
    for row in official_rows:
        local_identity = xml_by_box.get((row.frame_id, row.bbox_xyxy))
        if local_identity is None:
            unmatched += 1
            continue
        identity_votes[local_identity][row.global_identity] += 1
    conflicts = sum(len(votes) > 1 for votes in identity_votes.values())
    mapping = {
        local_identity: votes.most_common(1)[0][0]
        for local_identity, votes in identity_votes.items()
    }
    total = len(official_rows)
    audit = {
        "sequence_id": view.sequence_id,
        "view_id": view.view_id,
        "official_gt_rows": total,
        "official_gt_unmatched_rows": unmatched,
        "official_gt_match_fraction": 0.0 if total == 0 else (total - unmatched) / total,
        "local_id_mapping_count": len(mapping),
        "local_id_mapping_conflicts": conflicts,
        "mapping_is_xml_plus_one": int(bool(mapping) and all(global_id == local_id + 1 for local_id, global_id in mapping.items())),
    }
    return mapping, audit


def dataset_inventory_rows(root: Path, *, splits: Iterable[str] = ("train", "val", "test")) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for split in splits:
        for sequence_id in discover_mdmt_sequence_ids(root, split=split):
            first = load_mdmt_view(root, split=split, sequence_id=sequence_id, view_id=1)
            second = load_mdmt_view(root, split=split, sequence_id=sequence_id, view_id=2)
            labels = Counter(row.label for row in (*first.annotations, *second.annotations) if not row.outside)
            audit = audit_same_numeric_ids_across_views(first, second)
            rows.append(
                {
                    "split": split,
                    "sequence_id": sequence_id,
                    "view1_images": len(first.image_paths),
                    "view2_images": len(second.image_paths),
                    "view1_boxes": sum(not row.outside for row in first.annotations),
                    "view2_boxes": sum(not row.outside for row in second.annotations),
                    "view1_orphan_images": first.orphan_image_count,
                    "view2_orphan_images": second.orphan_image_count,
                    "labels": repr(dict(sorted(labels.items()))),
                    **{key: value for key, value in audit.items() if key != "sequence_id"},
                }
            )
    return rows
