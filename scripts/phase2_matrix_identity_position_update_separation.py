#!/usr/bin/env python3
"""Audit identity, position, and lifecycle support updates in fixed-lag tracking."""

from __future__ import annotations

import argparse
import csv
import hashlib
import heapq
import json
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

from phase2_matrix_fixed_lag_simulated_identity_cue_ablation import (  # noqa: E402
    _best_lag_for_delay,
    _pipeline_rows,
    write_rows,
)
from phase2_matrix_fixed_lag_temporal_spatial_robustness import (  # noqa: E402
    apply_support_pose_noise,
    augment_episode_rows,
    build_truth_lookup,
    count_primary_perturbations,
    safe_float,
)
from phase2_matrix_tracker_state_aware_reanchoring import _episode_metrics  # noqa: E402
from tracking.delay_injection import fixed_delay_frames, frames_to_ms  # noqa: E402
from tracking.matrix_gt import MatrixObservation, apply_delay_profile, load_matrix_observations, make_delay_profile  # noqa: E402
from tracking.matrix_identity_cue import (  # noqa: E402
    SimulatedIdentityCueTable,
    cue_config_for_strength,
    observation_sensor_key,
)
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
    filter_to_occlusion_support,
)
from tracking.matrix_real_appearance import embedding_norm_mismatches, load_embedding_cache  # noqa: E402
from tracking.matrix_reanchoring import (  # noqa: E402
    SupportUpdatePolicy,
    matrix_run_from_reanchoring,
    run_drop_delayed_sort,
    run_fixed_lag_multicue_update,
)


