"""Controlled OOSM baseline tracker for Phase 2 validation."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from tracking.delay_injection import DelayedObservation
from tracking.mot_metrics import Prediction, compute_identity_metrics


@dataclass(frozen=True)
class SupportUpdate:
    frame_id: int
    capture_time: int
    arrival_time: int
    delay: int
    track_id: int
    embedding: np.ndarray
    weight: float


@dataclass(frozen=True)
class TrackerRun:
    name: str
    predictions: list[Prediction]
    metrics: object
    latency_ms_per_frame: float
    support_updates_applied: int


class PrototypeTracker:
    """Tiny ReID-prototype tracker for GT-box controlled experiments."""

    def __init__(
        self,
        *,
        match_threshold: float = 0.20,
        support_threshold: float = 0.20,
        prototype_momentum: float = 0.20,
    ) -> None:
        self.match_threshold = float(match_threshold)
        self.support_threshold = float(support_threshold)
        self.prototype_momentum = float(prototype_momentum)
        self.next_track_id = 1
        self.prototypes: dict[int, np.ndarray] = {}

    def apply_support(self, embedding: np.ndarray, *, weight: float) -> bool:
        return self.apply_support_if_confident(embedding, weight=weight, min_margin=None)

    def apply_support_if_confident(
        self,
        embedding: np.ndarray,
        *,
        weight: float,
        min_margin: float | None,
    ) -> bool:
        if not self.prototypes:
            return False
        track_id, score, margin = nearest_prototype_with_margin(self.prototypes, embedding)
        if track_id is None or score < self.support_threshold:
            return False
        if min_margin is not None and margin < float(min_margin):
            return False
        update_weight = max(0.0, min(1.0, self.prototype_momentum * float(weight)))
        self.prototypes[track_id] = normalized_blend(self.prototypes[track_id], embedding, update_weight)
        return True

    def assign_frame(self, frame_embeddings: Mapping[int, np.ndarray], *, frame_id: int) -> list[Prediction]:
        gt_ids = sorted(int(value) for value in frame_embeddings)
        if not gt_ids:
            return []

        assigned: dict[int, int] = {}
        if self.prototypes:
            track_ids = sorted(self.prototypes)
            sims = np.zeros((len(gt_ids), len(track_ids)), dtype=np.float32)
            for row_idx, gt_id in enumerate(gt_ids):
                for col_idx, track_id in enumerate(track_ids):
                    sims[row_idx, col_idx] = cosine(frame_embeddings[gt_id], self.prototypes[track_id])
            row_ind, col_ind = linear_sum_assignment(-sims)
            for row_idx, col_idx in zip(row_ind, col_ind):
                score = float(sims[row_idx, col_idx])
                if score >= self.match_threshold:
                    assigned[gt_ids[row_idx]] = track_ids[col_idx]

        predictions: list[Prediction] = []
        for gt_id in gt_ids:
            pred_id = assigned.get(gt_id)
            if pred_id is None:
                pred_id = self.next_track_id
                self.next_track_id += 1
            self.prototypes[pred_id] = normalized_blend(
                self.prototypes.get(pred_id),
                frame_embeddings[gt_id],
                self.prototype_momentum,
            )
            predictions.append(Prediction(frame_id=int(frame_id), gt_id=int(gt_id), pred_id=int(pred_id)))
        return predictions


def run_oosm_baseline(
    *,
    name: str,
    base_embeddings: Mapping[int, Mapping[int, np.ndarray]],
    support_embeddings: Mapping[int, Mapping[int, np.ndarray]],
    delayed_observations: Sequence[DelayedObservation],
    frame_start: int,
    frame_end: int,
    match_threshold: float = 0.20,
    support_threshold: float = 0.20,
    prototype_momentum: float = 0.20,
    exp_decay_half_life: float = 10.0,
    event_gate_min_similarity: float = 0.60,
    event_gate_capture_min_margin: float = 0.05,
    event_gate_arrival_max_margin: float = 0.05,
    event_gate_apply_min_margin: float = 0.05,
) -> TrackerRun:
    start = time.perf_counter()
    schedule = build_support_schedule(
        name=name,
        support_embeddings=support_embeddings,
        base_embeddings=base_embeddings,
        delayed_observations=delayed_observations,
        exp_decay_half_life=exp_decay_half_life,
        event_gate_min_similarity=event_gate_min_similarity,
        event_gate_capture_min_margin=event_gate_capture_min_margin,
        event_gate_arrival_max_margin=event_gate_arrival_max_margin,
    )
    tracker = PrototypeTracker(
        match_threshold=match_threshold,
        support_threshold=support_threshold,
        prototype_momentum=prototype_momentum,
    )
    predictions: list[Prediction] = []
    applied = 0
    for frame_id in range(int(frame_start), int(frame_end) + 1):
        predictions.extend(tracker.assign_frame(base_embeddings.get(frame_id, {}), frame_id=frame_id))
        for update in schedule.get(frame_id, []):
            min_margin = event_gate_apply_min_margin if name == "event_gated_backfill" else None
            if tracker.apply_support_if_confident(update.embedding, weight=update.weight, min_margin=min_margin):
                applied += 1
    elapsed = time.perf_counter() - start
    n_frames = max(1, int(frame_end) - int(frame_start) + 1)
    return TrackerRun(
        name=name,
        predictions=predictions,
        metrics=compute_identity_metrics(predictions),
        latency_ms_per_frame=(elapsed * 1000.0 / n_frames),
        support_updates_applied=applied,
    )


def build_support_schedule(
    *,
    name: str,
    support_embeddings: Mapping[int, Mapping[int, np.ndarray]],
    base_embeddings: Mapping[int, Mapping[int, np.ndarray]] | None = None,
    delayed_observations: Sequence[DelayedObservation],
    exp_decay_half_life: float,
    event_gate_min_similarity: float = 0.60,
    event_gate_capture_min_margin: float = 0.05,
    event_gate_arrival_max_margin: float = 0.05,
) -> dict[int, list[SupportUpdate]]:
    schedule: dict[int, list[SupportUpdate]] = defaultdict(list)
    if name == "discard_oosm":
        return schedule

    for obs in delayed_observations:
        embedding = support_embeddings.get(int(obs.capture_time), {}).get(int(obs.track_id))
        if embedding is None:
            continue
        if name == "backfill":
            frame_id = int(obs.capture_time)
            weight = 1.0
        elif name == "event_gated_backfill":
            if base_embeddings is None or not event_gate_accepts(
                embedding,
                capture_candidates=base_embeddings.get(int(obs.capture_time), {}),
                arrival_candidates=base_embeddings.get(int(obs.arrival_time), {}),
                min_similarity=event_gate_min_similarity,
                capture_min_margin=event_gate_capture_min_margin,
                arrival_max_margin=event_gate_arrival_max_margin,
            ):
                continue
            frame_id = int(obs.capture_time)
            weight = 1.0
        elif name == "fuse_at_current":
            frame_id = int(obs.arrival_time)
            weight = 1.0
        elif name == "fuse_at_current_exp_decay":
            frame_id = int(obs.arrival_time)
            weight = math.exp(-math.log(2.0) * float(obs.delay) / float(exp_decay_half_life))
        else:
            raise ValueError(f"Unknown OOSM baseline: {name}")
        schedule[frame_id].append(
            SupportUpdate(
                frame_id=frame_id,
                capture_time=int(obs.capture_time),
                arrival_time=int(obs.arrival_time),
                delay=int(obs.delay),
                track_id=int(obs.track_id),
                embedding=embedding,
                weight=weight,
            )
        )
    return schedule


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def nearest_prototype(prototypes: Mapping[int, np.ndarray], embedding: np.ndarray) -> tuple[int | None, float]:
    best_id, best_score, _ = nearest_prototype_with_margin(prototypes, embedding)
    return best_id, best_score


def nearest_prototype_with_margin(
    prototypes: Mapping[int, np.ndarray],
    embedding: np.ndarray,
) -> tuple[int | None, float, float]:
    ranked = sorted(
        ((cosine(proto, embedding), int(track_id)) for track_id, proto in prototypes.items()),
        reverse=True,
    )
    if not ranked:
        return None, -1.0, 0.0
    best_score, best_id = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else -1.0
    return best_id, float(best_score), float(best_score - second_score)


def event_gate_accepts(
    support_embedding: np.ndarray,
    *,
    capture_candidates: Mapping[int, np.ndarray],
    arrival_candidates: Mapping[int, np.ndarray],
    min_similarity: float,
    capture_min_margin: float,
    arrival_max_margin: float,
) -> bool:
    """Observable gate for rare support OOSM Backfill updates."""
    capture_id, capture_score, capture_margin = nearest_prototype_with_margin(
        capture_candidates,
        support_embedding,
    )
    if capture_id is None:
        return False
    if capture_score < float(min_similarity) or capture_margin < float(capture_min_margin):
        return False

    arrival_id, _, arrival_margin = nearest_prototype_with_margin(arrival_candidates, support_embedding)
    if arrival_id is None:
        return True
    return arrival_id != capture_id or arrival_margin <= float(arrival_max_margin)


def normalized_blend(previous: np.ndarray | None, current: np.ndarray, weight: float) -> np.ndarray:
    if previous is None:
        out = np.asarray(current, dtype=np.float32)
    else:
        out = (1.0 - float(weight)) * np.asarray(previous, dtype=np.float32)
        out = out + (float(weight) * np.asarray(current, dtype=np.float32))
    norm = float(np.linalg.norm(out))
    return out / norm if norm > 0.0 else out
