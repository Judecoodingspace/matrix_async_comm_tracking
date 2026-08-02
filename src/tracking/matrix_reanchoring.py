"""Tracker-state-aware delayed re-anchoring baselines for MATRIX occlusion MOT."""

from __future__ import annotations

import math
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from tracking.matrix_identity_cue import ObservationEmbeddingMap, cosine_similarity, observation_sensor_key
from tracking.matrix_gt import MatrixObservation, MatrixTrackerRun
from tracking.mot_metrics import Prediction, compute_identity_metrics


@dataclass
class WorldSortTrack:
    track_id: int
    state: np.ndarray
    covariance: np.ndarray
    age: int
    hit_count: int
    miss_count: int
    last_frame: int
    last_primary_seen_frame: int | None
    last_support_seen_frame: int | None
    last_update_source: str
    association_margin: float = float("inf")
    fixed_lag_updates: int = 0
    recovery_updates: int = 0
    appearance_embedding: np.ndarray | None = None
    appearance_updates: int = 0
    last_identity_seen_frame: int | None = None
    identity_updates: int = 0

    @property
    def xy(self) -> np.ndarray:
        return self.state[:2]

    def copy(self) -> "WorldSortTrack":
        return WorldSortTrack(
            track_id=int(self.track_id),
            state=self.state.copy(),
            covariance=self.covariance.copy(),
            age=int(self.age),
            hit_count=int(self.hit_count),
            miss_count=int(self.miss_count),
            last_frame=int(self.last_frame),
            last_primary_seen_frame=self.last_primary_seen_frame,
            last_support_seen_frame=self.last_support_seen_frame,
            last_update_source=str(self.last_update_source),
            association_margin=float(self.association_margin),
            fixed_lag_updates=int(self.fixed_lag_updates),
            recovery_updates=int(self.recovery_updates),
            appearance_embedding=None if self.appearance_embedding is None else self.appearance_embedding.copy(),
            appearance_updates=int(self.appearance_updates),
            last_identity_seen_frame=self.last_identity_seen_frame,
            identity_updates=int(self.identity_updates),
        )


@dataclass(frozen=True)
class TrackerSnapshot:
    next_track_id: int
    tracks: dict[int, WorldSortTrack]


@dataclass(frozen=True)
class ReanchoringRun:
    pipeline: str
    delay_profile: str
    predictions: list[Prediction]
    diagnostics: list[dict[str, object]]
    mode_counts: dict[str, int]
    notes: str
    delay_frames: int
    delay_ms: float
    latency_ms_per_frame: float


class SupportUpdatePolicy(str, Enum):
    """Select which tracker state dimensions a support observation may update."""

    CURRENT_JOINT = "current_joint"
    POSITION_ONLY = "position_only"
    IDENTITY_GATED_POSITION_ONLY = "identity_gated_position_only"
    IDENTITY_ONLY_STRICT = "identity_only_strict"
    IDENTITY_ONLY_WITH_LIFECYCLE = "identity_only_with_lifecycle"
    SEPARATED = "separated_update"


def _obs_xy(obs: MatrixObservation) -> np.ndarray:
    return np.asarray(obs.world_xy, dtype=np.float64)


def _collapse_geometric_observations(
    observations: Sequence[MatrixObservation],
    *,
    precision: int = 4,
) -> list[MatrixObservation]:
    """Collapse duplicate multi-view measurements without reading person IDs."""
    grouped: dict[tuple[float, float], list[MatrixObservation]] = defaultdict(list)
    for obs in observations:
        xy = _obs_xy(obs)
        key = (round(float(xy[0]), precision), round(float(xy[1]), precision))
        grouped[key].append(obs)

    collapsed: list[MatrixObservation] = []
    for rows in grouped.values():
        first = rows[0]
        xyz = np.asarray([row.world_xyz for row in rows], dtype=np.float64).mean(axis=0)
        collapsed.append(
            MatrixObservation(
                frame_id=int(first.frame_id),
                drone_id=int(first.drone_id),
                person_id=int(first.person_id),  # evaluation metadata only
                position_id=int(first.position_id),
                world_xyz=(float(xyz[0]), float(xyz[1]), float(xyz[2])),
                bbox_xyxy=first.bbox_xyxy,
                capture_time=int(first.capture_time),
                arrival_time=int(first.arrival_time),
                delay=int(first.delay),
            )
        )
    return sorted(collapsed, key=lambda obs: (float(obs.world_xy[0]), float(obs.world_xy[1]), int(obs.drone_id)))


