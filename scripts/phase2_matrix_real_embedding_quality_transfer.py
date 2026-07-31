#!/usr/bin/env python3
"""Evaluate frozen real appearance embeddings in delayed MATRIX tracking."""

from __future__ import annotations

import argparse
import csv
import hashlib
import inspect
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import torch
from scipy.optimize import linear_sum_assignment

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from phase2_matrix_fixed_lag_simulated_identity_cue_ablation import (  # noqa: E402
    _best_lag_for_delay,
    _pipeline_rows,
    mean,
    write_rows,
)
from phase2_matrix_fixed_lag_temporal_spatial_robustness import (  # noqa: E402
    apply_support_pose_noise,
    augment_episode_rows,
    build_truth_lookup,
    count_primary_perturbations,
    fmt,
    safe_float,
    safe_int,
)
from phase2_matrix_identity_cue_quality_boundary import bootstrap_mean_ci, read_rows  # noqa: E402
from phase2_matrix_tracker_state_aware_reanchoring import _episode_metrics  # noqa: E402
from detection.osnet_reid import build_torchreid_osnet_x025  # noqa: E402
from tracking.delay_injection import fixed_delay_frames, frames_to_ms  # noqa: E402
from tracking.matrix_gt import (  # noqa: E402
    MatrixObservation,
    apply_delay_profile,
    load_matrix_observations,
    make_delay_profile,
)
from tracking.matrix_identity_cue import cosine_similarity, observation_sensor_key  # noqa: E402
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    filter_to_occlusion_support,
)
from tracking.matrix_real_appearance import (  # noqa: E402
    RealAppearanceEmbeddingTable,
    embedding_norm_mismatches,
    extract_m3ot_gem_embeddings,
    extract_osnet_embeddings,
    load_embedding_cache,
    los_visible_observations,
    save_embedding_cache,
    sha256_file,
)
from tracking.matrix_reanchoring import (  # noqa: E402
    WorldSortTracker,
    matrix_run_from_reanchoring,
    run_drop_delayed_sort,
    run_fixed_lag_multicue_update,
    run_primary_only_sort,
)


SCHEMA_VERSION = 1
SIMULATED_MARGIN_LOWER = 0.040019
SIMULATED_MARGIN_UPPER = 0.056747


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=999)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--support-drone-ids", nargs="*", type=int, default=[1, 2, 3, 4, 5, 6, 7])
    parser.add_argument("--embedding-backends", nargs="*", default=["m3ot_gem", "osnet_x0_25_msmt17"])
    parser.add_argument("--m3ot-detector", type=Path, default=Path("weights/m3ot_detector_best.pt"))
    parser.add_argument("--m3ot-reid-head", type=Path, default=Path("weights/gem_proj_head_l15.pt"))
    parser.add_argument("--m3ot-layer", type=int, default=15)
    parser.add_argument("--m3ot-image-width", type=int, default=640)
    parser.add_argument("--m3ot-image-height", type=int, default=512)
    parser.add_argument("--m3ot-roi-size", type=int, default=8)
    parser.add_argument("--torchreid-path", type=Path)
    parser.add_argument("--osnet-checkpoint", type=Path, default=Path("weights/osnet_x0_25_msmt17.pth"))
    parser.add_argument("--delay-profiles", nargs="*", default=["fixed_2", "fixed_3"])
    parser.add_argument("--lag-frames", nargs="*", type=int, default=[2, 3])
    parser.add_argument("--pose-noise-m", type=float, default=0.25)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--identity-only-distance-factor", type=float, default=2.0)
    parser.add_argument("--threshold-offsets", nargs="*", type=float, default=[-0.05, 0.0, 0.05])
    parser.add_argument("--false-accept-cost", type=float, default=5.0)
    parser.add_argument("--min-episode-length", type=int, default=2)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=Path("outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260731_matrix_real_embedding_quality_transfer"),
    )
    return parser.parse_args()


def _duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"


class ProgressPrinter:
    def __init__(self, *, frame_start: int, frame_end: int, progress_every: int) -> None:
        self.frame_start = int(frame_start)
        self.frame_end = int(frame_end)
        self.progress_every = max(int(progress_every), 1)
        self.started = time.perf_counter()

    def stage(self, index: int, name: str, message: str) -> None:
        print(f"[{index}/5][{name}] {message}", flush=True)

    def extraction_callback(self, event: Mapping[str, object]) -> None:
        elapsed = time.perf_counter() - self.started
        done = int(event["image_index"])
        total = max(int(event["image_count"]), 1)
        eta = elapsed / max(done, 1) * max(total - done, 0)
        print(
            f"[2/5][extract][{event['backend']}][D{int(event['drone_id']) + 1}] "
            f"frame={event['frame_id']} images={done}/{total} "
            f"obs={event['observation_count']}/{event['total_observations']} "
            f"elapsed={_duration(elapsed)} eta={_duration(eta)}",
            flush=True,
        )

    def condition_callback(
        self,
        *,
        condition_index: int,
        condition_total: int,
        description: str,
        condition_started: float,
    ):
        def callback(frame_id: int) -> None:
            completed = int(frame_id) - self.frame_start + 1
            total_frames = self.frame_end - self.frame_start + 1
            elapsed = time.perf_counter() - condition_started
            eta = elapsed / max(completed, 1) * max(total_frames - completed, 0)
            print(
                f"[4/5][track] condition={condition_index}/{condition_total} {description} "
                f"frame={frame_id}/{self.frame_end} elapsed={_duration(elapsed)} eta={_duration(eta)}",
                flush=True,
            )

        return callback


