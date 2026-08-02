#!/usr/bin/env python3
"""Validate history-1 compatibility and causal incremental local tracklets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from phase2_matrix_fixed_lag_temporal_spatial_robustness import apply_support_pose_noise  # noqa: E402
from phase2_matrix_identity_position_update_separation import threshold_by_fold  # noqa: E402
from tracking.delay_injection import fixed_delay_frames, frames_to_ms  # noqa: E402
from tracking.matrix_gt import (  # noqa: E402
    MatrixObservation,
    apply_delay_profile,
    load_matrix_observations,
    make_delay_profile,
)
from tracking.matrix_identity_cue import observation_sensor_key  # noqa: E402
from tracking.matrix_local_tracklet import (  # noqa: E402
    IncrementalTrackletUpdate,
    LocalDetection,
    LocalTrackletTracker,
    history1_update_from_observation,
    message_runtime_dict,
    message_schema_uses_person_id,
    observation_from_history1_update,
)
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    filter_to_occlusion_support,
)
from tracking.matrix_real_appearance import load_embedding_cache, los_visible_observations  # noqa: E402
from tracking.matrix_reanchoring import (  # noqa: E402
    SupportUpdatePolicy,
    matrix_run_from_reanchoring,
    run_fixed_lag_multicue_update,
)
from tracking.mot_metrics import Prediction, compute_identity_metrics  # noqa: E402


EXPERIMENT_ID = "exp_20260801_002_matrix_incremental_tracklet_update_foundation"
SCHEMA_VERSION = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=999)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--drone-ids", nargs="*", type=int, default=list(range(8)))
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--local-trackers", nargs="*", default=["bbox_sort", "bbox_osnet"])
    parser.add_argument("--pose-noise-m", type=float, default=0.25)
    parser.add_argument("--min-hits", type=int, default=1)
    parser.add_argument("--max-age", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--real-embedding-dir",
        type=Path,
        default=Path("outputs/20260731_matrix_real_embedding_quality_transfer"),
    )
    parser.add_argument(
        "--legacy-reference-dir",
        type=Path,
        default=Path("outputs/20260801_matrix_identity_position_update_separation_audit"),
    )
    parser.add_argument(
        "--tracklet-embedding-cache",
        type=Path,
        help="Complete all-view OSNet cache prepared for local tracklets. Defaults to output-dir/embedding_cache.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260801_matrix_incremental_tracklet_update_foundation"),
    )
    return parser.parse_args()


def write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def duration(seconds: float) -> str:
    value = max(0, int(seconds))
    return f"{value // 3600:02d}:{(value % 3600) // 60:02d}:{value % 60:02d}"


def stable_identity_fold(person_id: int, *, seed: int) -> int:
    digest = hashlib.sha256(f"{int(seed)}:person:{int(person_id)}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "little") % 2


def _mean(values: Iterable[float]) -> float:
    rows = [float(value) for value in values if math.isfinite(float(value))]
    return float("nan") if not rows else float(sum(rows) / len(rows))


def _bbox_center_gate(first: MatrixObservation, second: MatrixObservation) -> bool:
    first_box = np.asarray(first.bbox_xyxy, dtype=np.float64)
    second_box = np.asarray(second.bbox_xyxy, dtype=np.float64)
    first_center = np.asarray([(first_box[0] + first_box[2]) / 2, (first_box[1] + first_box[3]) / 2])
    second_center = np.asarray([(second_box[0] + second_box[2]) / 2, (second_box[1] + second_box[3]) / 2])
    scale = max(first_box[3] - first_box[1], 1.0)
    return float(np.linalg.norm(first_center - second_center) / scale) <= 2.5


def calibrate_local_thresholds(
    observations: Sequence[MatrixObservation],
    embeddings: Mapping[tuple, np.ndarray],
    *,
    seed: int,
) -> tuple[dict[int, float], list[dict[str, object]]]:
    """Calibrate with GT labels offline; runtime trackers only receive the threshold."""
    grouped: dict[tuple[int, int], list[MatrixObservation]] = defaultdict(list)
    for observation in observations:
        grouped[(int(observation.drone_id), int(observation.frame_id))].append(observation)
    pair_rows: list[dict[str, object]] = []
    for (view_id, frame_id), current in sorted(grouped.items()):
        previous = grouped.get((view_id, frame_id - 1), [])
        for first in previous:
            first_embedding = embeddings.get(observation_sensor_key(first))
            if first_embedding is None:
                continue
            for second in current:
                second_embedding = embeddings.get(observation_sensor_key(second))
                if second_embedding is None or not _bbox_center_gate(first, second):
                    continue
                first_fold = stable_identity_fold(first.person_id, seed=seed)
                second_fold = stable_identity_fold(second.person_id, seed=seed)
                if first_fold != second_fold:
                    continue
                pair_rows.append(
                    {
                        "view_id": view_id,
                        "frame_id": frame_id,
                        "fold": first_fold,
                        "same_identity": int(first.person_id == second.person_id),
                        "similarity": float(np.dot(first_embedding, second_embedding)),
                    }
                )
    thresholds: dict[int, float] = {}
    calibration_rows: list[dict[str, object]] = []
    for evaluation_fold in (0, 1):
        calibration_fold = 1 - evaluation_fold
        rows = [row for row in pair_rows if int(row["fold"]) == calibration_fold]
        same = np.asarray([row["similarity"] for row in rows if int(row["same_identity"]) == 1], dtype=float)
        different = np.asarray([row["similarity"] for row in rows if int(row["same_identity"]) == 0], dtype=float)
        if same.size == 0 or different.size == 0:
            raise ValueError(f"insufficient local appearance pairs for calibration fold {calibration_fold}")
        candidates = np.unique(np.quantile(np.concatenate([same, different]), np.linspace(0.0, 1.0, 401)))
        scored = []
        for threshold in candidates:
            true_accept = float(np.mean(same >= threshold))
            false_accept = float(np.mean(different >= threshold))
            scored.append((true_accept - false_accept, true_accept, -false_accept, float(threshold)))
        utility, same_accept, negative_false, threshold = max(scored)
        thresholds[evaluation_fold] = threshold
        calibration_rows.append(
            {
                "evaluation_fold": evaluation_fold,
                "calibration_fold": calibration_fold,
                "same_pairs": int(same.size),
                "different_pairs": int(different.size),
                "selected_threshold": threshold,
                "same_accept_rate": same_accept,
                "different_accept_rate": -negative_false,
                "utility": utility,
            }
        )
    return thresholds, calibration_rows


def _action_signature(rows: Sequence[Mapping[str, object]]) -> list[tuple[object, ...]]:
    fields = (
        "current_frame",
        "capture_time",
        "arrival_time",
        "drone_id",
        "position_id",
        "mode",
        "reject_reason",
        "track_id",
        "identity_gate_pass",
        "position_gate_pass",
        "identity_applied",
        "position_applied",
        "lifecycle_applied",
    )
    return [tuple(row.get(field, "") for field in fields) for row in rows]


def run_history1_equivalence(
    *,
    args: argparse.Namespace,
    observations: Sequence[MatrixObservation],
    embeddings: Mapping[tuple, np.ndarray],
    thresholds: Mapping[int, float],
    occlusion_keys: set[tuple[int, int]],
    strict_keys: set[tuple[int, int]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    previous_metrics = read_rows(args.legacy_reference_dir / "update_separation_pipeline_metrics.csv")
    total = 4
    index = 0
    for delay_name in ("fixed_2", "fixed_3"):
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        profile = make_delay_profile(
            observations,
            name=delay_name,
            seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        clean = apply_delay_profile(observations, profile)
        noisy = apply_support_pose_noise(
            clean,
            primary_drone_id=args.primary_drone_id,
            pose_xy_noise_m=args.pose_noise_m,
            seed=args.seed,
            profile_name=f"{delay_name}:noise={args.pose_noise_m:.3f}",
        )
        adapted: list[MatrixObservation] = []
        adapted_embeddings: dict[tuple, np.ndarray] = {}
        for local_id, observation in enumerate(noisy, start=1):
            embedding = embeddings.get(observation_sensor_key(observation))
            update = history1_update_from_observation(
                observation,
                local_track_id=local_id,
                embedding=embedding,
            )
            rebuilt = observation_from_history1_update(update, reference=observation)
            adapted.append(rebuilt)
            if update.pooled_embedding is not None:
                adapted_embeddings[observation_sensor_key(rebuilt)] = update.pooled_embedding
        for fold in (0, 1):
            index += 1
            started = time.perf_counter()
            print(
                f"[2/5][history1] condition={index}/{total} delay={delay_name} fold={fold} start",
                flush=True,
            )
            common = dict(
                truth_observations=clean,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=1.0,
                primary_drone_id=args.primary_drone_id,
                lag_frames=delay_frames,
                occlusion_keys=occlusion_keys,
                pipeline="identity_gated_position_only",
                use_identity_gate=True,
                identity_accept_threshold=float(thresholds[fold]),
                identity_only_distance_threshold=2.0,
                support_measurement_noise=max(0.05, args.pose_noise_m),
                support_update_policy=SupportUpdatePolicy.IDENTITY_GATED_POSITION_ONLY,
                support_margin_threshold=0.50,
                progress_every=args.progress_every,
            )
            reference = run_fixed_lag_multicue_update(noisy, appearance_embeddings=embeddings, **common)
            candidate = run_fixed_lag_multicue_update(adapted, appearance_embeddings=adapted_embeddings, **common)
            reference_metrics = matrix_run_from_reanchoring(reference)
            candidate_metrics = matrix_run_from_reanchoring(candidate)
            prediction_mismatch = sum(
                first != second for first, second in zip(reference.predictions, candidate.predictions)
            ) + abs(len(reference.predictions) - len(candidate.predictions))
            track_id_mismatch = sum(
                first.pred_id != second.pred_id
                for first, second in zip(reference.predictions, candidate.predictions)
            ) + abs(len(reference.predictions) - len(candidate.predictions))
            action_reference = _action_signature(reference.diagnostics)
            action_candidate = _action_signature(candidate.diagnostics)
            action_mismatch = sum(
                first != second for first, second in zip(action_reference, action_candidate)
            ) + abs(len(action_reference) - len(action_candidate))
            metric_error = max(
                abs(reference_metrics.idf1 - candidate_metrics.idf1),
                abs(reference_metrics.mota - candidate_metrics.mota),
                float(abs(reference_metrics.idsw - candidate_metrics.idsw)),
            )
            strict_predictions = [
                prediction
                for prediction in candidate.predictions
                if (int(prediction.frame_id), int(prediction.gt_id)) in strict_keys
            ]
            strict_metric = compute_identity_metrics(strict_predictions)
            prior = [
                row
                for row in previous_metrics
                if row.get("identity_source") == "osnet_x0_25_msmt17"
                and row.get("pipeline") == "identity_gated_position_only"
                and row.get("delay_profile") == delay_name
                and int(row.get("evaluation_fold", -1)) == fold
            ]
            prior_error: object = ""
            if args.frame_start == 0 and args.frame_end == 999 and len(prior) == 1:
                prior_error = abs(float(prior[0]["occlusion_idf1"]) - strict_metric.idf1)
            rows.append(
                {
                    "delay_profile": delay_name,
                    "delay_frames": delay_frames,
                    "evaluation_fold": fold,
                    "identity_threshold": thresholds[fold],
                    "prediction_mismatch": prediction_mismatch,
                    "track_id_mismatch": track_id_mismatch,
                    "support_action_mismatch": action_mismatch,
                    "metric_error": metric_error,
                    "prior_occlusion_idf1_error": prior_error,
                    "passed": int(
                        prediction_mismatch == 0
                        and track_id_mismatch == 0
                        and action_mismatch == 0
                        and metric_error < 1.0e-12
                        and (prior_error == "" or float(prior_error) < 1.0e-6)
                    ),
                }
            )
            print(
                f"[2/5][history1] condition={index}/{total} complete mismatch={prediction_mismatch}/"
                f"{action_mismatch} elapsed={duration(time.perf_counter() - started)}",
                flush=True,
            )
    return rows


def _condition_paths(checkpoint_dir: Path, name: str) -> dict[str, Path]:
    return {
        "done": checkpoint_dir / f"{name}.json",
        "predictions": checkpoint_dir / f"{name}.predictions.csv",
        "messages": checkpoint_dir / f"{name}.messages.csv",
        "appearance": checkpoint_dir / f"{name}.appearance.csv",
        "world": checkpoint_dir / f"{name}.world.csv",
        "audit": checkpoint_dir / f"{name}.audit.csv",
    }


def _condition_rows(paths: Mapping[str, Path]) -> dict[str, list[dict[str, str]]]:
    return {name: read_rows(path) for name, path in paths.items() if name != "done"}


def _local_condition(
    *,
    observations: Sequence[MatrixObservation],
    clean_lookup: Mapping[tuple, MatrixObservation],
    embeddings: Mapping[tuple, np.ndarray],
    view_id: int,
    variant: str,
    evaluation_fold: int,
    threshold: float,
    frame_start: int,
    frame_end: int,
    min_hits: int,
    max_age: int,
    seed: int,
    progress_every: int,
    condition_index: int,
    condition_total: int,
) -> dict[str, list[dict[str, object]]]:
    by_frame: dict[int, list[MatrixObservation]] = defaultdict(list)
    eval_by_key: dict[tuple, int] = {}
    for observation in observations:
        by_frame[int(observation.frame_id)].append(observation)
        eval_by_key[observation_sensor_key(observation)] = int(observation.person_id)
    tracker = LocalTrackletTracker(
        view_id=view_id,
        variant=variant,
        identity_threshold=threshold,
        min_hits=min_hits,
        max_age=max_age,
    )
    outputs: dict[str, list[dict[str, object]]] = {
        "predictions": [],
        "messages": [],
        "appearance": [],
        "world": [],
        "audit": [],
    }
    previous_latest: dict[int, np.ndarray] = {}
    previous_pooled: dict[int, np.ndarray] = {}
    started = time.perf_counter()
    future_reads = 0
    for frame_id in range(frame_start, frame_end + 1):
        frame_observations = sorted(
            by_frame.get(frame_id, []),
            key=lambda observation: observation_sensor_key(observation),
        )
        detections = [
            LocalDetection(
                sensor_key=observation_sensor_key(observation),
                frame_id=frame_id,
                drone_id=view_id,
                bbox_xyxy=observation.bbox_xyxy,
                world_xy=tuple(float(value) for value in observation.world_xyz[:2]),
                embedding=embeddings.get(observation_sensor_key(observation)),
            )
            for observation in frame_observations
        ]
        step = tracker.step(frame_id, detections)
        message_by_key = {
            message.sensor_key: message
            for message in step.messages
            if message.has_measurement and message.sensor_key is not None
        }
        for assignment in step.assignments:
            person_id = eval_by_key[assignment.sensor_key]
            in_evaluation_fold = evaluation_fold < 0 or stable_identity_fold(person_id, seed=seed) == evaluation_fold
            if in_evaluation_fold:
                outputs["predictions"].append(
                    {
                        "frame_id": frame_id,
                        "drone_id": view_id,
                        "variant": variant,
                        "evaluation_fold": evaluation_fold,
                        "person_id_eval_only": person_id,
                        "local_track_id": assignment.local_track_id,
                    }
                )
            message = message_by_key.get(assignment.sensor_key)
            if message is None:
                continue
            clean = clean_lookup[assignment.sensor_key]
            latest_error = float(
                np.linalg.norm(
                    np.asarray(detections[[item.sensor_key for item in detections].index(assignment.sensor_key)].world_xy)
                    - np.asarray(clean.world_xyz[:2])
                )
            )
            filtered_error = float(
                np.linalg.norm(np.asarray(message.filtered_world_xy) - np.asarray(clean.world_xyz[:2]))
            )
            if in_evaluation_fold:
                outputs["world"].append({
                    "frame_id": frame_id,
                    "drone_id": view_id,
                    "variant": variant,
                    "evaluation_fold": evaluation_fold,
                    "person_id_eval_only": person_id,
                    "local_track_id": assignment.local_track_id,
                    "single_frame_world_error_m": latest_error,
                    "filtered_world_error_m": filtered_error,
                    "history_length": message.history_length,
                })
            latest = message.latest_embedding
            pooled = message.pooled_embedding
            if latest is not None and pooled is not None:
                same_latest = previous_latest.get(person_id)
                same_pooled = previous_pooled.get(person_id)
                different_latest = [value for key, value in previous_latest.items() if key != person_id]
                different_pooled = [value for key, value in previous_pooled.items() if key != person_id]
                if (
                    in_evaluation_fold
                    and same_latest is not None
                    and same_pooled is not None
                    and different_latest
                    and different_pooled
                ):
                    latest_same = float(np.dot(latest, same_latest))
                    pooled_same = float(np.dot(pooled, same_pooled))
                    latest_different = max(float(np.dot(latest, value)) for value in different_latest)
                    pooled_different = max(float(np.dot(pooled, value)) for value in different_pooled)
                    outputs["appearance"].append(
                        {
                            "frame_id": frame_id,
                            "drone_id": view_id,
                            "variant": variant,
                            "evaluation_fold": evaluation_fold,
                            "person_id_eval_only": person_id,
                            "local_track_id": assignment.local_track_id,
                            "single_crop_same_similarity": latest_same,
                            "single_crop_different_similarity": latest_different,
                            "single_crop_margin": latest_same - latest_different,
                            "pooled_same_similarity": pooled_same,
                            "pooled_different_similarity": pooled_different,
                            "pooled_margin": pooled_same - pooled_different,
                            "history_length": message.history_length,
                        }
                    )
                previous_latest[person_id] = latest.copy()
                previous_pooled[person_id] = pooled.copy()
        for message in step.messages:
            row = message_runtime_dict(message)
            row.update({"variant": variant, "evaluation_fold": evaluation_fold})
            if message.sensor_key is not None:
                row["person_id_eval_only"] = eval_by_key[message.sensor_key]
            else:
                row["person_id_eval_only"] = ""
            outputs["messages"].append(row)
            future_reads += int(message.tracklet_start_frame > message.capture_time)
        if frame_id == frame_start or frame_id == frame_end or (frame_id - frame_start + 1) % max(progress_every, 1) == 0:
            done = frame_id - frame_start + 1
            total_frames = frame_end - frame_start + 1
            elapsed = time.perf_counter() - started
            eta = elapsed / max(done, 1) * max(total_frames - done, 0)
            print(
                f"[3/5][local] condition={condition_index}/{condition_total} view=D{view_id + 1} "
                f"tracker={variant} fold={evaluation_fold} frame={frame_id}/{frame_end} "
                f"elapsed={duration(elapsed)} eta={duration(eta)}",
                flush=True,
            )
    outputs["audit"].append(
        {
            "drone_id": view_id,
            "variant": variant,
            "evaluation_fold": evaluation_fold,
            "runtime_person_id_field_reads": 0,
            "future_read_count": future_reads,
            "local_id_reused_as_global_id": 0,
            "message_schema_person_id_fields": int(message_schema_uses_person_id()),
        }
    )
    return outputs


def _hash_condition(outputs: Mapping[str, Sequence[Mapping[str, object]]]) -> str:
    digest = hashlib.sha256()
    for name in sorted(outputs):
        digest.update(name.encode("ascii"))
        for row in outputs[name]:
            digest.update(json.dumps(row, sort_keys=True, default=str).encode("utf-8"))
    return digest.hexdigest()


def summarize_local_quality(
    prediction_rows: Sequence[Mapping[str, object]],
    *,
    strict_keys: set[tuple[int, int]],
) -> tuple[list[dict[str, object]], dict[str, dict[str, float]]]:
    grouped: dict[tuple[str, int, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in prediction_rows:
        grouped[(str(row["variant"]), int(row["evaluation_fold"]), int(row["drone_id"]))].append(row)
    quality: list[dict[str, object]] = []
    variant_predictions: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    dominant: dict[tuple[str, int, int, int], int] = {}
    for (variant, fold, view_id), rows in sorted(grouped.items()):
        predictions = [
            Prediction(int(row["frame_id"]), int(row["person_id_eval_only"]), int(row["local_track_id"]))
            for row in rows
        ]
        metrics = compute_identity_metrics(predictions)
        counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
        for row in rows:
            counts[int(row["local_track_id"])][int(row["person_id_eval_only"])] += 1
        correct = 0
        for track_id, identities in counts.items():
            person_id, count = max(identities.items(), key=lambda item: (item[1], -item[0]))
            dominant[(variant, fold, view_id, track_id)] = person_id
            correct += count
        quality.append(
            {
                "variant": variant,
                "evaluation_fold": fold,
                "drone_id": view_id,
                "n_eval_detections": len(rows),
                "local_idf1": metrics.idf1,
                "local_idsw": metrics.idsw,
                "weighted_purity": 0.0 if not rows else correct / len(rows),
                "n_local_tracks": len(counts),
            }
        )
        variant_predictions[variant].extend(rows)

    variant_summary: dict[str, dict[str, float]] = {}
    for variant, rows in variant_predictions.items():
        covered: set[tuple[int, int]] = set()
        for row in rows:
            key = (int(row["frame_id"]), int(row["person_id_eval_only"]))
            if int(row["drone_id"]) == 0 or key not in strict_keys:
                continue
            track_key = (
                variant,
                int(row["evaluation_fold"]),
                int(row["drone_id"]),
                int(row["local_track_id"]),
            )
            if dominant.get(track_key) == int(row["person_id_eval_only"]):
                covered.add(key)
        eligible = [row for row in quality if row["variant"] == variant and int(row["n_eval_detections"]) >= 100]
        variant_summary[variant] = {
            "macro_local_idf1": _mean(float(row["local_idf1"]) for row in eligible),
            "weighted_purity": (
                sum(float(row["weighted_purity"]) * int(row["n_eval_detections"]) for row in eligible)
                / max(sum(int(row["n_eval_detections"]) for row in eligible), 1)
            ),
            "min_view_idf1": min((float(row["local_idf1"]) for row in eligible), default=float("nan")),
            "occlusion_support_coverage": len(covered) / max(len(strict_keys), 1),
        }
    return quality, variant_summary


def summarize_components(
    rows: Sequence[Mapping[str, object]],
    *,
    value_fields: Sequence[str],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, int, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["variant"]), int(row["evaluation_fold"]), int(row["drone_id"]))].append(row)
    output = []
    for (variant, fold, drone_id), values in sorted(grouped.items()):
        summary: dict[str, object] = {
            "variant": variant,
            "evaluation_fold": fold,
            "drone_id": drone_id,
            "n_rows": len(values),
        }
        for field in value_fields:
            numeric = [float(row[field]) for row in values]
            summary[f"mean_{field}"] = _mean(numeric)
            summary[f"rmse_{field}"] = math.sqrt(max(_mean(value * value for value in numeric), 0.0))
        output.append(summary)
    return output


def cross_view_overlap(prediction_rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, int, int, int, int], set[int]] = defaultdict(set)
    for row in prediction_rows:
        key = (
            str(row["variant"]),
            int(row["evaluation_fold"]),
            int(row["drone_id"]),
            int(row["local_track_id"]),
            int(row["person_id_eval_only"]),
        )
        groups[key].add(int(row["frame_id"]))
    output: list[dict[str, object]] = []
    keys = sorted(groups)
    for index, first in enumerate(keys):
        for second in keys[index + 1 :]:
            if first[0] != second[0] or first[1] != second[1] or first[4] != second[4] or first[2] == second[2]:
                continue
            intersection = groups[first] & groups[second]
            if not intersection:
                continue
            union = groups[first] | groups[second]
            output.append(
                {
                    "variant": first[0],
                    "evaluation_fold": first[1],
                    "person_id_eval_only": first[4],
                    "view_a": first[2],
                    "local_track_a": first[3],
                    "view_b": second[2],
                    "local_track_b": second[3],
                    "overlap_frames": len(intersection),
                    "temporal_iou": len(intersection) / len(union),
                }
            )
    return output


def write_decision(
    path: Path,
    *,
    history_rows: Sequence[Mapping[str, object]],
    audit_rows: Sequence[Mapping[str, object]],
    variant_summary: Mapping[str, Mapping[str, float]],
    appearance_summary: Sequence[Mapping[str, object]],
    world_summary: Sequence[Mapping[str, object]],
    embedding_coverage: float,
) -> str:
    history_pass = bool(history_rows) and all(int(row["passed"]) == 1 for row in history_rows)
    measurement_pass = (
        not message_schema_uses_person_id()
        and all(int(row["runtime_person_id_field_reads"]) == 0 for row in audit_rows)
        and all(int(row["future_read_count"]) == 0 for row in audit_rows)
        and all(int(row["local_id_reused_as_global_id"]) == 0 for row in audit_rows)
        and all(int(row.get("determinism_mismatch", 1)) == 0 for row in audit_rows)
        and embedding_coverage >= 0.95
    )
    osnet = variant_summary.get("bbox_osnet", {})
    quality_pass = bool(osnet) and (
        float(osnet.get("macro_local_idf1", 0.0)) >= 0.80
        and float(osnet.get("weighted_purity", 0.0)) >= 0.95
        and float(osnet.get("min_view_idf1", 0.0)) >= 0.70
        and float(osnet.get("occlusion_support_coverage", 0.0)) >= 0.90
    )
    appearance_signal = _mean(
        float(row["mean_pooled_margin"]) - float(row["mean_single_crop_margin"])
        for row in appearance_summary
        if math.isfinite(float(row["mean_pooled_margin"]))
        and math.isfinite(float(row["mean_single_crop_margin"]))
    )
    support_world = [row for row in world_summary if int(row["drone_id"]) != 0]
    latest_rmse = _mean(
        float(row["rmse_single_frame_world_error_m"])
        for row in support_world
    )
    filtered_rmse = _mean(
        float(row["rmse_filtered_world_error_m"])
        for row in support_world
    )
    world_improvement = 0.0 if latest_rmse <= 0 else (latest_rmse - filtered_rmse) / latest_rmse
    aggregation_signal = appearance_signal >= 0.02 or world_improvement >= 0.10
    if not history_pass or not measurement_pass:
        decision = "measurement_invalid"
    elif not quality_pass:
        decision = "local_tracklet_quality_blocked"
    elif aggregation_signal:
        decision = "ready_with_aggregation_signal"
    else:
        decision = "ready_for_async_tracklet_fusion"
    lines = [
        "# Incremental Tracklet Foundation Decision",
        "",
        f"- decision: `{decision}`",
        f"- history1_equivalence_pass: `{int(history_pass)}`",
        f"- no_gt_and_causality_gate_pass: `{int(measurement_pass)}`",
        f"- local_tracklet_quality_pass: `{int(quality_pass)}`",
        f"- embedding_coverage: `{embedding_coverage:.6f}`",
        f"- pooled_appearance_margin_improvement: `{appearance_signal:.6f}`",
        f"- filtered_world_rmse_improvement: `{world_improvement:.6f}`",
        "",
        "## Interpretation",
        "",
        "This experiment validates the incremental message and local-tracklet foundation only. "
        "It does not claim that tracklet-level asynchronous fusion improves global MVMOT yet.",
        "",
        "## Variant Readiness",
        "",
        "| Variant | Macro local IDF1 | Purity | Minimum-view IDF1 | Occlusion support coverage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for variant, row in sorted(variant_summary.items()):
        lines.append(
            f"| {variant} | {row['macro_local_idf1']:.6f} | {row['weighted_purity']:.6f} | "
            f"{row['min_view_idf1']:.6f} | {row['occlusion_support_coverage']:.6f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    print(f"[1/5][prepare] experiment={EXPERIMENT_ID} loading MATRIX observations", flush=True)
    all_observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    visible_observations, crop_audit = los_visible_observations(args.matrix_root, all_observations)
    visible_observations = [row for row in visible_observations if int(row.drone_id) in set(args.drone_ids)]
    default_tracklet_cache = args.output_dir / "embedding_cache" / "osnet_x0_25_msmt17.npz"
    cache_path = args.tracklet_embedding_cache or (
        default_tracklet_cache
        if default_tracklet_cache.is_file()
        else args.real_embedding_dir / "embedding_cache" / "osnet_x0_25_msmt17.npz"
    )
    osnet = load_embedding_cache(cache_path)
    visible_with_embedding = sum(observation_sensor_key(row) in osnet.embeddings for row in visible_observations)
    embedding_coverage = visible_with_embedding / max(len(visible_observations), 1)
    print(
        f"[1/5][prepare] observations={len(visible_observations)} embeddings={visible_with_embedding} "
        f"coverage={embedding_coverage:.4f}",
        flush=True,
    )
    write_rows(
        args.output_dir / "local_tracklet_embedding_coverage.csv",
        [
            {
                "embedding_cache": str(cache_path),
                "los_observations": len(visible_observations),
                "covered_observations": visible_with_embedding,
                "embedding_coverage": embedding_coverage,
                "coverage_gate_pass": int(embedding_coverage >= 0.95),
            }
        ],
    )
    if embedding_coverage < 0.95:
        decision_path = args.output_dir / "incremental_tracklet_foundation_decision.md"
        decision_path.write_text(
            "# Incremental Tracklet Foundation Decision\n\n"
            "- decision: `measurement_invalid`\n"
            "- blocker: `incomplete_all_view_osnet_cache`\n"
            f"- embedding_coverage: `{embedding_coverage:.6f}`\n"
            f"- cache: `{cache_path}`\n\n"
            "The previous cache contains the occlusion-support observation stream, not the complete "
            "per-view local-detection stream. Prepare the all-view cache before running Gate B.\n",
            encoding="utf-8",
        )
        raise RuntimeError(
            f"all-view OSNet cache coverage {embedding_coverage:.2%} is below 95%; "
            "run scripts/prepare_matrix_local_tracklet_osnet_cache.py first"
        )
    thresholds, calibration_rows = calibrate_local_thresholds(
        visible_observations,
        osnet.embeddings,
        seed=args.seed,
    )
    write_rows(args.output_dir / "local_tracklet_threshold_calibration.csv", calibration_rows)

    visibilities = build_frame_visibilities(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        support_drone_ids=tuple(drone for drone in args.drone_ids if drone != args.primary_drone_id),
    )
    episodes = build_occlusion_episodes(visibilities, min_episode_length=1)
    occlusion_keys = build_occlusion_event_keys(episodes, min_episode_length=1)
    strict_episodes = build_occlusion_episodes(visibilities, min_episode_length=2)
    strict_keys = build_occlusion_event_keys(strict_episodes, min_episode_length=1)
    legacy_observations = filter_to_occlusion_support(
        all_observations,
        occlusion_event_keys=occlusion_keys,
        primary_drone_id=args.primary_drone_id,
    )
    history_rows = run_history1_equivalence(
        args=args,
        observations=legacy_observations,
        embeddings=osnet.embeddings,
        thresholds=threshold_by_fold(args.real_embedding_dir, "osnet_x0_25_msmt17"),
        occlusion_keys=occlusion_keys,
        strict_keys=strict_keys,
    )
    write_rows(args.output_dir / "history1_equivalence_audit.csv", history_rows)
    if not all(int(row["passed"]) == 1 for row in history_rows):
        write_decision(
            args.output_dir / "incremental_tracklet_foundation_decision.md",
            history_rows=history_rows,
            audit_rows=[],
            variant_summary={},
            appearance_summary=[],
            world_summary=[],
            embedding_coverage=embedding_coverage,
        )
        raise RuntimeError("history-1 equivalence gate failed; local-tracklet stage was not run")

    noisy_visible = apply_support_pose_noise(
        visible_observations,
        primary_drone_id=args.primary_drone_id,
        pose_xy_noise_m=args.pose_noise_m,
        seed=args.seed,
        profile_name=f"local_tracklet:noise={args.pose_noise_m:.3f}",
    )
    clean_lookup = {observation_sensor_key(row): row for row in visible_observations}
    noisy_by_view: dict[int, list[MatrixObservation]] = defaultdict(list)
    for observation in noisy_visible:
        noisy_by_view[int(observation.drone_id)].append(observation)

    conditions: list[tuple[int, str, int, float]] = []
    for view_id in args.drone_ids:
        if "bbox_sort" in args.local_trackers:
            conditions.append((view_id, "bbox_sort", -1, 0.0))
        if "bbox_osnet" in args.local_trackers:
            for fold in (0, 1):
                conditions.append((view_id, "bbox_osnet", fold, thresholds[fold]))
    unknown = sorted(set(args.local_trackers) - {"bbox_sort", "bbox_osnet"})
    if unknown:
        raise ValueError(f"unknown local tracker variants: {unknown}")

    combined: dict[str, list[dict[str, object]]] = {
        "predictions": [],
        "messages": [],
        "appearance": [],
        "world": [],
        "audit": [],
    }
    cache_stat = cache_path.stat()
    cache_token = f"{cache_path.resolve()}:{cache_stat.st_size}:{cache_stat.st_mtime_ns}"
    for condition_index, (view_id, variant, fold, threshold) in enumerate(conditions, start=1):
        name = f"D{view_id + 1}__{variant}__fold{fold}"
        paths = _condition_paths(checkpoint_dir, name)
        if args.resume and paths["done"].is_file():
            payload = json.loads(paths["done"].read_text(encoding="utf-8"))
            if payload.get("schema_version") == SCHEMA_VERSION and payload.get("cache_token") == cache_token:
                loaded = _condition_rows(paths)
                for key, rows in loaded.items():
                    combined[key].extend(rows)
                print(
                    f"[3/5][local] condition={condition_index}/{len(conditions)} resume: skip completed "
                    f"{name} checkpoint={paths['done']}",
                    flush=True,
                )
                continue
            print(
                f"[3/5][local] condition={condition_index}/{len(conditions)} resume: invalidate stale "
                f"checkpoint={paths['done']}",
                flush=True,
            )
        condition = _local_condition(
            observations=noisy_by_view.get(view_id, []),
            clean_lookup=clean_lookup,
            embeddings=osnet.embeddings,
            view_id=view_id,
            variant=variant,
            evaluation_fold=fold,
            threshold=threshold,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            min_hits=args.min_hits,
            max_age=args.max_age,
            seed=args.seed,
            progress_every=args.progress_every,
            condition_index=condition_index,
            condition_total=len(conditions),
        )
        repeated = _local_condition(
            observations=noisy_by_view.get(view_id, []),
            clean_lookup=clean_lookup,
            embeddings=osnet.embeddings,
            view_id=view_id,
            variant=variant,
            evaluation_fold=fold,
            threshold=threshold,
            frame_start=args.frame_start,
            frame_end=args.frame_end,
            min_hits=args.min_hits,
            max_age=args.max_age,
            seed=args.seed,
            progress_every=max(args.frame_end - args.frame_start + 1, 1),
            condition_index=condition_index,
            condition_total=len(conditions),
        )
        mismatch = int(_hash_condition(condition) != _hash_condition(repeated))
        condition["audit"][0]["determinism_mismatch"] = mismatch
        for key, rows in condition.items():
            write_rows(paths[key], rows)
            combined[key].extend(rows)
        atomic_json(
            paths["done"],
            {
                "schema_version": SCHEMA_VERSION,
                "name": name,
                "complete": True,
                "cache_token": cache_token,
            },
        )
        print(
            f"[3/5][local] condition={condition_index}/{len(conditions)} complete {name} "
            f"determinism_mismatch={mismatch} checkpoint={paths['done']}",
            flush=True,
        )

    print("[4/5][aggregate] computing local identity and component readiness", flush=True)
    local_quality, variant_summary = summarize_local_quality(combined["predictions"], strict_keys=strict_keys)
    appearance_summary = summarize_components(
        combined["appearance"],
        value_fields=("single_crop_margin", "pooled_margin"),
    )
    world_summary = summarize_components(
        combined["world"],
        value_fields=("single_frame_world_error_m", "filtered_world_error_m"),
    )
    write_rows(args.output_dir / "local_tracklet_predictions.csv", combined["predictions"])
    write_rows(args.output_dir / "local_tracklet_manifest.csv", combined["messages"])
    write_rows(args.output_dir / "local_tracklet_quality_by_view.csv", local_quality)
    failure_cases = [
        row
        for row in local_quality
        if int(row["n_eval_detections"]) >= 100
        and (float(row["local_idf1"]) < 0.70 or float(row["weighted_purity"]) < 0.95)
    ]
    write_rows(args.output_dir / "local_tracklet_failure_cases.csv", failure_cases)
    write_rows(args.output_dir / "incremental_tracklet_message_manifest.csv", combined["messages"])
    write_rows(args.output_dir / "incremental_tracklet_causality_audit.csv", combined["audit"])
    write_rows(args.output_dir / "tracklet_appearance_quality.csv", appearance_summary)
    write_rows(args.output_dir / "tracklet_world_state_quality.csv", world_summary)
    write_rows(args.output_dir / "cross_view_tracklet_overlap.csv", cross_view_overlap(combined["predictions"]))
    decision = write_decision(
        args.output_dir / "incremental_tracklet_foundation_decision.md",
        history_rows=history_rows,
        audit_rows=combined["audit"],
        variant_summary=variant_summary,
        appearance_summary=appearance_summary,
        world_summary=world_summary,
        embedding_coverage=embedding_coverage,
    )
    print(f"[5/5][finalize] decision={decision} outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
