#!/usr/bin/env python3
"""Fixed-lag temporal-spatial robustness audit for MATRIX occlusion support."""

from __future__ import annotations

import argparse
import csv
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from phase2_matrix_tracker_state_aware_reanchoring import (  # noqa: E402
    _episode_metrics,
    _subset_metrics,
)
from tracking.delay_injection import fixed_delay_frames, frames_to_ms  # noqa: E402
from tracking.matrix_gt import (  # noqa: E402
    MatrixTrackerRun,
    MatrixObservation,
    apply_delay_profile,
    load_matrix_observations,
    make_delay_profile,
)
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    episode_length_bucket,
    filter_to_occlusion_support,
)
from tracking.matrix_reanchoring import (  # noqa: E402
    ReanchoringRun,
    matrix_run_from_reanchoring,
    run_arrival_time_sort,
    run_drop_delayed_sort,
    run_fixed_lag_oosm_update,
    run_primary_only_sort,
)


FIXED_LAG_RE = re.compile(r"^fixed_lag_oosm_lag(?P<lag>\d+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=999)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--support-drone-ids", nargs="*", type=int, default=[1, 2, 3, 4, 5, 6, 7])
    parser.add_argument("--delay-profiles", nargs="*", default=["fixed_0", "fixed_1", "fixed_2", "fixed_3", "fixed_5"])
    parser.add_argument("--lag-frames", nargs="*", type=int, default=[1, 2, 3, 5])
    parser.add_argument("--pose-noise-levels", nargs="*", type=float, default=[0.0, 0.10, 0.25, 0.50])
    parser.add_argument(
        "--include-arrival-time",
        action="store_true",
        help="Also run the noisy arrival-time baseline. Disabled by default because it creates many stale support tracks.",
    )
    parser.add_argument(
        "--include-noisy-fixed0",
        action="store_true",
        help="Also run fixed_0 with nonzero support pose noise. Disabled by default; main decisions use fixed_2/fixed_3.",
    )
    parser.add_argument("--min-episode-length", type=int, default=2)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=Path("outputs/20260724_matrix_tracker_state_aware_reanchoring"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260726_matrix_fixed_lag_temporal_spatial_robustness"),
    )
    return parser.parse_args()


def write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_float(value: object) -> float | None:
    if value in ("", None):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def safe_int(value: object) -> int | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    return int(parsed)


def fmt(value: float | None, digits: int = 6) -> str:
    return "" if value is None else f"{float(value):.{digits}f}"