def stable_identity_fold(person_id: int, *, seed: int, folds: int = 2) -> int:
    digest = hashlib.sha256(f"{int(seed)}:person:{int(person_id)}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "little") % int(folds)


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def build_manifest(args: argparse.Namespace) -> dict[str, object]:
    weights: dict[str, str] = {}
    if "m3ot_gem" in args.embedding_backends:
        weights["m3ot_detector_sha256"] = sha256_file(args.m3ot_detector)
        weights["m3ot_reid_head_sha256"] = sha256_file(args.m3ot_reid_head)
    if "osnet_x0_25_msmt17" in args.embedding_backends:
        weights["osnet_sha256"] = sha256_file(args.osnet_checkpoint)
    return {
        "schema_version": SCHEMA_VERSION,
        "matrix_root": str(args.matrix_root.expanduser().resolve()),
        "frame_start": int(args.frame_start),
        "frame_end": int(args.frame_end),
        "fps": float(args.fps),
        "primary_drone_id": int(args.primary_drone_id),
        "support_drone_ids": [int(value) for value in args.support_drone_ids],
        "embedding_backends": list(args.embedding_backends),
        "delay_profiles": list(args.delay_profiles),
        "lag_frames": [int(value) for value in args.lag_frames],
        "pose_noise_m": float(args.pose_noise_m),
        "distance_threshold": float(args.distance_threshold),
        "threshold_offsets": [float(value) for value in args.threshold_offsets],
        "false_accept_cost": float(args.false_accept_cost),
        "seed": int(args.seed),
        **weights,
    }


def ensure_manifest(path: Path, manifest: Mapping[str, object], *, resume: bool) -> None:
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != dict(manifest):
            raise ValueError(f"output manifest differs from requested run: {path}")
        if not resume:
            raise ValueError("output already exists; pass --resume or choose a new output directory")
        return
    atomic_write_json(path, manifest)


def global_pair_rows(
    observations: Sequence[MatrixObservation],
    table: RealAppearanceEmbeddingTable,
    *,
    seed: int,
    max_observations_per_person: int = 32,
) -> list[dict[str, object]]:
    grouped: dict[int, list[MatrixObservation]] = defaultdict(list)
    for observation in observations:
        if table.embedding_for(observation) is not None:
            grouped[int(observation.person_id)].append(observation)
    for rows in grouped.values():
        rows.sort(key=lambda row: (int(row.capture_time), int(row.drone_id), row.bbox_xyxy))

    output: list[dict[str, object]] = []
    person_ids = sorted(grouped)
    for person_id in person_ids:
        values = grouped[person_id][: int(max_observations_per_person)]
        cross_view = [
            (left, right)
            for left, right in zip(values, values[1:])
            if int(left.drone_id) != int(right.drone_id)
        ]
        for left, right in cross_view:
            score = cosine_similarity(table.embedding_for(left), table.embedding_for(right))
            if score is not None:
                output.append(
                    {
                        "backend": table.backend,
                        "pair_scope": "global_cross_view",
                        "pair_label": "same",
                        "target_person_id": person_id,
                        "target_fold": stable_identity_fold(person_id, seed=seed),
                        "score": f"{score:.6f}",
                    }
                )
    for left_person, right_person in zip(person_ids, person_ids[1:]):
        for left, right in zip(
            grouped[left_person][: int(max_observations_per_person)],
            grouped[right_person][: int(max_observations_per_person)],
        ):
            score = cosine_similarity(table.embedding_for(left), table.embedding_for(right))
            if score is not None:
                output.append(
                    {
                        "backend": table.backend,
                        "pair_scope": "global_cross_identity",
                        "pair_label": "different",
                        "target_person_id": left_person,
                        "target_fold": stable_identity_fold(left_person, seed=seed),
                        "score": f"{score:.6f}",
                    }
                )
    return output


def _track_truth_labels(
    tracker: WorldSortTracker,
    truth_by_person: Mapping[int, np.ndarray],
    *,
    max_distance: float,
) -> dict[int, int]:
    track_ids = sorted(tracker.tracks)
    person_ids = sorted(truth_by_person)
    if not track_ids or not person_ids:
        return {}
    cost = np.asarray(
        [
            [float(np.linalg.norm(tracker.tracks[track_id].xy - truth_by_person[person_id])) for person_id in person_ids]
            for track_id in track_ids
        ],
        dtype=np.float64,
    )
    rows, columns = linear_sum_assignment(cost)
    return {
        int(track_ids[row]): int(person_ids[column])
        for row, column in zip(rows, columns)
        if float(cost[row, column]) <= float(max_distance)
    }


def candidate_pair_rows(
    clean_observations: Sequence[MatrixObservation],
    noisy_observations: Sequence[MatrixObservation],
    table: RealAppearanceEmbeddingTable,
    *,
    frame_start: int,
    frame_end: int,
    primary_drone_id: int,
    distance_threshold: float,
    candidate_radius: float,
    delay_profile: str,
    seed: int,
    progress_every: int,
    progress: ProgressPrinter,
) -> list[dict[str, object]]:
    clean_primary: dict[int, list[MatrixObservation]] = defaultdict(list)
    noisy_support: dict[int, list[MatrixObservation]] = defaultdict(list)
    truths: dict[int, dict[int, list[np.ndarray]]] = defaultdict(lambda: defaultdict(list))
    for observation in clean_observations:
        truths[int(observation.capture_time)][int(observation.person_id)].append(
            np.asarray(observation.world_xy, dtype=np.float64)
        )
        if int(observation.drone_id) == int(primary_drone_id):
            clean_primary[int(observation.capture_time)].append(observation)
    for observation in noisy_observations:
        if int(observation.drone_id) != int(primary_drone_id) and table.embedding_for(observation) is not None:
            noisy_support[int(observation.capture_time)].append(observation)

    tracker = WorldSortTracker(distance_threshold=distance_threshold)
    output: list[dict[str, object]] = []
    started = time.perf_counter()
    for frame_id in range(int(frame_start), int(frame_end) + 1):
        tracker.update_frame(
            frame_id=frame_id,
            primary_observations=clean_primary.get(frame_id, []),
            support_observations=[],
            support_mode="fixed_lag_update",
            support_allow_new=False,
            support_margin_threshold=0.50,
            appearance_embeddings=table.embeddings,
        )
        truth_frame = {
            person_id: np.asarray(values, dtype=np.float64).mean(axis=0)
            for person_id, values in truths.get(frame_id, {}).items()
        }
        labels = _track_truth_labels(tracker, truth_frame, max_distance=distance_threshold)
        for observation in noisy_support.get(frame_id, []):
            support_embedding = table.embedding_for(observation)
            if support_embedding is None:
                continue
            for track_id, track in sorted(tracker.tracks.items()):
                if track.appearance_embedding is None:
                    continue
                residual = float(np.linalg.norm(np.asarray(observation.world_xy) - track.xy))
                if residual > float(candidate_radius):
                    continue
                candidate_person = labels.get(int(track_id))
                if candidate_person is None:
                    continue
                score = cosine_similarity(support_embedding, track.appearance_embedding)
                if score is None:
                    continue
                output.append(
                    {
                        "backend": table.backend,
                        "delay_profile": delay_profile,
                        "frame_id": frame_id,
                        "drone_id": int(observation.drone_id),
                        "target_person_id": int(observation.person_id),
                        "target_fold": stable_identity_fold(int(observation.person_id), seed=seed),
                        "candidate_track_id": int(track_id),
                        "pair_label": "same" if int(candidate_person) == int(observation.person_id) else "different",
                        "score": f"{float(score):.6f}",
                        "geometry_residual_m": f"{residual:.6f}",
                    }
                )
        if frame_id == frame_start or frame_id == frame_end or (frame_id - frame_start + 1) % max(progress_every, 1) == 0:
            elapsed = time.perf_counter() - started
            completed = frame_id - frame_start + 1
            total = frame_end - frame_start + 1
            eta = elapsed / max(completed, 1) * max(total - completed, 0)
            progress.stage(
                3,
                "calibrate",
                f"backend={table.backend} delay={delay_profile} frame={frame_id}/{frame_end} "
                f"pairs={len(output)} elapsed={_duration(elapsed)} eta={_duration(eta)}",
            )
    return output


def _candidate_thresholds(scores: Sequence[float], *, max_candidates: int = 200) -> list[float]:
    values = np.unique(np.asarray(scores, dtype=np.float64))
    if values.size == 0:
        return []
    if values.size > max_candidates:
        values = np.quantile(values, np.linspace(0.0, 1.0, max_candidates))
    if values.size == 1:
        return [float(values[0])]
    midpoints = (values[:-1] + values[1:]) / 2.0
    return sorted({float(values[0] - 1.0e-6), *[float(value) for value in midpoints], float(values[-1] + 1.0e-6)})


def calibrate_thresholds(
    candidate_rows: Sequence[Mapping[str, object]],
    *,
    backends: Sequence[str],
    false_accept_cost: float,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for backend in backends:
        backend_rows = [row for row in candidate_rows if str(row["backend"]) == str(backend)]
        for eval_fold in (0, 1):
            calibration = [row for row in backend_rows if int(row["target_fold"]) != eval_fold]
            same = [float(row["score"]) for row in calibration if str(row["pair_label"]) == "same"]
            different = [float(row["score"]) for row in calibration if str(row["pair_label"]) == "different"]
            candidates = _candidate_thresholds([*same, *different])
            if not same or not different or not candidates:
                raise ValueError(f"insufficient candidate pairs for {backend} eval fold {eval_fold}")
            operating: list[tuple[float, float, float, float]] = []
            for threshold in candidates:
                tpr = sum(value >= threshold for value in same) / len(same)
                fpr = sum(value >= threshold for value in different) / len(different)
                utility = tpr - float(false_accept_cost) * fpr
                operating.append((utility, -fpr, tpr, threshold))
            utility, negative_fpr, tpr, threshold = max(operating)
            output.append(
                {
                    "backend": backend,
                    "evaluation_fold": eval_fold,
                    "calibration_fold": 1 - eval_fold,
                    "calibration_same_pairs": len(same),
                    "calibration_different_pairs": len(different),
                    "selected_threshold": f"{threshold:.6f}",
                    "same_accept_rate": f"{tpr:.6f}",
                    "different_accept_rate": f"{-negative_fpr:.6f}",
                    "calibration_utility": f"{utility:.6f}",
                }
            )
    return output


def embedding_quality_rows(
    pair_rows: Sequence[Mapping[str, object]],
    tables: Mapping[str, RealAppearanceEmbeddingTable],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for backend, table in tables.items():
        rows = [row for row in pair_rows if str(row["backend"]) == backend and str(row["pair_scope"]).startswith("global")]
        same = [float(row["score"]) for row in rows if str(row["pair_label"]) == "same"]
        different = [float(row["score"]) for row in rows if str(row["pair_label"]) == "different"]
        same_mean = mean(same)
        different_mean = mean(different)
        margin = None if same_mean is None or different_mean is None else same_mean - different_mean
        if margin is None:
            relation = "unavailable"
        elif margin < SIMULATED_MARGIN_LOWER:
            relation = "below"
        elif margin <= SIMULATED_MARGIN_UPPER:
            relation = "within"
        else:
            relation = "above"
        output.append(
            {
                "backend": backend,
                "embedding_dim": table.embedding_dim,
                "same_pair_count": len(same),
                "different_pair_count": len(different),
                "mean_same_similarity": fmt(same_mean),
                "mean_different_similarity": fmt(different_mean),
                "mean_similarity_margin": fmt(margin),
                "simulated_boundary_lower": f"{SIMULATED_MARGIN_LOWER:.6f}",
                "simulated_boundary_upper": f"{SIMULATED_MARGIN_UPPER:.6f}",
                "quality_relation": relation,
            }
        )
    return output


def _checkpoint_name(*parts: object) -> str:
    token = "__".join(str(part).replace("-", "m").replace(".", "p") for part in parts)
    return f"{token}.json"


def _tag_rows(rows: Sequence[Mapping[str, object]], **tags: object) -> list[dict[str, object]]:
    return [{**dict(row), **tags} for row in rows]


def transfer_summary_rows(
    episode_rows: Sequence[Mapping[str, object]],
    *,
    bootstrap_samples: int,
    seed: int,
) -> list[dict[str, object]]:
    covariance_lookup = {
        (str(row["delay_profile"]), str(row["person_id"]), str(row["start_frame"]), str(row["end_frame"])): row
        for row in episode_rows
        if str(row.get("pipeline")) == "fixed_lag_world_xy_covariance"
    }
    grouped: dict[tuple[str, str, str, str], list[tuple[Mapping[str, object], float, float]]] = defaultdict(list)
    for row in episode_rows:
        if str(row.get("eligible", "0")) != "1" or str(row.get("useful_window_bucket")) != "[0.75,1]":
            continue
        if "real_appearance" not in str(row.get("pipeline")):
            continue
        baseline = covariance_lookup.get(
            (str(row["delay_profile"]), str(row["person_id"]), str(row["start_frame"]), str(row["end_frame"]))
        )
        if baseline is None:
            continue
        survival = safe_float(row.get("identity_survival_rate"))
        baseline_survival = safe_float(baseline.get("identity_survival_rate"))
        idsw = safe_float(row.get("window_idsw"))
        baseline_idsw = safe_float(baseline.get("window_idsw"))
        if survival is None or baseline_survival is None or idsw is None or baseline_idsw is None:
            continue
        key = (
            str(row["backend"]),
            str(row["delay_ms"]),
            str(row["pipeline"]),
            str(row["threshold_role"]),
        )
        grouped[key].append((row, survival - baseline_survival, idsw - baseline_idsw))

    output: list[dict[str, object]] = []
    for index, (key, values) in enumerate(sorted(grouped.items())):
        rows = [value[0] for value in values]
        survival_vs_cov = [value[1] for value in values]
        idsw_vs_cov = [value[2] for value in values]
        ci_low, ci_high = bootstrap_mean_ci(
            survival_vs_cov,
            samples=bootstrap_samples,
            seed=int(seed) + index,
        )
        output.append(
            {
                "backend": key[0],
                "delay_ms": key[1],
                "pipeline": key[2],
                "threshold_role": key[3],
                "n_episodes": len(rows),
                "mean_survival_delta_vs_drop": fmt(mean([float(row["survival_delta_vs_drop"]) for row in rows])),
                "mean_window_idsw_delta_vs_drop": fmt(mean([float(row["window_idsw_delta_vs_drop"]) for row in rows])),
                "mean_survival_delta_vs_covariance": fmt(mean(survival_vs_cov)),
                "survival_vs_covariance_ci_low": fmt(ci_low),
                "survival_vs_covariance_ci_high": fmt(ci_high),
                "mean_window_idsw_delta_vs_covariance": fmt(mean(idsw_vs_cov)),
            }
        )
    return output


def decide(
    quality_rows: Sequence[Mapping[str, object]],
    transfer_rows: Sequence[Mapping[str, object]],
    *,
    measurement_valid: bool,
) -> dict[str, object]:
    if not measurement_valid:
        return {"decision": "measurement_invalid", "tracking_transfer": "not_evaluated", "boundary_consistency": "not_evaluated"}
    selected = [
        row
        for row in transfer_rows
        if str(row["threshold_role"]) == "selected"
        and str(row["pipeline"]) == "fixed_lag_world_xy_covariance_real_appearance"
    ]
    pass_by_backend: dict[str, bool] = {}
    partial_by_backend: dict[str, bool] = {}
    for backend in {str(row["backend"]) for row in quality_rows}:
        cells = [row for row in selected if str(row["backend"]) == backend]
        passing: list[Mapping[str, object]] = []
        for row in cells:
            survival_drop = safe_float(row.get("mean_survival_delta_vs_drop"))
            idsw_drop = safe_float(row.get("mean_window_idsw_delta_vs_drop"))
            survival_covariance = safe_float(row.get("mean_survival_delta_vs_covariance"))
            ci_low = safe_float(row.get("survival_vs_covariance_ci_low"))
            if (
                survival_drop is not None
                and idsw_drop is not None
                and survival_covariance is not None
                and ci_low is not None
                and survival_drop >= 0.05
                and idsw_drop <= 0.0
                and survival_covariance >= 0.05
                and ci_low > 0.0
            ):
                passing.append(row)
        pass_by_backend[backend] = len(passing) >= 2
        partial_by_backend[backend] = any(math.isclose(float(row["delay_ms"]), 1000.0) for row in passing)
    if any(pass_by_backend.values()):
        tracking = "tracking_transfer_supported"
    elif any(partial_by_backend.values()):
        tracking = "partial_transfer_delay_conditioned"
    else:
        tracking = "tracking_transfer_failed"

    relation = {str(row["backend"]): str(row["quality_relation"]) for row in quality_rows}
    contradictions = [
        backend
        for backend, passed in pass_by_backend.items()
        if (relation.get(backend) == "below" and passed)
        or (relation.get(backend) in {"within", "above"} and not passed)
    ]
    boundary = "simulated_boundary_not_transferable" if contradictions else "boundary_consistent"
    if tracking == "tracking_transfer_failed" and all(value == "below" for value in relation.values()):
        decision = "frozen_embedding_domain_shift_failure"
    elif boundary == "simulated_boundary_not_transferable":
        decision = boundary
    else:
        decision = tracking
    return {
        "decision": decision,
        "tracking_transfer": tracking,
        "boundary_consistency": boundary,
        "passing_backends": ",".join(sorted(key for key, value in pass_by_backend.items() if value)),
    }


def _reference_mismatches(rows: Sequence[Mapping[str, object]], reference_dir: Path, *, tolerance: float = 1.0e-6) -> tuple[int, str]:
    reference = read_rows(reference_dir / "sim_identity_pipeline_metrics.csv")
    if not reference:
        return 0, "not_available"
    actual = {
        (str(row["delay_profile"]), str(row["pipeline"])): row
        for row in rows
        if str(row.get("pipeline")) in {"drop_delayed_sort", "fixed_lag_world_xy", "fixed_lag_world_xy_covariance"}
    }
    expected = {
        (str(row["delay_profile"]), str(row["pipeline"])): row
        for row in reference
        if math.isclose(float(row.get("pose_xy_noise_m", -1)), 0.25)
        and str(row.get("delay_profile")) in {"fixed_2", "fixed_3"}
        and str(row.get("pipeline")) in {"drop_delayed_sort", "fixed_lag_world_xy", "fixed_lag_world_xy_covariance"}
    }
    mismatches = 0
    for key, row in expected.items():
        if key not in actual:
            mismatches += 1
            continue
        for field in ("aggregate_idf1", "aggregate_idsw", "occlusion_idf1", "occlusion_idsw"):
            if abs(float(row[field]) - float(actual[key][field])) > tolerance:
                mismatches += 1
    return mismatches, "checked"


def write_decision(path: Path, decision: Mapping[str, object], quality: Sequence[Mapping[str, object]], measurement: Mapping[str, object]) -> None:
    lines = [
        "# Real Embedding Quality Transfer Decision",
        "",
        f"**Decision**: `{decision['decision']}`",
        "",
        f"- tracking transfer: `{decision['tracking_transfer']}`",
        f"- boundary consistency: `{decision['boundary_consistency']}`",
        f"- passing backends: `{decision.get('passing_backends', '')}`",
        f"- measurement valid: `{measurement['measurement_valid']}`",
        f"- checkpoints: `{measurement['completed_condition_checkpoints']}/{measurement['expected_condition_checkpoints']}`",
        "",
        "## Embedding Quality",
        "",
        "| backend | margin | relation |",
        "| --- | ---: | --- |",
        *[f"| {row['backend']} | {row['mean_similarity_margin']} | {row['quality_relation']} |" for row in quality],
        "",
        "The numeric simulated margin is an empirical reference. The decisive result is held-out tracking transfer under the calibrated candidate-conditioned threshold.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    allowed_backends = {"m3ot_gem", "osnet_x0_25_msmt17"}
    unknown = set(args.embedding_backends) - allowed_backends
    if unknown:
        raise ValueError(f"unknown embedding backends: {sorted(unknown)}")
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(f"CUDA requested but unavailable: {args.device}")
    for delay_name in args.delay_profiles:
        fixed_delay_frames(delay_name)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    progress = ProgressPrinter(frame_start=args.frame_start, frame_end=args.frame_end, progress_every=args.progress_every)
    manifest = build_manifest(args)
    ensure_manifest(output_dir / "run_manifest.json", manifest, resume=bool(args.resume))

    progress.stage(1, "prepare", "loading MATRIX observations and strict occlusion episodes")
    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    visibilities = build_frame_visibilities(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        support_drone_ids=tuple(args.support_drone_ids),
    )
    all_episodes = build_occlusion_episodes(visibilities, min_episode_length=1)
    metric_episodes = build_occlusion_episodes(visibilities, min_episode_length=args.min_episode_length)
    occlusion_keys_all = build_occlusion_event_keys(all_episodes, min_episode_length=1)
    strict_keys = build_occlusion_event_keys(metric_episodes, min_episode_length=1)
    occlusion_observations = filter_to_occlusion_support(
        observations,
        occlusion_event_keys=occlusion_keys_all,
        primary_drone_id=args.primary_drone_id,
    )
    los_observations, los_audit = los_visible_observations(args.matrix_root, occlusion_observations)
    progress.stage(
        1,
        "prepare",
        f"observations={len(occlusion_observations)} LoS-visible crops={len(los_observations)} episodes={len(metric_episodes)}",
    )

    tables: dict[str, RealAppearanceEmbeddingTable] = {}
    crop_audit: list[dict[str, object]] = list(los_audit)
    progress.stage(2, "extract", f"backends={','.join(args.embedding_backends)}")
    for backend in args.embedding_backends:
        cache_path = output_dir / "embedding_cache" / f"{backend}.npz"
        if args.resume and cache_path.is_file():
            print(f"[2/5][extract][{backend}] resume: load cache {cache_path}", flush=True)
            table = load_embedding_cache(cache_path)
            audit_rows: list[dict[str, object]] = []
        elif backend == "m3ot_gem":
            table, audit_rows = extract_m3ot_gem_embeddings(
                los_observations,
                matrix_root=args.matrix_root,
                detector_checkpoint=args.m3ot_detector,
                head_checkpoint=args.m3ot_reid_head,
                device=args.device,
                layer=args.m3ot_layer,
                image_width=args.m3ot_image_width,
                image_height=args.m3ot_image_height,
                roi_size=args.m3ot_roi_size,
                min_roi_size=1,
                batch_size=args.batch_size,
                progress_every=args.progress_every,
                progress_callback=progress.extraction_callback,
            )
            save_embedding_cache(cache_path, table)
        else:
            model, random_init, source = build_torchreid_osnet_x025(
                checkpoint=args.osnet_checkpoint,
                device=torch.device(args.device),
                torchreid_path=args.torchreid_path,
                pretrained=False,
            )
            if random_init:
                raise RuntimeError(f"formal OSNet backend must not be randomly initialized: {source}")
            table, audit_rows = extract_osnet_embeddings(
                los_observations,
                matrix_root=args.matrix_root,
                model=model,
                device=torch.device(args.device),
                batch_size=args.batch_size,
                progress_every=args.progress_every,
                progress_callback=progress.extraction_callback,
            )
            save_embedding_cache(cache_path, table)
        tables[backend] = table
        crop_audit.extend(audit_rows)
        print(
            f"[2/5][extract][{backend}] complete embeddings={len(table.embeddings)} dim={table.embedding_dim} cache={cache_path}",
            flush=True,
        )

    global_pairs: list[dict[str, object]] = []
    candidate_pairs: list[dict[str, object]] = []
    noisy_by_delay: dict[str, tuple[list[MatrixObservation], list[MatrixObservation], int, float, int]] = {}
    primary_perturbation_mismatches = 0
    progress.stage(3, "calibrate", "building global and active-track candidate-conditioned pairs")
    for backend, table in tables.items():
        global_pairs.extend(global_pair_rows(los_observations, table, seed=args.seed))
    for delay_name in args.delay_profiles:
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        lag_frames = _best_lag_for_delay(delay_frames, args.lag_frames)
        profile = make_delay_profile(
            occlusion_observations,
            name=delay_name,
            seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        clean_delayed = apply_delay_profile(occlusion_observations, profile)
        noisy_delayed = apply_support_pose_noise(
            clean_delayed,
            primary_drone_id=args.primary_drone_id,
            pose_xy_noise_m=args.pose_noise_m,
            seed=args.seed,
            profile_name=f"{delay_name}:noise={args.pose_noise_m:.3f}",
        )
        primary_perturbation_mismatches += count_primary_perturbations(
            clean_delayed,
            noisy_delayed,
            primary_drone_id=args.primary_drone_id,
        )
        noisy_by_delay[delay_name] = (clean_delayed, noisy_delayed, delay_frames, delay_ms, lag_frames)
        for backend, table in tables.items():
            candidate_pairs.extend(
                candidate_pair_rows(
                    clean_delayed,
                    noisy_delayed,
                    table,
                    frame_start=args.frame_start,
                    frame_end=args.frame_end,
                    primary_drone_id=args.primary_drone_id,
                    distance_threshold=args.distance_threshold,
                    candidate_radius=args.distance_threshold * args.identity_only_distance_factor,
                    delay_profile=delay_name,
                    seed=args.seed,
                    progress_every=args.progress_every,
                    progress=progress,
                )
            )
    threshold_rows = calibrate_thresholds(
        candidate_pairs,
        backends=args.embedding_backends,
        false_accept_cost=args.false_accept_cost,
    )
    quality_rows = embedding_quality_rows(global_pairs, tables)
    write_rows(output_dir / "real_embedding_candidate_pairs.csv", candidate_pairs)
    write_rows(output_dir / "real_embedding_threshold_calibration.csv", threshold_rows)
    progress.stage(3, "calibrate", f"candidate pairs={len(candidate_pairs)} thresholds={len(threshold_rows)}")

    threshold_lookup = {
        (str(row["backend"]), int(row["evaluation_fold"])): float(row["selected_threshold"])
        for row in threshold_rows
    }
    appearance_pipelines = (
        ("fixed_lag_world_xy_real_appearance", None),
        ("fixed_lag_world_xy_covariance_real_appearance", max(0.05, float(args.pose_noise_m))),
    )
    expected_baselines = len(args.delay_profiles)
    expected_conditions = (
        len(args.embedding_backends)
        * 2
        * len(args.delay_profiles)
        * len(args.threshold_offsets)
        * len(appearance_pipelines)
    )
    condition_total = expected_baselines + expected_conditions
    condition_index = 0
    pipeline_rows: list[dict[str, object]] = []
    episode_rows: list[dict[str, object]] = []
    truth_lookup = build_truth_lookup(occlusion_observations)
    max_delay_frames = max(fixed_delay_frames(name) for name in args.delay_profiles)
    drop_runs: dict[str, object] = {}

    for delay_name in args.delay_profiles:
        clean_delayed, noisy_delayed, delay_frames, delay_ms, lag_frames = noisy_by_delay[delay_name]
        checkpoint_path = output_dir / "checkpoints" / _checkpoint_name("baseline", delay_name)
        condition_index += 1
        if args.resume and checkpoint_path.is_file():
            print(f"[4/5][track] condition={condition_index}/{condition_total} resume: skip completed {checkpoint_path}", flush=True)
            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            pipeline_rows.extend(payload["pipeline_rows"])
            episode_rows.extend(payload["episode_rows"])
        else:
            def baseline_callback(pipeline_name: str):
                return progress.condition_callback(
                    condition_index=condition_index,
                    condition_total=condition_total,
                    description=f"delay={delay_name} pipeline={pipeline_name}",
                    condition_started=time.perf_counter(),
                )

            primary = run_primary_only_sort(
                noisy_delayed,
                truth_observations=clean_delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                progress_callback=baseline_callback("primary_only_sort"),
                progress_every=args.progress_every,
            )
            drop = run_drop_delayed_sort(
                noisy_delayed,
                truth_observations=clean_delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                progress_callback=baseline_callback("drop_delayed_sort"),
                progress_every=args.progress_every,
            )
            geometry = run_fixed_lag_multicue_update(
                noisy_delayed,
                truth_observations=clean_delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                lag_frames=lag_frames,
                occlusion_keys=occlusion_keys_all,
                pipeline="fixed_lag_world_xy",
                progress_callback=baseline_callback("fixed_lag_world_xy"),
                progress_every=args.progress_every,
            )
            covariance = run_fixed_lag_multicue_update(
                noisy_delayed,
                truth_observations=clean_delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                lag_frames=lag_frames,
                occlusion_keys=occlusion_keys_all,
                pipeline="fixed_lag_world_xy_covariance",
                support_measurement_noise=max(0.05, float(args.pose_noise_m)),
                progress_callback=baseline_callback("fixed_lag_world_xy_covariance"),
                progress_every=args.progress_every,
            )
            runs = {
                run.pipeline: matrix_run_from_reanchoring(run)
                for run in (primary, drop, geometry, covariance)
            }
            drop_runs[delay_name] = runs["drop_delayed_sort"]
            p_rows = _pipeline_rows(
                runs=runs,
                strict_keys=strict_keys,
                pose_noise_m=args.pose_noise_m,
                cue_strength="real",
                cue_type="baseline",
                delay_name=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
            )
            raw_episode = _episode_metrics(
                runs=runs,
                episodes=metric_episodes,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                max_delay_frames=max_delay_frames,
            )
            tagged = _tag_rows(raw_episode, pose_xy_noise_m=f"{args.pose_noise_m:.3f}")
            e_rows = augment_episode_rows(tagged, truth_lookup=truth_lookup, gate_radius_m=args.distance_threshold)
            atomic_write_json(checkpoint_path, {"pipeline_rows": p_rows, "episode_rows": e_rows})
            pipeline_rows.extend(p_rows)
            episode_rows.extend(e_rows)
            print(f"[4/5][track] condition={condition_index}/{condition_total} complete checkpoint={checkpoint_path}", flush=True)

    for delay_name in args.delay_profiles:
        if delay_name in drop_runs:
            continue
        clean_delayed, noisy_delayed, delay_frames, delay_ms, _lag_frames = noisy_by_delay[delay_name]
        print(f"[4/5][track] resume: rebuilding shared drop predictions delay={delay_name}", flush=True)
        rebuild_started = time.perf_counter()
        drop_runs[delay_name] = matrix_run_from_reanchoring(
            run_drop_delayed_sort(
                noisy_delayed,
                truth_observations=clean_delayed,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                distance_threshold=args.distance_threshold,
                primary_drone_id=args.primary_drone_id,
                progress_callback=progress.condition_callback(
                    condition_index=condition_index,
                    condition_total=condition_total,
                    description=f"resume-shared-drop delay={delay_name}",
                    condition_started=rebuild_started,
                ),
                progress_every=args.progress_every,
            )
        )

    for backend in args.embedding_backends:
        table = tables[backend]
        for eval_fold in (0, 1):
            selected_threshold = threshold_lookup[(backend, eval_fold)]
            threshold_conditions = []
            for offset in args.threshold_offsets:
                threshold = min(1.0, max(-1.0, selected_threshold + float(offset)))
                role = "selected" if math.isclose(float(offset), 0.0) else ("lower" if offset < 0 else "upper")
                threshold_conditions.append((role, threshold))
            for delay_name in args.delay_profiles:
                clean_delayed, noisy_delayed, delay_frames, delay_ms, lag_frames = noisy_by_delay[delay_name]
                for role, threshold in threshold_conditions:
                    for pipeline, support_noise in appearance_pipelines:
                        condition_index += 1
                        checkpoint_path = output_dir / "checkpoints" / _checkpoint_name(
                            backend,
                            f"fold{eval_fold}",
                            delay_name,
                            role,
                            f"t{threshold:.6f}",
                            pipeline,
                        )
                        if args.resume and checkpoint_path.is_file():
                            print(
                                f"[4/5][track] condition={condition_index}/{condition_total} resume: skip completed {checkpoint_path}",
                                flush=True,
                            )
                            payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                            pipeline_rows.extend(payload["pipeline_rows"])
                            episode_rows.extend(payload["episode_rows"])
                            continue
                        description = (
                            f"model={backend} fold={eval_fold} delay={delay_name} T={threshold:.4f} "
                            f"pipeline={pipeline}"
                        )
                        print(f"[4/5][track] condition={condition_index}/{condition_total} start {description}", flush=True)
                        started = time.perf_counter()
                        callback = progress.condition_callback(
                            condition_index=condition_index,
                            condition_total=condition_total,
                            description=description,
                            condition_started=started,
                        )
                        run = run_fixed_lag_multicue_update(
                            noisy_delayed,
                            truth_observations=clean_delayed,
                            delay_profile=delay_name,
                            delay_frames=delay_frames,
                            delay_ms=delay_ms,
                            frame_start=args.frame_start,
                            frame_end=args.frame_end,
                            distance_threshold=args.distance_threshold,
                            primary_drone_id=args.primary_drone_id,
                            lag_frames=lag_frames,
                            occlusion_keys=occlusion_keys_all,
                            pipeline=pipeline,
                            appearance_embeddings=table.embeddings,
                            use_identity_gate=True,
                            identity_accept_threshold=threshold,
                            identity_only_distance_threshold=args.distance_threshold * args.identity_only_distance_factor,
                            support_measurement_noise=support_noise,
                            progress_callback=callback,
                            progress_every=args.progress_every,
                        )
                        matrix_run = matrix_run_from_reanchoring(run)
                        runs = {"drop_delayed_sort": drop_runs[delay_name], pipeline: matrix_run}
                        p_rows = _tag_rows(
                            _pipeline_rows(
                                runs={pipeline: matrix_run},
                                strict_keys=strict_keys,
                                pose_noise_m=args.pose_noise_m,
                                cue_strength="real",
                                cue_type="real_appearance",
                                delay_name=delay_name,
                                delay_frames=delay_frames,
                                delay_ms=delay_ms,
                            ),
                            backend=backend,
                            evaluation_fold=eval_fold,
                            identity_accept_threshold=f"{threshold:.6f}",
                            threshold_role=role,
                        )
                        raw_episode = _episode_metrics(
                            runs=runs,
                            episodes=metric_episodes,
                            delay_profile=delay_name,
                            delay_frames=delay_frames,
                            delay_ms=delay_ms,
                            frame_start=args.frame_start,
                            frame_end=args.frame_end,
                            max_delay_frames=max_delay_frames,
                        )
                        tagged = _tag_rows(raw_episode, pose_xy_noise_m=f"{args.pose_noise_m:.3f}")
                        augmented = augment_episode_rows(tagged, truth_lookup=truth_lookup, gate_radius_m=args.distance_threshold)
                        e_rows = _tag_rows(
                            [row for row in augmented if stable_identity_fold(int(row["person_id"]), seed=args.seed) == eval_fold],
                            backend=backend,
                            evaluation_fold=eval_fold,
                            identity_accept_threshold=f"{threshold:.6f}",
                            threshold_role=role,
                        )
                        atomic_write_json(checkpoint_path, {"pipeline_rows": p_rows, "episode_rows": e_rows})
                        pipeline_rows.extend(p_rows)
                        episode_rows.extend(e_rows)
                        print(
                            f"[4/5][track] condition={condition_index}/{condition_total} complete "
                            f"elapsed={_duration(time.perf_counter() - started)} checkpoint={checkpoint_path}",
                            flush=True,
                        )

    progress.stage(5, "report", "aggregating transfer metrics and measurement gates")
    transfer_rows = transfer_summary_rows(episode_rows, bootstrap_samples=args.bootstrap_samples, seed=args.seed)
    reference_mismatches, reference_status = _reference_mismatches(pipeline_rows, args.reference_dir)
    completed_checkpoints = len(list((output_dir / "checkpoints").glob("*.json")))
    coverage_rows: list[dict[str, object]] = []
    norm_mismatches = 0
    for backend, table in tables.items():
        coverage = len(table.embeddings) / max(len(los_observations), 1)
        backend_norm_mismatches = embedding_norm_mismatches(table)
        norm_mismatches += backend_norm_mismatches
        coverage_rows.append(
            {
                "backend": backend,
                "expected_los_observations": len(los_observations),
                "embedding_count": len(table.embeddings),
                "embedding_coverage": f"{coverage:.6f}",
                "norm_mismatches": backend_norm_mismatches,
            }
        )
    fold_people = {
        fold: {int(episode.person_id) for episode in metric_episodes if stable_identity_fold(episode.person_id, seed=args.seed) == fold}
        for fold in (0, 1)
    }
    fold_overlap = len(fold_people[0] & fold_people[1])
    identity_lookup_uses_person_id = int("person_id" in inspect.getsource(observation_sensor_key))
    measurement_valid = bool(
        all(float(row["embedding_coverage"]) >= 0.95 for row in coverage_rows)
        and norm_mismatches == 0
        and fold_overlap == 0
        and identity_lookup_uses_person_id == 0
        and primary_perturbation_mismatches == 0
        and reference_mismatches == 0
        and completed_checkpoints == condition_total
    )
    measurement = {
        "measurement_valid": int(measurement_valid),
        "primary_perturbation_mismatches": primary_perturbation_mismatches,
        "embedding_norm_mismatches": norm_mismatches,
        "identity_lookup_key_uses_person_id": identity_lookup_uses_person_id,
        "calibration_evaluation_fold_overlap": fold_overlap,
        "reference_reproduction_status": reference_status,
        "reference_reproduction_mismatches": reference_mismatches,
        "expected_condition_checkpoints": condition_total,
        "completed_condition_checkpoints": completed_checkpoints,
    }
    decision = decide(quality_rows, transfer_rows, measurement_valid=measurement_valid)

    write_rows(output_dir / "real_embedding_manifest.csv", [{**manifest, "backend_count": len(tables)}])
    write_rows(output_dir / "real_embedding_crop_audit.csv", crop_audit)
    write_rows(output_dir / "real_embedding_quality_summary.csv", quality_rows)
    write_rows(output_dir / "real_embedding_pipeline_metrics.csv", pipeline_rows)
    write_rows(output_dir / "real_embedding_episode_metrics.csv", episode_rows)
    write_rows(output_dir / "real_embedding_transfer_summary.csv", transfer_rows)
    write_rows(output_dir / "real_embedding_measurement_gate.csv", [{**measurement, "coverage": json.dumps(coverage_rows)}])
    write_decision(output_dir / "real_embedding_decision.md", decision, quality_rows, measurement)
    progress.stage(
        5,
        "report",
        f"complete decision={decision['decision']} checkpoints={completed_checkpoints}/{condition_total} output={output_dir}",
    )


if __name__ == "__main__":
    main()
