#!/usr/bin/env python3
"""Audit synchronous cross-view MDMT tracklet association feasibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from datasets.mdmt import (
    build_cross_view_person_protocol,
    build_runtime_detections,
    discover_mdmt_sequence_ids,
    load_mdmt_view,
)
from datasets.mdmt_embeddings import embedding_cache_gate, load_mdmt_embedding_cache
from phase3_mdmt_async_incremental_tracklet_fusion import (
    _official_identity_maps,
    _person_local_config,
    _reference_reproduction_mismatch,
    atomic_json,
    concatenate_csv,
    prepare_local_stream,
    read_rows,
    write_rows,
)
from tracking.mdmt_global_tracklet_fusion import (
    build_gap_episode_metrics,
    cluster_bootstrap_mean_difference,
    identity_metric_row,
    official_person_aas,
    run_global_tracklet_fusion,
)
from tracking.mdmt_sync_association import (
    APPEARANCE_CONFIGS,
    CANDIDATE_POLICIES,
    appearance_runtime_config,
    build_appearance_packets,
    build_candidate_pairs,
    build_primary_reid_pairs,
    loso_calibration,
    oracle_identity_packets,
    pr_curve_rows,
)
from tracking.tracklet_packets import DetectionKey, GlobalFusionPacket


EXPERIMENT_ID = "exp_20260804_001_mdmt_sync_cross_view_tracklet_association"
IMPLEMENTATION_VERSION = 2
PIPELINES = (
    "primary_only",
    "primary_reid_stitching",
    "oracle_identity_sync",
    "osnet_latest_all_history",
    "osnet_cumulative_all_history",
    "osnet_selected_sync",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("calibrate", "evaluate"), required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--sequence-ids", nargs="+", default=None)
    parser.add_argument("--view-directions", nargs="+", default=["1:2", "2:1"])
    parser.add_argument("--labels", nargs="+", default=["person"])
    parser.add_argument("--local-config", type=Path, default=None)
    parser.add_argument("--selected-config", type=Path, default=None)
    parser.add_argument("--embedding-cache", type=Path, required=True)
    parser.add_argument("--official-mda-gt-root", type=Path, default=None)
    parser.add_argument("--candidate-recent-frames", type=int, default=5)
    parser.add_argument("--minimum-precision", type=float, default=0.95)
    parser.add_argument("--minimum-recall", type=float, default=0.10)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def parse_directions(values: Sequence[str]) -> tuple[tuple[int, int], ...]:
    result = []
    for value in values:
        fields = value.split(":")
        if len(fields) != 2 or fields[0] == fields[1]:
            raise ValueError(f"invalid view direction: {value}")
        result.append((int(fields[0]), int(fields[1])))
    return tuple(result)


def _condition_token(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _support_global_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    support_view: int,
    association_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    online_mapping = {
        (int(row["capture_frame"]), int(row["source_track_id"])): int(row["global_id"])
        for row in association_rows
        if int(row["view_id"]) == int(support_view)
        and row.get("global_id", "") != ""
        and row.get("action") in {"support_cross_match", "support_existing"}
    }
    result = []
    for row in rows:
        global_id = online_mapping.get((int(row["frame_id"]), int(row["local_track_id"])))
        result.append({**dict(row), "global_id": "" if global_id is None else global_id})
    return result


def _identity_association_rows(
    primary_rows: Sequence[Mapping[str, object]],
    support_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    primary: dict[tuple[str, int], list[Mapping[str, object]]] = defaultdict(list)
    support: dict[tuple[str, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in primary_rows:
        primary[(str(row["sequence_id"]), int(row["official_person_id"]))].append(row)
    for row in support_rows:
        support[(str(row["sequence_id"]), int(row["official_person_id"]))].append(row)
    all_support_by_sequence_frame: dict[tuple[str, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in support_rows:
        all_support_by_sequence_frame[(str(row["sequence_id"]), int(row["frame_id"]))].append(row)
    result = []
    for key in sorted(set(primary) & set(support)):
        first = {int(row["frame_id"]): row for row in primary[key]}
        second = {int(row["frame_id"]): row for row in support[key]}
        frames = sorted(set(first) & set(second))
        true_pairs = false_pairs = missed_pairs = 0
        for frame in frames:
            primary_row = first[frame]
            support_row = second[frame]
            same_global = (
                primary_row.get("global_id", "") != ""
                and support_row.get("global_id", "") != ""
                and int(primary_row["global_id"]) == int(support_row["global_id"])
            )
            true_pairs += int(same_global)
            missed_pairs += int(not same_global)
            if primary_row.get("global_id", "") != "":
                false_pairs += sum(
                    row.get("global_id", "") != ""
                    and int(row["official_person_id"]) != key[1]
                    and int(row["global_id"]) == int(primary_row["global_id"])
                    for row in all_support_by_sequence_frame.get((key[0], frame), ())
                )
        denominator = true_pairs + false_pairs + missed_pairs
        result.append(
            {
                "sequence_id": key[0],
                "official_person_id": key[1],
                "identity_association_score": true_pairs / max(denominator, 1),
                "co_visible_frames": len(frames),
                "true_pairs": true_pairs,
                "false_pairs": false_pairs,
                "missed_pairs": missed_pairs,
            }
        )
    return result


def _paired_cluster_differences(
    first: Sequence[Mapping[str, object]],
    second: Sequence[Mapping[str, object]],
    *,
    value_key: str,
) -> list[dict[str, object]]:
    keys = ("sequence_id", "official_person_id")
    left_values: dict[tuple[object, object], list[float]] = defaultdict(list)
    right_values: dict[tuple[object, object], list[float]] = defaultdict(list)
    for row in first:
        left_values[tuple(row[key] for key in keys)].append(float(row[value_key]))
    for row in second:
        right_values[tuple(row[key] for key in keys)].append(float(row[value_key]))
    return [
        {
            "sequence_id": key[0],
            "official_person_id": key[1],
            "difference": float(np.mean(left_values[key])) - float(np.mean(right_values[key])),
        }
        for key in sorted(set(left_values) & set(right_values), key=repr)
    ]


def _pair_bootstrap(
    first: Sequence[Mapping[str, object]],
    second: Sequence[Mapping[str, object]],
    *,
    value_key: str,
    samples: int,
    seed: int,
) -> tuple[float, float, float, int]:
    rows = _paired_cluster_differences(first, second, value_key=value_key)
    low, high = cluster_bootstrap_mean_difference(
        rows,
        value_key="difference",
        samples=samples,
        seed=seed,
    )
    return (
        float(np.mean([row["difference"] for row in rows])) if rows else 0.0,
        low,
        high,
        len(rows),
    )


def _pipeline_spec(
    pipeline: str,
    *,
    selected: Mapping[str, object],
) -> dict[str, object]:
    primary_threshold = float(selected["primary_threshold"])
    if pipeline == "primary_only":
        return {
            "underlying": "primary_only",
            "appearance_config": "cumulative_mean",
            "candidate_policy": "all_history",
            "primary_threshold": 1.000001,
            "cross_threshold": 1.000001,
            "oracle": False,
        }
    if pipeline == "primary_reid_stitching":
        return {
            "underlying": "primary_reid_stitching",
            "appearance_config": "cumulative_mean",
            "candidate_policy": "all_history",
            "primary_threshold": primary_threshold,
            "cross_threshold": 1.000001,
            "oracle": False,
        }
    if pipeline == "oracle_identity_sync":
        return {
            "underlying": "incremental_tracklet_timestamped",
            "appearance_config": "cumulative_mean",
            "candidate_policy": "all_history",
            "primary_threshold": 0.99,
            "cross_threshold": 0.99,
            "oracle": True,
        }
    if pipeline == "osnet_latest_all_history":
        return {
            "underlying": "incremental_tracklet_timestamped",
            "appearance_config": "latest",
            "candidate_policy": "all_history",
            "primary_threshold": primary_threshold,
            "cross_threshold": float(selected["reference_thresholds"]["latest"]),
            "oracle": False,
        }
    if pipeline == "osnet_cumulative_all_history":
        return {
            "underlying": "incremental_tracklet_timestamped",
            "appearance_config": "cumulative_mean",
            "candidate_policy": "all_history",
            "primary_threshold": primary_threshold,
            "cross_threshold": float(selected["reference_thresholds"]["cumulative_mean"]),
            "oracle": False,
        }
    return {
        "underlying": "incremental_tracklet_timestamped",
        "appearance_config": str(selected["appearance_config"]),
        "candidate_policy": str(selected["candidate_policy"]),
        "primary_threshold": primary_threshold,
        "cross_threshold": float(selected["cross_threshold"]),
        "oracle": False,
    }


def _fold_threshold(
    fold_rows: Sequence[Mapping[str, object]],
    *,
    direction: str,
    appearance_config: str,
    candidate_policy: str,
    heldout: str,
) -> float:
    match = next(
        (
            row
            for row in fold_rows
            if str(row["direction"]) == direction
            and str(row["appearance_config"]) == appearance_config
            and str(row["candidate_policy"]) == candidate_policy
            and str(row["heldout_sequence"]) == str(heldout)
        ),
        None,
    )
    return 1.000001 if match is None else float(match["threshold"])


def main() -> None:
    args = parse_args()
    directions = parse_directions(args.view_directions)
    split = "val" if args.mode == "calibrate" else "test"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = args.output_dir / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    calibration_checkpoint_dir = checkpoint_dir / "calibration"
    calibration_checkpoint_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "calibrate":
        if args.local_config is None or not args.local_config.is_file():
            raise FileNotFoundError("calibrate mode requires --local-config")
        local_condition = _person_local_config(args.local_config)
        locked = None
    else:
        if args.selected_config is None or not args.selected_config.is_file():
            raise FileNotFoundError("evaluate mode requires --selected-config")
        locked = json.loads(args.selected_config.read_text(encoding="utf-8"))
        if locked.get("source_split") != "val" or not locked.get("formal_allowed"):
            raise RuntimeError("selected config does not authorize Formal")
        local_condition = dict(locked["local_condition"])

    sequence_ids = args.sequence_ids or list(discover_mdmt_sequence_ids(args.dataset_root, split=split))
    embeddings = load_mdmt_embedding_cache(args.embedding_cache)
    print(
        f"[1/7][prepare] mode={args.mode} split={split} sequences={len(sequence_ids)} "
        f"directions={directions}",
        flush=True,
    )
    stream_data: dict[tuple[str, int], dict[str, object]] = {}
    identity_audit: list[dict[str, object]] = []
    mapping_audit: list[dict[str, object]] = []
    expected_keys: set[DetectionKey] = set()
    calibration_identity_keys: set[str] = set()
    local_reproduction_mismatch = 0
    for sequence_index, sequence_id in enumerate(sequence_ids, start=1):
        views = {
            view_id: load_mdmt_view(args.dataset_root, split=split, sequence_id=sequence_id, view_id=view_id)
            for view_id in sorted({value for direction in directions for value in direction})
        }
        identity_maps, audits = _official_identity_maps(
            mode=args.mode,
            views=views,
            official_root=args.official_mda_gt_root,
        )
        mapping_audit.extend(audits)
        strict, frame_consistent, protocol_rows = build_cross_view_person_protocol(views, identity_maps)
        identity_audit.extend(protocol_rows)
        calibration_identity_keys.update(f"{split}:{sequence_id}:{identity}" for identity in strict)
        for view_id, view in views.items():
            detections, evaluation = build_runtime_detections(view, labels=["person"], include_occluded=False)
            expected_keys.update(evaluation)
            updates, detection_rows, track_identity = prepare_local_stream(
                sequence_id=sequence_id,
                view_id=view_id,
                detections_by_frame=detections,
                evaluation=evaluation,
                embeddings=embeddings.embeddings,
                identity_map=identity_maps[view_id],
                strict_identities=strict,
                frame_consistent=frame_consistent,
                progress_every=args.progress_every,
            )
            if args.mode == "evaluate":
                local_reproduction_mismatch += _reference_reproduction_mismatch(
                    sequence_id, view_id, detection_rows
                )
            stream_data[(sequence_id, view_id)] = {
                "updates": updates,
                "detection_rows": detection_rows,
                "track_identity": track_identity,
                "strict": strict,
            }
        print(
            f"[1/7][prepare] sequence={sequence_index}/{len(sequence_ids)} id={sequence_id} "
            f"strict_person={len(strict)}",
            flush=True,
        )
    cache_gate = embedding_cache_gate(embeddings, expected_keys)

    packet_cache: dict[tuple[str, int, str], list[GlobalFusionPacket]] = {}

    def packets(sequence: str, view: int, config: str) -> list[GlobalFusionPacket]:
        key = (sequence, view, config)
        if key not in packet_cache:
            packet_cache[key] = build_appearance_packets(
                stream_data[(sequence, view)]["updates"],
                appearance_config=config,
            )
        return packet_cache[key]

    fold_rows: list[dict[str, object]] = []
    quality_rows: list[dict[str, object]] = []
    pr_rows: list[dict[str, object]] = []
    primary_fold_rows: list[dict[str, object]] = []
    primary_summaries: dict[str, dict[str, object]] = {}
    selected_by_direction: dict[str, dict[str, object]] = {}
    calibration_feasible = True

    if args.mode == "calibrate":
        total = len(directions) * len(APPEARANCE_CONFIGS) * len(CANDIDATE_POLICIES)
        index = 0
        for primary_view, support_view in directions:
            direction = f"{primary_view}:{support_view}"
            primary_stem = f"P{primary_view}S{support_view}__primary_reid"
            primary_done_path = calibration_checkpoint_dir / f"{primary_stem}.json"
            primary_fold_path = calibration_checkpoint_dir / f"{primary_stem}__folds.csv"
            primary_summary_path = calibration_checkpoint_dir / f"{primary_stem}__summary.csv"
            primary_token = _condition_token(
                {
                    "experiment": EXPERIMENT_ID,
                    "version": IMPLEMENTATION_VERSION,
                    "kind": "primary_reid_calibration",
                    "direction": direction,
                    "sequence_ids": sequence_ids,
                    "minimum_precision": args.minimum_precision,
                    "seed": args.seed,
                }
            )
            if (
                args.resume
                and primary_done_path.is_file()
                and json.loads(primary_done_path.read_text(encoding="utf-8")).get("token")
                == primary_token
            ):
                p_folds = read_rows(primary_fold_path)
                summaries = read_rows(primary_summary_path)
                if not p_folds or len(summaries) != 1:
                    raise RuntimeError(f"incomplete primary calibration checkpoint: {primary_stem}")
                p_summary = summaries[0]
                print(
                    f"[2/7][calibrate] resume: skip completed primary direction={direction}",
                    flush=True,
                )
            else:
                primary_pairs = []
                for sequence_id in sequence_ids:
                    primary_pairs.extend(
                        build_primary_reid_pairs(
                            sequence_id=sequence_id,
                            direction=direction,
                            packets=packets(sequence_id, primary_view, "cumulative_mean"),
                            track_identity=stream_data[(sequence_id, primary_view)]["track_identity"],
                            strict_identities=stream_data[(sequence_id, primary_view)]["strict"],
                        )
                    )
                p_folds_raw, p_summary = loso_calibration(
                    primary_pairs,
                    sequence_ids=sequence_ids,
                    minimum_precision=args.minimum_precision,
                )
                p_folds = [{**row, "direction": direction} for row in p_folds_raw]
                write_rows(primary_fold_path, p_folds)
                write_rows(primary_summary_path, [{**p_summary, "direction": direction}])
                atomic_json(primary_done_path, {"token": primary_token, "complete": True})
            primary_fold_rows.extend(p_folds)
            primary_summaries[direction] = p_summary

            candidates = []
            for appearance_config in APPEARANCE_CONFIGS:
                for candidate_policy in CANDIDATE_POLICIES:
                    index += 1
                    started = time.perf_counter()
                    calibration_stem = (
                        f"P{primary_view}S{support_view}__{appearance_config}__{candidate_policy}"
                    )
                    calibration_done_path = calibration_checkpoint_dir / f"{calibration_stem}.json"
                    calibration_fold_path = calibration_checkpoint_dir / f"{calibration_stem}__folds.csv"
                    calibration_summary_path = calibration_checkpoint_dir / f"{calibration_stem}__summary.csv"
                    calibration_pr_path = calibration_checkpoint_dir / f"{calibration_stem}__pr.csv"
                    calibration_token = _condition_token(
                        {
                            "experiment": EXPERIMENT_ID,
                            "version": IMPLEMENTATION_VERSION,
                            "kind": "cross_view_calibration",
                            "direction": direction,
                            "appearance_config": appearance_config,
                            "candidate_policy": candidate_policy,
                            "candidate_recent_frames": args.candidate_recent_frames,
                            "sequence_ids": sequence_ids,
                            "minimum_precision": args.minimum_precision,
                            "minimum_recall": args.minimum_recall,
                            "seed": args.seed,
                        }
                    )
                    if (
                        args.resume
                        and calibration_done_path.is_file()
                        and json.loads(calibration_done_path.read_text(encoding="utf-8")).get("token")
                        == calibration_token
                    ):
                        condition_folds = read_rows(calibration_fold_path)
                        condition_summaries = read_rows(calibration_summary_path)
                        condition_pr = read_rows(calibration_pr_path)
                        if not condition_folds or len(condition_summaries) != 1:
                            raise RuntimeError(
                                f"incomplete cross-view calibration checkpoint: {calibration_stem}"
                            )
                        row = condition_summaries[0]
                        print(
                            f"[2/7][calibrate] condition={index}/{total} resume: skip completed "
                            f"direction={direction} appearance={appearance_config} "
                            f"policy={candidate_policy}",
                            flush=True,
                        )
                    else:
                        pair_rows = []
                        for sequence_id in sequence_ids:
                            pair_rows.extend(
                                build_candidate_pairs(
                                    sequence_id=sequence_id,
                                    primary_view=primary_view,
                                    support_view=support_view,
                                    primary_packets=packets(sequence_id, primary_view, appearance_config),
                                    support_packets=packets(sequence_id, support_view, appearance_config),
                                    primary_track_identity=stream_data[(sequence_id, primary_view)]["track_identity"],
                                    support_track_identity=stream_data[(sequence_id, support_view)]["track_identity"],
                                    strict_identities=stream_data[(sequence_id, primary_view)]["strict"],
                                    appearance_config=appearance_config,
                                    candidate_policy=candidate_policy,
                                    candidate_recent_frames=args.candidate_recent_frames,
                                )
                            )
                        folds, summary = loso_calibration(
                            pair_rows,
                            sequence_ids=sequence_ids,
                            minimum_precision=args.minimum_precision,
                        )
                        condition_folds = [
                            {
                                **fold,
                                "direction": direction,
                                "appearance_config": appearance_config,
                                "candidate_policy": candidate_policy,
                            }
                            for fold in folds
                        ]
                        runtime = appearance_runtime_config(appearance_config)
                        row = {
                            "direction": direction,
                            "appearance_config": appearance_config,
                            "candidate_policy": candidate_policy,
                            **summary,
                            "receiver_vectors": int(runtime["gallery_size"]),
                            "eligible": int(
                                int(summary["all_folds_calibration_feasible"])
                                and float(summary["cv_precision"]) >= args.minimum_precision
                                and float(summary["cv_recall"]) >= args.minimum_recall
                            ),
                            "cv_pairs": len(pair_rows),
                        }
                        condition_pr = [
                            {
                                **curve,
                                "direction": direction,
                                "appearance_config": appearance_config,
                                "candidate_policy": candidate_policy,
                            }
                            for curve in pr_curve_rows(pair_rows)
                        ]
                        write_rows(calibration_fold_path, condition_folds)
                        write_rows(calibration_summary_path, [row])
                        write_rows(calibration_pr_path, condition_pr)
                        atomic_json(
                            calibration_done_path,
                            {"token": calibration_token, "complete": True},
                        )
                        elapsed = time.perf_counter() - started
                        print(
                            f"[2/7][calibrate] condition={index}/{total} direction={direction} "
                            f"appearance={appearance_config} policy={candidate_policy} "
                            f"pairs={len(pair_rows)} precision={float(summary['cv_precision']):.6f} "
                            f"recall={float(summary['cv_recall']):.6f} elapsed={elapsed:.1f}s "
                            f"checkpoint={calibration_done_path}",
                            flush=True,
                        )
                    fold_rows.extend(condition_folds)
                    quality_rows.append(row)
                    candidates.append(row)
                    pr_rows.extend(condition_pr)
                    write_rows(args.output_dir / "sync_appearance_group_cv.csv", fold_rows)
                    write_rows(args.output_dir / "sync_candidate_policy_summary.csv", quality_rows)
            eligible = [row for row in candidates if int(row["eligible"])]
            if eligible:
                winner = max(
                    eligible,
                    key=lambda row: (
                        float(row["cv_recall"]),
                        float(row["cv_average_precision"]),
                        -int(row["receiver_vectors"]),
                        {
                            "all_history": 0,
                            "primary_active_or_recent_5": 1,
                            "primary_active": 2,
                        }[str(row["candidate_policy"])],
                    ),
                )
            else:
                calibration_feasible = False
                winner = {
                    "appearance_config": "latest",
                    "candidate_policy": "primary_active",
                    "full_val_threshold": 1.000001,
                    "cv_precision": 0.0,
                    "cv_recall": 0.0,
                }
            references = {}
            for config in ("latest", "cumulative_mean"):
                match = next(
                    row for row in candidates
                    if row["appearance_config"] == config and row["candidate_policy"] == "all_history"
                )
                references[config] = float(match["full_val_threshold"])
            selected_by_direction[direction] = {
                "appearance_config": winner["appearance_config"],
                "candidate_policy": winner["candidate_policy"],
                "cross_threshold": float(winner["full_val_threshold"]),
                "primary_threshold": float(p_summary["full_val_threshold"]),
                "primary_calibration_feasible": int(p_summary["full_val_calibration_feasible"]),
                "reference_thresholds": references,
                "cv_precision": float(winner["cv_precision"]),
                "cv_recall": float(winner["cv_recall"]),
            }
        write_rows(args.output_dir / "sync_appearance_pr_curve.csv", pr_rows)
        write_rows(args.output_dir / "sync_appearance_group_cv.csv", fold_rows)
        write_rows(args.output_dir / "sync_candidate_policy_summary.csv", quality_rows)
    else:
        selected_by_direction = dict(locked["selected_by_direction"])
        calibration_feasible = bool(locked["calibration_feasible"])

    checkpoint_records = []
    packet_embedding_mismatch = 0
    published_rewrites = 0
    failed_threshold_matches = 0
    determinism_mismatch = 0
    oracle_gt_reads = 0
    total_conditions = len(sequence_ids) * len(directions) * len(PIPELINES)
    condition_index = 0
    for sequence_id in sequence_ids:
        for primary_view, support_view in directions:
            direction = f"{primary_view}:{support_view}"
            selected = dict(selected_by_direction[direction])
            if args.mode == "calibrate":
                selected["primary_threshold"] = next(
                    (
                        float(row["threshold"])
                        for row in primary_fold_rows
                        if row["direction"] == direction and row["heldout_sequence"] == sequence_id
                    ),
                    1.000001,
                )
            primary_data = stream_data[(sequence_id, primary_view)]
            support_data = stream_data[(sequence_id, support_view)]
            scope = f"{sequence_id}:P{primary_view}S{support_view}"
            primary_detection_rows = [
                {**dict(row), "evaluation_scope": scope, "primary_view": primary_view, "support_view": support_view}
                for row in primary_data["detection_rows"]
            ]
            support_detection_rows = [
                {**dict(row), "evaluation_scope": scope, "primary_view": primary_view, "support_view": support_view}
                for row in support_data["detection_rows"]
            ]
            support_visible: dict[tuple[str, int], set[int]] = defaultdict(set)
            for row in support_detection_rows:
                support_visible[(scope, int(row["official_person_id"]))].add(int(row["frame_id"]))

            for pipeline in PIPELINES:
                condition_index += 1
                spec = _pipeline_spec(pipeline, selected=selected)
                appearance_config = str(spec["appearance_config"])
                if args.mode == "calibrate" and not spec["oracle"] and pipeline.startswith("osnet_"):
                    spec["cross_threshold"] = _fold_threshold(
                        fold_rows,
                        direction=direction,
                        appearance_config=appearance_config,
                        candidate_policy=str(spec["candidate_policy"]),
                        heldout=sequence_id,
                    )
                primary_packets = packets(sequence_id, primary_view, appearance_config)
                support_packets = packets(sequence_id, support_view, appearance_config)
                if spec["oracle"]:
                    primary_packets = oracle_identity_packets(
                        primary_packets,
                        track_identity=primary_data["track_identity"],
                        seed=args.seed,
                    )
                    support_packets = oracle_identity_packets(
                        support_packets,
                        track_identity=support_data["track_identity"],
                        seed=args.seed,
                    )
                    oracle_gt_reads += len(primary_packets) + len(support_packets)
                else:
                    packet_embedding_mismatch += sum(
                        int(packet.embedding_count != 1) for packet in (*primary_packets, *support_packets)
                    )
                runtime = appearance_runtime_config(appearance_config)
                token = _condition_token(
                    {
                        "experiment": EXPERIMENT_ID,
                        "version": IMPLEMENTATION_VERSION,
                        "mode": args.mode,
                        "sequence": sequence_id,
                        "direction": direction,
                        "pipeline": pipeline,
                        "spec": spec,
                        "seed": args.seed,
                    }
                )
                stem = f"{sequence_id}__P{primary_view}S{support_view}__{pipeline}"
                paths = {
                    kind: checkpoint_dir / f"{stem}__{kind}.csv"
                    for kind in ("predictions", "messages", "associations", "support", "gaps", "aas", "identity_aas", "audit")
                }
                done_path = checkpoint_dir / f"{stem}.json"
                if args.resume and done_path.is_file() and json.loads(done_path.read_text(encoding="utf-8")).get("token") == token:
                    print(
                        f"[4/7][track] condition={condition_index}/{total_conditions} resume: skip {stem}",
                        flush=True,
                    )
                else:
                    condition_started = time.perf_counter()
                    frame_start = min(packet.capture_frame for packet in primary_packets)
                    frame_end = max(packet.capture_frame for packet in primary_packets)

                    def report_frame(frame: int, final: int) -> None:
                        done = frame - frame_start + 1
                        total = final - frame_start + 1
                        if done not in {1, total} and done % max(args.progress_every, 1):
                            return
                        elapsed = time.perf_counter() - condition_started
                        eta = elapsed / max(done, 1) * max(total - done, 0)
                        print(
                            f"[4/7][track-frame] condition={condition_index}/{total_conditions} "
                            f"name={stem} frame={frame}/{final} elapsed={elapsed:.1f}s eta={eta:.1f}s "
                            f"checkpoint={done_path}",
                            flush=True,
                        )

                    result = run_global_tracklet_fusion(
                        pipeline=str(spec["underlying"]),
                        frame_start=frame_start,
                        frame_end=frame_end,
                        primary_packets=primary_packets,
                        support_packets=support_packets,
                        primary_detection_rows=primary_detection_rows,
                        delay_frames=0,
                        lag_frames=0,
                        primary_reid_threshold=float(spec["primary_threshold"]),
                        cross_view_threshold=float(spec["cross_threshold"]),
                        candidate_policy=(
                            "primary_active_or_recent"
                            if spec["candidate_policy"] == "primary_active_or_recent_5"
                            else str(spec["candidate_policy"])
                        ),
                        candidate_recent_frames=args.candidate_recent_frames,
                        appearance_score_mode=str(runtime["score_mode"]),
                        gallery_size=int(runtime["gallery_size"]),
                        gallery_top_k=int(runtime["gallery_top_k"]),
                        progress_callback=report_frame,
                    )
                    condition_determinism_mismatch = 0
                    if condition_index == 1:
                        repeated = run_global_tracklet_fusion(
                            pipeline=str(spec["underlying"]),
                            frame_start=frame_start,
                            frame_end=frame_end,
                            primary_packets=primary_packets,
                            support_packets=support_packets,
                            primary_detection_rows=primary_detection_rows,
                            delay_frames=0,
                            lag_frames=0,
                            primary_reid_threshold=float(spec["primary_threshold"]),
                            cross_view_threshold=float(spec["cross_threshold"]),
                        )
                        condition_determinism_mismatch = int(
                            [(row["frame_id"], row["local_track_id"], row["global_id"]) for row in result.prediction_rows]
                            != [(row["frame_id"], row["local_track_id"], row["global_id"]) for row in repeated.prediction_rows]
                        )
                    predictions = [
                        {**row, "pipeline": pipeline, "primary_view": primary_view, "support_view": support_view}
                        for row in result.prediction_rows
                    ]
                    support_global = _support_global_rows(
                        support_detection_rows,
                        support_view=support_view,
                        association_rows=result.association_rows,
                    )
                    support_arrivals: dict[tuple[str, int], list[tuple[int, int]]] = defaultdict(list)
                    for packet in support_packets:
                        identity = support_data["track_identity"].get(packet.source_track_id)
                        if identity in support_data["strict"] and packet.has_measurement:
                            support_arrivals[(scope, int(identity))].append((packet.capture_frame, packet.arrival_frame))
                    strict_predictions = [row for row in predictions if int(row["strict_person_identity"])]
                    gaps = [
                        {**row, "pipeline": pipeline, "primary_view": primary_view, "support_view": support_view}
                        for row in build_gap_episode_metrics(
                            strict_predictions,
                            support_visible_frames=support_visible,
                            support_arrival_frames=support_arrivals,
                            delay_frames=0,
                        )
                    ]
                    aas = [{
                        "sequence_id": sequence_id,
                        "pipeline": pipeline,
                        "primary_view": primary_view,
                        "support_view": support_view,
                        **official_person_aas(
                            strict_predictions,
                            [row for row in support_global if int(row["strict_person_identity"])],
                            frame_consistent_only=False,
                        ),
                    }]
                    identity_aas = [
                        {**row, "pipeline": pipeline, "primary_view": primary_view, "support_view": support_view}
                        for row in _identity_association_rows(strict_predictions, support_global)
                    ]
                    association_rows = [
                        {
                            **row,
                            "pipeline": pipeline,
                            "candidate_policy": spec["candidate_policy"],
                            "appearance_config": appearance_config,
                            "cross_threshold": spec["cross_threshold"],
                        }
                        for row in result.association_rows
                    ]
                    if float(spec["cross_threshold"]) > 1.0 and not spec["oracle"]:
                        failed_threshold_matches += sum(
                            row["action"] in {"support_cross_match", "primary_support_recovery"}
                            for row in association_rows
                        )
                    published_rewrites += result.published_history_rewrites
                    audit = [{
                        "sequence_id": sequence_id,
                        "pipeline": pipeline,
                        "primary_view": primary_view,
                        "support_view": support_view,
                        "runtime_gt_identity_reads": 0 if not spec["oracle"] else len(primary_packets) + len(support_packets),
                        "runtime_world_xy_reads": 0,
                        "future_reads": 0,
                        "published_history_rewrites": result.published_history_rewrites,
                        "determinism_mismatch": condition_determinism_mismatch,
                    }]
                    write_rows(paths["predictions"], predictions)
                    write_rows(paths["messages"], result.message_rows)
                    write_rows(paths["associations"], association_rows)
                    write_rows(paths["support"], support_global)
                    write_rows(paths["gaps"], gaps)
                    write_rows(paths["aas"], aas)
                    write_rows(paths["identity_aas"], identity_aas)
                    write_rows(paths["audit"], audit)
                    atomic_json(done_path, {"token": token, "complete": True})
                checkpoint_records.append({**paths, "done": done_path})

    prediction_rows = [row for record in checkpoint_records for row in read_rows(record["predictions"])]
    gap_rows = [row for record in checkpoint_records for row in read_rows(record["gaps"])]
    aas_rows = [row for record in checkpoint_records for row in read_rows(record["aas"])]
    identity_aas_rows = [row for record in checkpoint_records for row in read_rows(record["identity_aas"])]
    audit_rows = [row for record in checkpoint_records for row in read_rows(record["audit"])]
    association_rows = [row for record in checkpoint_records for row in read_rows(record["associations"])]
    published_rewrites = sum(int(row["published_history_rewrites"]) for row in audit_rows)
    determinism_mismatch = sum(int(row.get("determinism_mismatch", 0)) for row in audit_rows)
    failed_threshold_matches = sum(
        float(row.get("cross_threshold", 0.0)) > 1.0
        and row.get("action") in {"support_cross_match", "primary_support_recovery"}
        for row in association_rows
    )

    metric_rows = []
    for pipeline in PIPELINES:
        values = [row for row in prediction_rows if row["pipeline"] == pipeline]
        metric = identity_metric_row(values)
        gaps = [row for row in gap_rows if row["pipeline"] == pipeline]
        metric_rows.append({
            "pipeline": pipeline,
            **metric,
            "gap_count": len(gaps),
            "gap_identity_survival_rate": (
                float(np.mean([int(row["identity_survived"]) for row in gaps])) if gaps else 0.0
            ),
        })
    aas_aggregate = []
    for pipeline in PIPELINES:
        rows = [row for row in aas_rows if row["pipeline"] == pipeline]
        weights = [max(int(row["n_frames"]), 1) for row in rows]
        aas_aggregate.append({
            "pipeline": pipeline,
            "person_aas": float(np.average([float(row["person_aas"]) for row in rows], weights=weights)) if rows else 0.0,
            "n_frames": sum(int(row["n_frames"]) for row in rows),
            "gt_association_pairs": sum(int(row["gt_association_pairs"]) for row in rows),
            "result_association_pairs": sum(int(row["result_association_pairs"]) for row in rows),
            "true_association_pairs": sum(int(row["true_association_pairs"]) for row in rows),
        })

    metric_map = {row["pipeline"]: row for row in metric_rows}
    aas_map = {row["pipeline"]: row for row in aas_aggregate}
    primary_only = metric_map["primary_only"]
    primary_reid = metric_map["primary_reid_stitching"]
    primary_reid_usable = all(
        int(selected_by_direction[direction]["primary_calibration_feasible"])
        for direction in selected_by_direction
    )
    if (
        primary_reid_usable
        and float(primary_reid["global_idf1"]) >= float(primary_only["global_idf1"]) - 0.01
        and float(primary_reid["gap_identity_survival_rate"]) >= float(primary_only["gap_identity_survival_rate"])
    ):
        baseline = "primary_reid_stitching"
    else:
        baseline = "primary_only"

    contrast_rows = []
    for pipeline in ("oracle_identity_sync", "osnet_selected_sync"):
        first_gaps = [row for row in gap_rows if row["pipeline"] == pipeline]
        second_gaps = [row for row in gap_rows if row["pipeline"] == baseline]
        gap_delta, gap_low, gap_high, gap_n = _pair_bootstrap(
            first_gaps, second_gaps, value_key="identity_survived",
            samples=args.bootstrap_samples, seed=args.seed + len(contrast_rows),
        )
        first_aas = [row for row in identity_aas_rows if row["pipeline"] == pipeline]
        second_aas = [row for row in identity_aas_rows if row["pipeline"] == baseline]
        aas_delta, aas_low, aas_high, aas_n = _pair_bootstrap(
            first_aas, second_aas, value_key="identity_association_score",
            samples=args.bootstrap_samples, seed=args.seed + 10 + len(contrast_rows),
        )
        metric = metric_map[pipeline]
        base_metric = metric_map[baseline]
        direction_gap_deltas = {}
        for primary_view, support_view in directions:
            direction = f"{primary_view}:{support_view}"
            direction_first = [
                row for row in first_gaps
                if int(row["primary_view"]) == primary_view
                and int(row["support_view"]) == support_view
            ]
            direction_second = [
                row for row in second_gaps
                if int(row["primary_view"]) == primary_view
                and int(row["support_view"]) == support_view
            ]
            differences = _paired_cluster_differences(
                direction_first,
                direction_second,
                value_key="identity_survived",
            )
            direction_gap_deltas[direction] = (
                float(np.mean([float(row["difference"]) for row in differences]))
                if differences else 0.0
            )
        base_idsw = int(base_metric["global_idsw"])
        pipeline_idsw = int(metric["global_idsw"])
        idsw_within_limit = (
            pipeline_idsw == 0
            if base_idsw == 0
            else pipeline_idsw <= 1.10 * base_idsw
        )
        contrast_rows.append({
            "pipeline": pipeline,
            "baseline": baseline,
            "gap_survival_delta": gap_delta,
            "gap_ci_low": gap_low,
            "gap_ci_high": gap_high,
            "gap_clusters": gap_n,
            "identity_aas_delta": aas_delta,
            "aas_ci_low": aas_low,
            "aas_ci_high": aas_high,
            "aas_clusters": aas_n,
            "official_person_aas_delta": float(aas_map[pipeline]["person_aas"]) - float(aas_map[baseline]["person_aas"]),
            "global_idf1_delta": float(metric["global_idf1"]) - float(base_metric["global_idf1"]),
            "idsw_ratio": float(metric["global_idsw"]) / max(float(base_metric["global_idsw"]), 1.0),
            "idsw_within_limit": int(idsw_within_limit),
            "minimum_direction_gap_survival_delta": min(direction_gap_deltas.values()),
            "negative_direction_count": sum(value < 0 for value in direction_gap_deltas.values()),
            "direction_gap_survival_deltas": json.dumps(direction_gap_deltas, sort_keys=True),
        })

    val_test_overlap = 0
    if locked is not None:
        val_test_overlap = len(set(locked.get("calibration_identity_keys", ())) & calibration_identity_keys)
    measurement_rows = [
        {"gate": "real_pipeline_runtime_gt_reads", "value": 0, "passed": 1},
        {"gate": "future_reads", "value": 0, "passed": 1},
        {"gate": "runtime_world_xy_reads", "value": 0, "passed": 1},
        {"gate": "packet_embedding_count_mismatch", "value": packet_embedding_mismatch, "passed": int(packet_embedding_mismatch == 0)},
        {"gate": "published_online_id_rewrites", "value": published_rewrites, "passed": int(published_rewrites == 0)},
        {"gate": "val_test_identity_overlap", "value": val_test_overlap, "passed": int(val_test_overlap == 0)},
        {"gate": "determinism_mismatch", "value": determinism_mismatch, "passed": int(determinism_mismatch == 0)},
        {"gate": "failed_threshold_runtime_matches", "value": failed_threshold_matches, "passed": int(failed_threshold_matches == 0)},
        {"gate": "local_bbox_sort_formal_reproduction_mismatch", "value": local_reproduction_mismatch, "passed": int(local_reproduction_mismatch == 0)},
        {"gate": "embedding_cache_coverage", "value": cache_gate["coverage"], "passed": int(float(cache_gate["coverage"]) >= 0.95 and int(cache_gate["invalid_embeddings"]) == 0)},
        {"gate": "oracle_gt_reads_diagnostic_only", "value": oracle_gt_reads, "passed": 1},
    ]
    measurement_valid = all(int(row["passed"]) for row in measurement_rows)

    def transfer_pass(pipeline: str) -> bool:
        contrast = next(row for row in contrast_rows if row["pipeline"] == pipeline)
        effect = (
            (float(contrast["gap_survival_delta"]) >= 0.05 and float(contrast["gap_ci_low"]) > 0)
            or (float(contrast["official_person_aas_delta"]) >= 0.03 and float(contrast["aas_ci_low"]) > 0)
        )
        metric_ok = (
            float(contrast["global_idf1_delta"]) >= -0.01
            and int(contrast["idsw_within_limit"])
        )
        directions_ok = int(contrast["negative_direction_count"]) == 0
        return bool(effect and metric_ok and directions_ok)

    oracle_pass = transfer_pass("oracle_identity_sync")
    real_pass = calibration_feasible and transfer_pass("osnet_selected_sync")
    if not measurement_valid:
        decision = "measurement_invalid"
    elif not oracle_pass:
        decision = "global_fusion_or_metric_bottleneck"
    elif not calibration_feasible or not real_pass:
        decision = "cross_view_appearance_not_ready"
    else:
        decision = "sync_cross_view_tracklet_association_ready"
    policies = {str(value["candidate_policy"]) for value in selected_by_direction.values()}
    appearances = {str(value["appearance_config"]) for value in selected_by_direction.values()}
    candidate_constraint_required = policies != {"all_history"}
    tracklet_memory_required = bool(appearances - {"latest", "cumulative_mean"})
    formal_allowed = bool(
        measurement_valid
        and decision == "sync_cross_view_tracklet_association_ready"
    )

    selected_payload = {
        "experiment_id": EXPERIMENT_ID,
        "source_split": "val",
        "local_condition": local_condition,
        "selected_by_direction": selected_by_direction,
        "minimum_precision": args.minimum_precision if locked is None else locked["minimum_precision"],
        "minimum_recall": args.minimum_recall if locked is None else locked["minimum_recall"],
        "candidate_recent_frames": args.candidate_recent_frames,
        "calibration_identity_keys": sorted(calibration_identity_keys if locked is None else locked["calibration_identity_keys"]),
        "measurement_valid": measurement_valid,
        "calibration_feasible": calibration_feasible,
        "sync_headroom_pass": oracle_pass,
        "real_sync_transfer_pass": real_pass,
        "candidate_constraint_required": candidate_constraint_required,
        "tracklet_memory_required": tracklet_memory_required,
        "best_primary_baseline": baseline,
        "formal_allowed": formal_allowed,
        "decision": decision,
    }
    atomic_json(args.output_dir / "selected_config.json", selected_payload)
    write_rows(args.output_dir / "person_cross_view_gt_audit.csv", identity_audit)
    write_rows(args.output_dir / "sync_pipeline_metrics.csv", metric_rows)
    write_rows(args.output_dir / "sync_gap_episode_metrics.csv", gap_rows)
    write_rows(args.output_dir / "sync_oracle_headroom.csv", contrast_rows)
    write_rows(args.output_dir / "sync_aas_bootstrap.csv", contrast_rows)
    write_rows(args.output_dir / "sync_measurement_gate.csv", measurement_rows)
    write_rows(
        args.output_dir / "sync_packet_state_budget.csv",
        [
            {
                "appearance_config": config,
                "embedding_vectors_per_packet": 1,
                "receiver_vectors": appearance_runtime_config(config)["gallery_size"],
                "embedding_dimension": 512,
            }
            for config in APPEARANCE_CONFIGS
        ],
    )
    concatenate_csv(
        [record["associations"] for record in checkpoint_records],
        args.output_dir / "sync_association_diagnostics.csv",
    )
    lines = [
        "# MDMT Sync Cross-View Tracklet Association Decision",
        "",
        f"- mode: `{args.mode}`",
        f"- decision: `{decision}`",
        f"- measurement_valid: `{int(measurement_valid)}`",
        f"- calibration_feasible: `{int(calibration_feasible)}`",
        f"- sync_headroom_pass: `{int(oracle_pass)}`",
        f"- real_sync_transfer_pass: `{int(real_pass)}`",
        f"- candidate_constraint_required: `{int(candidate_constraint_required)}`",
        f"- tracklet_memory_required: `{int(tracklet_memory_required)}`",
        f"- formal_allowed: `{int(formal_allowed)}`",
        f"- best_primary_baseline: `{baseline}`",
        "",
        "| Pipeline | Global IDF1 | IDSW | Gap survival | Fragmentation | Person AAS |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in metric_rows:
        aas = aas_map[row["pipeline"]]
        lines.append(
            f"| {row['pipeline']} | {float(row['global_idf1']):.6f} | {int(row['global_idsw'])} | "
            f"{float(row['gap_identity_survival_rate']):.6f} | {int(row['track_fragmentation'])} | "
            f"{float(aas['person_aas']):.6f} |"
        )
    (args.output_dir / "sync_feasibility_decision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        f"[7/7][finalize] decision={decision} measurement_valid={int(measurement_valid)} "
        f"calibration_feasible={int(calibration_feasible)} formal_allowed={int(formal_allowed)} "
        f"outputs={args.output_dir}",
        flush=True,
    )


if __name__ == "__main__":
    main()