EXPERIMENT_ID = "exp_20260801_001_matrix_identity_position_update_separation_audit"
SCHEMA_VERSION = 1
POLICIES = (
    "identity_gated_position_only",
    "identity_only_strict",
    "identity_only_with_lifecycle",
    "current_joint_reference",
    "separated_update",
)
POLICY_MAP = {
    "identity_gated_position_only": SupportUpdatePolicy.IDENTITY_GATED_POSITION_ONLY,
    "identity_only_strict": SupportUpdatePolicy.IDENTITY_ONLY_STRICT,
    "identity_only_with_lifecycle": SupportUpdatePolicy.IDENTITY_ONLY_WITH_LIFECYCLE,
    "current_joint_reference": SupportUpdatePolicy.CURRENT_JOINT,
    "separated_update": SupportUpdatePolicy.SEPARATED,
}


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
    parser.add_argument("--identity-sources", nargs="*", default=["osnet_x0_25_msmt17", "simulated_medium"])
    parser.add_argument("--distance-threshold", type=float, default=1.0)
    parser.add_argument("--margin-threshold", type=float, default=0.50)
    parser.add_argument("--identity-only-distance-factor", type=float, default=2.0)
    parser.add_argument("--simulated-threshold", type=float, default=0.25)
    parser.add_argument("--min-episode-length", type=int, default=2)
    parser.add_argument("--bootstrap-samples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--real-embedding-dir",
        type=Path,
        default=Path("outputs/20260731_matrix_real_embedding_quality_transfer"),
    )
    parser.add_argument(
        "--simulated-reference-dir",
        type=Path,
        default=Path("outputs/20260726_matrix_fixed_lag_simulated_identity_cue_ablation"),
    )
    parser.add_argument(
        "--zero-noise-reference-dir",
        type=Path,
        default=Path("outputs/20260724_matrix_tracker_state_aware_reanchoring"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260801_matrix_identity_position_update_separation_audit"),
    )
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def duration(seconds: float) -> str:
    value = max(0, int(seconds))
    return f"{value // 3600:02d}:{(value % 3600) // 60:02d}:{value % 60:02d}"


class ProgressPrinter:
    def __init__(self, *, frame_start: int, frame_end: int, every: int, total: int) -> None:
        self.frame_start = int(frame_start)
        self.frame_end = int(frame_end)
        self.every = max(1, int(every))
        self.total = max(1, int(total))
        self.started = time.perf_counter()

    def callback(self, *, index: int, description: str, condition_started: float):
        def report(frame_id: int) -> None:
            done = int(frame_id) - self.frame_start + 1
            frames = self.frame_end - self.frame_start + 1
            elapsed = time.perf_counter() - condition_started
            eta = elapsed / max(done, 1) * max(frames - done, 0)
            print(
                f"[3/4][track] condition={index}/{self.total} {description} "
                f"frame={frame_id}/{self.frame_end} elapsed={duration(elapsed)} eta={duration(eta)}",
                flush=True,
            )

        return report

    def condition(self, index: int, description: str, checkpoint: Path, *, resumed: bool = False) -> None:
        elapsed = time.perf_counter() - self.started
        status = "resume: skip completed" if resumed else "complete"
        print(
            f"[3/4][track] condition={index}/{self.total} {status} {description} "
            f"elapsed={duration(elapsed)} checkpoint={checkpoint}",
            flush=True,
        )


def stable_identity_fold(person_id: int, *, seed: int) -> int:
    digest = hashlib.sha256(f"{int(seed)}:person:{int(person_id)}".encode("ascii")).digest()
    return int.from_bytes(digest[:8], "little") % 2


def identity_key_uses_person_id(observations: Sequence[MatrixObservation]) -> int:
    from dataclasses import replace

    for observation in observations[:100]:
        changed = replace(observation, person_id=int(observation.person_id) + 1_000_000)
        if observation_sensor_key(observation) != observation_sensor_key(changed):
            return 1
    return 0


def threshold_by_fold(real_embedding_dir: Path, backend: str) -> dict[int, float]:
    calibration = {
        int(row["evaluation_fold"]): float(row["selected_threshold"])
        for row in read_rows(real_embedding_dir / "real_embedding_threshold_calibration.csv")
        if row.get("backend") == backend
    }
    runtime: dict[int, float] = {}
    for row in read_rows(real_embedding_dir / "real_embedding_pipeline_metrics.csv"):
        if (
            row.get("backend") == backend
            and row.get("pipeline") == "fixed_lag_world_xy_covariance_real_appearance"
            and row.get("threshold_role") == "selected"
        ):
            runtime[int(row["evaluation_fold"])] = float(row["identity_accept_threshold"])
    if set(calibration) != {0, 1} or set(runtime) != {0, 1}:
        raise ValueError(
            f"expected calibration/runtime thresholds for folds 0 and 1, got {sorted(calibration)}/{sorted(runtime)}"
        )
    for fold in (0, 1):
        if abs(calibration[fold] - runtime[fold]) > 1.0e-4:
            raise ValueError(
                f"calibration/runtime threshold mismatch for fold {fold}: {calibration[fold]} vs {runtime[fold]}"
            )
    return runtime


def checkpoint_name(source: str, fold: int, delay: str, policy: str) -> str:
    return f"{source}__fold{fold}__{delay}__{policy}"


def diagnostic_key(row: Mapping[str, object]) -> tuple[str, ...]:
    return tuple(
        str(row.get(field, ""))
        for field in (
            "pipeline",
            "delay_profile",
            "current_frame",
            "capture_time",
            "arrival_time",
            "drone_id",
            "position_id",
            "bbox_xyxy",
            "track_id",
        )
    )


def deduplicate_diagnostics(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    latest: dict[tuple[str, ...], dict[str, object]] = {}
    for row in rows:
        if str(row.get("source", "")) != "support":
            continue
        latest[diagnostic_key(row)] = dict(row)
    return list(latest.values())


def tag_rows(
    rows: Iterable[Mapping[str, object]],
    *,
    source: str,
    fold: int,
    threshold: float | None,
    policy: str,
) -> list[dict[str, object]]:
    return [
        {
            **dict(row),
            "identity_source": source,
            "evaluation_fold": fold,
            "identity_accept_threshold": "" if threshold is None else f"{float(threshold):.6f}",
            "support_update_policy": policy,
        }
        for row in rows
    ]


def parse_state_xy(value: object) -> np.ndarray | None:
    text = str(value or "")
    if not text:
        return None
    parts = text.split(",")
    if len(parts) < 2:
        return None
    return np.asarray([float(parts[0]), float(parts[1])], dtype=np.float64)


def annotate_action_truth(
    rows: Sequence[Mapping[str, object]],
    truth: Mapping[tuple[int, int], np.ndarray],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        key = (int(item.get("capture_time", 0)), int(item.get("person_id_eval_only", -1)))
        truth_xy = truth.get(key)
        before = parse_state_xy(item.get("state_before"))
        after = parse_state_xy(item.get("state_after"))
        before_error = None if truth_xy is None or before is None else float(np.linalg.norm(before - truth_xy))
        after_error = None if truth_xy is None or after is None else float(np.linalg.norm(after - truth_xy))
        delta = None if before_error is None or after_error is None else after_error - before_error
        item.update(
            {
                "clean_target_error_before_m": "" if before_error is None else f"{before_error:.6f}",
                "clean_target_error_after_m": "" if after_error is None else f"{after_error:.6f}",
                "clean_target_error_delta_m": "" if delta is None else f"{delta:.6f}",
                "harmful_position_update": int(
                    str(item.get("position_applied", "0")) == "1" and delta is not None and delta > 1.0e-9
                ),
            }
        )
        output.append(item)
    return output


def action_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(
            str(row.get("identity_source", "")),
            str(row.get("evaluation_fold", "")),
            str(row.get("delay_profile", "")),
            str(row.get("pipeline", "")),
        )].append(row)
    output: list[dict[str, object]] = []
    for key, values in sorted(grouped.items()):
        shifts = [safe_float(row.get("kinematic_shift_m")) for row in values]
        shifts = [value for value in shifts if value is not None]
        position_rows = [row for row in values if str(row.get("position_applied", "0")) == "1"]
        output.append(
            {
                "identity_source": key[0],
                "evaluation_fold": key[1],
                "delay_profile": key[2],
                "pipeline": key[3],
                "n_support_actions": len(values),
                "n_identity_applied": sum(str(row.get("identity_applied", "0")) == "1" for row in values),
                "n_position_applied": len(position_rows),
                "n_lifecycle_applied": sum(str(row.get("lifecycle_applied", "0")) == "1" for row in values),
                "n_harmful_position_updates": sum(str(row.get("harmful_position_update", "0")) == "1" for row in values),
                "harmful_position_fraction": "" if not position_rows else f"{sum(str(row.get('harmful_position_update', '0')) == '1' for row in position_rows) / len(position_rows):.6f}",
                "mean_kinematic_shift_m": "" if not shifts else f"{float(np.mean(shifts)):.6f}",
            }
        )
    return output


def combine_action_diagnostics(
    paths: Sequence[Path],
    output_path: Path,
    truth: Mapping[tuple[int, int], np.ndarray],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    fieldnames: list[str] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
        for field in header:
            if field not in fieldnames:
                fieldnames.append(field)
    for field in (
        "clean_target_error_before_m",
        "clean_target_error_after_m",
        "clean_target_error_delta_m",
        "harmful_position_update",
    ):
        if field not in fieldnames:
            fieldnames.append(field)

    grouped: dict[tuple[str, str, str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    harmful_heap: list[tuple[float, int, dict[str, object]]] = []
    row_index = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output_handle:
        writer = csv.DictWriter(output_handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for path in paths:
            with path.open("r", encoding="utf-8", newline="") as input_handle:
                for raw in csv.DictReader(input_handle):
                    row = annotate_action_truth([raw], truth)[0]
                    writer.writerow(row)
                    key = (
                        str(row.get("identity_source", "")),
                        str(row.get("evaluation_fold", "")),
                        str(row.get("delay_profile", "")),
                        str(row.get("pipeline", "")),
                    )
                    stats = grouped[key]
                    stats["n_support_actions"] += 1
                    stats["n_identity_applied"] += int(str(row.get("identity_applied", "0")) == "1")
                    position_applied = int(str(row.get("position_applied", "0")) == "1")
                    stats["n_position_applied"] += position_applied
                    stats["n_lifecycle_applied"] += int(str(row.get("lifecycle_applied", "0")) == "1")
                    harmful = int(str(row.get("harmful_position_update", "0")) == "1")
                    stats["n_harmful_position_updates"] += harmful
                    shift = safe_float(row.get("kinematic_shift_m"))
                    if shift is not None:
                        stats["kinematic_shift_sum"] += shift
                        stats["kinematic_shift_count"] += 1
                    if harmful:
                        delta = safe_float(row.get("clean_target_error_delta_m")) or 0.0
                        item = (float(delta), row_index, row)
                        if len(harmful_heap) < 200:
                            heapq.heappush(harmful_heap, item)
                        elif item[0] > harmful_heap[0][0]:
                            heapq.heapreplace(harmful_heap, item)
                    row_index += 1

    summaries: list[dict[str, object]] = []
    for key, stats in sorted(grouped.items()):
        position_count = int(stats["n_position_applied"])
        shift_count = int(stats["kinematic_shift_count"])
        summaries.append(
            {
                "identity_source": key[0],
                "evaluation_fold": key[1],
                "delay_profile": key[2],
                "pipeline": key[3],
                "n_support_actions": int(stats["n_support_actions"]),
                "n_identity_applied": int(stats["n_identity_applied"]),
                "n_position_applied": position_count,
                "n_lifecycle_applied": int(stats["n_lifecycle_applied"]),
                "n_harmful_position_updates": int(stats["n_harmful_position_updates"]),
                "harmful_position_fraction": "" if not position_count else f"{stats['n_harmful_position_updates'] / position_count:.6f}",
                "mean_kinematic_shift_m": "" if not shift_count else f"{stats['kinematic_shift_sum'] / shift_count:.6f}",
            }
        )
    cases = [item[2] for item in sorted(harmful_heap, key=lambda item: item[0], reverse=True)]
    return summaries, cases


def eligible_rows(
    rows: Sequence[Mapping[str, object]], source: str, fold: int, *, identity_fold_seed: int
) -> list[Mapping[str, object]]:
    result = []
    for row in rows:
        if str(row.get("identity_source")) != source or str(row.get("eligible", "0")) != "1":
            continue
        if str(row.get("useful_window_bucket")) != "[0.75,1]":
            continue
        if source == "osnet_x0_25_msmt17" and stable_identity_fold(
            int(row["person_id"]), seed=identity_fold_seed
        ) != int(fold):
            continue
        result.append(row)
    return result


def cluster_bootstrap_ci(
    paired: Sequence[tuple[int, float]], *, samples: int, seed: int
) -> tuple[float | None, float | None]:
    if not paired:
        return None, None
    grouped: dict[int, list[float]] = defaultdict(list)
    for person_id, value in paired:
        grouped[int(person_id)].append(float(value))
    people = sorted(grouped)
    if len(people) == 1 or samples <= 0:
        mean_value = float(np.mean([value for values in grouped.values() for value in values]))
        return mean_value, mean_value
    rng = np.random.default_rng(int(seed))
    means = []
    for _index in range(int(samples)):
        selected = rng.choice(people, size=len(people), replace=True)
        values = [value for person in selected for value in grouped[int(person)]]
        means.append(float(np.mean(values)))
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def episode_map(rows: Sequence[Mapping[str, object]], pipeline: str) -> dict[tuple[str, str, str, str], Mapping[str, object]]:
    return {
        (str(row["delay_profile"]), str(row["person_id"]), str(row["start_frame"]), str(row["end_frame"])): row
        for row in rows
        if str(row.get("pipeline")) == pipeline
    }


def contrast_rows(
    episode_rows: Sequence[Mapping[str, object]], *, bootstrap_samples: int, seed: int
) -> list[dict[str, object]]:
    comparisons = (
        ("identity_candidate_selection", "identity_gated_position_only", "covariance_position_only"),
        ("separated_vs_current", "separated_update", "current_joint_reference"),
        ("lifecycle_effect", "identity_only_with_lifecycle", "identity_only_strict"),
        ("support_template_effect", "current_joint_reference", "identity_gated_position_only"),
    )
    output: list[dict[str, object]] = []
    for source in ("osnet_x0_25_msmt17", "simulated_medium"):
        folds = (0, 1) if source == "osnet_x0_25_msmt17" else (-1,)
        for fold in folds:
            rows = eligible_rows(episode_rows, source, fold, identity_fold_seed=seed)
            for delay in ("fixed_2", "fixed_3"):
                delayed = [row for row in rows if str(row.get("delay_profile")) == delay]
                for name, left_name, right_name in comparisons:
                    left = episode_map(delayed, left_name)
                    right = episode_map(delayed, right_name)
                    paired_survival: list[tuple[int, float]] = []
                    paired_idsw: list[float] = []
                    right_idsw_values: list[float] = []
                    for key in sorted(set(left) & set(right)):
                        left_survival = safe_float(left[key].get("identity_survival_rate"))
                        right_survival = safe_float(right[key].get("identity_survival_rate"))
                        left_idsw = safe_float(left[key].get("window_idsw"))
                        right_idsw = safe_float(right[key].get("window_idsw"))
                        if left_survival is not None and right_survival is not None:
                            paired_survival.append((int(key[1]), left_survival - right_survival))
                        if left_idsw is not None and right_idsw is not None:
                            paired_idsw.append(left_idsw - right_idsw)
                            right_idsw_values.append(right_idsw)
                    ci_low, ci_high = cluster_bootstrap_ci(
                        paired_survival,
                        samples=bootstrap_samples,
                        seed=seed + fold + fixed_delay_frames(delay) * 101 + len(name),
                    )
                    output.append(
                        {
                            "identity_source": source,
                            "evaluation_fold": fold,
                            "delay_profile": delay,
                            "contrast": name,
                            "left_pipeline": left_name,
                            "right_pipeline": right_name,
                            "n_episodes": len(paired_survival),
                            "mean_survival_difference": "" if not paired_survival else f"{float(np.mean([value for _person, value in paired_survival])):.6f}",
                            "survival_ci_low": "" if ci_low is None else f"{ci_low:.6f}",
                            "survival_ci_high": "" if ci_high is None else f"{ci_high:.6f}",
                            "mean_window_idsw_difference": "" if not paired_idsw else f"{float(np.mean(paired_idsw)):.6f}",
                            "right_mean_window_idsw": "" if not right_idsw_values else f"{float(np.mean(right_idsw_values)):.6f}",
                        }
                    )
    return output


def reference_zero_noise(path: Path) -> dict[str, float]:
    rows = read_rows(path / "reanchoring_pipeline_metrics.csv")
    result: dict[str, float] = {}
    for delay, pipeline in (("fixed_2", "fixed_lag_oosm_lag2"), ("fixed_3", "fixed_lag_oosm_lag3")):
        matches = [row for row in rows if row.get("delay_profile") == delay and row.get("pipeline") == pipeline]
        if len(matches) != 1:
            raise ValueError(f"missing unique zero-noise reference for {delay}/{pipeline}")
        result[delay] = float(matches[0]["occlusion_idf1"])
    return result


def headroom_rows(
    pipeline_rows: Sequence[Mapping[str, object]], zero_noise: Mapping[str, float]
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for source in ("osnet_x0_25_msmt17", "simulated_medium"):
        for delay in ("fixed_2", "fixed_3"):
            source_rows = [
                row for row in pipeline_rows
                if str(row.get("identity_source")) == source and str(row.get("delay_profile")) == delay
                and str(row.get("pipeline")) in POLICIES
            ]
            by_pipeline: dict[str, list[float]] = defaultdict(list)
            for row in source_rows:
                value = safe_float(row.get("occlusion_idf1"))
                if value is not None:
                    by_pipeline[str(row["pipeline"])].append(value)
            drop_values = [
                safe_float(row.get("occlusion_idf1")) for row in pipeline_rows
                if str(row.get("identity_source")) == "baseline"
                and str(row.get("delay_profile")) == delay
                and str(row.get("pipeline")) == "drop_delayed_sort"
            ]
            drop_values = [value for value in drop_values if value is not None]
            if not by_pipeline or not drop_values:
                continue
            means = {pipeline: float(np.mean(values)) for pipeline, values in by_pipeline.items()}
            best_pipeline = max(means, key=means.get)
            best = means[best_pipeline]
            drop = float(np.mean(drop_values))
            denominator = float(zero_noise[delay]) - drop
            recovery = 0.0 if abs(denominator) < 1.0e-12 else (best - drop) / denominator
            output.append(
                {
                    "identity_source": source,
                    "delay_profile": delay,
                    "best_pipeline": best_pipeline,
                    "best_occlusion_idf1": f"{best:.6f}",
                    "drop_occlusion_idf1": f"{drop:.6f}",
                    "zero_noise_occlusion_idf1": f"{float(zero_noise[delay]):.6f}",
                    "headroom_recovery_ratio": f"{recovery:.6f}",
                }
            )
    return output


def reference_mismatches(
    pipeline_rows: Sequence[Mapping[str, object]], real_dir: Path, simulated_dir: Path
) -> tuple[int, int]:
    real_reference = read_rows(real_dir / "real_embedding_pipeline_metrics.csv")
    simulated_reference = read_rows(simulated_dir / "sim_identity_pipeline_metrics.csv")
    real_mismatch = 0
    for row in pipeline_rows:
        if str(row.get("identity_source")) != "osnet_x0_25_msmt17" or str(row.get("pipeline")) != "current_joint_reference":
            continue
        matches = [
            ref for ref in real_reference
            if ref.get("backend") == "osnet_x0_25_msmt17"
            and ref.get("delay_profile") == str(row.get("delay_profile"))
            and ref.get("pipeline") == "fixed_lag_world_xy_covariance_real_appearance"
            and ref.get("evaluation_fold") == str(row.get("evaluation_fold"))
            and ref.get("threshold_role") == "selected"
        ]
        if len(matches) != 1:
            real_mismatch += 1
            continue
        for field in ("aggregate_idf1", "aggregate_idsw", "occlusion_idf1", "occlusion_idsw"):
            if abs(float(row[field]) - float(matches[0][field])) > 1.0e-6:
                real_mismatch += 1
                break
    simulated_mismatch = 0
    for row in pipeline_rows:
        if str(row.get("identity_source")) != "simulated_medium" or str(row.get("pipeline")) != "current_joint_reference":
            continue
        matches = [
            ref for ref in simulated_reference
            if ref.get("delay_profile") == str(row.get("delay_profile"))
            and ref.get("pipeline") == "fixed_lag_world_xy_covariance_identity_medium"
        ]
        if len(matches) != 1:
            simulated_mismatch += 1
            continue
        for field in ("aggregate_idf1", "aggregate_idsw", "occlusion_idf1", "occlusion_idsw"):
            if abs(float(row[field]) - float(matches[0][field])) > 1.0e-6:
                simulated_mismatch += 1
                break
    return real_mismatch, simulated_mismatch


def decision_flags(
    contrasts: Sequence[Mapping[str, object]], headroom: Sequence[Mapping[str, object]], measurement_valid: bool
) -> dict[str, object]:
    def rows_for(contrast: str, source: str) -> list[Mapping[str, object]]:
        return [row for row in contrasts if row.get("contrast") == contrast and row.get("identity_source") == source]

    def value(row: Mapping[str, object], field: str, default: float) -> float:
        parsed = safe_float(row.get(field))
        return default if parsed is None else parsed

    candidate = rows_for("identity_candidate_selection", "osnet_x0_25_msmt17")
    candidate_supported = bool(candidate) and all(
        value(row, "mean_survival_difference", -1.0) >= 0.05
        and value(row, "survival_ci_low", -1.0) > 0.0
        and value(row, "mean_window_idsw_difference", 1.0) <= 0.0
        for row in candidate
    )
    separated = rows_for("separated_vs_current", "osnet_x0_25_msmt17")
    separated_supported = bool(separated) and all(
        (
            value(row, "mean_survival_difference", -1.0) >= 0.03
            or (
                value(row, "mean_survival_difference", -1.0) >= -0.01
                and value(row, "mean_window_idsw_difference", 0.0)
                <= -0.10 * max(value(row, "right_mean_window_idsw", 0.0), 1.0e-12)
            )
        )
        for row in separated
    )
    lifecycle = [row for source in ("osnet_x0_25_msmt17", "simulated_medium") for row in rows_for("lifecycle_effect", source)]
    lifecycle_dominant = bool(lifecycle) and all(
        value(row, "mean_survival_difference", -1.0) >= 0.05 for row in lifecycle
    )
    simulated_headroom = [row for row in headroom if row.get("identity_source") == "simulated_medium"]
    tracker_bottleneck = bool(simulated_headroom) and any(
        value(row, "headroom_recovery_ratio", 0.0) < 0.60 for row in simulated_headroom
    )
    if not measurement_valid:
        next_branch = "measurement_invalid"
    elif separated_supported:
        next_branch = "continue_separated_update_with_real_geometry"
    elif tracker_bottleneck:
        next_branch = "appearance_assisted_primary_reacquisition_and_tracklet_memory"
    elif candidate_supported:
        next_branch = "identity_gate_only_supported"
    else:
        next_branch = "inconclusive"
    return {
        "measurement_valid": int(measurement_valid),
        "identity_candidate_selection_supported": int(candidate_supported),
        "separated_update_supported": int(separated_supported),
        "lifecycle_effect_dominant": int(lifecycle_dominant),
        "tracker_architecture_bottleneck": int(tracker_bottleneck),
        "next_branch": next_branch,
    }


def write_decision(path: Path, flags: Mapping[str, object], headroom: Sequence[Mapping[str, object]]) -> None:
    lines = [
        "# Identity-Position Update Separation Decision",
        "",
        f"**Next branch**: `{flags['next_branch']}`",
        "",
        f"- measurement valid: `{flags['measurement_valid']}`",
        f"- identity candidate selection supported: `{flags['identity_candidate_selection_supported']}`",
        f"- separated update supported: `{flags['separated_update_supported']}`",
        f"- lifecycle effect dominant: `{flags['lifecycle_effect_dominant']}`",
        f"- tracker architecture bottleneck: `{flags['tracker_architecture_bottleneck']}`",
        "",
        "## Zero-noise headroom recovery",
        "",
        "| Identity source | Delay | Best pipeline | Best IDF1 | Recovery ratio |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in headroom:
        lines.append(
            f"| {row['identity_source']} | {row['delay_profile']} | {row['best_pipeline']} | "
            f"{row['best_occlusion_idf1']} | {row['headroom_recovery_ratio']} |"
        )
    lines.extend(
        [
            "",
            "`identity_only_strict` failing does not show that identity evidence is useless. It shows that the current geometry-only primary association has no direct path from identity state to published predictions.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/4][prepare] experiment={EXPERIMENT_ID} loading observations", flush=True)
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
    occlusion_keys = build_occlusion_event_keys(all_episodes, min_episode_length=1)
    strict_keys = build_occlusion_event_keys(metric_episodes, min_episode_length=1)
    occlusion_observations = filter_to_occlusion_support(
        observations,
        occlusion_event_keys=occlusion_keys,
        primary_drone_id=args.primary_drone_id,
    )
    truth_lookup = build_truth_lookup(occlusion_observations)
    max_delay_frames = max(fixed_delay_frames(name) for name in args.delay_profiles)

    osnet_cache = args.real_embedding_dir / "embedding_cache" / "osnet_x0_25_msmt17.npz"
    osnet_table = load_embedding_cache(osnet_cache)
    thresholds = threshold_by_fold(args.real_embedding_dir, "osnet_x0_25_msmt17")
    simulated_table = SimulatedIdentityCueTable.from_observations(
        occlusion_observations,
        config=cue_config_for_strength("medium", seed=args.seed, dim=128),
    )
    print(
        f"[2/4][identity] osnet={len(osnet_table.embeddings)} simulated={len(simulated_table.embeddings)} "
        f"thresholds={thresholds}",
        flush=True,
    )

    source_specs = []
    if "osnet_x0_25_msmt17" in args.identity_sources:
        source_specs.extend(
            [
                ("osnet_x0_25_msmt17", 0, thresholds[0], osnet_table.embeddings),
                ("osnet_x0_25_msmt17", 1, thresholds[1], osnet_table.embeddings),
            ]
        )
    if "simulated_medium" in args.identity_sources:
        source_specs.append(("simulated_medium", -1, args.simulated_threshold, simulated_table.embeddings))
    unknown_sources = sorted(set(args.identity_sources) - {"osnet_x0_25_msmt17", "simulated_medium"})
    if unknown_sources:
        raise ValueError(f"unsupported identity sources: {unknown_sources}")
    total_conditions = len(args.delay_profiles) * (2 + len(POLICIES) * len(source_specs))
    progress = ProgressPrinter(
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        every=args.progress_every,
        total=total_conditions,
    )
    condition_index = 0
    pipeline_rows: list[dict[str, object]] = []
    raw_episode_rows: list[dict[str, object]] = []
    diagnostic_paths: list[Path] = []
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
            pose_xy_noise_m=args.pose_noise_m,
            seed=args.seed,
            profile_name=f"{delay_name}:noise={args.pose_noise_m:.3f}",
        )
        primary_perturbation_mismatches += count_primary_perturbations(
            clean_delayed,
            noisy_delayed,
            primary_drone_id=args.primary_drone_id,
        )

        baseline_runs = []
        for pipeline in ("drop_delayed_sort", "covariance_position_only"):
            condition_index += 1
            name = checkpoint_name("baseline", -1, delay_name, pipeline)
            checkpoint = checkpoint_dir / f"{name}.json"
            diagnostic_path = checkpoint_dir / f"{name}.diagnostics.csv"
            if args.resume and checkpoint.is_file():
                payload = json.loads(checkpoint.read_text(encoding="utf-8"))
                pipeline_rows.extend(payload["pipeline_rows"])
                raw_episode_rows.extend(payload["episode_rows"])
                if not diagnostic_path.is_file():
                    raise FileNotFoundError(f"checkpoint exists without diagnostics: {diagnostic_path}")
                diagnostic_paths.append(diagnostic_path)
                progress.condition(condition_index, name, checkpoint, resumed=True)
                continue
            started = time.perf_counter()
            callback = progress.callback(index=condition_index, description=name, condition_started=started)
            if pipeline == "drop_delayed_sort":
                run = run_drop_delayed_sort(
                    noisy_delayed,
                    truth_observations=clean_delayed,
                    delay_profile=delay_name,
                    delay_frames=delay_frames,
                    delay_ms=delay_ms,
                    frame_start=args.frame_start,
                    frame_end=args.frame_end,
                    distance_threshold=args.distance_threshold,
                    primary_drone_id=args.primary_drone_id,
                    progress_callback=callback,
                    progress_every=args.progress_every,
                )
            else:
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
                    occlusion_keys=occlusion_keys,
                    pipeline=pipeline,
                    support_measurement_noise=max(0.05, args.pose_noise_m),
                    support_update_policy=SupportUpdatePolicy.POSITION_ONLY,
                    support_margin_threshold=args.margin_threshold,
                    progress_callback=callback,
                    progress_every=args.progress_every,
                )
            matrix_run = matrix_run_from_reanchoring(run)
            tagged_pipeline = tag_rows(
                [row for row in _pipeline_rows(
                    runs={pipeline: matrix_run},
                    strict_keys=strict_keys,
                    pose_noise_m=args.pose_noise_m,
                    cue_strength="none",
                    cue_type="baseline",
                    delay_name=delay_name,
                    delay_frames=delay_frames,
                    delay_ms=delay_ms,
                ) if str(row.get("pipeline")) == pipeline],
                source="baseline",
                fold=-1,
                threshold=None,
                policy=pipeline,
            )
            tagged_episode = tag_rows(
                _episode_metrics(
                    runs={pipeline: matrix_run},
                    episodes=metric_episodes,
                    delay_profile=delay_name,
                    delay_frames=delay_frames,
                    delay_ms=delay_ms,
                    frame_start=args.frame_start,
                    frame_end=args.frame_end,
                    max_delay_frames=max_delay_frames,
                ),
                source="baseline",
                fold=-1,
                threshold=None,
                policy=pipeline,
            )
            tagged_diagnostics = tag_rows(
                deduplicate_diagnostics(run.diagnostics),
                source="baseline",
                fold=-1,
                threshold=None,
                policy=pipeline,
            )
            write_rows(diagnostic_path, tagged_diagnostics)
            payload = {"pipeline_rows": tagged_pipeline, "episode_rows": tagged_episode, "diagnostics_file": diagnostic_path.name}
            atomic_write_json(checkpoint, payload)
            pipeline_rows.extend(tagged_pipeline)
            raw_episode_rows.extend(tagged_episode)
            diagnostic_paths.append(diagnostic_path)
            progress.condition(condition_index, name, checkpoint)
            baseline_runs.append(matrix_run)

        for source, fold, threshold, embeddings in source_specs:
            for pipeline in POLICIES:
                condition_index += 1
                name = checkpoint_name(source, fold, delay_name, pipeline)
                checkpoint = checkpoint_dir / f"{name}.json"
                diagnostic_path = checkpoint_dir / f"{name}.diagnostics.csv"
                if args.resume and checkpoint.is_file():
                    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
                    pipeline_rows.extend(payload["pipeline_rows"])
                    raw_episode_rows.extend(payload["episode_rows"])
                    if not diagnostic_path.is_file():
                        raise FileNotFoundError(f"checkpoint exists without diagnostics: {diagnostic_path}")
                    diagnostic_paths.append(diagnostic_path)
                    progress.condition(condition_index, name, checkpoint, resumed=True)
                    continue
                started = time.perf_counter()
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
                    occlusion_keys=occlusion_keys,
                    pipeline=pipeline,
                    appearance_embeddings=embeddings,
                    use_identity_gate=True,
                    identity_accept_threshold=threshold,
                    identity_only_distance_threshold=args.distance_threshold * args.identity_only_distance_factor,
                    support_measurement_noise=max(0.05, args.pose_noise_m),
                    support_update_policy=POLICY_MAP[pipeline],
                    support_margin_threshold=args.margin_threshold,
                    progress_callback=progress.callback(
                        index=condition_index,
                        description=name,
                        condition_started=started,
                    ),
                    progress_every=args.progress_every,
                )
                matrix_run = matrix_run_from_reanchoring(run)
                tagged_pipeline = tag_rows(
                    [row for row in _pipeline_rows(
                        runs={pipeline: matrix_run},
                        strict_keys=strict_keys,
                        pose_noise_m=args.pose_noise_m,
                        cue_strength=source,
                        cue_type="update_separation",
                        delay_name=delay_name,
                        delay_frames=delay_frames,
                        delay_ms=delay_ms,
                    ) if str(row.get("pipeline")) == pipeline],
                    source=source,
                    fold=fold,
                    threshold=threshold,
                    policy=pipeline,
                )
                tagged_episode = tag_rows(
                    _episode_metrics(
                        runs={pipeline: matrix_run},
                        episodes=metric_episodes,
                        delay_profile=delay_name,
                        delay_frames=delay_frames,
                        delay_ms=delay_ms,
                        frame_start=args.frame_start,
                        frame_end=args.frame_end,
                        max_delay_frames=max_delay_frames,
                    ),
                    source=source,
                    fold=fold,
                    threshold=threshold,
                    policy=pipeline,
                )
                tagged_diagnostics = tag_rows(
                    deduplicate_diagnostics(run.diagnostics),
                    source=source,
                    fold=fold,
                    threshold=threshold,
                    policy=pipeline,
                )
                write_rows(diagnostic_path, tagged_diagnostics)
                payload = {"pipeline_rows": tagged_pipeline, "episode_rows": tagged_episode, "diagnostics_file": diagnostic_path.name}
                atomic_write_json(checkpoint, payload)
                pipeline_rows.extend(tagged_pipeline)
                raw_episode_rows.extend(tagged_episode)
                diagnostic_paths.append(diagnostic_path)
                progress.condition(condition_index, name, checkpoint)

    # Add one shared drop row per delay/source so episode deltas can be computed within each source.
    baseline_drop_pipeline = [row for row in pipeline_rows if row.get("identity_source") == "baseline" and row.get("pipeline") == "drop_delayed_sort"]
    baseline_drop_episodes = [row for row in raw_episode_rows if row.get("identity_source") == "baseline" and row.get("pipeline") == "drop_delayed_sort"]
    for source, folds in (("osnet_x0_25_msmt17", (0, 1)), ("simulated_medium", (-1,))):
        for fold in folds:
            pipeline_rows.extend(tag_rows(baseline_drop_pipeline, source=source, fold=fold, threshold=None, policy="drop_delayed_sort"))
            raw_episode_rows.extend(tag_rows(baseline_drop_episodes, source=source, fold=fold, threshold=None, policy="drop_delayed_sort"))
    for source, folds in (("osnet_x0_25_msmt17", (0, 1)), ("simulated_medium", (-1,))):
        for fold in folds:
            covariance_pipeline = [row for row in pipeline_rows if row.get("identity_source") == "baseline" and row.get("pipeline") == "covariance_position_only"]
            covariance_episode = [row for row in raw_episode_rows if row.get("identity_source") == "baseline" and row.get("pipeline") == "covariance_position_only"]
            pipeline_rows.extend(tag_rows(covariance_pipeline, source=source, fold=fold, threshold=None, policy="covariance_position_only"))
            raw_episode_rows.extend(tag_rows(covariance_episode, source=source, fold=fold, threshold=None, policy="covariance_position_only"))

    episode_rows = augment_episode_rows(raw_episode_rows, truth_lookup=truth_lookup, gate_radius_m=args.distance_threshold)
    for row in episode_rows:
        if row.get("lag_frames", "") == "" and row.get("pipeline") != "drop_delayed_sort":
            row["lag_frames"] = fixed_delay_frames(str(row["delay_profile"]))
            row["lag_eligible"] = 1
    action_summary_rows, case_samples = combine_action_diagnostics(
        diagnostic_paths,
        output_dir / "update_separation_action_diagnostics.csv",
        truth_lookup,
    )
    contrasts = contrast_rows(episode_rows, bootstrap_samples=args.bootstrap_samples, seed=args.seed)
    zero_noise = reference_zero_noise(args.zero_noise_reference_dir)
    headroom = headroom_rows(pipeline_rows, zero_noise)
    reference_status = "checked" if args.frame_start == 0 and args.frame_end == 999 else "not_applicable_frame_range"
    if reference_status == "checked":
        real_mismatch, simulated_mismatch = reference_mismatches(
            pipeline_rows,
            args.real_embedding_dir,
            args.simulated_reference_dir,
        )
    else:
        real_mismatch, simulated_mismatch = 0, 0
    expected_checkpoints = total_conditions
    completed_checkpoints = len(list(checkpoint_dir.glob("*.json")))
    measurement = {
        "measurement_valid": int(
            primary_perturbation_mismatches == 0
            and embedding_norm_mismatches(osnet_table) == 0
            and identity_key_uses_person_id(occlusion_observations) == 0
            and real_mismatch == 0
            and simulated_mismatch == 0
            and completed_checkpoints == expected_checkpoints
        ),
        "primary_perturbation_mismatches": primary_perturbation_mismatches,
        "embedding_norm_mismatches": embedding_norm_mismatches(osnet_table),
        "identity_lookup_key_uses_person_id": identity_key_uses_person_id(occlusion_observations),
        "real_current_joint_reference_mismatches": real_mismatch,
        "simulated_current_joint_reference_mismatches": simulated_mismatch,
        "reference_reproduction_status": reference_status,
        "expected_condition_checkpoints": expected_checkpoints,
        "completed_condition_checkpoints": completed_checkpoints,
    }
    flags = decision_flags(contrasts, headroom, bool(measurement["measurement_valid"]))
    write_rows(output_dir / "update_separation_pipeline_metrics.csv", pipeline_rows)
    write_rows(output_dir / "update_separation_episode_metrics.csv", episode_rows)
    write_rows(output_dir / "update_separation_effect_summary.csv", contrasts)
    write_rows(output_dir / "update_separation_headroom_recovery.csv", headroom)
    write_rows(output_dir / "update_separation_case_samples.csv", case_samples)
    write_rows(output_dir / "update_separation_measurement_gate.csv", [{**measurement, **flags}])
    write_rows(output_dir / "update_separation_action_summary.csv", action_summary_rows)
    write_decision(output_dir / "update_separation_decision.md", flags, headroom)
    atomic_write_json(
        output_dir / "run_manifest.json",
        {
            "schema_version": SCHEMA_VERSION,
            "experiment_id": EXPERIMENT_ID,
            "frame_start": args.frame_start,
            "frame_end": args.frame_end,
            "delay_profiles": args.delay_profiles,
            "lag_frames": args.lag_frames,
            "pose_noise_m": args.pose_noise_m,
            "identity_sources": args.identity_sources,
            "seed": args.seed,
        },
    )
    print(
        f"[4/4][finalize] decision={flags['next_branch']} measurement_valid={flags['measurement_valid']} "
        f"outputs={output_dir.resolve()}",
        flush=True,
    )


if __name__ == "__main__":
    main()