class WorldSortTracker:
    """A small BEV/SORT-style tracker for controlled GT world-coordinate tests."""

    def __init__(
        self,
        *,
        distance_threshold: float = 1.0,
        process_noise: float = 0.05,
        measurement_noise: float = 0.05,
        initial_covariance: float = 0.10,
        max_miss: int = 1000,
    ) -> None:
        self.distance_threshold = float(distance_threshold)
        self.process_noise = float(process_noise)
        self.measurement_noise = float(measurement_noise)
        self.initial_covariance = float(initial_covariance)
        self.max_miss = int(max_miss)
        self.next_track_id = 1
        self.tracks: dict[int, WorldSortTrack] = {}

    def snapshot(self) -> TrackerSnapshot:
        return TrackerSnapshot(
            next_track_id=int(self.next_track_id),
            tracks={track_id: track.copy() for track_id, track in self.tracks.items()},
        )

    def restore(self, snapshot: TrackerSnapshot | None) -> None:
        if snapshot is None:
            self.next_track_id = 1
            self.tracks = {}
            return
        self.next_track_id = int(snapshot.next_track_id)
        self.tracks = {track_id: track.copy() for track_id, track in snapshot.tracks.items()}

    def predict_to(self, frame_id: int) -> None:
        for track in self.tracks.values():
            dt = int(frame_id) - int(track.last_frame)
            if dt <= 0:
                continue
            f = np.asarray(
                [
                    [1.0, 0.0, float(dt), 0.0],
                    [0.0, 1.0, 0.0, float(dt)],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                dtype=np.float64,
            )
            q = self.process_noise
            q_mat = np.diag([q * dt * dt, q * dt * dt, q * dt, q * dt]).astype(np.float64)
            track.state = f @ track.state
            track.covariance = f @ track.covariance @ f.T + q_mat
            track.last_frame = int(frame_id)
            track.age += int(dt)

    def covariance_trace(self, track_id: int) -> float:
        track = self.tracks[int(track_id)]
        return float(np.trace(track.covariance[:2, :2]))

    def ranked_tracks(self, xy: np.ndarray, *, track_ids: Sequence[int] | None = None) -> list[tuple[int, float]]:
        if track_ids is None:
            candidates = sorted(self.tracks)
        else:
            candidates = sorted(int(track_id) for track_id in track_ids if int(track_id) in self.tracks)
        xy_arr = np.asarray(xy, dtype=np.float64)
        return sorted(
            (
                (int(track_id), float(np.linalg.norm(xy_arr - self.tracks[int(track_id)].xy)))
                for track_id in candidates
            ),
            key=lambda item: (item[1], item[0]),
        )

    def association_margin(self, xy: np.ndarray, *, track_ids: Sequence[int] | None = None) -> float:
        ranked = self.ranked_tracks(xy, track_ids=track_ids)
        if len(ranked) < 2:
            return float("inf")
        return float(ranked[1][1] - ranked[0][1])

    def create_track(
        self,
        xy: np.ndarray,
        *,
        frame_id: int,
        source: str,
        appearance_embedding: np.ndarray | None = None,
    ) -> int:
        xy_arr = np.asarray(xy, dtype=np.float64)
        track_id = int(self.next_track_id)
        self.next_track_id += 1
        state = np.asarray([xy_arr[0], xy_arr[1], 0.0, 0.0], dtype=np.float64)
        covariance = np.eye(4, dtype=np.float64) * self.initial_covariance
        self.tracks[track_id] = WorldSortTrack(
            track_id=track_id,
            state=state,
            covariance=covariance,
            age=1,
            hit_count=1,
            miss_count=0,
            last_frame=int(frame_id),
            last_primary_seen_frame=int(frame_id) if source == "primary" else None,
            last_support_seen_frame=int(frame_id) if source == "support" else None,
            last_update_source=source,
            appearance_embedding=None if appearance_embedding is None else np.asarray(appearance_embedding, dtype=np.float64).copy(),
            appearance_updates=0 if appearance_embedding is None else 1,
            last_identity_seen_frame=None if appearance_embedding is None else int(frame_id),
            identity_updates=0 if appearance_embedding is None else 1,
        )
        return track_id

    def _update_appearance(self, track_id: int, embedding: np.ndarray | None, *, alpha: float = 0.20) -> float:
        if embedding is None:
            return 0.0
        track = self.tracks[int(track_id)]
        emb = np.asarray(embedding, dtype=np.float64)
        norm = float(np.linalg.norm(emb))
        if norm <= 1.0e-12:
            return 0.0
        emb = emb / norm
        before = None if track.appearance_embedding is None else track.appearance_embedding.copy()
        if track.appearance_embedding is None:
            track.appearance_embedding = emb.copy()
        else:
            mixed = (1.0 - float(alpha)) * track.appearance_embedding + float(alpha) * emb
            mixed_norm = float(np.linalg.norm(mixed))
            track.appearance_embedding = mixed if mixed_norm <= 1.0e-12 else mixed / mixed_norm
        track.appearance_updates += 1
        if before is None:
            return 1.0
        similarity = cosine_similarity(before, track.appearance_embedding)
        return 0.0 if similarity is None else max(0.0, 1.0 - float(similarity))

    def _update_identity_state(
        self,
        track_id: int,
        embedding: np.ndarray | None,
        *,
        frame_id: int,
    ) -> float:
        track = self.tracks[int(track_id)]
        previous_updates = int(track.appearance_updates)
        shift = self._update_appearance(track_id, embedding)
        if int(track.appearance_updates) > previous_updates:
            track.last_identity_seen_frame = int(frame_id)
            track.identity_updates += 1
        return shift

    def _refresh_track_lifecycle(
        self,
        track_id: int,
        *,
        frame_id: int,
        source: str,
        mode: str,
        margin: float,
    ) -> None:
        track = self.tracks[int(track_id)]
        track.hit_count += 1
        track.miss_count = 0
        track.last_frame = int(frame_id)
        track.last_update_source = source
        track.association_margin = float(margin)
        if source == "primary":
            track.last_primary_seen_frame = int(frame_id)
        else:
            track.last_support_seen_frame = int(frame_id)
        if mode == "fixed_lag_update":
            track.fixed_lag_updates += 1
        if mode == "recovery_stitch":
            track.recovery_updates += 1

    def _update_position_state(
        self,
        track_id: int,
        xy: np.ndarray,
        *,
        measurement_noise: float | None = None,
    ) -> float:
        track = self.tracks[int(track_id)]
        before = track.state.copy()
        z = np.asarray(xy, dtype=np.float64)
        h = np.asarray([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=np.float64)
        noise = self.measurement_noise if measurement_noise is None else float(measurement_noise)
        r = np.eye(2, dtype=np.float64) * (noise ** 2)
        innovation = z - (h @ track.state)
        s = h @ track.covariance @ h.T + r
        k = track.covariance @ h.T @ np.linalg.inv(s)
        track.state = track.state + (k @ innovation)
        track.covariance = (np.eye(4, dtype=np.float64) - k @ h) @ track.covariance
        return float(np.linalg.norm(track.state[:2] - before[:2]))

    def _update_track(
        self,
        track_id: int,
        xy: np.ndarray,
        *,
        frame_id: int,
        source: str,
        mode: str,
        margin: float,
        measurement_noise: float | None = None,
        appearance_embedding: np.ndarray | None = None,
    ) -> None:
        self._update_position_state(track_id, xy, measurement_noise=measurement_noise)
        self._refresh_track_lifecycle(
            track_id,
            frame_id=frame_id,
            source=source,
            mode=mode,
            margin=margin,
        )
        self._update_identity_state(track_id, appearance_embedding, frame_id=frame_id)

    def _identity_only_update(
        self,
        track_id: int,
        *,
        frame_id: int,
        source: str,
        mode: str,
        margin: float,
        appearance_embedding: np.ndarray | None = None,
    ) -> None:
        self._refresh_track_lifecycle(
            track_id,
            frame_id=frame_id,
            source=source,
            mode=mode,
            margin=margin,
        )
        self._update_identity_state(track_id, appearance_embedding, frame_id=frame_id)

    def _associate_primary(
        self,
        observations: Sequence[MatrixObservation],
        *,
        frame_id: int,
        appearance_embeddings: ObservationEmbeddingMap | None = None,
    ) -> tuple[set[int], list[dict[str, object]]]:
        obs_rows = _collapse_geometric_observations(observations)
        diagnostics: list[dict[str, object]] = []
        matched_tracks: set[int] = set()
        if not obs_rows:
            return matched_tracks, diagnostics

        track_ids = sorted(self.tracks)
        assignments: dict[int, int] = {}
        distances: dict[int, float] = {}
        if track_ids:
            cost = np.zeros((len(obs_rows), len(track_ids)), dtype=np.float64)
            for row, obs in enumerate(obs_rows):
                xy = _obs_xy(obs)
                for col, track_id in enumerate(track_ids):
                    cost[row, col] = float(np.linalg.norm(xy - self.tracks[track_id].xy))
            rows, cols = linear_sum_assignment(cost)
            for row, col in zip(rows, cols):
                distance = float(cost[row, col])
                if distance <= self.distance_threshold:
                    assignments[int(row)] = int(track_ids[col])
                    distances[int(row)] = distance

        for row, obs in enumerate(obs_rows):
            xy = _obs_xy(obs)
            margin = self.association_margin(xy)
            appearance = None if appearance_embeddings is None else appearance_embeddings.get(observation_sensor_key(obs))
            track_id = assignments.get(row)
            if track_id is None:
                track_id = self.create_track(
                    xy,
                    frame_id=frame_id,
                    source="primary",
                    appearance_embedding=appearance,
                )
                residual = 0.0
                mode = "primary_create"
            else:
                residual = distances[row]
                self._update_track(
                    track_id,
                    xy,
                    frame_id=frame_id,
                    source="primary",
                    mode="primary_update",
                    margin=margin,
                    appearance_embedding=appearance,
                )
                mode = "primary_update"
            matched_tracks.add(int(track_id))
            diagnostics.append(
                {
                    "mode": mode,
                    "track_id": int(track_id),
                    "residual_m": residual,
                    "association_margin_m": margin,
                    "source": "primary",
                }
            )
        return matched_tracks, diagnostics

    def update_support(
        self,
        observations: Sequence[MatrixObservation],
        *,
        frame_id: int,
        mode: str,
        allow_new_tracks: bool,
        margin_threshold: float,
        risky_only: bool = False,
        occlusion_keys: set[tuple[int, int]] | None = None,
        recovery_distance_threshold: float | None = None,
        appearance_embeddings: ObservationEmbeddingMap | None = None,
        use_identity_gate: bool = False,
        identity_accept_threshold: float = 0.25,
        identity_only_distance_threshold: float | None = None,
        support_measurement_noise: float | None = None,
        update_policy: SupportUpdatePolicy | str = SupportUpdatePolicy.CURRENT_JOINT,
    ) -> tuple[set[int], list[dict[str, object]]]:
        policy = SupportUpdatePolicy(update_policy)
        identity_policies = {
            SupportUpdatePolicy.IDENTITY_GATED_POSITION_ONLY,
            SupportUpdatePolicy.IDENTITY_ONLY_STRICT,
            SupportUpdatePolicy.IDENTITY_ONLY_WITH_LIFECYCLE,
            SupportUpdatePolicy.SEPARATED,
        }
        if policy in identity_policies and not use_identity_gate:
            raise ValueError(f"support update policy {policy.value} requires use_identity_gate=True")

        obs_rows = _collapse_geometric_observations(observations)
        diagnostics: list[dict[str, object]] = []
        matched_tracks: set[int] = set()
        used_tracks: set[int] = set()
        threshold = self.distance_threshold if recovery_distance_threshold is None else float(recovery_distance_threshold)
        identity_radius = threshold * 2.0 if identity_only_distance_threshold is None else float(identity_only_distance_threshold)

        def state_text(track: WorldSortTrack | None) -> str:
            if track is None:
                return ""
            return ",".join(f"{float(value):.6f}" for value in track.state)

        def action_diag(
            obs: MatrixObservation,
            *,
            action_mode: str,
            track_id: int | None,
            residual: float,
            margin: float,
            before: WorldSortTrack | None,
            reject_reason: str = "",
            identity_similarity: float | None = None,
            identity_gate_pass: bool = False,
            position_gate_pass: bool = False,
            identity_applied: bool = False,
            position_applied: bool = False,
            lifecycle_applied: bool = False,
        ) -> dict[str, object]:
            after = None if track_id is None else self.tracks.get(int(track_id))
            before_xy = None if before is None else before.xy.copy()
            after_xy = None if after is None else after.xy.copy()
            kinematic_shift = ""
            if before_xy is not None and after_xy is not None:
                kinematic_shift = f"{float(np.linalg.norm(after_xy - before_xy)):.6f}"
            appearance_shift = ""
            if before is not None and after is not None:
                similarity = cosine_similarity(before.appearance_embedding, after.appearance_embedding)
                if similarity is not None:
                    appearance_shift = f"{max(0.0, 1.0 - float(similarity)):.6f}"
                elif before.appearance_embedding is None and after.appearance_embedding is not None:
                    appearance_shift = "1.000000"
            row = {
                **_support_diag(obs, frame_id, action_mode, track_id, residual, margin, after, reject_reason),
                "update_policy": policy.value,
                "identity_gate_pass": int(identity_gate_pass),
                "position_gate_pass": int(position_gate_pass),
                "identity_applied": int(identity_applied),
                "position_applied": int(position_applied),
                "lifecycle_applied": int(lifecycle_applied),
                "identity_similarity": "" if identity_similarity is None else f"{float(identity_similarity):.6f}",
                "identity_accept_threshold": f"{float(identity_accept_threshold):.6f}" if use_identity_gate else "",
                "support_measurement_noise_m": "" if support_measurement_noise is None else f"{float(support_measurement_noise):.6f}",
                "kinematic_shift_m": kinematic_shift,
                "appearance_shift": appearance_shift,
                "state_before": state_text(before),
                "state_after": state_text(after),
                "covariance_trace_before": "" if before is None else f"{float(np.trace(before.covariance[:2, :2])):.6f}",
                "covariance_trace_after": "" if after is None else f"{float(np.trace(after.covariance[:2, :2])):.6f}",
                "miss_count_before": "" if before is None else int(before.miss_count),
                "miss_count_after": "" if after is None else int(after.miss_count),
            }
            return row

        for obs in obs_rows:
            xy = _obs_xy(obs)
            appearance = None if appearance_embeddings is None else appearance_embeddings.get(observation_sensor_key(obs))
            candidate_ids = [
                track_id for track_id, track in self.tracks.items()
                if int(track_id) not in used_tracks
                and (
                    not risky_only
                    or is_track_high_risk(
                        track,
                        current_frame=frame_id,
                        covariance_threshold=1.0,
                        occlusion_keys=occlusion_keys,
                        obs=obs,
                    )
                )
            ]
            ranked = self.ranked_tracks(xy, track_ids=candidate_ids)
            identity_scores = {
                int(track_id): cosine_similarity(self.tracks[int(track_id)].appearance_embedding, appearance)
                for track_id in candidate_ids
            }
            if use_identity_gate:
                ranked = [
                    (track_id, distance)
                    for track_id, distance in ranked
                    if identity_scores.get(int(track_id)) is not None
                    and float(identity_scores[int(track_id)]) >= float(identity_accept_threshold)
                ]
            margin = self.association_margin(xy, track_ids=[track_id for track_id, _distance in ranked])
            if not ranked:
                if allow_new_tracks:
                    track_id = self.create_track(
                        xy,
                        frame_id=frame_id,
                        source="support",
                        appearance_embedding=appearance,
                    )
                    matched_tracks.add(track_id)
                    used_tracks.add(track_id)
                    diagnostics.append(action_diag(
                        obs,
                        action_mode=mode,
                        track_id=track_id,
                        residual=0.0,
                        margin=margin,
                        before=None,
                        identity_gate_pass=not use_identity_gate,
                        position_gate_pass=True,
                        identity_applied=appearance is not None,
                        position_applied=True,
                        lifecycle_applied=True,
                    ))
                else:
                    diagnostics.append(action_diag(
                        obs,
                        action_mode="reject",
                        track_id=None,
                        residual=float("inf"),
                        margin=margin,
                        before=None,
                        reject_reason="identity_gate" if use_identity_gate else "no_track",
                    ))
                continue

            track_id, residual = ranked[0]
            identity_similarity = identity_scores.get(int(track_id))
            before = self.tracks[int(track_id)].copy()
            identity_pass = bool(
                use_identity_gate
                and identity_similarity is not None
                and float(identity_similarity) >= float(identity_accept_threshold)
            )
            position_pass = bool(residual <= threshold and margin >= float(margin_threshold))
            expanded_identity_pass = bool(identity_pass and residual <= identity_radius and margin >= float(margin_threshold))

            if policy == SupportUpdatePolicy.CURRENT_JOINT:
                reject_reason = ""
                if residual > threshold:
                    reject_reason = "candidate_gate"
                elif margin < float(margin_threshold):
                    reject_reason = "association_margin"
                if reject_reason and use_identity_gate and reject_reason == "candidate_gate" and residual <= identity_radius:
                    self._identity_only_update(
                        track_id,
                        frame_id=frame_id,
                        source="support",
                        mode=mode,
                        margin=margin,
                        appearance_embedding=appearance,
                    )
                    matched_tracks.add(int(track_id))
                    used_tracks.add(int(track_id))
                    diagnostics.append(action_diag(
                        obs,
                        action_mode="identity_only_update",
                        track_id=track_id,
                        residual=residual,
                        margin=margin,
                        before=before,
                        identity_similarity=identity_similarity,
                        identity_gate_pass=identity_pass,
                        identity_applied=True,
                        lifecycle_applied=True,
                    ))
                    continue
                if reject_reason:
                    diagnostics.append(action_diag(
                        obs,
                        action_mode="reject",
                        track_id=track_id,
                        residual=residual,
                        margin=margin,
                        before=before,
                        reject_reason=reject_reason,
                        identity_similarity=identity_similarity,
                        identity_gate_pass=identity_pass,
                    ))
                    continue
                self._update_track(
                    track_id,
                    xy,
                    frame_id=frame_id,
                    source="support",
                    mode=mode,
                    margin=margin,
                    measurement_noise=support_measurement_noise,
                    appearance_embedding=appearance,
                )
                matched_tracks.add(int(track_id))
                used_tracks.add(int(track_id))
                diagnostics.append(action_diag(
                    obs,
                    action_mode=mode,
                    track_id=track_id,
                    residual=residual,
                    margin=margin,
                    before=before,
                    identity_similarity=identity_similarity,
                    identity_gate_pass=identity_pass,
                    position_gate_pass=True,
                    identity_applied=appearance is not None,
                    position_applied=True,
                    lifecycle_applied=True,
                ))
                continue

            if policy in {SupportUpdatePolicy.POSITION_ONLY, SupportUpdatePolicy.IDENTITY_GATED_POSITION_ONLY}:
                if position_pass:
                    self._update_track(
                        track_id,
                        xy,
                        frame_id=frame_id,
                        source="support",
                        mode=mode,
                        margin=margin,
                        measurement_noise=support_measurement_noise,
                        appearance_embedding=None,
                    )
                    matched_tracks.add(int(track_id))
                    used_tracks.add(int(track_id))
                    diagnostics.append(action_diag(
                        obs,
                        action_mode="position_only_update",
                        track_id=track_id,
                        residual=residual,
                        margin=margin,
                        before=before,
                        identity_similarity=identity_similarity,
                        identity_gate_pass=identity_pass,
                        position_gate_pass=True,
                        position_applied=True,
                        lifecycle_applied=True,
                    ))
                else:
                    diagnostics.append(action_diag(
                        obs,
                        action_mode="reject",
                        track_id=track_id,
                        residual=residual,
                        margin=margin,
                        before=before,
                        reject_reason="candidate_gate" if residual > threshold else "association_margin",
                        identity_similarity=identity_similarity,
                        identity_gate_pass=identity_pass,
                    ))
                continue

            if policy in {SupportUpdatePolicy.IDENTITY_ONLY_STRICT, SupportUpdatePolicy.IDENTITY_ONLY_WITH_LIFECYCLE}:
                if expanded_identity_pass:
                    if policy == SupportUpdatePolicy.IDENTITY_ONLY_WITH_LIFECYCLE:
                        self._identity_only_update(
                            track_id,
                            frame_id=frame_id,
                            source="support",
                            mode=mode,
                            margin=margin,
                            appearance_embedding=appearance,
                        )
                        matched_tracks.add(int(track_id))
                        lifecycle_applied = True
                        action_mode = "identity_only_with_lifecycle"
                    else:
                        self._update_identity_state(track_id, appearance, frame_id=frame_id)
                        lifecycle_applied = False
                        action_mode = "identity_only_strict"
                    used_tracks.add(int(track_id))
                    diagnostics.append(action_diag(
                        obs,
                        action_mode=action_mode,
                        track_id=track_id,
                        residual=residual,
                        margin=margin,
                        before=before,
                        identity_similarity=identity_similarity,
                        identity_gate_pass=True,
                        position_gate_pass=position_pass,
                        identity_applied=True,
                        lifecycle_applied=lifecycle_applied,
                    ))
                else:
                    diagnostics.append(action_diag(
                        obs,
                        action_mode="reject",
                        track_id=track_id,
                        residual=residual,
                        margin=margin,
                        before=before,
                        reject_reason="identity_radius" if residual > identity_radius else "association_margin",
                        identity_similarity=identity_similarity,
                        identity_gate_pass=identity_pass,
                    ))
                continue

            if expanded_identity_pass:
                if position_pass:
                    self._update_track(
                        track_id,
                        xy,
                        frame_id=frame_id,
                        source="support",
                        mode=mode,
                        margin=margin,
                        measurement_noise=support_measurement_noise,
                        appearance_embedding=appearance,
                    )
                    matched_tracks.add(int(track_id))
                    action_mode = "separated_joint_update"
                    position_applied = True
                    lifecycle_applied = True
                else:
                    self._update_identity_state(track_id, appearance, frame_id=frame_id)
                    action_mode = "separated_identity_only"
                    position_applied = False
                    lifecycle_applied = False
                used_tracks.add(int(track_id))
                diagnostics.append(action_diag(
                    obs,
                    action_mode=action_mode,
                    track_id=track_id,
                    residual=residual,
                    margin=margin,
                    before=before,
                    identity_similarity=identity_similarity,
                    identity_gate_pass=True,
                    position_gate_pass=position_pass,
                    identity_applied=True,
                    position_applied=position_applied,
                    lifecycle_applied=lifecycle_applied,
                ))
            else:
                diagnostics.append(action_diag(
                    obs,
                    action_mode="reject",
                    track_id=track_id,
                    residual=residual,
                    margin=margin,
                    before=before,
                    reject_reason="identity_radius" if residual > identity_radius else "association_margin",
                    identity_similarity=identity_similarity,
                    identity_gate_pass=identity_pass,
                ))

        return matched_tracks, diagnostics

    def update_frame(
        self,
        *,
        frame_id: int,
        primary_observations: Sequence[MatrixObservation],
        support_observations: Sequence[MatrixObservation],
        support_mode: str,
        support_allow_new: bool,
        support_margin_threshold: float,
        support_risky_only: bool = False,
        occlusion_keys: set[tuple[int, int]] | None = None,
        recovery_distance_threshold: float | None = None,
        appearance_embeddings: ObservationEmbeddingMap | None = None,
        use_identity_gate: bool = False,
        identity_accept_threshold: float = 0.25,
        identity_only_distance_threshold: float | None = None,
        support_measurement_noise: float | None = None,
        support_update_policy: SupportUpdatePolicy | str = SupportUpdatePolicy.CURRENT_JOINT,
    ) -> list[dict[str, object]]:
        self.predict_to(frame_id)
        matched: set[int] = set()
        diagnostics: list[dict[str, object]] = []
        primary_matched, primary_diag = self._associate_primary(
            primary_observations,
            frame_id=frame_id,
            appearance_embeddings=appearance_embeddings,
        )
        matched.update(primary_matched)
        diagnostics.extend(primary_diag)
        support_matched, support_diag = self.update_support(
            support_observations,
            frame_id=frame_id,
            mode=support_mode,
            allow_new_tracks=support_allow_new,
            margin_threshold=support_margin_threshold,
            risky_only=support_risky_only,
            occlusion_keys=occlusion_keys,
            recovery_distance_threshold=recovery_distance_threshold,
            appearance_embeddings=appearance_embeddings,
            use_identity_gate=use_identity_gate,
            identity_accept_threshold=identity_accept_threshold,
            identity_only_distance_threshold=identity_only_distance_threshold,
            support_measurement_noise=support_measurement_noise,
            update_policy=support_update_policy,
        )
        matched.update(support_matched)
        diagnostics.extend(support_diag)
        for track_id in list(self.tracks):
            if track_id not in matched:
                self.tracks[track_id].miss_count += 1
        return diagnostics

    def predict_truths(
        self,
        truths: Mapping[int, np.ndarray],
        *,
        frame_id: int,
        miss_start_id: int,
    ) -> tuple[list[Prediction], int]:
        predictions: list[Prediction] = []
        next_miss_id = int(miss_start_id)
        track_ids = sorted(self.tracks)
        for person_id in sorted(truths):
            truth_xy = np.asarray(truths[person_id], dtype=np.float64)
            if not track_ids:
                pred_id = next_miss_id
                next_miss_id -= 1
            else:
                ranked = sorted(
                    (
                        (float(np.linalg.norm(truth_xy - self.tracks[track_id].xy)), int(track_id))
                        for track_id in track_ids
                    ),
                    key=lambda item: (item[0], item[1]),
                )
                distance, pred_id = ranked[0]
                if distance > self.distance_threshold:
                    pred_id = next_miss_id
                    next_miss_id -= 1
            predictions.append(Prediction(frame_id=int(frame_id), gt_id=int(person_id), pred_id=int(pred_id)))
        return predictions, next_miss_id


def is_track_high_risk(
    track: WorldSortTrack,
    *,
    current_frame: int,
    covariance_threshold: float,
    occlusion_keys: set[tuple[int, int]] | None = None,
    obs: MatrixObservation | None = None,
) -> bool:
    time_since_primary = (
        math.inf if track.last_primary_seen_frame is None else int(current_frame) - int(track.last_primary_seen_frame)
    )
    return bool(
        int(track.miss_count) > 0
        or float(time_since_primary) > 0
        or float(np.trace(track.covariance[:2, :2])) >= float(covariance_threshold)
        or float(track.association_margin) < 0.50
    )


def _support_diag(
    obs: MatrixObservation,
    current_frame: int,
    mode: str,
    track_id: int | None,
    residual: float,
    margin: float,
    track: WorldSortTrack | None,
    reject_reason: str = "",
) -> dict[str, object]:
    if track is None:
        miss_count: object = ""
        time_since_primary: object = ""
        covariance_trace: object = ""
        track_age: object = ""
        last_primary_seen: object = ""
    else:
        miss_count = int(track.miss_count)
        time_since_primary = "" if track.last_primary_seen_frame is None else int(current_frame) - int(track.last_primary_seen_frame)
        covariance_trace = f"{float(np.trace(track.covariance[:2, :2])):.6f}"
        track_age = int(track.age)
        last_primary_seen = "" if track.last_primary_seen_frame is None else int(track.last_primary_seen_frame)
    return {
        "current_frame": int(current_frame),
        "capture_time": int(obs.capture_time),
        "arrival_time": int(obs.arrival_time),
        "delay_frames": int(obs.delay),
        "person_id_eval_only": int(obs.person_id),
        "drone_id": int(obs.drone_id),
        "position_id": int(obs.position_id),
        "bbox_xyxy": ",".join(str(int(value)) for value in obs.bbox_xyxy),
        "mode": mode,
        "reject_reason": reject_reason,
        "track_id": "" if track_id is None else int(track_id),
        "residual_m": "inf" if math.isinf(float(residual)) else f"{float(residual):.6f}",
        "association_margin_m": "inf" if math.isinf(float(margin)) else f"{float(margin):.6f}",
        "miss_count": miss_count,
        "time_since_primary_seen": time_since_primary,
        "covariance_trace": covariance_trace,
        "track_age": track_age,
        "last_primary_seen_frame": last_primary_seen,
        "source": "support",
    }


def _truth_by_frame(observations: Sequence[MatrixObservation], frame_start: int, frame_end: int) -> dict[int, dict[int, np.ndarray]]:
    grouped: dict[tuple[int, int], list[np.ndarray]] = defaultdict(list)
    for obs in observations:
        if int(frame_start) <= int(obs.capture_time) <= int(frame_end):
            grouped[(int(obs.capture_time), int(obs.person_id))].append(_obs_xy(obs))
    truth: dict[int, dict[int, np.ndarray]] = defaultdict(dict)
    for (frame_id, person_id), xys in grouped.items():
        truth[int(frame_id)][int(person_id)] = np.asarray(xys, dtype=np.float64).mean(axis=0)
    return truth


def _schedule_observations(
    observations: Sequence[MatrixObservation],
    *,
    primary_drone_id: int,
) -> tuple[dict[int, list[MatrixObservation]], dict[int, list[MatrixObservation]]]:
    primary_by_capture: dict[int, list[MatrixObservation]] = defaultdict(list)
    support_by_arrival: dict[int, list[MatrixObservation]] = defaultdict(list)
    for obs in observations:
        if int(obs.drone_id) == int(primary_drone_id):
            primary_by_capture[int(obs.capture_time)].append(obs)
        else:
            support_by_arrival[int(obs.arrival_time)].append(obs)
    return primary_by_capture, support_by_arrival


def _mode_counter(diagnostics: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counter = Counter(str(row.get("mode", "")) for row in diagnostics if str(row.get("source", "")) == "support")
    return dict(sorted(counter.items()))


def _make_run(
    *,
    pipeline: str,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    predictions: list[Prediction],
    diagnostics: list[dict[str, object]],
    notes: str,
    start_time: float,
    frame_start: int,
    frame_end: int,
) -> ReanchoringRun:
    frames = max(1, int(frame_end) - int(frame_start) + 1)
    return ReanchoringRun(
        pipeline=pipeline,
        delay_profile=delay_profile,
        predictions=predictions,
        diagnostics=diagnostics,
        mode_counts=_mode_counter(diagnostics),
        notes=notes,
        delay_frames=int(delay_frames),
        delay_ms=float(delay_ms),
        latency_ms_per_frame=(time.perf_counter() - start_time) * 1000.0 / frames,
    )


def _run_sequential_sort(
    *,
    pipeline: str,
    observations: Sequence[MatrixObservation],
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    support_policy: str,
    support_allow_new: bool,
    support_margin_threshold: float,
    occlusion_keys: set[tuple[int, int]] | None = None,
    progress_callback: Callable[[int], None] | None = None,
    progress_every: int = 25,
) -> ReanchoringRun:
    start = time.perf_counter()
    tracker = WorldSortTracker(distance_threshold=distance_threshold)
    primary_by_capture, support_by_arrival = _schedule_observations(observations, primary_drone_id=primary_drone_id)
    truths = _truth_by_frame(truth_observations if truth_observations is not None else observations, frame_start, frame_end)
    diagnostics: list[dict[str, object]] = []
    predictions: list[Prediction] = []
    next_miss_id = -1

    for frame_id in range(int(frame_start), int(frame_end) + 1):
        primary = primary_by_capture.get(frame_id, [])
        arrivals = support_by_arrival.get(frame_id, [])
        if support_policy == "none":
            support: list[MatrixObservation] = []
            for obs in arrivals:
                diagnostics.append(_support_diag(obs, frame_id, "reject", None, float("inf"), float("inf"), None, "primary_only"))
        elif support_policy == "drop_delayed":
            support = [obs for obs in arrivals if int(obs.delay) == 0]
            for obs in arrivals:
                if int(obs.delay) != 0:
                    diagnostics.append(_support_diag(obs, frame_id, "reject", None, float("inf"), float("inf"), None, "delayed_drop"))
        elif support_policy == "arrival_time":
            support = list(arrivals)
        elif support_policy == "recovery_only":
            support = []
        else:
            raise ValueError(f"unknown support policy: {support_policy}")

        if support_policy == "arrival_time":
            support_mode = "arrival_fusion"
        elif support_policy == "drop_delayed":
            support_mode = "sync_support"
        else:
            support_mode = "recovery_stitch"
        risky_only = support_policy == "recovery_only"
        frame_diag = tracker.update_frame(
            frame_id=frame_id,
            primary_observations=primary,
            support_observations=support,
            support_mode=support_mode,
            support_allow_new=support_allow_new,
            support_margin_threshold=support_margin_threshold,
            support_risky_only=risky_only,
            occlusion_keys=occlusion_keys,
            recovery_distance_threshold=distance_threshold * (2.0 if risky_only else 1.0),
        )
        diagnostics.extend(_annotate_pipeline(frame_diag, pipeline, delay_profile, delay_ms))
        frame_predictions, next_miss_id = tracker.predict_truths(
            truths.get(frame_id, {}),
            frame_id=frame_id,
            miss_start_id=next_miss_id,
        )
        predictions.extend(frame_predictions)

        if support_policy == "recovery_only" and arrivals:
            recoverable = [
                obs for obs in arrivals
                if not (occlusion_keys is not None and (int(frame_id), int(obs.person_id)) in occlusion_keys)
                and any(float(np.linalg.norm(_obs_xy(obs) - _obs_xy(primary_obs))) <= distance_threshold for primary_obs in primary)
            ]
            late_diag = tracker.update_support(
                recoverable,
                frame_id=frame_id,
                mode="recovery_stitch",
                allow_new_tracks=False,
                margin_threshold=support_margin_threshold,
                risky_only=True,
                occlusion_keys=occlusion_keys,
                recovery_distance_threshold=distance_threshold * 2.0,
            )[1]
            diagnostics.extend(_annotate_pipeline(late_diag, pipeline, delay_profile, delay_ms))
            for obs in arrivals:
                if obs not in recoverable:
                    diagnostics.append(
                        {
                            **_support_diag(obs, frame_id, "reject", None, float("inf"), float("inf"), None, "no_primary_recovery_anchor"),
                            "pipeline": pipeline,
                            "delay_profile": delay_profile,
                            "delay_ms": f"{float(delay_ms):.3f}",
                        }
                    )

        if progress_callback is not None and (
            frame_id == int(frame_start)
            or frame_id == int(frame_end)
            or (frame_id - int(frame_start) + 1) % max(int(progress_every), 1) == 0
        ):
            progress_callback(int(frame_id))

    return _make_run(
        pipeline=pipeline,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        predictions=predictions,
        diagnostics=_annotate_pipeline(diagnostics, pipeline, delay_profile, delay_ms),
        notes=support_policy,
        start_time=start,
        frame_start=frame_start,
        frame_end=frame_end,
    )


def _run_lag_or_state_aware(
    *,
    pipeline: str,
    observations: Sequence[MatrixObservation],
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    lag_frames: int,
    state_aware: bool,
    support_margin_threshold: float,
    occlusion_keys: set[tuple[int, int]] | None = None,
    appearance_embeddings: ObservationEmbeddingMap | None = None,
    use_identity_gate: bool = False,
    identity_accept_threshold: float = 0.25,
    identity_only_distance_threshold: float | None = None,
    support_measurement_noise: float | None = None,
    support_update_policy: SupportUpdatePolicy | str = SupportUpdatePolicy.CURRENT_JOINT,
    progress_callback: Callable[[int], None] | None = None,
    progress_every: int = 25,
) -> ReanchoringRun:
    start = time.perf_counter()
    tracker = WorldSortTracker(distance_threshold=distance_threshold)
    primary_by_capture, support_by_arrival = _schedule_observations(observations, primary_drone_id=primary_drone_id)
    truths = _truth_by_frame(truth_observations if truth_observations is not None else observations, frame_start, frame_end)
    known_support_by_capture: dict[int, list[MatrixObservation]] = defaultdict(list)
    snapshots: dict[int, TrackerSnapshot] = {}
    diagnostics: list[dict[str, object]] = []
    predictions: list[Prediction] = []
    next_miss_id = -1

    def save_snapshot(frame_id: int) -> None:
        snapshots[int(frame_id)] = tracker.snapshot()

    def restore_before(frame_id: int) -> None:
        tracker.restore(snapshots.get(int(frame_id) - 1))

    def apply_frame(frame_id: int) -> None:
        frame_diag = tracker.update_frame(
            frame_id=frame_id,
            primary_observations=primary_by_capture.get(frame_id, []),
            support_observations=known_support_by_capture.get(frame_id, []),
            support_mode="fixed_lag_update",
            support_allow_new=False,
            support_margin_threshold=support_margin_threshold,
            support_risky_only=False,
            occlusion_keys=occlusion_keys,
            appearance_embeddings=appearance_embeddings,
            use_identity_gate=use_identity_gate,
            identity_accept_threshold=identity_accept_threshold,
            identity_only_distance_threshold=identity_only_distance_threshold,
            support_measurement_noise=support_measurement_noise,
            support_update_policy=support_update_policy,
        )
        diagnostics.extend(_annotate_pipeline(frame_diag, pipeline, delay_profile, delay_ms))
        save_snapshot(frame_id)

    for current_frame in range(int(frame_start), int(frame_end) + 1):
        arrivals = support_by_arrival.get(current_frame, [])
        eligible = [obs for obs in arrivals if int(current_frame) - int(obs.capture_time) <= int(lag_frames)]
        late = [obs for obs in arrivals if obs not in eligible]

        if eligible:
            for obs in eligible:
                known_support_by_capture[int(obs.capture_time)].append(obs)
            replay_start = min(int(obs.capture_time) for obs in eligible)
            restore_before(replay_start)
            for replay_frame in range(replay_start, current_frame + 1):
                apply_frame(replay_frame)
        else:
            apply_frame(current_frame)

        if late:
            if state_aware:
                late_diag = tracker.update_support(
                    late,
                    frame_id=current_frame,
                    mode="recovery_stitch",
                    allow_new_tracks=False,
                    margin_threshold=support_margin_threshold,
                    risky_only=True,
                    occlusion_keys=occlusion_keys,
                    recovery_distance_threshold=distance_threshold * 2.0,
                    appearance_embeddings=appearance_embeddings,
                    use_identity_gate=use_identity_gate,
                    identity_accept_threshold=identity_accept_threshold,
                    identity_only_distance_threshold=identity_only_distance_threshold,
                    support_measurement_noise=support_measurement_noise,
                    update_policy=support_update_policy,
                )[1]
                diagnostics.extend(_annotate_pipeline(late_diag, pipeline, delay_profile, delay_ms))
            else:
                for obs in late:
                    diagnostics.append(
                        {
                            **_support_diag(obs, current_frame, "reject", None, float("inf"), float("inf"), None, "beyond_lag"),
                            "pipeline": pipeline,
                            "delay_profile": delay_profile,
                            "delay_ms": f"{float(delay_ms):.3f}",
                        }
                    )

        frame_predictions, next_miss_id = tracker.predict_truths(
            truths.get(current_frame, {}),
            frame_id=current_frame,
            miss_start_id=next_miss_id,
        )
        predictions.extend(frame_predictions)

        if progress_callback is not None and (
            current_frame == int(frame_start)
            or current_frame == int(frame_end)
            or (current_frame - int(frame_start) + 1) % max(int(progress_every), 1) == 0
        ):
            progress_callback(int(current_frame))

    notes = f"state-aware lag={lag_frames}" if state_aware else f"fixed lag={lag_frames}"
    return _make_run(
        pipeline=pipeline,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        predictions=predictions,
        diagnostics=diagnostics,
        notes=notes,
        start_time=start,
        frame_start=frame_start,
        frame_end=frame_end,
    )


def _annotate_pipeline(
    diagnostics: Sequence[Mapping[str, object]],
    pipeline: str,
    delay_profile: str,
    delay_ms: float,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in diagnostics:
        item = dict(row)
        item.setdefault("pipeline", pipeline)
        item.setdefault("delay_profile", delay_profile)
        item.setdefault("delay_ms", f"{float(delay_ms):.3f}")
        rows.append(item)
    return rows


def run_primary_only_sort(
    observations: Sequence[MatrixObservation],
    *,
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    progress_callback: Callable[[int], None] | None = None,
    progress_every: int = 25,
) -> ReanchoringRun:
    return _run_sequential_sort(
        pipeline="primary_only_sort",
        observations=observations,
        truth_observations=truth_observations,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        frame_start=frame_start,
        frame_end=frame_end,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
        support_policy="none",
        support_allow_new=False,
        support_margin_threshold=0.50,
        progress_callback=progress_callback,
        progress_every=progress_every,
    )


def run_drop_delayed_sort(
    observations: Sequence[MatrixObservation],
    *,
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    progress_callback: Callable[[int], None] | None = None,
    progress_every: int = 25,
) -> ReanchoringRun:
    return _run_sequential_sort(
        pipeline="drop_delayed_sort",
        observations=observations,
        truth_observations=truth_observations,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        frame_start=frame_start,
        frame_end=frame_end,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
        support_policy="drop_delayed",
        support_allow_new=True,
        support_margin_threshold=0.50,
        progress_callback=progress_callback,
        progress_every=progress_every,
    )


def run_arrival_time_sort(
    observations: Sequence[MatrixObservation],
    *,
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
) -> ReanchoringRun:
    return _run_sequential_sort(
        pipeline="arrival_time_sort",
        observations=observations,
        truth_observations=truth_observations,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        frame_start=frame_start,
        frame_end=frame_end,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
        support_policy="arrival_time",
        support_allow_new=True,
        support_margin_threshold=0.50,
    )


def run_recovery_only_stitching(
    observations: Sequence[MatrixObservation],
    *,
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    occlusion_keys: set[tuple[int, int]] | None,
) -> ReanchoringRun:
    return _run_sequential_sort(
        pipeline="recovery_only_stitching",
        observations=observations,
        truth_observations=truth_observations,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        frame_start=frame_start,
        frame_end=frame_end,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
        support_policy="recovery_only",
        support_allow_new=False,
        support_margin_threshold=0.50,
        occlusion_keys=occlusion_keys,
    )


def run_fixed_lag_oosm_update(
    observations: Sequence[MatrixObservation],
    *,
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    lag_frames: int,
    occlusion_keys: set[tuple[int, int]] | None,
) -> ReanchoringRun:
    return _run_lag_or_state_aware(
        pipeline=f"fixed_lag_oosm_lag{int(lag_frames)}",
        observations=observations,
        truth_observations=truth_observations,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        frame_start=frame_start,
        frame_end=frame_end,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
        lag_frames=lag_frames,
        state_aware=False,
        support_margin_threshold=0.50,
        occlusion_keys=occlusion_keys,
    )


def run_fixed_lag_multicue_update(
    observations: Sequence[MatrixObservation],
    *,
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    lag_frames: int,
    occlusion_keys: set[tuple[int, int]] | None,
    pipeline: str,
    appearance_embeddings: ObservationEmbeddingMap | None = None,
    use_identity_gate: bool = False,
    identity_accept_threshold: float = 0.25,
    identity_only_distance_threshold: float | None = None,
    support_measurement_noise: float | None = None,
    support_update_policy: SupportUpdatePolicy | str = SupportUpdatePolicy.CURRENT_JOINT,
    support_margin_threshold: float = 0.50,
    progress_callback: Callable[[int], None] | None = None,
    progress_every: int = 25,
) -> ReanchoringRun:
    return _run_lag_or_state_aware(
        pipeline=pipeline,
        observations=observations,
        truth_observations=truth_observations,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        frame_start=frame_start,
        frame_end=frame_end,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
        lag_frames=lag_frames,
        state_aware=False,
        support_margin_threshold=support_margin_threshold,
        occlusion_keys=occlusion_keys,
        appearance_embeddings=appearance_embeddings,
        use_identity_gate=use_identity_gate,
        identity_accept_threshold=identity_accept_threshold,
        identity_only_distance_threshold=identity_only_distance_threshold,
        support_measurement_noise=support_measurement_noise,
        support_update_policy=support_update_policy,
        progress_callback=progress_callback,
        progress_every=progress_every,
    )


def run_state_aware_reanchoring(
    observations: Sequence[MatrixObservation],
    *,
    truth_observations: Sequence[MatrixObservation] | None = None,
    delay_profile: str,
    delay_frames: int,
    delay_ms: float,
    frame_start: int,
    frame_end: int,
    distance_threshold: float,
    primary_drone_id: int,
    lag_frames: int,
    occlusion_keys: set[tuple[int, int]] | None,
) -> ReanchoringRun:
    return _run_lag_or_state_aware(
        pipeline="state_aware_reanchoring",
        observations=observations,
        truth_observations=truth_observations,
        delay_profile=delay_profile,
        delay_frames=delay_frames,
        delay_ms=delay_ms,
        frame_start=frame_start,
        frame_end=frame_end,
        distance_threshold=distance_threshold,
        primary_drone_id=primary_drone_id,
        lag_frames=lag_frames,
        state_aware=True,
        support_margin_threshold=0.50,
        occlusion_keys=occlusion_keys,
    )


def matrix_run_from_reanchoring(run: ReanchoringRun) -> MatrixTrackerRun:
    metrics = compute_identity_metrics(run.predictions)
    return MatrixTrackerRun(
        pipeline=run.pipeline,
        delay_profile=run.delay_profile,
        predictions=run.predictions,
        idf1=metrics.idf1,
        idsw=metrics.idsw,
        mota=metrics.mota,
        world_xy_mae=0.0,
        world_xy_rmse=0.0,
        gt_detections=metrics.gt_detections,
        pred_detections=len(run.predictions),
        latency_ms_per_frame=run.latency_ms_per_frame,
        notes=run.notes,
        delay_frames=run.delay_frames,
        delay_ms=run.delay_ms,
    )
