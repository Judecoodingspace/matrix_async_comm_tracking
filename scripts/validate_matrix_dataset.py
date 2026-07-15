#!/usr/bin/env python3
"""Validate MATRIX dataset fields needed for asynchronous multi-UAV MOT."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--max-timesteps", type=int, default=50)
    parser.add_argument(
        "--output-md",
        type=Path,
        default=Path("summary_md/experiments/2026-6-21/matrix_dataset_readiness.md"),
    )
    return parser.parse_args()


def first_existing(root: Path, candidates: Iterable[str]) -> Path | None:
    for rel in candidates:
        path = root / rel
        if path.exists():
            return path
    return None


def sorted_numbered_files(path: Path, suffix: str) -> list[Path]:
    if not path.exists():
        return []
    return sorted(path.glob(f"*{suffix}"), key=lambda p: p.name)


def pick_field(row: Mapping[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in row:
            return row[name]
    lowered = {str(key).lower(): key for key in row}
    for name in names:
        key = lowered.get(name.lower())
        if key is not None:
            return row[key]
    return None


def frame_id_from_name(path: Path) -> int | None:
    match = re.search(r"(\d+)", path.stem)
    return int(match.group(1)) if match else None


def bbox_is_visible(view: Mapping[str, Any]) -> bool:
    vals = [pick_field(view, ["xmin", "ymin", "xmax", "ymax"])]
    xmin = pick_field(view, ["xmin", "x_min", "left"])
    ymin = pick_field(view, ["ymin", "y_min", "top"])
    xmax = pick_field(view, ["xmax", "x_max", "right"])
    ymax = pick_field(view, ["ymax", "y_max", "bottom"])
    vals = [xmin, ymin, xmax, ymax]
    if any(value is None for value in vals):
        return False
    try:
        nums = [float(value) for value in vals]
    except (TypeError, ValueError):
        return False
    return nums[0] >= 0 and nums[1] >= 0 and nums[2] > nums[0] and nums[3] > nums[1]


def load_annotation_rows(annotation_files: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in annotation_files:
        frame_id = frame_id_from_name(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append(f"{path}: JSON decode failed: {exc}")
            continue
        if not isinstance(data, list):
            warnings.append(f"{path}: expected list annotation, got {type(data).__name__}")
            continue
        for item in data:
            if not isinstance(item, dict):
                continue
            person_id = pick_field(item, ["personID", "personId", "pid", "id"])
            position_id = pick_field(item, ["positionID", "positionId", "pos_id", "position"])
            views = pick_field(item, ["views", "view"])
            if not isinstance(views, list):
                views = []
            visible_views = sum(1 for view in views if isinstance(view, dict) and bbox_is_visible(view))
            rows.append(
                {
                    "frame_id": frame_id,
                    "person_id": None if person_id is None else int(float(person_id)),
                    "position_id": None if position_id is None else int(float(position_id)),
                    "n_views": len(views),
                    "visible_views": visible_views,
                }
            )
    return rows, warnings


def parse_pedestrian_3d(path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    if not path.exists():
        return rows
    frame_idx = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            frame_idx += 1
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        pid, pos_id, x, y, z = map(float, parts[:5])
        rows.append({"frame_idx": frame_idx, "person_id": pid, "position_id": pos_id, "x": x, "y": y, "z": z})
    return rows


def count_pom_rectangles(path: Path) -> tuple[int, int]:
    visible = 0
    total = 0
    if not path.exists():
        return visible, total
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "RECTANGLE" not in line:
            continue
        total += 1
        if "notvisible" not in line:
            visible += 1
    return visible, total


def summarize(root: Path, max_timesteps: int) -> tuple[list[str], dict[str, Any]]:
    ann_dir = root / "annotations_positions"
    pom_dir = root / "POMs"
    image_dir = root / "image_subsets"
    calib_dir = root / "calibrations"
    ped_dir = root / "matchings" / "Pedestrians"
    los_dir = ped_dir / "LoS"

    annotation_files = sorted_numbered_files(ann_dir, ".json")[:max_timesteps]
    pom_files = sorted_numbered_files(pom_dir, ".pom")[:max_timesteps]
    ped_3d_files = sorted_numbered_files(ped_dir, ".txt")[:max_timesteps]
    los_files = sorted_numbered_files(los_dir, ".txt")[: max_timesteps * 8]
    image_subdirs = sorted([p for p in image_dir.glob("D*") if p.is_dir()]) if image_dir.exists() else []
    intr_files = list((calib_dir / "intrinsic").glob("*.xml")) if (calib_dir / "intrinsic").exists() else []
    extr_files = list((calib_dir / "extrinsic").glob("*.xml")) if (calib_dir / "extrinsic").exists() else []

    ann_rows, warnings = load_annotation_rows(annotation_files)
    person_frames: dict[int, set[int]] = defaultdict(set)
    person_positions: dict[int, set[int]] = defaultdict(set)
    missing_person = 0
    missing_position = 0
    visible_view_counts: list[int] = []
    for row in ann_rows:
        if row["person_id"] is None:
            missing_person += 1
            continue
        person_id = int(row["person_id"])
        if row["frame_id"] is not None:
            person_frames[person_id].add(int(row["frame_id"]))
        if row["position_id"] is None:
            missing_position += 1
        else:
            person_positions[person_id].add(int(row["position_id"]))
        visible_view_counts.append(int(row["visible_views"]))

    unstable_position_ids = {
        person_id: len(pos_ids)
        for person_id, pos_ids in person_positions.items()
        if len(pos_ids) > 1
    }
    single_frame_people = sum(1 for frames in person_frames.values() if len(frames) == 1)

    ped_rows = [row for path in ped_3d_files for row in parse_pedestrian_3d(path)]
    ped_has_world = all(all(math.isfinite(row[key]) for key in ("x", "y", "z")) for row in ped_rows)

    pom_visible_total = 0
    pom_rect_total = 0
    for path in pom_files:
        visible, total = count_pom_rectangles(path)
        pom_visible_total += visible
        pom_rect_total += total

    summary = {
        "root": str(root),
        "annotation_files": len(annotation_files),
        "annotation_rows": len(ann_rows),
        "unique_person_ids": len(person_frames),
        "missing_person_id_rows": missing_person,
        "missing_position_id_rows": missing_position,
        "unstable_position_id_people": len(unstable_position_ids),
        "single_frame_people": single_frame_people,
        "visible_view_mean": (sum(visible_view_counts) / len(visible_view_counts)) if visible_view_counts else float("nan"),
        "visible_view_hist": dict(sorted(Counter(visible_view_counts).items())),
        "ped_3d_files": len(ped_3d_files),
        "ped_3d_rows": len(ped_rows),
        "ped_3d_has_world_xyz": ped_has_world,
        "pom_files": len(pom_files),
        "pom_visible_rectangles": pom_visible_total,
        "pom_rectangles": pom_rect_total,
        "los_files": len(los_files),
        "image_drone_dirs": len(image_subdirs),
        "intrinsic_files": len(intr_files),
        "extrinsic_files": len(extr_files),
        "warnings": warnings[:20],
    }
    return readiness_lines(summary), summary


def readiness_lines(summary: Mapping[str, Any]) -> list[str]:
    checks = [
        ("annotation JSON exists", summary["annotation_files"] > 0),
        ("personID exists", summary["annotation_rows"] > 0 and summary["missing_person_id_rows"] == 0),
        ("positionID exists", summary["annotation_rows"] > 0 and summary["missing_position_id_rows"] == 0),
        ("personID persists across frames", summary["unique_person_ids"] > 0 and summary["single_frame_people"] < summary["unique_person_ids"]),
        ("3D/world coordinate files exist", summary["ped_3d_files"] > 0 and summary["ped_3d_rows"] > 0),
        ("3D/world xyz values parse", bool(summary["ped_3d_has_world_xyz"])),
        ("POM files exist", summary["pom_files"] > 0 and summary["pom_rectangles"] > 0),
        ("LoS files exist", summary["los_files"] > 0),
        ("8 drone image directories exist", summary["image_drone_dirs"] >= 8),
        ("dynamic calibration files exist", summary["intrinsic_files"] > 0 and summary["extrinsic_files"] > 0),
    ]
    return [f"- [{'x' if ok else ' '}] {name}" for name, ok in checks]


def write_report(path: Path, *, readiness: list[str], summary: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    visible_hist = ", ".join(f"{k}:{v}" for k, v in summary["visible_view_hist"].items())
    lines = [
        "# MATRIX Dataset Readiness Check",
        "",
        "## Readiness",
        "",
        *readiness,
        "",
        "## Summary",
        "",
        f"- Root: `{summary['root']}`",
        f"- Annotation files sampled: {summary['annotation_files']}",
        f"- Annotation rows: {summary['annotation_rows']}",
        f"- Unique person IDs: {summary['unique_person_ids']}",
        f"- Missing personID rows: {summary['missing_person_id_rows']}",
        f"- Missing positionID rows: {summary['missing_position_id_rows']}",
        f"- People with changing positionID across sampled frames: {summary['unstable_position_id_people']}",
        f"- People observed in only one sampled frame: {summary['single_frame_people']}",
        f"- Mean visible views per row: {summary['visible_view_mean']:.3f}",
        f"- Visible-view histogram: `{visible_hist}`",
        f"- Pedestrian 3D files sampled: {summary['ped_3d_files']}",
        f"- Pedestrian 3D rows: {summary['ped_3d_rows']}",
        f"- POM files sampled: {summary['pom_files']}",
        f"- POM visible / total rectangles: {summary['pom_visible_rectangles']} / {summary['pom_rectangles']}",
        f"- LoS files sampled: {summary['los_files']}",
        f"- Drone image directories: {summary['image_drone_dirs']}",
        f"- Intrinsic / extrinsic calibration files: {summary['intrinsic_files']} / {summary['extrinsic_files']}",
    ]
    if summary["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Use `personID` as the identity key for MDMOT. Treat `positionID` as a grid/location key unless this report shows it is stable per person across frames.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    root = args.matrix_root.expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"MATRIX root does not exist: {root}")
    readiness, summary = summarize(root, args.max_timesteps)
    write_report(args.output_md, readiness=readiness, summary=summary)
    print(f"matrix_root={root}")
    print(f"annotation_files={summary['annotation_files']} annotation_rows={summary['annotation_rows']}")
    print(f"unique_person_ids={summary['unique_person_ids']} ped_3d_rows={summary['ped_3d_rows']}")
    print(f"report={args.output_md.resolve()}")


if __name__ == "__main__":
    main()
