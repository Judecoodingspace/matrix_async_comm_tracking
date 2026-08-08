"""Causal appearance memories for synchronous MDMT tracklet association."""

from __future__ import annotations

import hashlib
from collections import defaultdict, deque
from dataclasses import replace
from typing import Mapping, Sequence

import numpy as np

from tracking.matrix_identity_cue import normalize_vector
from tracking.mdmt_global_tracklet_fusion import cosine_similarity, select_precision_threshold
from tracking.tracklet_packets import GlobalFusionPacket, IncrementalTrackletUpdate


APPEARANCE_CONFIGS = (
    "latest",
    "cumulative_mean",
    "ema_0.9",
    "window_mean_3",
    "window_mean_5",
    "window_mean_10",
    "receiver_gallery_max_5",
    "receiver_gallery_max_10",
    "receiver_gallery_top3_of_10",
)

CANDIDATE_POLICIES = (
    "all_history",
    "primary_active",
    "primary_active_or_recent_5",
)


def appearance_runtime_config(name: str) -> dict[str, object]:
    if name not in APPEARANCE_CONFIGS:
        raise ValueError(f"unknown appearance config: {name}")
    if name == "receiver_gallery_max_5":
        return {"score_mode": "gallery_max", "gallery_size": 5, "gallery_top_k": 1}
    if name == "receiver_gallery_max_10":
        return {"score_mode": "gallery_max", "gallery_size": 10, "gallery_top_k": 1}
    if name == "receiver_gallery_top3_of_10":
        return {"score_mode": "gallery_topk", "gallery_size": 10, "gallery_top_k": 3}
    return {"score_mode": "latest", "gallery_size": 1, "gallery_top_k": 1}


def _window_size(name: str) -> int | None:
    return int(name.rsplit("_", 1)[-1]) if name.startswith("window_mean_") else None


def build_appearance_packets(
    updates: Sequence[IncrementalTrackletUpdate],
    *,
    appearance_config: str,
    delay_frames: int = 0,
) -> list[GlobalFusionPacket]:
    """Build one-vector causal packets from local-tracklet updates."""
    runtime = appearance_runtime_config(appearance_config)
    window_size = _window_size(appearance_config)
    sums: dict[int, np.ndarray] = {}
    counts: dict[int, int] = defaultdict(int)
    emas: dict[int, np.ndarray] = {}
    windows: dict[int, deque[np.ndarray]] = {}
    latest: dict[int, np.ndarray] = {}
    packets: list[GlobalFusionPacket] = []
    for update in sorted(updates, key=lambda row: (row.capture_time, row.local_track_id)):
        track_id = int(update.local_track_id)
        measurement = update.latest_embedding if update.has_measurement else None
        if measurement is not None:
            value = normalize_vector(measurement).astype(np.float64)
            latest[track_id] = value
            if track_id not in sums:
                sums[track_id] = value.copy()
            else:
                sums[track_id] += value
            counts[track_id] += 1
            if track_id not in emas:
                emas[track_id] = value.copy()
            else:
                emas[track_id] = normalize_vector(0.9 * emas[track_id] + 0.1 * value)
            if window_size is not None:
                windows.setdefault(track_id, deque(maxlen=window_size)).append(value.copy())

        if appearance_config in {
            "latest",
            "receiver_gallery_max_5",
            "receiver_gallery_max_10",
            "receiver_gallery_top3_of_10",
        }:
            descriptor = latest.get(track_id)
            appearance_count = int(descriptor is not None)
        elif appearance_config == "cumulative_mean":
            descriptor = None if track_id not in sums else normalize_vector(sums[track_id])
            appearance_count = counts[track_id]
        elif appearance_config == "ema_0.9":
            descriptor = emas.get(track_id)
            appearance_count = counts[track_id]
        else:
            history = list(windows.get(track_id, ()))
            descriptor = None if not history else normalize_vector(np.sum(history, axis=0))
            appearance_count = len(history)

        packets.append(
            GlobalFusionPacket(
                sequence_id=str(update.sequence_id),
                view_id=int(update.view_id),
                source_track_id=track_id,
                tracklet_id_persistent=(
                    f"{update.sequence_id}:V{int(update.view_id)}:T{track_id}"
                ),
                capture_frame=int(update.capture_time),
                arrival_frame=int(update.capture_time) + int(delay_frames),
                tracklet_start_frame=int(update.tracklet_start_frame),
                history_length=int(update.history_length),
                latest_bbox=tuple(float(value) for value in update.latest_bbox),
                bbox_velocity=tuple(float(value) for value in update.bbox_velocity),
                appearance_vector=(
                    None if descriptor is None else np.asarray(descriptor, dtype=np.float64).copy()
                ),
                appearance_kind=appearance_config,
                appearance_count=int(appearance_count),
                hit_count=int(update.hit_count),
                miss_count=int(update.miss_count),
                has_measurement=bool(update.has_measurement),
                sensor_key=update.sensor_key,
            )
        )
    return packets