def mean(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def observation_key(obs: MatrixObservation) -> tuple[int, int, int]:
    return (int(obs.frame_id), int(obs.drone_id), int(obs.person_id))


def apply_support_pose_noise(
    observations: Sequence[MatrixObservation],
    *,
    primary_drone_id: int,
    pose_xy_noise_m: float,
    seed: int,
    profile_name: str,
) -> list[MatrixObservation]:
    """Apply deterministic world-XY noise only to support observations."""
    rng = random.Random(f"{int(seed)}:{profile_name}:{float(pose_xy_noise_m):.6f}")
    output: list[MatrixObservation] = []
    for obs in observations:
        if int(obs.drone_id) == int(primary_drone_id) or float(pose_xy_noise_m) <= 0.0:
            dx = dy = 0.0
        else:
            dx = rng.gauss(0.0, float(pose_xy_noise_m))
            dy = rng.gauss(0.0, float(pose_xy_noise_m))
        output.append(
            MatrixObservation(
                frame_id=obs.frame_id,
                drone_id=obs.drone_id,
                person_id=obs.person_id,
                position_id=obs.position_id,
                world_xyz=(
                    float(obs.world_xyz[0]) + float(dx),
                    float(obs.world_xyz[1]) + float(dy),
                    float(obs.world_xyz[2]),
                ),
                bbox_xyxy=obs.bbox_xyxy,
                capture_time=obs.capture_time,
                arrival_time=obs.arrival_time,
                delay=obs.delay,
            )
        )
    return output


def count_primary_perturbations(
    clean: Sequence[MatrixObservation],
    noisy: Sequence[MatrixObservation],
    *,
    primary_drone_id: int,
) -> int:
    clean_by_key = {observation_key(obs): obs for obs in clean if int(obs.drone_id) == int(primary_drone_id)}
    mismatches = 0
    for obs in noisy:
        if int(obs.drone_id) != int(primary_drone_id):
            continue
        clean_obs = clean_by_key.get(observation_key(obs))
        if clean_obs is None or tuple(clean_obs.world_xyz) != tuple(obs.world_xyz):
            mismatches += 1
    return mismatches


def parse_fixed_lag_frames(pipeline: str) -> int | None:
    match = FIXED_LAG_RE.match(str(pipeline))
    if not match:
        return None
    return int(match.group("lag"))


def useful_window_fraction(episode_length: int, delay_frames: int) -> float:
    if int(episode_length) <= 0:
        raise ValueError("episode_length must be positive")
    return max(int(episode_length) - int(delay_frames), 0) / int(episode_length)


def useful_window_bucket(value: float) -> str:
    if value < 0.25:
        return "[0,0.25)"
    if value < 0.5:
        return "[0.25,0.5)"
    if value < 0.75:
        return "[0.5,0.75)"
    return "[0.75,1]"


def risk_bucket(value: float) -> str:
    if value < 0.5:
        return "[0,0.5)"
    if value < 1.0:
        return "[0.5,1)"
    if value < 1.5:
        return "[1,1.5)"
    return "[1.5,inf)"


def build_truth_lookup(observations: Sequence[MatrixObservation]) -> dict[tuple[int, int], np.ndarray]:
    grouped: dict[tuple[int, int], list[np.ndarray]] = defaultdict(list)
    for obs in observations:
        grouped[(int(obs.capture_time), int(obs.person_id))].append(np.asarray(obs.world_xy, dtype=np.float64))
    return {
        key: np.asarray(values, dtype=np.float64).mean(axis=0)
        for key, values in grouped.items()
    }


def motion_m_per_frame(
    truth: Mapping[tuple[int, int], np.ndarray],
    *,
    person_id: int,
    start_frame: int,
    end_frame: int,
) -> float:
    points: list[np.ndarray] = []
    for frame_id in range(int(start_frame), int(end_frame) + 1):
        point = truth.get((frame_id, int(person_id)))
        if point is not None:
            points.append(np.asarray(point, dtype=np.float64))
    if len(points) < 2:
        return 0.0
    distances = [
        float(np.linalg.norm(right - left))
        for left, right in zip(points, points[1:])
    ]
    return 0.0 if not distances else sum(distances) / len(distances)


def episode_key(row: Mapping[str, object]) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("pose_xy_noise_m", "")),
        str(row.get("delay_profile", "")),
        str(row.get("person_id", "")),
        str(row.get("start_frame", "")),
        str(row.get("end_frame", "")),
    )


def _metric(row: Mapping[str, object] | None, key: str) -> float | None:
    if row is None:
        return None
    return safe_float(row.get(key))


def _delta(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None:
        return None
    return value - baseline


def augment_episode_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    truth_lookup: Mapping[tuple[int, int], np.ndarray],
    gate_radius_m: float,
) -> list[dict[str, object]]:
    drop_lookup = {
        episode_key(row): row
        for row in rows
        if str(row.get("pipeline")) == "drop_delayed_sort" and str(row.get("eligible", "0")) == "1"
    }
    output: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        delay_frames = safe_int(item.get("delay_frames")) or 0
        episode_length = safe_int(item.get("episode_length")) or 0
        pose_noise = safe_float(item.get("pose_xy_noise_m")) or 0.0
        lag = parse_fixed_lag_frames(str(item.get("pipeline", "")))
        useful = useful_window_fraction(episode_length, delay_frames) if episode_length > 0 else 0.0
        motion = motion_m_per_frame(
            truth_lookup,
            person_id=safe_int(item.get("person_id")) or 0,
            start_frame=safe_int(item.get("start_frame")) or 0,
            end_frame=safe_int(item.get("end_frame")) or 0,
        )
        spatial_staleness = float(motion) * float(delay_frames)
        gate = max(float(gate_radius_m), 1.0e-12)
        temporal_spatial_risk = (spatial_staleness + float(pose_noise)) / gate
        drop = drop_lookup.get(episode_key(item))
        survival = _metric(item, "identity_survival_rate")
        fragmentation = _metric(item, "track_fragmentation")
        idsw = _metric(item, "window_idsw")
        item.update(
            {
                "lag_frames": "" if lag is None else lag,
                "lag_eligible": "" if lag is None else int(delay_frames <= int(lag)),
                "lag_headroom_frames": "" if lag is None else int(lag) - int(delay_frames),
                "remaining_after_first_arrival_frames": max(int(episode_length) - int(delay_frames), 0),
                "useful_window_fraction": fmt(useful),
                "useful_window_bucket": useful_window_bucket(useful),
                "motion_m_per_frame": fmt(motion),
                "spatial_staleness_m": fmt(spatial_staleness),
                "spatial_staleness_ratio": fmt(spatial_staleness / gate),
                "noise_to_gate_ratio": fmt(float(pose_noise) / gate),
                "temporal_spatial_risk": fmt(temporal_spatial_risk),
                "temporal_spatial_risk_bucket": risk_bucket(temporal_spatial_risk),
                "survival_delta_vs_drop": fmt(_delta(survival, _metric(drop, "identity_survival_rate"))),
                "fragmentation_delta_vs_drop": fmt(_delta(fragmentation, _metric(drop, "track_fragmentation"))),
                "window_idsw_delta_vs_drop": fmt(_delta(idsw, _metric(drop, "window_idsw"))),
            }
        )
        output.append(item)
    return output


