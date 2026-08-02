#!/usr/bin/env python3
"""Repair BoT-SORT candidate recall and compare soft versus hard appearance authority."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from phase3_matrix_mobile_camera_local_tracklet_readiness import (  # noqa: E402
    _condition_name,
    _condition_paths,
    _condition_token,
    _run_condition,
    atomic_json,
    read_rows,
    summarize_quality,
    write_rows,
)
from tracking.matrix_gt import MatrixObservation, load_matrix_observations  # noqa: E402
from tracking.matrix_identity_cue import observation_sensor_key  # noqa: E402
from tracking.matrix_local_tracklet import bbox_iou  # noqa: E402
from tracking.matrix_mature_local_tracklet import validate_mature_tracker_environment  # noqa: E402
from tracking.matrix_occlusion import (  # noqa: E402
    build_frame_visibilities,
    build_occlusion_episodes,
    build_occlusion_event_keys,
)
from tracking.matrix_real_appearance import load_embedding_cache, los_visible_observations  # noqa: E402


EXPERIMENT_ID = "exp_20260802_002_matrix_botsort_candidate_gate_repair"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=199)
    parser.add_argument("--drone-ids", nargs="+", type=int, default=list(range(8)))
    parser.add_argument("--primary-drone-id", type=int, default=0)
    parser.add_argument("--proximity-thresholds", nargs="+", type=float, default=(0.1, 0.3, 0.5))
    parser.add_argument("--appearance-modes", nargs="+", choices=("soft", "hard_veto"), default=("soft", "hard_veto"))
    parser.add_argument("--track-buffer", type=int, default=5)
    parser.add_argument("--match-thresh", type=float, default=0.8)
    parser.add_argument("--osnet-threshold", type=float, default=0.785027)
    parser.add_argument("--appearance-ema", type=float, default=0.9)
    parser.add_argument("--gmc-method", default="sparseOptFlow")
    parser.add_argument("--gmc-downscale", type=int, default=2)
    parser.add_argument(
        "--gmc-reference-dir",
        type=Path,
        default=Path("outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_pilot/checkpoints/gmc"),
    )
    parser.add_argument(
        "--embedding-cache",
        type=Path,
        default=Path(
            "outputs/20260802_matrix_mobile_camera_local_tracklet_readiness_cache/"
            "osnet_x0_25_msmt17.npz"
        ),
    )
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/20260802_matrix_botsort_candidate_gate_repair_pilot"),
    )
    return parser.parse_args()


def proximity_label(value: float) -> str:
    return f"p{float(value):.2f}".replace(".", "p")


def build_repair_conditions(args: argparse.Namespace) -> list[dict[str, object]]:
    conditions = [
        {
            "pipeline": "botsort_gmc_noapp_reference",
            "track_buffer": int(args.track_buffer),
            "match_thresh": float(args.match_thresh),
            "use_gmc": True,
            "use_appearance": False,
            "appearance_mode": "none",
            "proximity_threshold": 0.5,
            "mature": True,
        }
    ]
    for proximity in args.proximity_thresholds:
        for appearance_mode in args.appearance_modes:
            conditions.append(
                {
                    "pipeline": f"botsort_gmc_osnet_{appearance_mode}_{proximity_label(proximity)}",
                    "track_buffer": int(args.track_buffer),
                    "match_thresh": float(args.match_thresh),
                    "use_gmc": True,
                    "use_appearance": True,
                    "appearance_mode": appearance_mode,
                    "proximity_threshold": float(proximity),
                    "mature": True,
                }
            )
    return conditions


def load_gmc_reference(args: argparse.Namespace, view_id: int) -> tuple[dict[int, np.ndarray], list[dict[str, str]]]:
    stem = f"D{view_id + 1}_{args.frame_start}_{args.frame_end}"
    cache_path = args.gmc_reference_dir / f"{stem}.npz"
    audit_path = args.gmc_reference_dir / f"{stem}.csv"
    if not cache_path.is_file() or not audit_path.is_file():
        raise FileNotFoundError(
            f"missing GMC reference {cache_path}; run exp_20260802_001 Pilot for the same frame range"
        )
    with np.load(cache_path) as payload:
        warps = {int(key[1:]): np.asarray(payload[key], dtype=np.float64) for key in payload.files}
    expected = set(range(int(args.frame_start), int(args.frame_end) + 1))
    if set(warps) != expected:
        raise ValueError(f"GMC reference frame mismatch for D{view_id + 1}")
    return warps, read_rows(audit_path)


def warp_bbox(bbox: Sequence[float], warp: np.ndarray) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = [float(value) for value in bbox]
    corners = np.asarray(
        [[x1, y1, 1.0], [x2, y1, 1.0], [x2, y2, 1.0], [x1, y2, 1.0]],
        dtype=np.float64,
    ).T
    transformed = np.asarray(warp, dtype=np.float64) @ corners
    return (
        float(np.min(transformed[0])),
        float(np.min(transformed[1])),
        float(np.max(transformed[0])),
        float(np.max(transformed[1])),
    )


def candidate_pair_diagnostics(
    observations: Sequence[MatrixObservation],
    embeddings: Mapping[tuple, np.ndarray],
    warps_by_view: Mapping[int, Mapping[int, np.ndarray]],
    proximity_thresholds: Sequence[float],
    *,
    identity_threshold: float,
) -> list[dict[str, object]]:
    by_image: dict[tuple[int, int], list[MatrixObservation]] = defaultdict(list)
    for observation in observations:
        by_image[(int(observation.drone_id), int(observation.frame_id))].append(observation)
    totals = {float(value): defaultdict(int) for value in proximity_thresholds}
    total_same_consecutive = 0
    first_frame = min((int(row.frame_id) for row in observations), default=0)
    for (view_id, frame_id), current in sorted(by_image.items()):
        if frame_id <= first_frame:
            continue
        previous = by_image.get((view_id, frame_id - 1), [])
        if not previous:
            continue
        warp = warps_by_view[view_id][frame_id]
        for first in previous:
            first_embedding = embeddings.get(observation_sensor_key(first))
            if first_embedding is None:
                continue
            transformed = warp_bbox(first.bbox_xyxy, warp)
            for second in current:
                second_embedding = embeddings.get(observation_sensor_key(second))
                if second_embedding is None:
                    continue
                same = int(first.person_id) == int(second.person_id)
                if same:
                    total_same_consecutive += 1
                overlap = bbox_iou(transformed, second.bbox_xyxy)
                similarity = float(np.dot(first_embedding, second_embedding))
                for proximity in proximity_thresholds:
                    threshold = float(proximity)
                    if overlap < threshold:
                        continue
                    prefix = "same" if same else "different"
                    totals[threshold][f"{prefix}_geometry_pairs"] += 1
                    if similarity >= float(identity_threshold):
                        totals[threshold][f"{prefix}_identity_pass"] += 1
    rows = []
    for proximity in sorted(totals):
        values = totals[proximity]
        same_geometry = int(values["same_geometry_pairs"])
        different_geometry = int(values["different_geometry_pairs"])
        same_pass = int(values["same_identity_pass"])
        different_pass = int(values["different_identity_pass"])
        rows.append(
            {
                "proximity_threshold": proximity,
                "total_same_consecutive_pairs": total_same_consecutive,
                "same_geometry_pairs": same_geometry,
                "different_geometry_pairs": different_geometry,
                "same_candidate_recall": same_geometry / max(total_same_consecutive, 1),
                "same_identity_accept_rate": same_pass / max(same_geometry, 1),
                "different_identity_accept_rate": different_pass / max(different_geometry, 1),
                "hard_gate_accepted_precision": same_pass / max(same_pass + different_pass, 1),
                "hard_gate_same_pair_recall": same_pass / max(total_same_consecutive, 1),
            }
        )
    return rows


def _full_readiness(row: Mapping[str, object]) -> bool:
    return (
        float(row["macro_local_idf1"]) >= 0.80
        and float(row["weighted_purity"]) >= 0.95
        and float(row["minimum_per_view_local_idf1"]) >= 0.70
        and float(row["occlusion_support_coverage"]) >= 0.90
    )


def decide(pipeline_rows: Sequence[Mapping[str, object]], measurement_valid: bool) -> tuple[str, list[str]]:
    passing = [str(row["pipeline"]) for row in pipeline_rows if _full_readiness(row)]
    if not measurement_valid:
        return "measurement_invalid", passing
    if passing:
        return "candidate_gate_repair_ready", passing
    hard_p03 = next(
        (
            row
            for row in pipeline_rows
            if str(row["pipeline"]) == "botsort_gmc_osnet_hard_veto_p0p30"
        ),
        None,
    )
    soft_p03 = next(
        (row for row in pipeline_rows if str(row["pipeline"]) == "botsort_gmc_osnet_soft_p0p30"),
        None,
    )
    if hard_p03 and soft_p03:
        purity_gain = float(hard_p03["weighted_purity"]) - float(soft_p03["weighted_purity"])
        idf1_loss = float(soft_p03["macro_local_idf1"]) - float(hard_p03["macro_local_idf1"])
        if float(hard_p03["weighted_purity"]) >= 0.95 and idf1_loss <= 0.01:
            return "hard_veto_signal_but_not_ready", passing
        if purity_gain >= 0.05:
            return "hard_veto_tradeoff_only", passing
    return "candidate_recall_still_blocked", passing


def write_decision(
    path: Path,
    *,
    decision: str,
    passing: Sequence[str],
    pipeline_rows: Sequence[Mapping[str, object]],
    candidate_rows: Sequence[Mapping[str, object]],
    measurement_valid: bool,
) -> None:
    lines = [
        "# BoT-SORT Candidate Gate Repair Decision",
        "",
        f"- decision: `{decision}`",
        f"- measurement_valid: `{int(measurement_valid)}`",
        f"- passing pipelines: `{', '.join(passing) if passing else 'none'}`",
        "- formal_allowed: `" + str(int(decision == "candidate_gate_repair_ready")) + "`",
        "",
        "## Pipeline Metrics",
        "",
        "| Pipeline | Proximity | Appearance | IDF1 | Purity | Min-view IDF1 | Coverage | Fragmentation |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in pipeline_rows:
        lines.append(
            f"| {row['pipeline']} | {row.get('proximity_threshold', '')} | "
            f"{row.get('appearance_mode', '')} | {float(row['macro_local_idf1']):.6f} | "
            f"{float(row['weighted_purity']):.6f} | "
            f"{float(row['minimum_per_view_local_idf1']):.6f} | "
            f"{float(row['occlusion_support_coverage']):.6f} | {row['fragmentation_count']} |"
        )
    lines.extend(
        [
            "",
            "## Offline Candidate Diagnostic",
            "",
            "| Proximity | Same recall | Hard-gate precision | Hard-gate same recall |",
            "| ---: | ---: | ---: | ---: |",
        ]
    )
    for row in candidate_rows:
        lines.append(
            f"| {float(row['proximity_threshold']):.2f} | "
            f"{float(row['same_candidate_recall']):.6f} | "
            f"{float(row['hard_gate_accepted_precision']):.6f} | "
            f"{float(row['hard_gate_same_pair_recall']):.6f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    if args.frame_start != 0 or args.frame_end != 199:
        print("[warning] primary decision rules were designed for frames 0-199", flush=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints" / "conditions"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    versions = validate_mature_tracker_environment()
    print(
        f"[1/5][prepare] experiment={EXPERIMENT_ID} ultralytics={versions['ultralytics']} "
        f"lap={versions['lap']}",
        flush=True,
    )
    observations = load_matrix_observations(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
    )
    visible, _ = los_visible_observations(args.matrix_root, observations)
    wanted_views = set(args.drone_ids)
    visible = [row for row in visible if int(row.drone_id) in wanted_views]
    embedding_table = load_embedding_cache(args.embedding_cache)
    covered = sum(observation_sensor_key(row) in embedding_table.embeddings for row in visible)
    coverage = covered / max(len(visible), 1)
    if coverage < 0.95:
        raise RuntimeError(f"embedding coverage {coverage:.2%} is below 95%")
    print(f"[1/5][prepare] visible={len(visible)} embedding_coverage={coverage:.6f}", flush=True)

    by_view: dict[int, list[MatrixObservation]] = defaultdict(list)
    warps_by_view: dict[int, dict[int, np.ndarray]] = {}
    gmc_audit: list[dict[str, object]] = []
    for observation in visible:
        by_view[int(observation.drone_id)].append(observation)
    for view_id in args.drone_ids:
        warps, rows = load_gmc_reference(args, view_id)
        warps_by_view[view_id] = warps
        gmc_audit.extend(rows)
        print(f"[2/5][gmc] D{view_id + 1} resume: reused reference", flush=True)
    write_rows(args.output_dir / "candidate_gate_gmc_audit.csv", gmc_audit)

    conditions = build_repair_conditions(args)
    total = len(conditions) * len(args.drone_ids)
    combined = {"predictions": [], "messages": [], "diagnostics": [], "audit": []}
    index = 0
    for condition in conditions:
        for view_id in args.drone_ids:
            index += 1
            name = _condition_name(condition, view_id)
            paths = _condition_paths(checkpoint_dir, name)
            token = _condition_token(condition, args)
            if args.resume and paths["done"].is_file():
                payload = json.loads(paths["done"].read_text(encoding="utf-8"))
                if payload.get("token") == token:
                    for key in combined:
                        combined[key].extend(read_rows(paths[key]))
                    print(
                        f"[3/5][track] condition={index}/{total} resume: skip completed {name}",
                        flush=True,
                    )
                    continue
            output = _run_condition(
                args=args,
                condition=condition,
                condition_index=index,
                condition_total=total,
                view_id=view_id,
                observations=by_view.get(view_id, []),
                embeddings=embedding_table.embeddings,
                warps=warps_by_view[view_id],
            )
            for key, rows in output.items():
                write_rows(paths[key], rows)
                combined[key].extend(rows)
            atomic_json(paths["done"], {"complete": True, "token": token, "name": name})
            print(f"[3/5][track] condition={index}/{total} complete {name}", flush=True)

    print("[4/5][aggregate] computing tracker and candidate diagnostics", flush=True)
    visibilities = build_frame_visibilities(
        args.matrix_root,
        frame_start=args.frame_start,
        frame_end=args.frame_end,
        primary_drone_id=args.primary_drone_id,
        support_drone_ids=tuple(view for view in args.drone_ids if view != args.primary_drone_id),
    )
    episodes = build_occlusion_episodes(visibilities, min_episode_length=1)
    occlusion_keys = build_occlusion_event_keys(episodes, min_episode_length=1)
    quality, pipeline_rows, merge_rows, coverage_rows = summarize_quality(
        combined["predictions"],
        eval_start=args.frame_start,
        occlusion_keys=occlusion_keys,
        primary_drone_id=args.primary_drone_id,
    )
    condition_by_pipeline = {str(row["pipeline"]): row for row in conditions}
    for row in pipeline_rows:
        condition = condition_by_pipeline[str(row["pipeline"])]
        row["appearance_mode"] = condition["appearance_mode"]
        row["proximity_threshold"] = condition["proximity_threshold"]
    candidate_rows = candidate_pair_diagnostics(
        visible,
        embedding_table.embeddings,
        warps_by_view,
        args.proximity_thresholds,
        identity_threshold=args.osnet_threshold,
    )
    measurement_valid = (
        coverage >= 0.95
        and all(int(row["runtime_person_id_reads"]) == 0 for row in combined["audit"])
        and all(int(row["runtime_occlusion_label_reads"]) == 0 for row in combined["audit"])
        and all(int(row["runtime_world_xy_association_reads"]) == 0 for row in combined["audit"])
        and all(int(row["future_reads"]) == 0 for row in combined["audit"])
        and all(int(row["determinism_mismatch"]) == 0 for row in combined["audit"])
    )
    decision, passing = decide(pipeline_rows, measurement_valid)
    person_reads = sum(int(row["runtime_person_id_reads"]) for row in combined["audit"])
    occlusion_reads = sum(int(row["runtime_occlusion_label_reads"]) for row in combined["audit"])
    world_xy_reads = sum(int(row["runtime_world_xy_association_reads"]) for row in combined["audit"])
    future_reads = sum(int(row["future_reads"]) for row in combined["audit"])
    determinism_mismatches = sum(int(row["determinism_mismatch"]) for row in combined["audit"])
    measurement_rows = [
        {"gate": "embedding_coverage", "value": coverage, "passed": int(coverage >= 0.95)},
        {"gate": "runtime_person_id_reads", "value": person_reads, "passed": int(person_reads == 0)},
        {"gate": "runtime_occlusion_label_reads", "value": occlusion_reads, "passed": int(occlusion_reads == 0)},
        {"gate": "runtime_world_xy_association_reads", "value": world_xy_reads, "passed": int(world_xy_reads == 0)},
        {"gate": "future_reads", "value": future_reads, "passed": int(future_reads == 0)},
        {"gate": "determinism_mismatch", "value": determinism_mismatches, "passed": int(determinism_mismatches == 0)},
    ]
    write_rows(args.output_dir / "candidate_gate_pipeline_metrics.csv", pipeline_rows)
    write_rows(args.output_dir / "candidate_gate_quality_by_view.csv", quality)
    write_rows(args.output_dir / "candidate_gate_merge_fragmentation.csv", merge_rows)
    write_rows(args.output_dir / "candidate_gate_occlusion_coverage.csv", coverage_rows)
    write_rows(args.output_dir / "candidate_gate_pair_diagnostics.csv", candidate_rows)
    write_rows(args.output_dir / "candidate_gate_association_diagnostics.csv", combined["diagnostics"])
    write_rows(args.output_dir / "candidate_gate_measurement_gate.csv", measurement_rows)
    write_decision(
        args.output_dir / "candidate_gate_decision.md",
        decision=decision,
        passing=passing,
        pipeline_rows=pipeline_rows,
        candidate_rows=candidate_rows,
        measurement_valid=measurement_valid,
    )
    print(f"[5/5][finalize] decision={decision} formal_allowed={int(bool(passing))} outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
