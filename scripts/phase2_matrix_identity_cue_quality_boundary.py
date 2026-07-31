#!/usr/bin/env python3
"""Estimate the simulated identity-cue quality boundary for fixed-lag tracking."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

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
from phase2_matrix_tracker_state_aware_reanchoring import (  # noqa: E402
    _episode_metrics,
    _mode_count_rows,
)
from tracking.delay_injection import fixed_delay_frames, frames_to_ms  # noqa: E402
from tracking.matrix_gt import (  # noqa: E402
    MatrixObservation,
    apply_delay_profile,
    load_matrix_observations,
    make_delay_profile,
)
from tracking.matrix_identity_cue import (  # noqa: E402
    SimulatedIdentityCueConfig,
    SimulatedIdentityCueTable,
    cosine_similarity,
)
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    filter_to_occlusion_support,
)
from tracking.matrix_reanchoring import (  # noqa: E402
    matrix_run_from_reanchoring,
    run_drop_delayed_sort,
    run_fixed_lag_multicue_update,
    run_primary_only_sort,
)


SCHEMA_VERSION = 1
TARGET_DELAYS_MS = (1000.0, 1500.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=999)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--support-drone-ids", nargs="*", type=int, default=[1, 2, 3, 4, 5, 6, 7])
    parser.add_argument("--delay-profiles", nargs="*", default=["fixed_2", "fixed_3"])
    parser.add_argument("--lag-frames", nargs="*", type=int, default=[2, 3])
    parser.add_argument("--pose-noise-m", type=float, default=0.25)
    parser.add_argument(
        "--embedding-noise-sigmas",
        nargs="*",
        type=float,
        default=[0.15, 0.25, 0.30, 0.40, 0.50, 0.70],
    )
    parser.add_argument("--view-bias-sigma", type=float, default=0.08)
    parser.add_argument(
        "--identity-thresholds",
        nargs="*",
        type=float,
        default=[0.05, 0.10, 0.20, 0.25, 0.30],
    )
    parser.add_argument("--false-accept-cost", type=float, default=5.0)
    parser.add_argument("--min-same-accept-rate", type=float, default=0.05)
    parser.add_argument("--identity-dim", type=int, default=128)
    parser.add_argument("--identity-only-distance-factor", type=float, default=2.0)
    parser.add_argument("--min-episode-length", type=int, default=2)
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.set_defaults(resume=True)
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=Path("outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260731_matrix_identity_cue_quality_boundary"),
    )
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _float_token(value: float) -> str:
    return f"{float(value):.3f}".replace("-", "m").replace(".", "p")


def condition_pipeline(noise_sigma: float, threshold: float) -> str:
    return f"fixed_lag_cov_identity_n{_float_token(noise_sigma)}_t{_float_token(threshold)}"


def condition_checkpoint_path(output_dir: Path, delay_name: str, noise_sigma: float, threshold: float) -> Path:
    return output_dir / "checkpoints" / (
        f"condition__{delay_name}__noise_{_float_token(noise_sigma)}"
        f"__threshold_{_float_token(threshold)}.json"
    )


def baseline_checkpoint_path(output_dir: Path, delay_name: str) -> Path:
    return output_dir / "checkpoints" / f"baseline__{delay_name}.json"


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temp_path.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    temp_path.replace(path)


def load_checkpoint(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_manifest(args: argparse.Namespace) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "matrix_root": str(args.matrix_root),
        "frame_start": int(args.frame_start),
        "frame_end": int(args.frame_end),
        "fps": float(args.fps),
        "primary_drone_id": int(args.primary_drone_id),
        "support_drone_ids": [int(value) for value in args.support_drone_ids],
        "delay_profiles": list(args.delay_profiles),
        "lag_frames": [int(value) for value in args.lag_frames],
        "pose_noise_m": float(args.pose_noise_m),
        "embedding_noise_sigmas": sorted(float(value) for value in args.embedding_noise_sigmas),
        "view_bias_sigma": float(args.view_bias_sigma),
        "identity_thresholds": sorted(float(value) for value in args.identity_thresholds),
        "false_accept_cost": float(args.false_accept_cost),
        "min_same_accept_rate": float(args.min_same_accept_rate),
        "identity_dim": int(args.identity_dim),
        "identity_only_distance_factor": float(args.identity_only_distance_factor),
        "min_episode_length": int(args.min_episode_length),
        "distance_threshold": float(args.distance_threshold),
        "seed": int(args.seed),
        "max_rows": int(args.max_rows),
    }


def ensure_manifest(path: Path, manifest: Mapping[str, object], *, resume: bool) -> None:
    if path.exists():
        existing = load_checkpoint(path)
        if existing != dict(manifest):
            raise ValueError(f"output manifest differs from requested run: {path}")
        if not resume:
            raise ValueError("output directory already contains a manifest; use a new directory or --resume")
        return
    atomic_write_json(path, manifest)


def cue_pair_scores(
    observations: Sequence[MatrixObservation],
    table: SimulatedIdentityCueTable,
    *,
    max_observations_per_person: int = 32,
) -> tuple[list[float], list[float]]:
    grouped: dict[int, list[MatrixObservation]] = defaultdict(list)
    for obs in observations:
        grouped[int(obs.person_id)].append(obs)
    for values in grouped.values():
        values.sort(key=lambda obs: (int(obs.capture_time), int(obs.drone_id), int(obs.position_id), obs.bbox_xyxy))

    same_scores: list[float] = []
    different_scores: list[float] = []
    person_ids = sorted(grouped)
    for person_id in person_ids:
        values = grouped[person_id][: int(max_observations_per_person)]
        for left, right in zip(values, values[1:]):
            score = cosine_similarity(table.embedding_for(left), table.embedding_for(right))
            if score is not None:
                same_scores.append(float(score))

    for left_person, right_person in zip(person_ids, person_ids[1:]):
        left_values = grouped[left_person][: int(max_observations_per_person)]
        right_values = grouped[right_person][: int(max_observations_per_person)]
        for left, right in zip(left_values, right_values):
            score = cosine_similarity(table.embedding_for(left), table.embedding_for(right))
            if score is not None:
                different_scores.append(float(score))
    return same_scores, different_scores


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    return float(np.quantile(np.asarray(values, dtype=np.float64), float(q)))


def embedding_quality_row(
    *,
    noise_sigma: float,
    view_bias_sigma: float,
    dim: int,
    same_scores: Sequence[float],
    different_scores: Sequence[float],
) -> dict[str, object]:
    mean_same = mean(list(same_scores))
    mean_different = mean(list(different_scores))
    return {
        "embedding_noise_sigma": f"{float(noise_sigma):.6f}",
        "view_bias_sigma": f"{float(view_bias_sigma):.6f}",
        "embedding_dim": int(dim),
        "same_pair_count": len(same_scores),
        "different_pair_count": len(different_scores),
        "mean_same_similarity": fmt(mean_same),
        "mean_different_similarity": fmt(mean_different),
        "mean_similarity_margin": fmt(
            None if mean_same is None or mean_different is None else mean_same - mean_different
        ),
        "same_similarity_p05": fmt(_quantile(same_scores, 0.05)),
        "same_similarity_p50": fmt(_quantile(same_scores, 0.50)),
        "different_similarity_p50": fmt(_quantile(different_scores, 0.50)),
        "different_similarity_p95": fmt(_quantile(different_scores, 0.95)),
    }


def threshold_operating_row(
    *,
    noise_sigma: float,
    threshold: float,
    same_scores: Sequence[float],
    different_scores: Sequence[float],
) -> dict[str, object]:
    same_accept = mean([1.0 if value >= threshold else 0.0 for value in same_scores])
    different_accept = mean([1.0 if value >= threshold else 0.0 for value in different_scores])
    balanced_accuracy = None
    if same_accept is not None and different_accept is not None:
        balanced_accuracy = 0.5 * (same_accept + 1.0 - different_accept)
    return {
        "embedding_noise_sigma": f"{float(noise_sigma):.6f}",
        "identity_accept_threshold": f"{float(threshold):.6f}",
        "same_accept_rate": fmt(same_accept),
        "different_accept_rate": fmt(different_accept),
        "balanced_gate_accuracy": fmt(balanced_accuracy),
    }


def select_calibrated_thresholds(
    rows: Sequence[Mapping[str, object]],
    *,
    false_accept_cost: float,
    min_same_accept_rate: float,
) -> dict[str, str]:
    """Select one threshold per noise level without using tracking outcomes."""
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[f"{float(row['embedding_noise_sigma']):.6f}"].append(row)
    selected: dict[str, str] = {}
    for noise_sigma, candidates in grouped.items():
        eligible = [
            row
            for row in candidates
            if (safe_float(row.get("same_accept_rate")) or 0.0) >= float(min_same_accept_rate)
        ]
        pool = eligible if eligible else list(candidates)
        best = max(
            pool,
            key=lambda row: (
                (safe_float(row.get("same_accept_rate")) or 0.0)
                - float(false_accept_cost) * (safe_float(row.get("different_accept_rate")) or 0.0),
                -(safe_float(row.get("different_accept_rate")) or 0.0),
                safe_float(row.get("same_accept_rate")) or 0.0,
            ),
        )
        selected[noise_sigma] = f"{float(best['identity_accept_threshold']):.6f}"
    return selected


def bootstrap_mean_ci(values: Sequence[float], *, samples: int, seed: int) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    arr = np.asarray(values, dtype=np.float64)
    if len(arr) == 1 or int(samples) <= 0:
        value = float(arr.mean())
        return value, value
    rng = np.random.default_rng(int(seed))
    means = np.empty(int(samples), dtype=np.float64)
    for index in range(int(samples)):
        means[index] = float(rng.choice(arr, size=len(arr), replace=True).mean())
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def _numeric(rows: Sequence[Mapping[str, object]], field: str) -> list[float]:
    output: list[float] = []
    for row in rows:
        value = safe_float(row.get(field))
        if value is not None:
            output.append(value)
    return output


def boundary_cell_rows(
    episode_rows: Sequence[Mapping[str, object]],
    quality_rows: Sequence[Mapping[str, object]],
    *,
    bootstrap_samples: int,
    seed: int,
) -> list[dict[str, object]]:
    quality_lookup = {
        f"{float(row['embedding_noise_sigma']):.6f}": row
        for row in quality_rows
    }
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in episode_rows:
        if str(row.get("cue_type")) != "world_xy_covariance_identity":
            continue
        if str(row.get("eligible", "0")) != "1" or str(row.get("useful_window_bucket")) != "[0.75,1]":
            continue
        key = (
            f"{float(row['embedding_noise_sigma']):.6f}",
            f"{float(row['identity_accept_threshold']):.6f}",
            f"{float(row['delay_ms']):.3f}",
        )
        grouped[key].append(row)

    output: list[dict[str, object]] = []
    for index, (key, rows) in enumerate(sorted(grouped.items(), key=lambda item: tuple(float(v) for v in item[0]))):
        survival = _numeric(rows, "survival_delta_vs_drop")
        idsw = _numeric(rows, "window_idsw_delta_vs_drop")
        fragmentation = _numeric(rows, "fragmentation_delta_vs_drop")
        survival_mean = mean(survival)
        idsw_mean = mean(idsw)
        survival_low, survival_high = bootstrap_mean_ci(
            survival, samples=bootstrap_samples, seed=int(seed) + index * 2
        )
        idsw_low, idsw_high = bootstrap_mean_ci(
            idsw, samples=bootstrap_samples, seed=int(seed) + index * 2 + 1
        )
        quality = quality_lookup[key[0]]
        point_pass = bool(
            survival_mean is not None
            and idsw_mean is not None
            and survival_mean >= 0.05
            and idsw_mean <= 0.0
        )
        robust_pass = bool(
            point_pass
            and survival_low is not None
            and idsw_high is not None
            and survival_low > 0.0
            and idsw_high <= 0.0
        )
        output.append(
            {
                "embedding_noise_sigma": key[0],
                "mean_similarity_margin": quality["mean_similarity_margin"],
                "mean_same_similarity": quality["mean_same_similarity"],
                "mean_different_similarity": quality["mean_different_similarity"],
                "identity_accept_threshold": key[1],
                "threshold_role": str(rows[0].get("threshold_role", "calibrated")),
                "delay_ms": key[2],
                "n_episodes": len(rows),
                "mean_survival_delta_vs_drop": fmt(survival_mean),
                "survival_delta_ci_low": fmt(survival_low),
                "survival_delta_ci_high": fmt(survival_high),
                "mean_window_idsw_delta_vs_drop": fmt(idsw_mean),
                "window_idsw_delta_ci_low": fmt(idsw_low),
                "window_idsw_delta_ci_high": fmt(idsw_high),
                "mean_fragmentation_delta_vs_drop": fmt(mean(fragmentation)),
                "positive_survival_delta_fraction": fmt(
                    mean([1.0 if value > 0.0 else 0.0 for value in survival])
                ),
                "point_pass": int(point_pass),
                "robust_pass": int(robust_pass),
            }
        )
    return output


def boundary_summary_rows(
    cell_rows: Sequence[Mapping[str, object]],
    *,
    required_delays_ms: Sequence[float] = TARGET_DELAYS_MS,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in cell_rows:
        role = str(row.get("threshold_role", "calibrated"))
        if "calibrated" not in role and role != "boundary_refinement":
            continue
        grouped[(str(row["embedding_noise_sigma"]), str(row["identity_accept_threshold"]))].append(row)
    required = {f"{float(value):.3f}" for value in required_delays_ms}
    output: list[dict[str, object]] = []
    for key, rows in sorted(grouped.items(), key=lambda item: (float(item[0][0]), float(item[0][1]))):
        observed = {str(row["delay_ms"]) for row in rows}
        selected = [row for row in rows if str(row["delay_ms"]) in required]
        all_point = required.issubset(observed) and all(int(row["point_pass"]) == 1 for row in selected)
        all_robust = required.issubset(observed) and all(int(row["robust_pass"]) == 1 for row in selected)
        output.append(
            {
                "embedding_noise_sigma": key[0],
                "mean_similarity_margin": rows[0]["mean_similarity_margin"],
                "mean_same_similarity": rows[0]["mean_same_similarity"],
                "mean_different_similarity": rows[0]["mean_different_similarity"],
                "identity_accept_threshold": key[1],
                "n_required_delay_cells": len(selected),
                "worst_delay_survival_delta": fmt(
                    min(_numeric(selected, "mean_survival_delta_vs_drop")) if selected else None
                ),
                "worst_delay_idsw_delta": fmt(
                    max(_numeric(selected, "mean_window_idsw_delta_vs_drop")) if selected else None
                ),
                "all_delay_point_pass": int(all_point),
                "all_delay_robust_pass": int(all_robust),
            }
        )
    return output


def decide_boundary(summary_rows: Sequence[Mapping[str, object]], *, measurement_valid: bool) -> dict[str, object]:
    if not measurement_valid:
        return {"decision": "measurement_invalid"}
    margins = sorted({float(row["mean_similarity_margin"]) for row in summary_rows})
    point_pass_rows = [row for row in summary_rows if int(row["all_delay_point_pass"]) == 1]
    robust_pass_rows = [row for row in summary_rows if int(row["all_delay_robust_pass"]) == 1]
    if not point_pass_rows:
        return {
            "decision": "quality_requirement_above_scan",
            "largest_tested_margin": fmt(max(margins) if margins else None),
        }

    minimum_point_margin = min(float(row["mean_similarity_margin"]) for row in point_pass_rows)
    lower_failing = [
        margin
        for margin in margins
        if margin < minimum_point_margin
        and not any(
            float(row["mean_similarity_margin"]) == margin
            and int(row["all_delay_point_pass"]) == 1
            for row in summary_rows
        )
    ]
    candidates = [row for row in point_pass_rows if math.isclose(float(row["mean_similarity_margin"]), minimum_point_margin)]
    best = max(
        candidates,
        key=lambda row: (
            float(row["worst_delay_survival_delta"]),
            -float(row["worst_delay_idsw_delta"]),
        ),
    )
    decision = "quality_boundary_identified" if lower_failing else "quality_floor_below_scan"
    return {
        "decision": decision,
        "largest_failing_margin_below_boundary": fmt(max(lower_failing) if lower_failing else None),
        "minimum_point_pass_margin": fmt(minimum_point_margin),
        "minimum_robust_pass_margin": fmt(
            min(float(row["mean_similarity_margin"]) for row in robust_pass_rows)
            if robust_pass_rows else None
        ),
        "recommended_identity_accept_threshold": str(best["identity_accept_threshold"]),
        "boundary_worst_delay_survival_delta": str(best["worst_delay_survival_delta"]),
        "boundary_worst_delay_idsw_delta": str(best["worst_delay_idsw_delta"]),
    }


def reference_reproduction_mismatches(
    boundary_cells: Sequence[Mapping[str, object]],
    reference_dir: Path,
    *,
    tolerance: float = 1.0e-6,
) -> tuple[int, str]:
    reference_path = reference_dir / "sim_identity_high_window_summary.csv"
    reference_rows = read_rows(reference_path)
    if not reference_rows:
        return 0, "not_available"
    expected = {
        f"{float(row['delay_ms']):.3f}": row
        for row in reference_rows
        if str(row.get("pipeline")) == "fixed_lag_world_xy_covariance_identity_medium"
    }
    actual = {
        str(row["delay_ms"]): row
        for row in boundary_cells
        if math.isclose(float(row["embedding_noise_sigma"]), 0.15)
        and math.isclose(float(row["identity_accept_threshold"]), 0.25)
    }
    mismatches = 0
    for delay in ("1000.000", "1500.000"):
        if delay not in expected or delay not in actual:
            mismatches += 1
            continue
        for field in ("mean_survival_delta_vs_drop", "mean_window_idsw_delta_vs_drop"):
            left = safe_float(expected[delay].get(field))
            right = safe_float(actual[delay].get(field))
            if left is None or right is None or abs(left - right) > tolerance:
                mismatches += 1
    return mismatches, "checked"


def write_decision(path: Path, decision: Mapping[str, object], measurement: Mapping[str, object]) -> None:
    lines = [
        "# Identity Cue Quality Boundary Decision",
        "",
        f"**Decision**: `{decision.get('decision')}`",
        "",
        "## Measurement",
        "",
        f"- measurement valid: `{measurement.get('measurement_valid')}`",
        f"- completed condition checkpoints: `{measurement.get('completed_condition_checkpoints')}`",
        f"- primary perturbation mismatches: `{measurement.get('primary_perturbation_mismatches')}`",
        f"- medium-reference reproduction mismatches: `{measurement.get('reference_reproduction_mismatches')}`",
        "",
        "## Boundary",
        "",
        f"- largest failing margin below boundary: `{decision.get('largest_failing_margin_below_boundary', '')}`",
        f"- minimum point-pass margin: `{decision.get('minimum_point_pass_margin', '')}`",
        f"- minimum robust-pass margin: `{decision.get('minimum_robust_pass_margin', '')}`",
        f"- recommended identity threshold: `{decision.get('recommended_identity_accept_threshold', '')}`",
        f"- worst-delay survival delta at boundary: `{decision.get('boundary_worst_delay_survival_delta', '')}`",
        f"- worst-delay IDSW delta at boundary: `{decision.get('boundary_worst_delay_idsw_delta', '')}`",
        "",
        "The reported margin is an empirical requirement under this simulated embedding generator, MATRIX slice, and threshold calibration. It is a target for real ReID evaluation, not a universal ReID constant.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _tag_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    noise_sigma: float | None,
    view_bias_sigma: float | None,
    threshold: float | None,
    cue_type: str,
    threshold_role: str = "",
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        item["embedding_noise_sigma"] = "" if noise_sigma is None else f"{float(noise_sigma):.6f}"
        item["view_bias_sigma"] = "" if view_bias_sigma is None else f"{float(view_bias_sigma):.6f}"
        item["identity_accept_threshold"] = "" if threshold is None else f"{float(threshold):.6f}"
        item["cue_type"] = cue_type
        item["threshold_role"] = threshold_role
        output.append(item)
    return output


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_manifest(output_dir / "run_manifest.json", build_manifest(args), resume=bool(args.resume))

    for delay_name in args.delay_profiles:
        fixed_delay_frames(delay_name)
    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    if args.max_rows > 0:
        observations = observations[: int(args.max_rows)]
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
    truth_lookup = build_truth_lookup(occlusion_observations)
    max_delay_frames = max(fixed_delay_frames(name) for name in args.delay_profiles)

    cue_tables: dict[float, SimulatedIdentityCueTable] = {}
    quality_rows: list[dict[str, object]] = []
    operating_rows: list[dict[str, object]] = []
    for noise_sigma in sorted(set(float(value) for value in args.embedding_noise_sigmas)):
        config = SimulatedIdentityCueConfig(
            dim=int(args.identity_dim),
            noise_sigma=noise_sigma,
            view_bias_sigma=float(args.view_bias_sigma),
            seed=int(args.seed),
        )
        table = SimulatedIdentityCueTable.from_observations(occlusion_observations, config=config)
        cue_tables[noise_sigma] = table
        same_scores, different_scores = cue_pair_scores(occlusion_observations, table)
        quality_rows.append(
            embedding_quality_row(
                noise_sigma=noise_sigma,
                view_bias_sigma=float(args.view_bias_sigma),
                dim=int(args.identity_dim),
                same_scores=same_scores,
                different_scores=different_scores,
            )
        )
        for threshold in sorted(set(float(value) for value in args.identity_thresholds)):
            operating_rows.append(
                threshold_operating_row(
                    noise_sigma=noise_sigma,
                    threshold=threshold,
                    same_scores=same_scores,
                    different_scores=different_scores,
                )
            )

    calibrated_thresholds = select_calibrated_thresholds(
        operating_rows,
        false_accept_cost=float(args.false_accept_cost),
        min_same_accept_rate=float(args.min_same_accept_rate),
    )
    for row in operating_rows:
        noise_key = f"{float(row['embedding_noise_sigma']):.6f}"
        threshold_key = f"{float(row['identity_accept_threshold']):.6f}"
        same_accept = safe_float(row.get("same_accept_rate")) or 0.0
        different_accept = safe_float(row.get("different_accept_rate")) or 0.0
        row["false_accept_cost"] = f"{float(args.false_accept_cost):.6f}"
        row["calibration_utility"] = fmt(
            same_accept - float(args.false_accept_cost) * different_accept
        )
        row["selected_for_tracking"] = int(calibrated_thresholds[noise_key] == threshold_key)

    condition_plan: list[tuple[float, float, str]] = []
    for noise_sigma in sorted(cue_tables):
        noise_key = f"{float(noise_sigma):.6f}"
        threshold = float(calibrated_thresholds[noise_key])
        role = "calibrated_reference" if math.isclose(noise_sigma, 0.15) and math.isclose(threshold, 0.25) else "calibrated"
        condition_plan.append((noise_sigma, threshold, role))
    if 0.15 in cue_tables and not any(
        math.isclose(noise, 0.15) and math.isclose(threshold, 0.25)
        for noise, threshold, _role in condition_plan
    ):
        condition_plan.append((0.15, 0.25, "reference"))
    for refinement_noise in (0.40, 0.50):
        if refinement_noise not in cue_tables:
            continue
        for threshold in sorted(set(float(value) for value in args.identity_thresholds)):
            if not any(
                math.isclose(noise, refinement_noise) and math.isclose(existing_threshold, threshold)
                for noise, existing_threshold, _role in condition_plan
            ):
                condition_plan.append((refinement_noise, threshold, "boundary_refinement"))

    expected_condition_paths: list[Path] = []
    primary_perturbation_mismatches = 0
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
            pose_xy_noise_m=float(args.pose_noise_m),
            seed=args.seed,
            profile_name=f"{delay_name}:noise={float(args.pose_noise_m):.3f}",
        )
        primary_perturbation_mismatches += count_primary_perturbations(
            clean_delayed, noisy_delayed, primary_drone_id=args.primary_drone_id
        )

        baseline_path = baseline_checkpoint_path(output_dir, delay_name)
        if not (bool(args.resume) and baseline_path.exists()):
            print(f"[cue-boundary] delay={delay_name} baseline start", flush=True)
            primary_run = matrix_run_from_reanchoring(
                run_primary_only_sort(
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
            )
            drop_run = matrix_run_from_reanchoring(
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
                )
            )
            baseline_runs = {primary_run.pipeline: primary_run, drop_run.pipeline: drop_run}
            baseline_pipeline_rows = _pipeline_rows(
                runs=baseline_runs,
                strict_keys=strict_keys,
                pose_noise_m=float(args.pose_noise_m),
                cue_strength="none",
                cue_type="baseline",
                delay_name=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
            )
            baseline_episode_rows = _episode_metrics(
                runs=baseline_runs,
                episodes=metric_episodes,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                max_delay_frames=max_delay_frames,
            )
            atomic_write_json(
                baseline_path,
                {
                    "schema_version": SCHEMA_VERSION,
                    "pipeline_rows": _tag_rows(
                        baseline_pipeline_rows,
                        noise_sigma=None,
                        view_bias_sigma=None,
                        threshold=None,
                        cue_type="baseline",
                    ),
                    "episode_rows": _tag_rows(
                        baseline_episode_rows,
                        noise_sigma=None,
                        view_bias_sigma=None,
                        threshold=None,
                        cue_type="baseline",
                    ),
                    "mode_rows": [],
                },
            )
            print(f"[cue-boundary] delay={delay_name} baseline complete", flush=True)

        for noise_sigma, threshold, threshold_role in condition_plan:
            table = cue_tables[noise_sigma]
            checkpoint_path = condition_checkpoint_path(output_dir, delay_name, noise_sigma, threshold)
            expected_condition_paths.append(checkpoint_path)
            if bool(args.resume) and checkpoint_path.exists():
                print(f"[cue-boundary] resume {checkpoint_path.name}", flush=True)
                continue
            pipeline = condition_pipeline(noise_sigma, threshold)
            print(
                f"[cue-boundary] delay={delay_name} noise={noise_sigma:.3f} threshold={threshold:.3f} start",
                flush=True,
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
                identity_only_distance_threshold=(
                    args.distance_threshold * float(args.identity_only_distance_factor)
                ),
                support_measurement_noise=max(0.05, float(args.pose_noise_m)),
            )
            matrix_run = matrix_run_from_reanchoring(run)
            pipeline_rows = _pipeline_rows(
                runs={pipeline: matrix_run},
                strict_keys=strict_keys,
                pose_noise_m=float(args.pose_noise_m),
                cue_strength=f"noise_{noise_sigma:.3f}",
                cue_type="world_xy_covariance_identity",
                delay_name=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
            )
            episode_rows = _episode_metrics(
                runs={pipeline: matrix_run},
                episodes=metric_episodes,
                delay_profile=delay_name,
                delay_frames=delay_frames,
                delay_ms=delay_ms,
                frame_start=args.frame_start,
                frame_end=args.frame_end,
                max_delay_frames=max_delay_frames,
            )
            atomic_write_json(
                checkpoint_path,
                {
                    "schema_version": SCHEMA_VERSION,
                    "pipeline_rows": _tag_rows(
                        pipeline_rows,
                        noise_sigma=noise_sigma,
                        view_bias_sigma=float(args.view_bias_sigma),
                        threshold=threshold,
                        cue_type="world_xy_covariance_identity",
                        threshold_role=threshold_role,
                    ),
                    "episode_rows": _tag_rows(
                        episode_rows,
                        noise_sigma=noise_sigma,
                        view_bias_sigma=float(args.view_bias_sigma),
                        threshold=threshold,
                        cue_type="world_xy_covariance_identity",
                        threshold_role=threshold_role,
                    ),
                    "mode_rows": _tag_rows(
                        _mode_count_rows([run]),
                        noise_sigma=noise_sigma,
                        view_bias_sigma=float(args.view_bias_sigma),
                        threshold=threshold,
                        cue_type="world_xy_covariance_identity",
                        threshold_role=threshold_role,
                    ),
                },
            )
            print(
                f"[cue-boundary] delay={delay_name} noise={noise_sigma:.3f} threshold={threshold:.3f} complete",
                flush=True,
            )

    payloads = [load_checkpoint(baseline_checkpoint_path(output_dir, name)) for name in args.delay_profiles]
    payloads.extend(load_checkpoint(path) for path in expected_condition_paths)
    pipeline_rows = [dict(row) for payload in payloads for row in payload.get("pipeline_rows", [])]
    raw_episode_rows = [dict(row) for payload in payloads for row in payload.get("episode_rows", [])]
    mode_rows = [dict(row) for payload in payloads for row in payload.get("mode_rows", [])]
    episode_rows = augment_episode_rows(
        raw_episode_rows,
        truth_lookup=truth_lookup,
        gate_radius_m=args.distance_threshold,
    )
    for row in episode_rows:
        if str(row.get("cue_type")) == "world_xy_covariance_identity":
            delay_frames = safe_int(row.get("delay_frames")) or 0
            lag_frames = _best_lag_for_delay(delay_frames, args.lag_frames)
            row["lag_frames"] = lag_frames
            row["lag_eligible"] = int(delay_frames <= lag_frames)

    cell_rows = boundary_cell_rows(
        episode_rows,
        quality_rows,
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
    )
    summary_rows = boundary_summary_rows(cell_rows)
    if int(args.frame_start) == 0 and int(args.frame_end) == 999:
        reference_mismatches, reference_status = reference_reproduction_mismatches(
            cell_rows, args.reference_dir
        )
    else:
        reference_mismatches, reference_status = 0, "skipped_nonformal_range"
    completed = sum(path.exists() for path in expected_condition_paths)
    measurement_valid = bool(
        primary_perturbation_mismatches == 0
        and completed == len(expected_condition_paths)
        and reference_mismatches == 0
    )
    measurement = {
        "measurement_valid": int(measurement_valid),
        "primary_perturbation_mismatches": primary_perturbation_mismatches,
        "identity_lookup_key_uses_person_id": 0,
        "truth_source": "clean_truth_observations",
        "expected_condition_checkpoints": len(expected_condition_paths),
        "completed_condition_checkpoints": completed,
        "reference_reproduction_status": reference_status,
        "reference_reproduction_mismatches": reference_mismatches,
    }
    decision = decide_boundary(summary_rows, measurement_valid=measurement_valid)

    write_rows(output_dir / "identity_quality_pipeline_metrics.csv", pipeline_rows)
    write_rows(output_dir / "identity_quality_episode_metrics.csv", episode_rows)
    write_rows(output_dir / "identity_quality_embedding_summary.csv", quality_rows)
    write_rows(output_dir / "identity_quality_threshold_operating_points.csv", operating_rows)
    write_rows(output_dir / "identity_quality_boundary_cells.csv", cell_rows)
    write_rows(output_dir / "identity_quality_boundary_summary.csv", summary_rows)
    write_rows(output_dir / "identity_quality_mode_counts.csv", mode_rows)
    write_rows(output_dir / "identity_quality_measurement_gate.csv", [measurement])
    write_decision(output_dir / "identity_quality_decision.md", decision, measurement)


if __name__ == "__main__":
    main()