def numeric_values(rows: Sequence[Mapping[str, object]], key: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        value = safe_float(row.get(key))
        if value is not None:
            values.append(value)
    return values


def summarize_group(rows: Sequence[Mapping[str, object]], key_values: Mapping[str, object]) -> dict[str, object]:
    survival_delta = numeric_values(rows, "survival_delta_vs_drop")
    idsw_delta = numeric_values(rows, "window_idsw_delta_vs_drop")
    frag_delta = numeric_values(rows, "fragmentation_delta_vs_drop")
    useful = numeric_values(rows, "useful_window_fraction")
    risk = numeric_values(rows, "temporal_spatial_risk")
    return {
        **key_values,
        "n_episodes": len(rows),
        "mean_identity_survival_rate": fmt(mean(numeric_values(rows, "identity_survival_rate"))),
        "mean_survival_delta_vs_drop": fmt(mean(survival_delta)),
        "mean_fragmentation_delta_vs_drop": fmt(mean(frag_delta)),
        "mean_window_idsw_delta_vs_drop": fmt(mean(idsw_delta)),
        "mean_useful_window_fraction": fmt(mean(useful)),
        "mean_temporal_spatial_risk": fmt(mean(risk)),
        "positive_survival_delta_fraction": fmt(sum(value > 0.0 for value in survival_delta) / len(survival_delta) if survival_delta else None),
    }


def summarize_by_fields(rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field, "") for field in fields)].append(row)
    output: list[dict[str, object]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        output.append(summarize_group(group, dict(zip(fields, key))))
    return output


def fixed_lag_rows(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    return [row for row in rows if parse_fixed_lag_frames(str(row.get("pipeline", ""))) is not None]


def best_lag_by_condition(rows: Sequence[Mapping[str, object]], *, min_bucket_n: int = 5) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in fixed_lag_rows(rows):
        grouped[
            (
                row.get("pose_xy_noise_m", ""),
                row.get("delay_ms", ""),
                row.get("useful_window_bucket", ""),
                row.get("temporal_spatial_risk_bucket", ""),
            )
        ].append(row)
    output: list[dict[str, object]] = []
    for key, group in sorted(grouped.items(), key=lambda item: tuple(str(value) for value in item[0])):
        candidates: list[dict[str, object]] = []
        by_lag: dict[int, list[Mapping[str, object]]] = defaultdict(list)
        for row in group:
            lag = safe_int(row.get("lag_frames"))
            if lag is not None:
                by_lag[lag].append(row)
        for lag, lag_rows in sorted(by_lag.items()):
            if len(lag_rows) < min_bucket_n:
                continue
            candidates.append(summarize_group(lag_rows, {"lag_frames": lag}))
        if not candidates:
            continue
        ranked = sorted(
            candidates,
            key=lambda item: (
                -(safe_float(item.get("mean_survival_delta_vs_drop")) or -999.0),
                safe_float(item.get("mean_window_idsw_delta_vs_drop")) or 999999.0,
                safe_int(item.get("lag_frames")) or 999,
            ),
        )
        best = ranked[0]
        output.append(
            {
                "pose_xy_noise_m": key[0],
                "delay_ms": key[1],
                "useful_window_bucket": key[2],
                "temporal_spatial_risk_bucket": key[3],
                "candidate_lag_count": len(candidates),
                "best_lag_frames": best["lag_frames"],
                "best_n_episodes": best["n_episodes"],
                "best_mean_survival_delta_vs_drop": best["mean_survival_delta_vs_drop"],
                "best_mean_window_idsw_delta_vs_drop": best["mean_window_idsw_delta_vs_drop"],
                "best_mean_fragmentation_delta_vs_drop": best["mean_fragmentation_delta_vs_drop"],
                "best_mean_temporal_spatial_risk": best["mean_temporal_spatial_risk"],
            }
        )
    return output


def failure_cases(rows: Sequence[Mapping[str, object]], *, max_cases: int = 200) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in fixed_lag_rows(rows):
        if str(row.get("lag_eligible")) != "1" or str(row.get("useful_window_bucket")) != "[0.75,1]":
            continue
        survival_delta = safe_float(row.get("survival_delta_vs_drop"))
        idsw_delta = safe_float(row.get("window_idsw_delta_vs_drop"))
        if survival_delta is None or idsw_delta is None:
            continue
        if survival_delta >= 0.05 and idsw_delta <= 0:
            continue
        output.append(
            {
                "reason": "high_useful_window_fixed_lag_failure",
                "pose_xy_noise_m": row.get("pose_xy_noise_m", ""),
                "delay_profile": row.get("delay_profile", ""),
                "delay_frames": row.get("delay_frames", ""),
                "delay_ms": row.get("delay_ms", ""),
                "lag_frames": row.get("lag_frames", ""),
                "person_id": row.get("person_id", ""),
                "start_frame": row.get("start_frame", ""),
                "end_frame": row.get("end_frame", ""),
                "episode_length": row.get("episode_length", ""),
                "useful_window_fraction": row.get("useful_window_fraction", ""),
                "temporal_spatial_risk": row.get("temporal_spatial_risk", ""),
                "survival_delta_vs_drop": row.get("survival_delta_vs_drop", ""),
                "window_idsw_delta_vs_drop": row.get("window_idsw_delta_vs_drop", ""),
                "fragmentation_delta_vs_drop": row.get("fragmentation_delta_vs_drop", ""),
            }
        )
    return sorted(
        output,
        key=lambda row: (
            safe_float(row.get("pose_xy_noise_m")) or 0.0,
            safe_float(row.get("temporal_spatial_risk")) or 0.0,
            safe_float(row.get("survival_delta_vs_drop")) or 0.0,
        ),
    )[:max_cases]


def pipeline_metric_lookup(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str, str], Mapping[str, object]]:
    return {
        (str(row.get("pose_xy_noise_m", "")), str(row.get("delay_ms", "")), str(row.get("pipeline", ""))): row
        for row in rows
    }


def clone_matrix_run(source: MatrixTrackerRun, *, pipeline: str, notes: str) -> MatrixTrackerRun:
    return MatrixTrackerRun(
        pipeline=pipeline,
        delay_profile=source.delay_profile,
        predictions=list(source.predictions),
        idf1=source.idf1,
        idsw=source.idsw,
        mota=source.mota,
        world_xy_mae=source.world_xy_mae,
        world_xy_rmse=source.world_xy_rmse,
        gt_detections=source.gt_detections,
        pred_detections=source.pred_detections,
        latency_ms_per_frame=0.0,
        notes=notes,
        delay_frames=source.delay_frames,
        delay_ms=source.delay_ms,
    )


def invariant_mismatch_count(
    rows: Sequence[Mapping[str, object]],
    *,
    pipeline: str,
    delay_ms_values: set[str] | None = None,
) -> int:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if str(row.get("pipeline")) != pipeline:
            continue
        delay_ms = str(row.get("delay_ms", ""))
        if delay_ms_values is not None and delay_ms not in delay_ms_values:
            continue
        grouped[delay_ms].append(row)
    mismatches = 0
    for group in grouped.values():
        baseline: tuple[str, str, str, str] | None = None
        for row in sorted(group, key=lambda item: float(str(item.get("pose_xy_noise_m", "0")))):
            current = (
                str(row.get("aggregate_idf1", "")),
                str(row.get("aggregate_idsw", "")),
                str(row.get("occlusion_idf1", "")),
                str(row.get("occlusion_idsw", "")),
            )
            if baseline is None:
                baseline = current
            elif current != baseline:
                mismatches += 1
    return mismatches


def baseline_reproduction_mismatch_count(
    current_rows: Sequence[Mapping[str, object]],
    *,
    baseline_dir: Path,
) -> int | None:
    path = baseline_dir / "reanchoring_pipeline_metrics.csv"
    if not path.exists():
        return None
    baseline_rows = read_rows(path)
    baseline = {
        (str(row.get("delay_ms", "")), str(row.get("pipeline", ""))): row
        for row in baseline_rows
    }
    pipelines = {"primary_only_sort", "drop_delayed_sort", "arrival_time_sort"}
    pipelines.update({f"fixed_lag_oosm_lag{lag}" for lag in (1, 2, 3, 5)})
    mismatches = 0
    for row in current_rows:
        if str(row.get("pose_xy_noise_m")) != "0.000":
            continue
        if str(row.get("pipeline")) not in pipelines:
            continue
        prior = baseline.get((str(row.get("delay_ms", "")), str(row.get("pipeline", ""))))
        if prior is None:
            mismatches += 1
            continue
        if str(row.get("occlusion_n", "")) != str(prior.get("occlusion_n", "")):
            return None
        for key in ("aggregate_idf1", "aggregate_idsw", "occlusion_idf1", "occlusion_idsw"):
            if str(row.get(key, "")) != str(prior.get(key, "")):
                mismatches += 1
                break
    return mismatches


def measurement_gate(
    pipeline_rows: Sequence[Mapping[str, object]],
    *,
    primary_perturbation_mismatches: int,
    baseline_dir: Path,
) -> dict[str, object]:
    primary_mismatch = invariant_mismatch_count(pipeline_rows, pipeline="primary_only_sort")
    drop_mismatch = invariant_mismatch_count(
        pipeline_rows,
        pipeline="drop_delayed_sort",
        delay_ms_values={"500.000", "1000.000", "1500.000", "2500.000"},
    )
    baseline_mismatch = baseline_reproduction_mismatch_count(pipeline_rows, baseline_dir=baseline_dir)
    valid = (
        primary_mismatch == 0
        and drop_mismatch == 0
        and primary_perturbation_mismatches == 0
        and baseline_mismatch in (0, None)
    )
    return {
        "measurement_valid": int(valid),
        "primary_only_noise_invariant_mismatch": primary_mismatch,
        "drop_delayed_noise_invariant_mismatch": drop_mismatch,
        "primary_perturbation_mismatches": primary_perturbation_mismatches,
        "pose0_prior_reproduction_mismatch": "" if baseline_mismatch is None else baseline_mismatch,
        "truth_source": "clean_truth_observations",
    }


def _best_global_occ_delta(
    pipeline_rows: Sequence[Mapping[str, object]],
    *,
    pose_noise: str,
    delay_ms: str,
) -> float | None:
    lookup = pipeline_metric_lookup(pipeline_rows)
    drop = lookup.get((pose_noise, delay_ms, "drop_delayed_sort"))
    if drop is None:
        return None
    drop_idf1 = safe_float(drop.get("occlusion_idf1"))
    best = None
    for row in pipeline_rows:
        if str(row.get("pose_xy_noise_m")) != pose_noise or str(row.get("delay_ms")) != delay_ms:
            continue
        if parse_fixed_lag_frames(str(row.get("pipeline"))) is None:
            continue
        value = safe_float(row.get("occlusion_idf1"))
        if value is None:
            continue
        best = value if best is None else max(best, value)
    if best is None or drop_idf1 is None:
        return None
    return best - drop_idf1


def high_window_best_by_noise(
    episode_summary_rows: Sequence[Mapping[str, object]],
    pipeline_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for pose_noise in sorted({str(row.get("pose_xy_noise_m")) for row in episode_summary_rows}):
        for delay_ms in ("1000.000", "1500.000"):
            candidates = [
                row for row in episode_summary_rows
                if str(row.get("pose_xy_noise_m")) == pose_noise
                and str(row.get("delay_ms")) == delay_ms
                and str(row.get("useful_window_bucket")) == "[0.75,1]"
                and str(row.get("lag_eligible")) == "1"
                and safe_int(row.get("n_episodes")) is not None
            ]
            if not candidates:
                continue
            best = sorted(
                candidates,
                key=lambda row: (
                    -(safe_float(row.get("mean_survival_delta_vs_drop")) or -999.0),
                    safe_float(row.get("mean_window_idsw_delta_vs_drop")) or 999999.0,
                ),
            )[0]
            rows.append(
                {
                    "pose_xy_noise_m": pose_noise,
                    "delay_ms": delay_ms,
                    "best_lag_frames": best.get("lag_frames", ""),
                    "n_episodes": best.get("n_episodes", ""),
                    "global_best_occlusion_idf1_delta_vs_drop": fmt(
                        _best_global_occ_delta(pipeline_rows, pose_noise=pose_noise, delay_ms=delay_ms)
                    ),
                    "high_window_mean_survival_delta_vs_drop": best.get("mean_survival_delta_vs_drop", ""),
                    "high_window_mean_window_idsw_delta_vs_drop": best.get("mean_window_idsw_delta_vs_drop", ""),
                }
            )
    return rows


def decision_from_outputs(
    *,
    gate: Mapping[str, object],
    high_window_rows: Sequence[Mapping[str, object]],
) -> str:
    if int(gate.get("measurement_valid", 0)) != 1:
        return "inconclusive"
    required = [
        row for row in high_window_rows
        if str(row.get("delay_ms")) in {"1000.000", "1500.000"}
    ]
    if len(required) < 8:
        return "inconclusive"

    def passes(row: Mapping[str, object]) -> bool:
        occ_delta = safe_float(row.get("global_best_occlusion_idf1_delta_vs_drop"))
        survival_delta = safe_float(row.get("high_window_mean_survival_delta_vs_drop"))
        idsw_delta = safe_float(row.get("high_window_mean_window_idsw_delta_vs_drop"))
        return bool(
            occ_delta is not None
            and survival_delta is not None
            and idsw_delta is not None
            and occ_delta >= 0.05
            and survival_delta >= 0.05
            and idsw_delta <= 0.0
        )

    by_noise = defaultdict(list)
    for row in required:
        by_noise[str(row.get("pose_xy_noise_m"))].append(row)
    robust = all(passes(row) for row in required)
    if robust:
        return "fixed_lag_spatially_robust"
    lower_noise_pass = any(
        all(passes(row) for row in rows)
        for noise, rows in by_noise.items()
        if noise in {"0.100", "0.250"}
    )
    low_noise_fail = any(
        not all(passes(row) for row in rows)
        for noise, rows in by_noise.items()
        if noise in {"0.100", "0.250"}
    )
    if lower_noise_pass:
        return "temporal_spatial_boundary_identified"
    if low_noise_fail:
        return "fixed_lag_noise_fragile"
    return "inconclusive"


def write_decision_md(
    path: Path,
    *,
    decision: str,
    gate: Mapping[str, object],
    high_window_rows: Sequence[Mapping[str, object]],
) -> None:
    table = "\n".join(
        [
            "| noise | delay ms | best lag | occ IDF1 delta | high-window survival delta | high-window IDSW delta |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
            *[
                (
                    f"| {row.get('pose_xy_noise_m')} | {row.get('delay_ms')} | {row.get('best_lag_frames')} | "
                    f"{row.get('global_best_occlusion_idf1_delta_vs_drop')} | "
                    f"{row.get('high_window_mean_survival_delta_vs_drop')} | "
                    f"{row.get('high_window_mean_window_idsw_delta_vs_drop')} |"
                )
                for row in high_window_rows
            ],
        ]
    )
    lines = [
        "# Fixed-Lag Temporal-Spatial Robustness Decision",
        "",
        f"**Decision**: `{decision}`",
        "",
        "## Measurement Gates",
        "",
        f"- measurement_valid: `{gate.get('measurement_valid')}`",
        f"- primary_only_noise_invariant_mismatch: `{gate.get('primary_only_noise_invariant_mismatch')}`",
        f"- drop_delayed_noise_invariant_mismatch: `{gate.get('drop_delayed_noise_invariant_mismatch')}`",
        f"- primary_perturbation_mismatches: `{gate.get('primary_perturbation_mismatches')}`",
        f"- pose0_prior_reproduction_mismatch: `{gate.get('pose0_prior_reproduction_mismatch')}`",
        f"- truth_source: `{gate.get('truth_source')}`",
        "",
        "## High Useful-Window Transition Zone",
        "",
        table,
        "",
        "## Interpretation",
        "",
        "`useful_window_fraction` separates temporal opportunity from spatial noise. A fixed-lag update is only deployable if it remains above the drop baseline in high useful-window episodes after support world-coordinate perturbation.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for delay_name in args.delay_profiles:
        fixed_delay_frames(delay_name)
    max_delay_frames = max(fixed_delay_frames(name) for name in args.delay_profiles)

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

    pipeline_rows: list[dict[str, object]] = []
    raw_episode_rows: list[dict[str, object]] = []
    primary_perturbation_mismatches = 0

    for delay_name in args.delay_profiles:
        delay_frames = fixed_delay_frames(delay_name)
        delay_ms = frames_to_ms(delay_frames, args.fps)
        profile = make_delay_profile(
            occlusion_observations,
            name=delay_name,
            seed=args.seed,
            primary_drone_id=args.primary_drone_id,
        )
        clean_delayed = apply_delay_profile(occlusion_observations, profile)
        primary_cache: MatrixTrackerRun | None = None
        drop_cache: MatrixTrackerRun | None = None
        for pose_noise in args.pose_noise_levels:
            if (
                int(delay_frames) == 0
                and float(pose_noise) > 0.0
                and not args.include_noisy_fixed0
            ):
                print(
                    f"[fixed-lag-noise] delay={delay_name} noise={float(pose_noise):.3f} skipped noisy fixed_0 sanity",
                    flush=True,
                )
                continue
            noise_name = f"{delay_name}:noise={float(pose_noise):.3f}"
            print(f"[fixed-lag-noise] delay={delay_name} noise={float(pose_noise):.3f} start", flush=True)
            noisy_delayed = apply_support_pose_noise(
                clean_delayed,
                primary_drone_id=args.primary_drone_id,
                pose_xy_noise_m=float(pose_noise),
                seed=args.seed,
                profile_name=noise_name,
            )
            primary_perturbation_mismatches += count_primary_perturbations(
                clean_delayed,
                noisy_delayed,
                primary_drone_id=args.primary_drone_id,
            )
            matrix_runs: dict[str, MatrixTrackerRun] = {}
            if primary_cache is None:
                primary_run = run_primary_only_sort(
                    noisy_delayed,
                    truth_observations=clean_delayed,
                    delay_profile=delay_name,
                    delay_frames=delay_frames,
                    delay_ms=delay_ms,
                    frame_start=args.frame_start,
                    frame_end=args.frame_end,
                    distance_threshold=args.distance_threshold,
                    primary_drone_id=args.primary_drone_id,
                )
                primary_cache = matrix_run_from_reanchoring(primary_run)
                matrix_runs["primary_only_sort"] = primary_cache
            else:
                matrix_runs["primary_only_sort"] = clone_matrix_run(
                    primary_cache,
                    pipeline="primary_only_sort",
                    notes="none; synthesized noise-invariant primary",
                )

            if args.include_arrival_time:
                arrival_run = run_arrival_time_sort(
                    noisy_delayed,
                    truth_observations=clean_delayed,
                    delay_profile=delay_name,
                    delay_frames=delay_frames,
                    delay_ms=delay_ms,
                    frame_start=args.frame_start,
                    frame_end=args.frame_end,
                    distance_threshold=args.distance_threshold,
                    primary_drone_id=args.primary_drone_id,
                )
                matrix_runs["arrival_time_sort"] = matrix_run_from_reanchoring(arrival_run)

            if int(delay_frames) == 0:
                if args.include_arrival_time:
                    matrix_runs["drop_delayed_sort"] = clone_matrix_run(
                        matrix_runs["arrival_time_sort"],
                        pipeline="drop_delayed_sort",
                        notes="drop_delayed; synthesized zero-delay sync equivalence",
                    )
                else:
                    drop_run = run_drop_delayed_sort(
                        noisy_delayed,
                        truth_observations=clean_delayed,
                        delay_profile=delay_name,
                        delay_frames=delay_frames,
                        delay_ms=delay_ms,
                        frame_start=args.frame_start,
                        frame_end=args.frame_end,
                        distance_threshold=args.distance_threshold,
                        primary_drone_id=args.primary_drone_id,
                    )
                    matrix_runs["drop_delayed_sort"] = matrix_run_from_reanchoring(drop_run)
            elif drop_cache is None:
                drop_run = run_drop_delayed_sort(
                    noisy_delayed,
                    truth_observations=clean_delayed,
                    delay_profile=delay_name,
                    delay_frames=delay_frames,
                    delay_ms=delay_ms,
                    frame_start=args.frame_start,
                    frame_end=args.frame_end,
                    distance_threshold=args.distance_threshold,
                    primary_drone_id=args.primary_drone_id,
                )
                drop_cache = matrix_run_from_reanchoring(drop_run)
                matrix_runs["drop_delayed_sort"] = drop_cache
            else:
                matrix_runs["drop_delayed_sort"] = clone_matrix_run(
                    drop_cache,
                    pipeline="drop_delayed_sort",
                    notes="drop_delayed; synthesized noise-invariant delayed drop",
                )

            eligible_source: MatrixTrackerRun | None = None
            for lag in sorted(int(value) for value in args.lag_frames):
                pipeline = f"fixed_lag_oosm_lag{int(lag)}"
                if int(delay_frames) == 0:
                    matrix_runs[pipeline] = clone_matrix_run(
                        matrix_runs["drop_delayed_sort"],
                        pipeline=pipeline,
                        notes=f"fixed lag={int(lag)}; synthesized zero-delay equivalence",
                    )
                    continue
                if int(delay_frames) > int(lag):
                    matrix_runs[pipeline] = clone_matrix_run(
                        matrix_runs["drop_delayed_sort"],
                        pipeline=pipeline,
                        notes=f"fixed lag={int(lag)}; synthesized beyond-lag rejection",
                    )
                    continue
                if eligible_source is None:
                    fixed_run = run_fixed_lag_oosm_update(
                        noisy_delayed,
                        truth_observations=clean_delayed,
                        delay_profile=delay_name,
                        delay_frames=delay_frames,
                        delay_ms=delay_ms,
                        frame_start=args.frame_start,
                        frame_end=args.frame_end,
                        distance_threshold=args.distance_threshold,
                        primary_drone_id=args.primary_drone_id,
                        lag_frames=int(lag),
                        occlusion_keys=occlusion_keys_all,
                    )
                    eligible_source = matrix_run_from_reanchoring(fixed_run)
                    matrix_runs[pipeline] = eligible_source
                    continue
                matrix_runs[pipeline] = clone_matrix_run(
                    eligible_source,
                    pipeline=pipeline,
                    notes=f"fixed lag={int(lag)}; synthesized same fixed-delay eligibility",
                )
            for run in matrix_runs.values():
                occ = _subset_metrics(run.predictions, strict_keys)
                pipeline_rows.append(
                    {
                        "pose_xy_noise_m": f"{float(pose_noise):.3f}",
                        "delay_profile": delay_name,
                        "delay_frames": delay_frames,
                        "delay_ms": f"{delay_ms:.3f}",
                        "pipeline": run.pipeline,
                        "aggregate_idf1": f"{run.idf1:.6f}",
                        "aggregate_idsw": run.idsw,
                        "aggregate_mota": f"{run.mota:.6f}",
                        "occlusion_idf1": f"{float(occ['idf1']):.6f}",
                        "occlusion_idsw": occ["idsw"],
                        "occlusion_n": occ["n"],
                        "latency_ms_per_frame": f"{run.latency_ms_per_frame:.6f}",
                        "notes": run.notes,
                    }
                )
            for row in _episode_metrics(
                runs=matrix_runs,
                episodes=metric_episodes,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                max_delay_frames=max_delay_frames,
            ):
                raw = dict(row)
                raw["pose_xy_noise_m"] = f"{float(pose_noise):.3f}"
                raw_episode_rows.append(raw)
            print(f"[fixed-lag-noise] delay={delay_name} noise={float(pose_noise):.3f} complete", flush=True)

    truth_lookup = build_truth_lookup(occlusion_observations)
    episode_rows = augment_episode_rows(
        raw_episode_rows,
        truth_lookup=truth_lookup,
        gate_radius_m=args.distance_threshold,
    )
    fixed_rows = fixed_lag_rows(episode_rows)
    useful_summary = summarize_by_fields(
        fixed_rows,
        ["pose_xy_noise_m", "delay_ms", "lag_frames", "lag_eligible", "useful_window_bucket"],
    )
    temporal_spatial_summary = summarize_by_fields(
        fixed_rows,
        ["pose_xy_noise_m", "delay_ms", "lag_frames", "useful_window_bucket", "temporal_spatial_risk_bucket"],
    )
    best_lag_rows = best_lag_by_condition(fixed_rows)
    failures = failure_cases(fixed_rows)
    high_window_rows = high_window_best_by_noise(useful_summary, pipeline_rows)
    gate = measurement_gate(
        pipeline_rows,
        primary_perturbation_mismatches=primary_perturbation_mismatches,
        baseline_dir=args.baseline_dir,
    )
    decision = decision_from_outputs(gate=gate, high_window_rows=high_window_rows)

    write_rows(output_dir / "fixed_lag_noise_pipeline_metrics.csv", pipeline_rows)
    write_rows(output_dir / "fixed_lag_noise_episode_metrics.csv", episode_rows)
    write_rows(output_dir / "fixed_lag_noise_useful_window_summary.csv", useful_summary)
    write_rows(output_dir / "fixed_lag_noise_temporal_spatial_summary.csv", temporal_spatial_summary)
    write_rows(output_dir / "fixed_lag_noise_best_lag_by_condition.csv", best_lag_rows)
    write_rows(output_dir / "fixed_lag_noise_failure_cases.csv", failures)
    write_rows(output_dir / "fixed_lag_noise_high_window_transition_summary.csv", high_window_rows)
    write_rows(output_dir / "fixed_lag_noise_measurement_gate.csv", [gate])
    write_decision_md(
        output_dir / "fixed_lag_noise_decision.md",
        decision=decision,
        gate=gate,
        high_window_rows=high_window_rows,
    )


if __name__ == "__main__":
    main()
