#!/usr/bin/env python3
"""Audit OC-SORT motion recovery and image/world state representations on MATRIX."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from phase3_matrix_mobile_camera_local_tracklet_readiness import (  # noqa: E402
    _load_or_compute_gmc,
    atomic_json,
    read_rows,
    summarize_quality,
    write_rows,
)
from tracking.matrix_gt import MatrixObservation, load_matrix_observations  # noqa: E402
from tracking.matrix_identity_cue import observation_sensor_key  # noqa: E402
from tracking.matrix_local_tracklet import LocalDetection, message_runtime_dict  # noqa: E402
from tracking.matrix_mature_local_tracklet import (  # noqa: E402
    MatureLocalTrackletTracker,
    validate_mature_tracker_environment,
)
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
)
from tracking.matrix_ocsort_local_tracklet import (  # noqa: E402
    OCSortLocalTrackletTracker,
    WorldXYOracleLocalTracker,
    compute_motion_representation_diagnostics,
)
from tracking.matrix_real_appearance import load_embedding_cache, los_visible_observations  # noqa: E402


EXPERIMENT_ID = "exp_20260802_003_matrix_ocsort_motion_representation_audit"
SCHEMA_VERSION = 1
DEPLOYABLE_FAMILIES = {"botsort", "ocsort", "deepocsort"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("calibrate", "evaluate"), required=True)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, required=True)
    parser.add_argument("--eval-start", type=int)
    parser.add_argument("--frame-end", type=int, required=True)
    parser.add_argument("--drone-ids", nargs="+", type=int, default=list(range(8)))
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--delta-ts", nargs="+", type=int, default=(1, 3))
    parser.add_argument("--inertias", nargs="+", type=float, default=(0.1, 0.2))
    parser.add_argument("--track-buffer", type=int, default=5)
    parser.add_argument("--match-thresh", type=float, default=0.8)
    parser.add_argument("--proximity-thresh", type=float, default=0.1)
    parser.add_argument("--osnet-threshold", type=float, default=0.785027)
    parser.add_argument("--appearance-ema", type=float, default=0.95)
    parser.add_argument("--gmc-method", default="sparseOptFlow")
    parser.add_argument("--gmc-downscale", type=int, default=2)
    parser.add_argument("--selected-config", type=Path)
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        default=Path(
            "outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_cache/"
            "osnet_x0_25_msmt17.npz"
        ),
    )
    parser.add_argument(
        "--botsort-reference-dir",
        type=Path,
        default=Path("outputs/20260802_matrix_botsort_candidate_gate_repair_pilot"),
    )
    parser.add_argument(
        "--gmc-reference-dir",
        type=Path,
        default=Path("outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_pilot/checkpoints/gmc"),
    )
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def duration(seconds: float) -> str:
    value = max(int(seconds), 0)
    return f"{value // 3600:02d}:{value % 3600 // 60:02d}:{value % 60:02d}"


def condition_name(condition: Mapping[str, object], view_id: int) -> str:
    return f"D{view_id + 1}__{condition['pipeline']}"


def condition_paths(root: Path, name: str) -> dict[str, Path]:
    return {
        "predictions": root / f"{name}__predictions.csv",
        "messages": root / f"{name}__messages.csv",
        "diagnostics": root / f"{name}__diagnostics.csv",
        "audit": root / f"{name}__audit.csv",
        "done": root / f"{name}.json",
    }


def condition_token(args: argparse.Namespace, condition: Mapping[str, object]) -> str:
    payload = {
        "schema": SCHEMA_VERSION,
        "condition": dict(condition),
        "frame_start": args.frame_start,
        "frame_end": args.frame_end,
        "embedding_cache": str(args.embedding_cache.resolve()),
        "osnet_threshold": args.osnet_threshold,
        "appearance_ema": args.appearance_ema,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def motion_conditions(args: argparse.Namespace) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "pipeline": "botsort_gmc_osnet_hard_p01",
            "family": "botsort",
            "tracker_type": "botsort",
            "delta_t": 0,
            "inertia": 0.0,
            "use_gmc": True,
            "use_appearance": True,
            "appearance_mode": "hard_veto",
            "oracle": False,
        }
    ]
    for delta_t in args.delta_ts:
        for inertia in args.inertias:
            suffix = f"dt{int(delta_t)}_i{float(inertia):.2f}".replace(".", "p")
            rows.extend(
                [
                    {
                        "pipeline": f"ocsort_no_gmc_noapp_{suffix}",
                        "family": "ocsort",
                        "tracker_type": "ocsort",
                        "delta_t": int(delta_t),
                        "inertia": float(inertia),
                        "use_gmc": False,
                        "use_appearance": False,
                        "appearance_mode": "none",
                        "oracle": False,
                    },
                    {
                        "pipeline": f"deepocsort_gmc_noapp_{suffix}",
                        "family": "deepocsort",
                        "tracker_type": "deepocsort",
                        "delta_t": int(delta_t),
                        "inertia": float(inertia),
                        "use_gmc": True,
                        "use_appearance": False,
                        "appearance_mode": "none",
                        "oracle": False,
                    },
                ]
            )
    rows.append(
        {
            "pipeline": "oracle_world_xy_cv",
            "family": "world_oracle",
            "tracker_type": "world_oracle",
            "delta_t": 0,
            "inertia": 0.0,
            "use_gmc": False,
            "use_appearance": False,
            "appearance_mode": "none",
            "oracle": True,
        }
    )
    return rows


def appearance_conditions(args: argparse.Namespace, selected_motion: Mapping[str, object]) -> list[dict[str, object]]:
    common = {
        "family": "deepocsort",
        "tracker_type": "deepocsort",
        "delta_t": int(selected_motion["delta_t"]),
        "inertia": float(selected_motion["inertia"]),
        "use_gmc": True,
        "use_appearance": True,
        "oracle": False,
    }
    return [
        {
            **common,
            "pipeline": "deepocsort_gmc_osnet_soft_p01",
            "appearance_mode": "soft",
        },
        {
            **common,
            "pipeline": "deepocsort_gmc_osnet_hard_p01",
            "appearance_mode": "hard_veto",
        },
    ]


def _tracker(args: argparse.Namespace, condition: Mapping[str, object], view_id: int):
    family = str(condition["family"])
    if family == "botsort":
        return MatureLocalTrackletTracker(
            view_id=view_id,
            track_buffer=args.track_buffer,
            match_thresh=args.match_thresh,
            use_appearance=True,
            similarity_threshold=args.osnet_threshold,
            proximity_threshold=args.proximity_thresh,
            appearance_mode="hard_veto",
        )
    if family in {"ocsort", "deepocsort"}:
        return OCSortLocalTrackletTracker(
            view_id=view_id,
            tracker_type=str(condition["tracker_type"]),
            delta_t=int(condition["delta_t"]),
            inertia=float(condition["inertia"]),
            track_buffer=args.track_buffer,
            match_thresh=args.match_thresh,
            use_gmc=bool(condition["use_gmc"]),
            use_appearance=bool(condition["use_appearance"]),
            appearance_mode=str(condition["appearance_mode"]),
            proximity_threshold=args.proximity_thresh,
            similarity_threshold=args.osnet_threshold,
            appearance_ema=args.appearance_ema,
        )
    if family == "world_oracle":
        return WorldXYOracleLocalTracker(view_id=view_id, distance_threshold=1.0, max_age=args.track_buffer)
    raise ValueError(f"unknown tracker family: {family}")


def _restore_tracker(snapshot, family: str):
    if family == "botsort":
        return MatureLocalTrackletTracker.from_snapshot(snapshot)
    if family in {"ocsort", "deepocsort"}:
        return OCSortLocalTrackletTracker.from_snapshot(snapshot)
    return WorldXYOracleLocalTracker.from_snapshot(snapshot)


def image_shape(matrix_root: Path, view_id: int, frame_id: int) -> tuple[int, int]:
    path = matrix_root / "image_subsets" / f"D{view_id + 1}" / f"{frame_id:04d}.png"
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(path)
    return int(image.shape[0]), int(image.shape[1])


def run_condition(
    *,
    args: argparse.Namespace,
    condition: Mapping[str, object],
    index: int,
    total: int,
    view_id: int,
    observations: Sequence[MatrixObservation],
    embeddings: Mapping[tuple, np.ndarray],
    warps: Mapping[int, np.ndarray],
) -> dict[str, list[dict[str, object]]]:
    by_frame: dict[int, list[MatrixObservation]] = defaultdict(list)
    eval_identity: dict[tuple, int] = {}
    for observation in observations:
        by_frame[int(observation.frame_id)].append(observation)
        eval_identity[observation_sensor_key(observation)] = int(observation.person_id)
    tracker = _tracker(args, condition, view_id)
    shape = image_shape(args.matrix_root, view_id, args.frame_start)
    outputs: dict[str, list[dict[str, object]]] = {
        "predictions": [],
        "messages": [],
        "diagnostics": [],
        "audit": [],
    }
    started = time.perf_counter()
    negative_id = -1
    determinism_mismatch = 0
    world_shuffle_mismatch = 0
    family = str(condition["family"])
    for frame_id in range(args.frame_start, args.frame_end + 1):
        frame_observations = sorted(by_frame.get(frame_id, []), key=observation_sensor_key)
        detections = [
            LocalDetection(
                sensor_key=observation_sensor_key(row),
                frame_id=frame_id,
                drone_id=view_id,
                bbox_xyxy=row.bbox_xyxy,
                world_xy=tuple(float(value) for value in row.world_xy),
                embedding=embeddings.get(observation_sensor_key(row)),
            )
            for row in frame_observations
        ]
        probe = frame_id < args.frame_start + 3
        snapshot = tracker.snapshot() if probe else None
        kwargs = {
            "frame_shape": shape,
            "warp": warps.get(frame_id) if bool(condition["use_gmc"]) else None,
        }
        step = tracker.step(frame_id, detections, **kwargs)
        if probe and snapshot is not None:
            repeated = _restore_tracker(snapshot, family).step(frame_id, detections, **kwargs)
            signature = [(row.sensor_key, row.local_track_id) for row in step.assignments]
            repeated_signature = [(row.sensor_key, row.local_track_id) for row in repeated.assignments]
            determinism_mismatch += int(signature != repeated_signature)
            if family in DEPLOYABLE_FAMILIES:
                shuffled = [
                    replace(row, world_xy=(row.world_xy[0] + 1000.0, row.world_xy[1] - 1000.0))
                    for row in detections
                ]
                shuffled_step = _restore_tracker(snapshot, family).step(frame_id, shuffled, **kwargs)
                shuffled_signature = [(row.sensor_key, row.local_track_id) for row in shuffled_step.assignments]
                world_shuffle_mismatch += int(signature != shuffled_signature)
        assignment_by_key = {row.sensor_key: row for row in step.assignments}
        for detection in detections:
            assignment = assignment_by_key.get(detection.sensor_key)
            assigned = assignment is not None
            local_id = int(assignment.local_track_id) if assigned else negative_id
            if not assigned:
                negative_id -= 1
            outputs["predictions"].append(
                {
                    "frame_id": frame_id,
                    "drone_id": view_id,
                    "pipeline": condition["pipeline"],
                    "family": family,
                    "track_buffer": args.track_buffer,
                    "match_thresh": args.match_thresh,
                    "delta_t": condition["delta_t"],
                    "inertia": condition["inertia"],
                    "use_gmc": int(bool(condition["use_gmc"])),
                    "use_appearance": int(bool(condition["use_appearance"])),
                    "appearance_mode": condition["appearance_mode"],
                    "oracle": int(bool(condition["oracle"])),
                    "sensor_key": repr(detection.sensor_key),
                    "person_id_eval_only": eval_identity[detection.sensor_key],
                    "local_track_id": local_id,
                    "assigned": int(assigned),
                    "confirmed": int(bool(getattr(assignment, "confirmed", assigned))) if assigned else 0,
                }
            )
        for message in step.messages:
            row = message_runtime_dict(message)
            row.update({"pipeline": condition["pipeline"], "family": family})
            outputs["messages"].append(row)
        for diagnostic in step.diagnostics:
            row = dict(diagnostic)
            row.update({"pipeline": condition["pipeline"], "family": family})
            outputs["diagnostics"].append(row)
        if (
            frame_id == args.frame_start
            or frame_id == args.frame_end
            or (frame_id - args.frame_start + 1) % max(args.progress_every, 1) == 0
        ):
            done = frame_id - args.frame_start + 1
            count = args.frame_end - args.frame_start + 1
            elapsed = time.perf_counter() - started
            eta = elapsed / max(done, 1) * max(count - done, 0)
            print(
                f"[4/6][track] condition={index}/{total} pipeline={condition['pipeline']} "
                f"D{view_id + 1} frame={frame_id}/{args.frame_end} "
                f"elapsed={duration(elapsed)} eta={duration(eta)}",
                flush=True,
            )
    outputs["audit"].append(
        {
            "pipeline": condition["pipeline"],
            "family": family,
            "drone_id": view_id,
            "runtime_person_id_reads": 0,
            "runtime_occlusion_label_reads": 0,
            "runtime_world_xy_association_reads": int(family == "world_oracle"),
            "future_reads": 0,
            "identity_schema_mismatch": 0,
            "world_xy_shuffle_mismatch": world_shuffle_mismatch if family in DEPLOYABLE_FAMILIES else "",
            "determinism_mismatch": determinism_mismatch,
        }
    )
    return outputs


def run_conditions(
    *,
    args: argparse.Namespace,
    conditions: Sequence[Mapping[str, object]],
    by_view: Mapping[int, Sequence[MatrixObservation]],
    embeddings: Mapping[tuple, np.ndarray],
    warps: Mapping[int, Mapping[int, np.ndarray]],
    checkpoint_dir: Path,
    start_index: int,
    total: int,
) -> tuple[dict[str, list[dict[str, object]]], int]:
    combined = {"predictions": [], "messages": [], "diagnostics": [], "audit": []}
    index = start_index
    for condition in conditions:
        for view_id in args.drone_ids:
            index += 1
            name = condition_name(condition, view_id)
            paths = condition_paths(checkpoint_dir, name)
            token = condition_token(args, condition)
            if args.resume and paths["done"].is_file():
                payload = json.loads(paths["done"].read_text(encoding="utf-8"))
                if payload.get("token") == token:
                    for key in combined:
                        combined[key].extend(read_rows(paths[key]))
                    print(f"[4/6][track] condition={index}/{total} resume: skip {name}", flush=True)
                    continue
            output = run_condition(
                args=args,
                condition=condition,
                index=index,
                total=total,
                view_id=view_id,
                observations=by_view.get(view_id, []),
                embeddings=embeddings,
                warps=warps[view_id],
            )
            for key, rows in output.items():
                write_rows(paths[key], rows)
                combined[key].extend(rows)
            atomic_json(paths["done"], {"complete": True, "token": token, "name": name})
            print(f"[4/6][track] condition={index}/{total} complete {name}", flush=True)
    return combined, index


def aggregate(
    args: argparse.Namespace,
    prediction_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    eval_start = args.frame_start if args.eval_start is None else args.eval_start
    visibilities = build_frame_visibilities(
        args.matrix_root,
        frame_start=eval_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        support_drone_ids=tuple(view for view in args.drone_ids if view != args.primary_drone_id),
    )
    episodes = build_occlusion_episodes(visibilities, min_episode_length=1)
    occlusion_keys = build_occlusion_event_keys(episodes, min_episode_length=1)
    return summarize_quality(
        prediction_rows,
        eval_start=eval_start,
        occlusion_keys=occlusion_keys,
        primary_drone_id=args.primary_drone_id,
    )


def select_motion_config(
    conditions: Sequence[Mapping[str, object]],
    pipeline_rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object], dict[str, object]]:
    condition_by_pipeline = {str(row["pipeline"]): dict(row) for row in conditions}
    selections: list[dict[str, object]] = []
    winners: dict[str, dict[str, object]] = {}
    for family in ("ocsort", "deepocsort"):
        candidates = [
            row
            for row in pipeline_rows
            if condition_by_pipeline.get(str(row["pipeline"]), {}).get("family") == family
            and not bool(condition_by_pipeline[str(row["pipeline"])]["use_appearance"])
        ]
        ranked = sorted(
            candidates,
            key=lambda row: (
                -float(row["macro_local_idf1"]),
                -float(row["weighted_purity"]),
                int(row["fragmentation_count"]),
                int(condition_by_pipeline[str(row["pipeline"])]["delta_t"]),
                float(condition_by_pipeline[str(row["pipeline"])]["inertia"]),
            ),
        )
        if not ranked:
            raise RuntimeError(f"no motion configuration for {family}")
        winners[family] = condition_by_pipeline[str(ranked[0]["pipeline"])]
        for rank, row in enumerate(ranked, start=1):
            selections.append({**dict(row), "family": family, "selection_rank": rank, "selected": int(rank == 1)})
    return selections, winners["ocsort"], winners["deepocsort"]


def summary_value(rows: Sequence[Mapping[str, object]], metric: str, field: str = "mean") -> float:
    row = next(item for item in rows if str(item["metric"]) == metric)
    return float(row[field])


def reference_mismatch(args: argparse.Namespace, pipeline_rows: Sequence[Mapping[str, object]]) -> float:
    if args.mode != "calibrate":
        return 0.0
    reference_path = args.botsort_reference_dir / "candidate_gate_pipeline_metrics.csv"
    reference = next(
        row
        for row in read_rows(reference_path)
        if row["pipeline"] == "botsort_gmc_osnet_hard_veto_p0p10"
    )
    current = next(row for row in pipeline_rows if row["pipeline"] == "botsort_gmc_osnet_hard_p01")
    fields = (
        "macro_local_idf1",
        "weighted_purity",
        "minimum_per_view_local_idf1",
        "occlusion_support_coverage",
        "fragmentation_count",
        "local_idsw",
    )
    return max(abs(float(current[field]) - float(reference[field])) for field in fields)


def full_readiness(row: Mapping[str, object]) -> bool:
    return (
        float(row["macro_local_idf1"]) >= 0.80
        and float(row["weighted_purity"]) >= 0.95
        and float(row["minimum_per_view_local_idf1"]) >= 0.70
        and float(row["occlusion_support_coverage"]) >= 0.90
    )


def decide(
    pipeline_rows: Sequence[Mapping[str, object]],
    conditions: Sequence[Mapping[str, object]],
    motion_summary: Sequence[Mapping[str, object]],
    measurement_valid: bool,
) -> tuple[str, list[str], dict[str, float]]:
    condition_by_pipeline = {str(row["pipeline"]): row for row in conditions}
    image_rows = [
        row
        for row in pipeline_rows
        if str(condition_by_pipeline[str(row["pipeline"])]["family"]) in DEPLOYABLE_FAMILIES
    ]
    passing = [str(row["pipeline"]) for row in image_rows if full_readiness(row)]
    baseline = next(row for row in image_rows if row["pipeline"] == "botsort_gmc_osnet_hard_p01")
    best_oc = max(
        (row for row in image_rows if str(row["pipeline"]).startswith(("ocsort_", "deepocsort_"))),
        key=lambda row: float(row["macro_local_idf1"]),
    )
    oracle = next(row for row in pipeline_rows if row["pipeline"] == "oracle_world_xy_cv")
    world_hold_p90 = summary_value(motion_summary, "world_hold_error_m", "p90")
    world_cv_p90 = summary_value(motion_summary, "world_cv_error_m", "p90")
    gmc_hold_recall = summary_value(motion_summary, "gmc_bbox_hold_candidate_recall_at_0.1")
    gmc_cv_recall = summary_value(motion_summary, "gmc_bbox_cv_candidate_recall_at_0.1")
    values = {
        "world_hold_p90": world_hold_p90,
        "world_cv_p90": world_cv_p90,
        "world_cv_reduction": (world_hold_p90 - world_cv_p90) / max(world_hold_p90, 1.0e-12),
        "gmc_hold_recall_at_0.1": gmc_hold_recall,
        "gmc_cv_recall_at_0.1": gmc_cv_recall,
        "gmc_cv_recall_gain": gmc_cv_recall - gmc_hold_recall,
        "best_image_idf1": max(float(row["macro_local_idf1"]) for row in image_rows),
        "oracle_world_idf1": float(oracle["macro_local_idf1"]),
        "best_oc_idf1_gain": float(best_oc["macro_local_idf1"]) - float(baseline["macro_local_idf1"]),
    }
    if not measurement_valid:
        return "measurement_invalid", passing, values
    if passing:
        return "mobile_local_tracker_ready", passing, values
    partial = (
        values["best_oc_idf1_gain"] >= 0.05
        and float(best_oc["weighted_purity"]) >= 0.90
        and int(best_oc["fragmentation_count"]) <= 0.90 * int(baseline["fragmentation_count"])
        and float(best_oc["occlusion_support_coverage"]) >= 0.90
    )
    if partial:
        return "ocsort_partial_but_not_ready", passing, values
    if values["oracle_world_idf1"] >= 0.80 and values["gmc_cv_recall_at_0.1"] >= 0.80 and values["best_image_idf1"] < 0.30:
        return "association_lifecycle_bottleneck", passing, values
    if values["oracle_world_idf1"] >= 0.80 and values["gmc_cv_recall_at_0.1"] < 0.80:
        return "image_representation_bottleneck", passing, values
    return "world_motion_or_annotation_bottleneck", passing, values


def write_decision(
    path: Path,
    *,
    mode: str,
    decision: str,
    passing: Sequence[str],
    pipeline_rows: Sequence[Mapping[str, object]],
    measurement_rows: Sequence[Mapping[str, object]],
    diagnostic_values: Mapping[str, float],
) -> None:
    lines = [
        "# OC-SORT Motion And Representation Decision",
        "",
        f"- mode: `{mode}`",
        f"- decision: `{decision}`",
        f"- formal_allowed: `{int(decision == 'mobile_local_tracker_ready')}`",
        f"- passing image pipelines: `{', '.join(passing) if passing else 'none'}`",
        "",
        "## Measurement Gate",
        "",
    ]
    lines.extend(f"- {row['gate']}: `{row['passed']}` ({row['value']})" for row in measurement_rows)
    lines.extend(["", "## Motion Diagnostics", ""])
    lines.extend(f"- {key}: `{value:.6f}`" for key, value in diagnostic_values.items())
    lines.extend(
        [
            "",
            "## Pipeline Metrics",
            "",
            "| Pipeline | IDF1 | Purity | Min-view IDF1 | Coverage | Fragmentation |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in sorted(pipeline_rows, key=lambda item: -float(item["macro_local_idf1"])):
        lines.append(
            f"| {row['pipeline']} | {float(row['macro_local_idf1']):.6f} | "
            f"{float(row['weighted_purity']):.6f} | {float(row['minimum_per_view_local_idf1']):.6f} | "
            f"{float(row['occlusion_support_coverage']):.6f} | {row['fragmentation_count']} |"
        )
    lines.extend(
        [
            "",
            "The clean world-XY pipeline is an oracle diagnostic and cannot by itself authorize Formal.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_reference_gmc(args: argparse.Namespace, view_id: int) -> tuple[dict[int, np.ndarray], list[dict[str, str]]] | None:
    stem = f"D{view_id + 1}_{args.frame_start}_{args.frame_end}"
    npz_path = args.gmc_reference_dir / f"{stem}.npz"
    csv_path = args.gmc_reference_dir / f"{stem}.csv"
    if not npz_path.is_file() or not csv_path.is_file():
        return None
    with np.load(npz_path) as payload:
        warps = {int(key[1:]): np.asarray(payload[key], dtype=np.float64) for key in payload.files}
    print(f"[2/6][gmc] D{view_id + 1} reused={npz_path}", flush=True)
    return warps, read_rows(csv_path)


def main() -> None:
    args = parse_args()
    if args.frame_end < args.frame_start:
        raise ValueError("frame-end must be >= frame-start")
    if args.mode == "calibrate" and args.eval_start is not None:
        raise ValueError("calibrate mode does not use eval-start")
    if args.mode == "evaluate" and (args.eval_start is None or args.selected_config is None):
        raise ValueError("evaluate mode requires eval-start and selected-config")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints" / "conditions"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    versions = validate_mature_tracker_environment()
    print(
        f"[1/6][prepare] experiment={EXPERIMENT_ID} mode={args.mode} "
        f"ultralytics={versions['ultralytics']} lap={versions['lap']}",
        flush=True,
    )
    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    visible, _ = los_visible_observations(args.matrix_root, observations)
    visible = [row for row in visible if int(row.drone_id) in set(args.drone_ids)]
    embeddings = load_embedding_cache(args.embedding_cache)
    embedding_coverage = sum(observation_sensor_key(row) in embeddings.embeddings for row in visible) / max(len(visible), 1)
    if embedding_coverage < 0.95:
        raise RuntimeError(f"embedding coverage {embedding_coverage:.2%} is below 95%")
    print(f"[1/6][prepare] visible={len(visible)} embedding_coverage={embedding_coverage:.6f}", flush=True)

    by_view: dict[int, list[MatrixObservation]] = defaultdict(list)
    boxes_by_view: dict[int, dict[int, list[tuple[int, int, int, int]]]] = defaultdict(lambda: defaultdict(list))
    for row in visible:
        by_view[int(row.drone_id)].append(row)
        boxes_by_view[int(row.drone_id)][int(row.frame_id)].append(row.bbox_xyxy)
    all_warps: dict[int, dict[int, np.ndarray]] = {}
    gmc_audit: list[dict[str, object]] = []
    for view_id in args.drone_ids:
        loaded = load_reference_gmc(args, view_id)
        if loaded is None:
            warps, audit = _load_or_compute_gmc(args=args, view_id=view_id, boxes_by_frame=boxes_by_view[view_id])
        else:
            warps, audit = loaded
        all_warps[view_id] = warps
        gmc_audit.extend(audit)

    print("[3/6][motion] computing offline world/image motion diagnostics", flush=True)
    transition_rows, motion_summary = compute_motion_representation_diagnostics(visible, all_warps)
    write_rows(args.output_dir / "motion_representation_transition_metrics.csv", transition_rows)
    write_rows(args.output_dir / "motion_representation_summary.csv", motion_summary)

    if args.mode == "evaluate":
        selected_payload = json.loads(args.selected_config.read_text(encoding="utf-8"))
        if int(selected_payload.get("formal_allowed", 0)) != 1:
            raise RuntimeError("Pilot did not authorize Formal")
        conditions = [dict(row) for row in selected_payload["formal_conditions"]]
        motion_selection: list[dict[str, object]] = []
        first_stage = conditions
        second_stage: list[dict[str, object]] = []
    else:
        first_stage = motion_conditions(args)
        conditions = list(first_stage)
        second_stage = []
        motion_selection = []

    initial_total = (len(first_stage) + (2 if args.mode == "calibrate" else 0)) * len(args.drone_ids)
    first_output, completed = run_conditions(
        args=args,
        conditions=first_stage,
        by_view=by_view,
        embeddings=embeddings.embeddings,
        warps=all_warps,
        checkpoint_dir=checkpoint_dir,
        start_index=0,
        total=initial_total,
    )
    if args.mode == "calibrate":
        _, first_pipeline_rows, _, _ = aggregate(args, first_output["predictions"])
        motion_selection, selected_ocsort, selected_deep = select_motion_config(first_stage, first_pipeline_rows)
        second_stage = appearance_conditions(args, selected_deep)
        conditions.extend(second_stage)
        second_output, completed = run_conditions(
            args=args,
            conditions=second_stage,
            by_view=by_view,
            embeddings=embeddings.embeddings,
            warps=all_warps,
            checkpoint_dir=checkpoint_dir,
            start_index=completed,
            total=initial_total,
        )
        for key in first_output:
            first_output[key].extend(second_output[key])
    print("[5/6][aggregate] computing local quality and decision gates", flush=True)
    quality, pipeline_rows, merge_rows, coverage_rows = aggregate(args, first_output["predictions"])
    condition_by_pipeline = {str(row["pipeline"]): row for row in conditions}
    for row in pipeline_rows:
        config = condition_by_pipeline[str(row["pipeline"])]
        row.update(
            {
                "family": config["family"],
                "delta_t": config["delta_t"],
                "inertia": config["inertia"],
                "use_gmc": int(bool(config["use_gmc"])),
                "use_appearance": int(bool(config["use_appearance"])),
                "appearance_mode": config["appearance_mode"],
                "oracle": int(bool(config["oracle"])),
            }
        )
    audit = first_output["audit"]
    deployable_audit = [row for row in audit if str(row["family"]) in DEPLOYABLE_FAMILIES]
    reference_error = reference_mismatch(args, pipeline_rows)
    measurement_rows = [
        {"gate": "botsort_reference_max_abs_error", "value": reference_error, "passed": int(reference_error < 1.0e-6)},
        {"gate": "embedding_coverage", "value": embedding_coverage, "passed": int(embedding_coverage >= 0.95)},
        {"gate": "runtime_person_id_reads", "value": sum(int(row["runtime_person_id_reads"]) for row in deployable_audit), "passed": 0},
        {"gate": "runtime_occlusion_label_reads", "value": sum(int(row["runtime_occlusion_label_reads"]) for row in deployable_audit), "passed": 0},
        {"gate": "runtime_world_xy_association_reads", "value": sum(int(row["runtime_world_xy_association_reads"]) for row in deployable_audit), "passed": 0},
        {"gate": "future_reads", "value": sum(int(row["future_reads"]) for row in deployable_audit), "passed": 0},
        {"gate": "identity_schema_mismatch", "value": sum(int(row["identity_schema_mismatch"]) for row in deployable_audit), "passed": 0},
        {"gate": "world_xy_shuffle_mismatch", "value": sum(int(row["world_xy_shuffle_mismatch"]) for row in deployable_audit), "passed": 0},
        {"gate": "determinism_mismatch", "value": sum(int(row["determinism_mismatch"]) for row in audit), "passed": 0},
    ]
    for row in measurement_rows[2:]:
        row["passed"] = int(float(row["value"]) == 0.0)
    measurement_valid = all(int(row["passed"]) == 1 for row in measurement_rows)
    decision, passing, diagnostic_values = decide(pipeline_rows, conditions, motion_summary, measurement_valid)
    formal_allowed = int(decision == "mobile_local_tracker_ready")
    if args.mode == "calibrate":
        selected_pipelines = {
            "botsort_gmc_osnet_hard_p01",
            str(selected_ocsort["pipeline"]),
            str(selected_deep["pipeline"]),
            "deepocsort_gmc_osnet_soft_p01",
            "deepocsort_gmc_osnet_hard_p01",
            "oracle_world_xy_cv",
        }
        payload = {
            "experiment_id": EXPERIMENT_ID,
            "schema_version": SCHEMA_VERSION,
            "formal_allowed": formal_allowed,
            "pilot_decision": decision,
            "formal_conditions": [row for row in conditions if str(row["pipeline"]) in selected_pipelines],
        }
        atomic_json(args.output_dir / "selected_config.json", payload)

    write_rows(args.output_dir / "ocsort_config_selection.csv", motion_selection)
    write_rows(args.output_dir / "ocsort_pipeline_metrics.csv", pipeline_rows)
    write_rows(args.output_dir / "ocsort_quality_by_view.csv", quality)
    write_rows(args.output_dir / "ocsort_merge_fragmentation.csv", merge_rows)
    write_rows(args.output_dir / "ocsort_occlusion_coverage.csv", coverage_rows)
    write_rows(args.output_dir / "ocsort_association_diagnostics.csv", first_output["diagnostics"])
    write_rows(args.output_dir / "ocsort_message_manifest.csv", first_output["messages"])
    write_rows(args.output_dir / "ocsort_measurement_gate.csv", measurement_rows)
    write_rows(args.output_dir / "ocsort_gmc_audit.csv", gmc_audit)
    write_decision(
        args.output_dir / "ocsort_decision.md",
        mode=args.mode,
        decision=decision,
        passing=passing,
        pipeline_rows=pipeline_rows,
        measurement_rows=measurement_rows,
        diagnostic_values=diagnostic_values,
    )
    print(
        f"[6/6][finalize] decision={decision} formal_allowed={formal_allowed} outputs={args.output_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