def _memory_score(
    query: np.ndarray,
    history: Sequence[np.ndarray],
    *,
    appearance_config: str,
) -> float | None:
    runtime = appearance_runtime_config(appearance_config)
    if not history:
        return None
    if runtime["score_mode"] == "latest":
        return cosine_similarity(query, history[-1])
    size = int(runtime["gallery_size"])
    values = [cosine_similarity(query, value) for value in history[-size:]]
    scores = sorted((float(value) for value in values if value is not None), reverse=True)
    if not scores:
        return None
    if runtime["score_mode"] == "gallery_max":
        return scores[0]
    count = min(int(runtime["gallery_top_k"]), len(scores))
    return float(np.mean(scores[:count]))


def build_candidate_pairs(
    *,
    sequence_id: str,
    primary_view: int,
    support_view: int,
    primary_packets: Sequence[GlobalFusionPacket],
    support_packets: Sequence[GlobalFusionPacket],
    primary_track_identity: Mapping[int, int],
    support_track_identity: Mapping[int, int],
    strict_identities: set[int],
    appearance_config: str,
    candidate_policy: str,
    candidate_recent_frames: int,
) -> list[dict[str, object]]:
    if candidate_policy not in CANDIDATE_POLICIES:
        raise ValueError(f"unknown candidate policy: {candidate_policy}")
    primary_by_frame: dict[int, list[GlobalFusionPacket]] = defaultdict(list)
    support_by_frame: dict[int, list[GlobalFusionPacket]] = defaultdict(list)
    for packet in primary_packets:
        if packet.has_measurement and packet.appearance_vector is not None:
            primary_by_frame[packet.capture_frame].append(packet)
    for packet in support_packets:
        if packet.has_measurement and packet.appearance_vector is not None:
            support_by_frame[packet.capture_frame].append(packet)

    primary_history: dict[int, list[np.ndarray]] = defaultdict(list)
    latest_capture: dict[int, int] = {}
    result: list[dict[str, object]] = []
    for frame_id in sorted(set(primary_by_frame) | set(support_by_frame)):
        for packet in primary_by_frame.get(frame_id, ()):
            primary_history[packet.source_track_id].append(packet.appearance_vector.copy())
            latest_capture[packet.source_track_id] = frame_id
        if candidate_policy == "all_history":
            candidates = sorted(primary_history)
        elif candidate_policy == "primary_active":
            candidates = sorted(track for track, frame in latest_capture.items() if frame == frame_id)
        else:
            candidates = sorted(
                track
                for track, frame in latest_capture.items()
                if 0 <= frame_id - frame <= int(candidate_recent_frames)
            )
        for support in support_by_frame.get(frame_id, ()):
            support_identity = support_track_identity.get(support.source_track_id)
            if support_identity not in strict_identities:
                continue
            for primary_track in candidates:
                primary_identity = primary_track_identity.get(primary_track)
                if primary_identity not in strict_identities:
                    continue
                similarity = _memory_score(
                    support.appearance_vector,
                    primary_history[primary_track],
                    appearance_config=appearance_config,
                )
                if similarity is None:
                    continue
                result.append(
                    {
                        "sequence_id": str(sequence_id),
                        "direction": f"{primary_view}:{support_view}",
                        "appearance_config": appearance_config,
                        "candidate_policy": candidate_policy,
                        "frame_id": int(frame_id),
                        "primary_track_id": int(primary_track),
                        "support_track_id": int(support.source_track_id),
                        "primary_age_frames": int(frame_id - latest_capture[primary_track]),
                        "similarity": float(similarity),
                        "same_identity": int(int(primary_identity) == int(support_identity)),
                    }
                )
    return result


def build_primary_reid_pairs(
    *,
    sequence_id: str,
    direction: str,
    packets: Sequence[GlobalFusionPacket],
    track_identity: Mapping[int, int],
    strict_identities: set[int],
) -> list[dict[str, object]]:
    measured = [
        packet
        for packet in packets
        if packet.has_measurement and packet.appearance_vector is not None
    ]
    final: dict[int, GlobalFusionPacket] = {}
    ranges: dict[int, list[int]] = defaultdict(list)
    for packet in measured:
        final[packet.source_track_id] = packet
        ranges[packet.source_track_id].append(packet.capture_frame)
    result: list[dict[str, object]] = []
    for current in sorted(final, key=lambda track: min(ranges[track])):
        identity = track_identity.get(current)
        if identity not in strict_identities:
            continue
        start = min(ranges[current])
        for previous in sorted(final):
            previous_identity = track_identity.get(previous)
            if previous_identity not in strict_identities or max(ranges[previous]) >= start:
                continue
            similarity = cosine_similarity(
                final[current].appearance_vector,
                final[previous].appearance_vector,
            )
            if similarity is not None:
                result.append(
                    {
                        "sequence_id": str(sequence_id),
                        "direction": direction,
                        "similarity": float(similarity),
                        "same_identity": int(int(identity) == int(previous_identity)),
                    }
                )
    return result


