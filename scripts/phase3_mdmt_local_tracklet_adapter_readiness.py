#!/usr/bin/env python3
"""Validate dataset-neutral local tracklet packets on MDMT paired views."""

from __future__ import annotations

import argparse
import csv
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping

import cv2
import numpy as np

from datasets.mdmt import (
    audit_same_numeric_ids_across_views,
    build_runtime_detections,
    discover_mdmt_sequence_ids,
    load_mdmt_view,
    load_official_mda_gt,
    reconcile_xml_to_official_mda,
)
from tracking.matrix_mature_local_tracklet import (
    MatureLocalTrackletTracker,
    compute_gmc_warps_from_paths,
    validate_mature_tracker_environment,
)
from tracking.mot_metrics import Prediction, compute_identity_metrics
from tracking.tracklet_packets import DetectionKey, message_runtime_dict, message_schema_uses_person_id


def _write_csv(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    values = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not values:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in values:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(values)


def _purity_and_fragmentation(rows: list[dict[str, object]]) -> tuple[float, float]:
    by_track: dict[int, Counter[int]] = defaultdict(Counter)
    by_identity: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        track_id = int(row["local_track_id"])
        identity = int(row["evaluation_local_identity"])
        by_track[track_id][identity] += 1
        by_identity[identity].add(track_id)
    total = sum(sum(counts.values()) for counts in by_track.values())
    purity = 0.0 if total == 0 else sum(max(counts.values()) for counts in by_track.values()) / total
    fragmentation = (
        0.0
        if not by_identity
        else float(np.mean([max(len(track_ids) - 1, 0) for track_ids in by_identity.values()]))
    )
    return purity, fragmentation


def _run_view(
    *,
    dataset_root: Path,
    split: str,
    sequence_id: str,
    view_id: int,
    frame_start: int,
    frame_end: int | None,
    labels: list[str] | None,
    include_occluded: bool,
    fps: float | None,
    use_gmc: bool,
    track_buffer: int,
    match_thresh: float,
    progress_every: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object], dict[str, object]]:
    view = load_mdmt_view(
        dataset_root,
        split=split,
        sequence_id=sequence_id,
        view_id=view_id,
    )
    last_frame = len(view.image_paths) - 1 if frame_end is None else min(frame_end, len(view.image_paths) - 1)
    detections_by_frame, evaluation = build_runtime_detections(
        view,
        frame_start=frame_start,
        frame_end=last_frame,
        labels=labels,
        include_occluded=include_occluded,
        fps=fps,
    )
    first_image = cv2.imread(str(view.image_paths[frame_start]), cv2.IMREAD_COLOR)
    if first_image is None:
        raise FileNotFoundError(view.image_paths[frame_start])
    frame_shape = (int(first_image.shape[0]), int(first_image.shape[1]))

    warps: dict[int, np.ndarray] = {}
    if use_gmc:
        boxes_by_frame = {
            frame_id: [row.bbox_xyxy for row in detections]
            for frame_id, detections in detections_by_frame.items()
        }
        paths = {frame_id: view.image_paths[frame_id] for frame_id in range(frame_start, last_frame + 1)}
        warps, _ = compute_gmc_warps_from_paths(
            image_paths=paths,
            view_id=view_id,
            boxes_by_frame=boxes_by_frame,
            progress_every=progress_every,
            progress_callback=lambda frame: print(
                f"[2/4][gmc] sequence={sequence_id} view={view_id} frame={frame}/{last_frame}",
                flush=True,
            ),
        )

    tracker = MatureLocalTrackletTracker(
        view_id=view_id,
        track_buffer=track_buffer,
        match_thresh=match_thresh,
        use_appearance=False,
        similarity_threshold=0.0,
    )
    prediction_rows: list[dict[str, object]] = []
    message_rows: list[dict[str, object]] = []
    started = time.monotonic()
    for offset, frame_id in enumerate(range(frame_start, last_frame + 1), start=1):
        step = tracker.step(
            frame_id,
            detections_by_frame[frame_id],
            frame_shape=frame_shape,
            warp=warps.get(frame_id),
        )
        for assignment in step.assignments:
            if not isinstance(assignment.sensor_key, DetectionKey):
                raise TypeError("MDMT assignment returned an unexpected runtime key")
            annotation = evaluation[assignment.sensor_key]
            prediction_rows.append(
                {
                    "split": split,
                    "sequence_id": sequence_id,
                    "view_id": view_id,
                    "frame_id": frame_id,
                    "local_track_id": assignment.local_track_id,
                    "evaluation_local_identity": annotation.local_identity,
                    "label": annotation.label,
                    "occluded": int(annotation.occluded),
                    "confirmed": int(assignment.confirmed),
                    "sensor_key": repr(assignment.sensor_key),
                }
            )
        for message in step.messages:
            message_rows.append({"split": split, **message_runtime_dict(message)})
        if offset == 1 or offset == last_frame - frame_start + 1 or offset % max(progress_every, 1) == 0:
            elapsed = time.monotonic() - started
            print(
                f"[3/4][track] sequence={sequence_id} view={view_id} "
                f"frame={frame_id}/{last_frame} elapsed={elapsed:.1f}s",
                flush=True,
            )

    predictions = [
        Prediction(
            frame_id=int(row["frame_id"]),
            gt_id=int(row["evaluation_local_identity"]),
            pred_id=int(row["local_track_id"]),
        )
        for row in prediction_rows
    ]
    metrics = compute_identity_metrics(predictions)
    purity, fragmentation = _purity_and_fragmentation(prediction_rows)
    expected = sum(len(rows) for rows in detections_by_frame.values())
    metric_row = {
        "split": split,
        "sequence_id": sequence_id,
        "view_id": view_id,
        "assigned_idf1": metrics.idf1,
        "idsw": metrics.idsw,
        "weighted_purity": purity,
        "mean_fragmentation": fragmentation,
        "assignment_coverage": 0.0 if expected == 0 else len(prediction_rows) / expected,
        "assigned_rows": len(prediction_rows),
        "expected_detection_rows": expected,
    }
    audit_row = {
        "split": split,
        "sequence_id": sequence_id,
        "view_id": view_id,
        "image_count": len(view.image_paths),
        "annotation_count": len(view.annotations),
        "orphan_image_count": view.orphan_image_count,
        "xml_path": str(view.xml_path),
        "runtime_world_xy_present": int(
            any(row.world_xy is not None for detections in detections_by_frame.values() for row in detections)
        ),
    }
    return prediction_rows, message_rows, metric_row, audit_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--split", choices=("train", "val", "test"), default="val")
    parser.add_argument("--sequence-ids", nargs="+", default=None)
    parser.add_argument("--view-ids", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=None)
    parser.add_argument("--labels", nargs="+", default=["person"])
    parser.add_argument("--exclude-occluded", action="store_true")
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument(
        "--official-mda-gt-root",
        type=Path,
        default=None,
        help="Official demo/eval/test GT directory; valid only with --split test",
    )
    parser.add_argument("--use-gmc", action="store_true")
    parser.add_argument("--track-buffer", type=int, default=5)
    parser.add_argument("--match-thresh", type=float, default=0.8)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    versions = validate_mature_tracker_environment()
    sequence_ids = args.sequence_ids or list(discover_mdmt_sequence_ids(args.dataset_root, split=args.split))
    print(
        f"[1/4][prepare] split={args.split} sequences={sequence_ids} views={args.view_ids} "
        f"tracker_env={versions}",
        flush=True,
    )

    predictions: list[dict[str, object]] = []
    messages: list[dict[str, object]] = []
    metrics: list[dict[str, object]] = []
    dataset_audit: list[dict[str, object]] = []
    cross_view_audit: list[dict[str, object]] = []
    official_mapping_audit: list[dict[str, object]] = []
    for sequence_id in sequence_ids:
        views = {
            view_id: load_mdmt_view(
                args.dataset_root,
                split=args.split,
                sequence_id=sequence_id,
                view_id=view_id,
            )
            for view_id in args.view_ids
        }
        if 1 in views and 2 in views:
            cross_view_audit.append(audit_same_numeric_ids_across_views(views[1], views[2]))
        for view_id in args.view_ids:
            result = _run_view(
                dataset_root=args.dataset_root,
                split=args.split,
                sequence_id=sequence_id,
                view_id=view_id,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                labels=args.labels,
                include_occluded=not args.exclude_occluded,
                fps=args.fps,
                use_gmc=args.use_gmc,
                track_buffer=args.track_buffer,
                match_thresh=args.match_thresh,
                progress_every=args.progress_every,
            )
            prediction_rows, message_rows, metric_row, audit_row = result
            if args.official_mda_gt_root is not None:
                if args.split != "test":
                    raise ValueError("official MDA GT is published for the test split only")
                gt_path = args.official_mda_gt_root / f"{sequence_id}-{view_id}.txt"
                official_rows = load_official_mda_gt(
                    gt_path,
                    sequence_id=sequence_id,
                    view_id=view_id,
                )
                identity_map, mapping_audit = reconcile_xml_to_official_mda(
                    views[view_id], official_rows
                )
                official_mapping_audit.append(mapping_audit)
                for row in prediction_rows:
                    row["official_global_identity"] = identity_map.get(
                        int(row["evaluation_local_identity"]), ""
                    )
            predictions.extend(prediction_rows)
            messages.extend(message_rows)
            metrics.append(metric_row)
            dataset_audit.append(audit_row)

    _write_csv(args.output_dir / "mdmt_local_predictions.csv", predictions)
    _write_csv(args.output_dir / "mdmt_local_messages.csv", messages)
    _write_csv(args.output_dir / "mdmt_local_metrics.csv", metrics)
    _write_csv(args.output_dir / "mdmt_dataset_audit.csv", dataset_audit)
    _write_csv(args.output_dir / "mdmt_cross_view_id_audit.csv", cross_view_audit)
    _write_csv(args.output_dir / "mdmt_official_mapping_audit.csv", official_mapping_audit)

    measurement_valid = (
        not message_schema_uses_person_id()
        and all(int(row["runtime_world_xy_present"]) == 0 for row in dataset_audit)
    )
    mapping_verified = bool(official_mapping_audit) and all(
        float(row["official_gt_match_fraction"]) == 1.0
        and int(row["local_id_mapping_conflicts"]) == 0
        for row in official_mapping_audit
    )
    decision = "adapter_ready_mapping_blocked" if measurement_valid and not mapping_verified else (
        "adapter_ready_official_mapping_available" if measurement_valid else "measurement_invalid"
    )
    decision_text = f"""# MDMT Dataset-Neutral Adapter Decision

- decision: `{decision}`
- measurement_valid: `{int(measurement_valid)}`
- official_cross_view_mapping_verified: `{int(mapping_verified)}`
- runtime packet contains GT identity: `{int(message_schema_uses_person_id())}`
- runtime image tracker receives world XY: `{int(any(int(row['runtime_world_xy_present']) for row in dataset_audit))}`

The adapter can produce per-view local tracklets and fixed-size incremental packets.
Official global identities are exposed only in offline prediction rows when the
test-split MDA GT is supplied; they never enter runtime detection keys or packets.
"""
    (args.output_dir / "mdmt_adapter_decision.md").write_text(decision_text, encoding="utf-8")
    print(f"[4/4][finalize] decision={decision} outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