def evaluate_threshold(rows: Sequence[Mapping[str, object]], threshold: float) -> dict[str, float | int]:
    labels = np.asarray([int(row["same_identity"]) for row in rows], dtype=np.int8)
    scores = np.asarray([float(row["similarity"]) for row in rows], dtype=np.float64)
    accepted = scores >= float(threshold)
    true_positive = int(labels[accepted].sum()) if accepted.size else 0
    false_positive = int(accepted.sum()) - true_positive
    positives = int(labels.sum())
    precision = true_positive / max(true_positive + false_positive, 1)
    recall = true_positive / max(positives, 1)
    return {
        "precision": float(precision),
        "recall": float(recall),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "n_pairs": len(rows),
        "n_positive": positives,
    }


def average_precision(rows: Sequence[Mapping[str, object]]) -> float:
    if not rows:
        return 0.0
    scores = np.asarray([float(row["similarity"]) for row in rows], dtype=np.float64)
    labels = np.asarray([int(row["same_identity"]) for row in rows], dtype=np.int8)
    positives = int(labels.sum())
    if positives == 0:
        return 0.0
    order = np.argsort(-scores, kind="stable")
    truth = labels[order]
    precision = np.cumsum(truth) / np.arange(1, len(truth) + 1)
    return float(np.sum(precision * truth) / positives)


def loso_calibration(
    rows: Sequence[Mapping[str, object]],
    *,
    sequence_ids: Sequence[str],
    minimum_precision: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    folds: list[dict[str, object]] = []
    heldout_predictions: list[dict[str, object]] = []
    for heldout in sequence_ids:
        training = [row for row in rows if str(row["sequence_id"]) != str(heldout)]
        evaluation = [row for row in rows if str(row["sequence_id"]) == str(heldout)]
        if training:
            selected = select_precision_threshold(
                [float(row["similarity"]) for row in training],
                [int(row["same_identity"]) for row in training],
                minimum_precision=minimum_precision,
            )
        else:
            selected = {
                "threshold": 1.000001,
                "precision": 0.0,
                "recall": 0.0,
                "calibration_feasible": 0,
            }
        evaluated = evaluate_threshold(evaluation, float(selected["threshold"]))
        folds.append(
            {
                "heldout_sequence": str(heldout),
                "threshold": selected["threshold"],
                "train_precision": selected["precision"],
                "train_recall": selected["recall"],
                "calibration_feasible": int(selected.get("calibration_feasible", 0)),
                "eval_precision": evaluated["precision"],
                "eval_recall": evaluated["recall"],
                "eval_pairs": evaluated["n_pairs"],
                "eval_positive": evaluated["n_positive"],
            }
        )
        heldout_predictions.extend(
            {**dict(row), "accepted": int(float(row["similarity"]) >= float(selected["threshold"]))}
            for row in evaluation
        )
    accepted = [row for row in heldout_predictions if int(row["accepted"])]
    tp = sum(int(row["same_identity"]) for row in accepted)
    fp = len(accepted) - tp
    positives = sum(int(row["same_identity"]) for row in heldout_predictions)
    full = select_precision_threshold(
        [float(row["similarity"]) for row in rows],
        [int(row["same_identity"]) for row in rows],
        minimum_precision=minimum_precision,
    ) if rows else {
        "threshold": 1.000001,
        "calibration_feasible": 0,
    }
    summary = {
        "cv_precision": float(tp / max(tp + fp, 1)),
        "cv_recall": float(tp / max(positives, 1)),
        "cv_true_positive": int(tp),
        "cv_false_positive": int(fp),
        "cv_pairs": len(heldout_predictions),
        "cv_positive": int(positives),
        "cv_average_precision": average_precision(heldout_predictions),
        "all_folds_calibration_feasible": int(all(int(row["calibration_feasible"]) for row in folds)),
        "full_val_threshold": float(full["threshold"]),
        "full_val_calibration_feasible": int(full.get("calibration_feasible", 0)),
    }
    return folds, summary


def pr_curve_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    points: int = 101,
) -> list[dict[str, object]]:
    if not rows:
        return []
    scores = np.asarray([float(row["similarity"]) for row in rows], dtype=np.float64)
    thresholds = np.unique(np.quantile(scores, np.linspace(0.0, 1.0, int(points))))
    return [
        {"threshold": float(threshold), **evaluate_threshold(rows, float(threshold))}
        for threshold in thresholds[::-1]
    ]


def oracle_identity_packets(
    packets: Sequence[GlobalFusionPacket],
    *,
    track_identity: Mapping[int, int],
    seed: int,
    dimension: int = 512,
) -> list[GlobalFusionPacket]:
    vectors: dict[int, np.ndarray] = {}
    result: list[GlobalFusionPacket] = []
    for packet in packets:
        identity = track_identity.get(packet.source_track_id)
        if identity is None:
            result.append(replace(packet, appearance_vector=None))
            continue
        if identity not in vectors:
            digest = hashlib.sha256(f"{seed}:{packet.sequence_id}:{identity}".encode("utf-8")).digest()
            vector_seed = int.from_bytes(digest[:8], "little", signed=False)
            vector = np.random.default_rng(vector_seed).normal(size=int(dimension))
            vectors[identity] = normalize_vector(vector).astype(np.float64)
        result.append(replace(packet, appearance_vector=vectors[identity].copy(), appearance_kind="oracle"))
    return result
