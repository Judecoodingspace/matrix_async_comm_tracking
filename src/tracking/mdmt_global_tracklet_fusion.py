"""Asynchronous global identity fusion for dataset-neutral local tracklets."""

from __future__ import annotations

import copy
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linear_sum_assignment

from tracking.matrix_identity_cue import normalize_vector
from tracking.tracklet_packets import GlobalFusionPacket


PIPELINES = (
    "primary_only",
    "primary_reid_stitching",
    "drop_delayed",
    "arrival_time_fusion",
    "history1_timestamped",
    "incremental_tracklet_timestamped",
    "fixed_lag_tracklet_update",
    "late_recovery_stitching",
)


def cosine_similarity(first: np.ndarray | None, second: np.ndarray | None) -> float | None:
    if first is None or second is None:
        return None
    return float(np.dot(normalize_vector(first), normalize_vector(second)))


@dataclass
class _AppearanceAccumulator:
    value_sum: np.ndarray | None = None
    count: int = 0

    @property
    def template(self) -> np.ndarray | None:
        return None if self.value_sum is None else normalize_vector(self.value_sum)

    def update(self, value: np.ndarray | None) -> None:
        if value is None:
            return
        normalized = normalize_vector(value)
        if self.value_sum is None:
            self.value_sum = normalized.astype(np.float64).copy()
        else:
            self.value_sum += normalized
        self.count += 1


@dataclass
class GlobalIdentityState:
    global_id: int
    primary_appearance: _AppearanceAccumulator = field(default_factory=_AppearanceAccumulator)
    support_appearance: _AppearanceAccumulator = field(default_factory=_AppearanceAccumulator)
    last_primary_capture: int = -1
    last_support_capture: int = -1


@dataclass
class GlobalFusionState:
    """Internal global state. It contains no evaluation identity."""

    next_global_id: int = 1
    identities: dict[int, GlobalIdentityState] = field(default_factory=dict)
    primary_local_to_global: dict[int, int] = field(default_factory=dict)
    support_tracklet_to_global: dict[str, int] = field(default_factory=dict)
    unresolved_support: dict[str, _AppearanceAccumulator] = field(default_factory=dict)

    def clone(self) -> "GlobalFusionState":
        return copy.deepcopy(self)

    def _new_identity(self) -> GlobalIdentityState:
        identity = GlobalIdentityState(self.next_global_id)
        self.identities[identity.global_id] = identity
        self.next_global_id += 1
        return identity

    def _support_key(self, packet: GlobalFusionPacket) -> str:
        return packet.tracklet_id_persistent or (
            f"{packet.sequence_id}:V{packet.view_id}:F{packet.capture_frame}:T{packet.source_track_id}"
        )

    def _refresh_mapped_support(
        self,
        packets: Sequence[GlobalFusionPacket],
        *,
        frame_id: int,
    ) -> tuple[list[GlobalFusionPacket], list[dict[str, object]]]:
        unknown: list[GlobalFusionPacket] = []
        diagnostics: list[dict[str, object]] = []
        for packet in packets:
            if not packet.has_measurement or packet.appearance_vector is None:
                diagnostics.append(_association_row(packet, frame_id, "support_no_measurement", None, None))
                continue
            key = self._support_key(packet)
            global_id = self.support_tracklet_to_global.get(key)
            if global_id is None:
                unknown.append(packet)
                continue
            identity = self.identities[global_id]
            identity.support_appearance.update(packet.appearance_vector)
            identity.last_support_capture = max(identity.last_support_capture, packet.capture_frame)
            diagnostics.append(_association_row(packet, frame_id, "support_existing", global_id, None))
        return unknown, diagnostics

    def _associate_unknown_support(
        self,
        packets: Sequence[GlobalFusionPacket],
        *,
        frame_id: int,
        cross_threshold: float,
    ) -> list[dict[str, object]]:
        diagnostics: list[dict[str, object]] = []
        candidates = sorted(self.identities)
        costs = np.full((len(packets), len(candidates)), 1.0e6, dtype=np.float64)
        similarities: dict[tuple[int, int], float | None] = {}
        for row_index, packet in enumerate(packets):
            for column_index, global_id in enumerate(candidates):
                similarity = cosine_similarity(
                    packet.appearance_vector,
                    self.identities[global_id].primary_appearance.template,
                )
                similarities[(row_index, column_index)] = similarity
                if similarity is not None and similarity >= cross_threshold:
                    costs[row_index, column_index] = 1.0 - similarity
        selected: dict[int, tuple[int, float]] = {}
        if costs.size:
            rows, columns = linear_sum_assignment(costs)
            for row_index, column_index in zip(rows, columns):
                if costs[int(row_index), int(column_index)] >= 1.0e5:
                    continue
                similarity = similarities[(int(row_index), int(column_index))]
                selected[int(row_index)] = (candidates[int(column_index)], float(similarity))
        for row_index, packet in enumerate(packets):
            key = self._support_key(packet)
            match = selected.get(row_index)
            if match is None:
                accumulator = self.unresolved_support.setdefault(key, _AppearanceAccumulator())
                accumulator.update(packet.appearance_vector)
                best = max(
                    (value for (row, _), value in similarities.items() if row == row_index and value is not None),
                    default=None,
                )
                diagnostics.append(_association_row(packet, frame_id, "support_unresolved", None, best))
                continue
            global_id, similarity = match
            self.support_tracklet_to_global[key] = global_id
            identity = self.identities[global_id]
            identity.support_appearance.update(packet.appearance_vector)
            identity.last_support_capture = max(identity.last_support_capture, packet.capture_frame)
            diagnostics.append(_association_row(packet, frame_id, "support_cross_match", global_id, similarity))
        return diagnostics

    def _candidate_similarity(
        self,
        packet: GlobalFusionPacket,
        identity: GlobalIdentityState,
        *,
        allow_primary_reid: bool,
        allow_cross_view: bool,
        primary_threshold: float,
        cross_threshold: float,
    ) -> tuple[float | None, str]:
        primary_similarity = (
            cosine_similarity(packet.appearance_vector, identity.primary_appearance.template)
            if allow_primary_reid
            else None
        )
        support_similarity = (
            cosine_similarity(packet.appearance_vector, identity.support_appearance.template)
            if allow_cross_view
            else None
        )
        options: list[tuple[float, str]] = []
        if primary_similarity is not None and primary_similarity >= primary_threshold:
            options.append((primary_similarity, "primary_reid"))
        if support_similarity is not None and support_similarity >= cross_threshold:
            options.append((support_similarity, "support_recovery"))
        return max(options, default=(None, "new_identity"), key=lambda row: -1.0 if row[0] is None else row[0])

    def _associate_primary(
        self,
        packets: Sequence[GlobalFusionPacket],
        *,
        frame_id: int,
        allow_primary_reid: bool,
        allow_cross_view: bool,
        primary_threshold: float,
        cross_threshold: float,
    ) -> list[dict[str, object]]:
        diagnostics: list[dict[str, object]] = []
        new_packets: list[GlobalFusionPacket] = []
        occupied: set[int] = set()
        for packet in packets:
            global_id = self.primary_local_to_global.get(packet.source_track_id)
            if global_id is None:
                new_packets.append(packet)
                continue
            occupied.add(global_id)
            identity = self.identities[global_id]
            if packet.has_measurement:
                identity.primary_appearance.update(packet.appearance_vector)
                identity.last_primary_capture = max(identity.last_primary_capture, packet.capture_frame)
            diagnostics.append(_association_row(packet, frame_id, "primary_existing", global_id, None))

        candidates = [global_id for global_id in sorted(self.identities) if global_id not in occupied]
        costs = np.full((len(new_packets), len(candidates)), 1.0e6, dtype=np.float64)
        evidence: dict[tuple[int, int], tuple[float | None, str]] = {}
        for row_index, packet in enumerate(new_packets):
            for column_index, global_id in enumerate(candidates):
                similarity, reason = self._candidate_similarity(
                    packet,
                    self.identities[global_id],
                    allow_primary_reid=allow_primary_reid,
                    allow_cross_view=allow_cross_view,
                    primary_threshold=primary_threshold,
                    cross_threshold=cross_threshold,
                )
                evidence[(row_index, column_index)] = (similarity, reason)
                if similarity is not None:
                    costs[row_index, column_index] = 1.0 - similarity
        selected: dict[int, tuple[int, float, str]] = {}
        if costs.size:
            rows, columns = linear_sum_assignment(costs)
            for row_index, column_index in zip(rows, columns):
                if costs[int(row_index), int(column_index)] >= 1.0e5:
                    continue
                similarity, reason = evidence[(int(row_index), int(column_index))]
                selected[int(row_index)] = (
                    candidates[int(column_index)],
                    float(similarity),
                    reason,
                )
        for row_index, packet in enumerate(new_packets):
            match = selected.get(row_index)
            if match is None:
                identity = self._new_identity()
                global_id = identity.global_id
                reason = "primary_new_identity"
                similarity = None
            else:
                global_id, similarity, source = match
                identity = self.identities[global_id]
                reason = f"primary_{source}"
            self.primary_local_to_global[packet.source_track_id] = global_id
            if packet.has_measurement:
                identity.primary_appearance.update(packet.appearance_vector)
                identity.last_primary_capture = max(identity.last_primary_capture, packet.capture_frame)
            diagnostics.append(_association_row(packet, frame_id, reason, global_id, similarity))
        return diagnostics

    def process_frame(
        self,
        *,
        frame_id: int,
        primary_packets: Sequence[GlobalFusionPacket],
        support_packets: Sequence[GlobalFusionPacket],
        allow_primary_reid: bool,
        allow_cross_view: bool,
        primary_threshold: float,
        cross_threshold: float,
    ) -> list[dict[str, object]]:
        unknown, diagnostics = self._refresh_mapped_support(support_packets, frame_id=frame_id)
        diagnostics.extend(
            self._associate_primary(
                primary_packets,
                frame_id=frame_id,
                allow_primary_reid=allow_primary_reid,
                allow_cross_view=allow_cross_view,
                primary_threshold=primary_threshold,
                cross_threshold=cross_threshold,
            )
        )
        if allow_cross_view:
            diagnostics.extend(
                self._associate_unknown_support(
                    unknown,
                    frame_id=frame_id,
                    cross_threshold=cross_threshold,
                )
            )
        return diagnostics


def _association_row(
    packet: GlobalFusionPacket,
    processing_frame: int,
    action: str,
    global_id: int | None,
    similarity: float | None,
) -> dict[str, object]:
    return {
        "sequence_id": packet.sequence_id,
        "view_id": packet.view_id,
        "source_track_id": packet.source_track_id,
        "capture_frame": packet.capture_frame,
        "arrival_frame": packet.arrival_frame,
        "processing_frame": int(processing_frame),
        "appearance_kind": packet.appearance_kind,
        "has_measurement": int(packet.has_measurement),
        "action": action,
        "global_id": "" if global_id is None else global_id,
        "similarity": "" if similarity is None else similarity,
    }


@dataclass(frozen=True)
class GlobalFusionRunResult:
    prediction_rows: tuple[dict[str, object], ...]
    message_rows: tuple[dict[str, object], ...]
    association_rows: tuple[dict[str, object], ...]
    final_state: GlobalFusionState
    published_history_rewrites: int
    fixed_lag_over_window_replays: int
    late_recovery_historical_mutations: int


def _packets_by_frame(packets: Iterable[GlobalFusionPacket], field: str) -> dict[int, list[GlobalFusionPacket]]:
    grouped: dict[int, list[GlobalFusionPacket]] = defaultdict(list)
    for packet in packets:
        grouped[int(getattr(packet, field))].append(packet)
    for rows in grouped.values():
        rows.sort(key=lambda item: (item.view_id, item.source_track_id, item.tracklet_id_persistent))
    return grouped


def _pipeline_mode(pipeline: str, delay_frames: int, lag_frames: int) -> tuple[str, bool, bool]:
    if pipeline not in PIPELINES:
        raise ValueError(f"unknown global fusion pipeline: {pipeline}")
    if pipeline == "primary_only":
        return "none", False, False
    if pipeline == "primary_reid_stitching":
        return "none", True, False
    if pipeline == "drop_delayed":
        return ("timestamped" if delay_frames == 0 else "none"), True, delay_frames == 0
    if pipeline == "arrival_time_fusion":
        return "arrival", True, True
    if pipeline in {"history1_timestamped", "incremental_tracklet_timestamped"}:
        return "timestamped", True, True
    if pipeline == "fixed_lag_tracklet_update":
        return ("timestamped" if delay_frames <= lag_frames else "none"), True, delay_frames <= lag_frames
    return ("timestamped" if delay_frames <= lag_frames else "recovery"), True, True


def run_global_tracklet_fusion(
    *,
    pipeline: str,
    frame_start: int,
    frame_end: int,
    primary_packets: Sequence[GlobalFusionPacket],
    support_packets: Sequence[GlobalFusionPacket],
    primary_detection_rows: Sequence[Mapping[str, object]],
    delay_frames: int,
    lag_frames: int,
    primary_reid_threshold: float,
    cross_view_threshold: float,
    progress_callback: Callable[[int, int], None] | None = None,
) -> GlobalFusionRunResult:
    """Run one causal online condition with immutable published predictions."""
    mode, allow_primary_reid, allow_cross = _pipeline_mode(pipeline, delay_frames, lag_frames)
    primary_by_capture = _packets_by_frame(primary_packets, "capture_frame")
    support_by_arrival = _packets_by_frame(support_packets, "arrival_frame")
    known_support_by_capture: dict[int, list[GlobalFusionPacket]] = defaultdict(list)
    detections_by_frame: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in primary_detection_rows:
        detections_by_frame[int(row["frame_id"])].append(row)

    state = GlobalFusionState()
    snapshots: dict[int, GlobalFusionState] = {}
    predictions: list[dict[str, object]] = []
    associations: list[dict[str, object]] = []
    messages: list[dict[str, object]] = []
    published_signature: list[tuple[int, int, int]] = []
    over_window_replays = 0
    late_historical_mutations = 0

    for packet in support_packets:
        if mode == "none":
            action = "drop"
        elif mode == "arrival":
            action = "arrival_fusion"
        elif mode == "recovery":
            action = "late_recovery"
        else:
            action = "timestamped_replay"
        messages.append(
            {
                "sequence_id": packet.sequence_id,
                "pipeline": pipeline,
                "view_id": packet.view_id,
                "source_track_id": packet.source_track_id,
                "tracklet_id_persistent": packet.tracklet_id_persistent,
                "capture_frame": packet.capture_frame,
                "arrival_frame": packet.arrival_frame,
                "delay_frames": packet.age_frames,
                "history_length": packet.history_length,
                "appearance_kind": packet.appearance_kind,
                "appearance_count": packet.appearance_count,
                "embedding_count": packet.embedding_count,
                "has_measurement": int(packet.has_measurement),
                "scheduled_action": action,
            }
        )

    for frame_id in range(int(frame_start), int(frame_end) + 1):
        arriving = support_by_arrival.get(frame_id, []) if mode != "none" else []
        if mode == "timestamped" and arriving:
            for packet in arriving:
                if packet.age_frames > lag_frames and pipeline == "fixed_lag_tracklet_update":
                    over_window_replays += 1
                    continue
                known_support_by_capture[packet.capture_frame].append(packet)
            replay_start = min(packet.capture_frame for packet in arriving)
            arriving_keys = {
                (packet.view_id, packet.source_track_id, packet.capture_frame)
                for packet in arriving
            }
            state = snapshots[replay_start - 1].clone() if replay_start - 1 in snapshots else GlobalFusionState()
            for replay_frame in range(replay_start, frame_id + 1):
                replay_diagnostics = state.process_frame(
                    frame_id=replay_frame,
                    primary_packets=primary_by_capture.get(replay_frame, []),
                    support_packets=known_support_by_capture.get(replay_frame, []),
                    allow_primary_reid=allow_primary_reid,
                    allow_cross_view=allow_cross,
                    primary_threshold=primary_reid_threshold,
                    cross_threshold=cross_view_threshold,
                )
                for row in replay_diagnostics:
                    row["pipeline"] = pipeline
                    row["is_replay"] = int(replay_frame < frame_id or bool(arriving))
                associations.extend(
                    row
                    for row in replay_diagnostics
                    if replay_frame == frame_id
                    or (
                        int(row["view_id"]),
                        int(row["source_track_id"]),
                        int(row["capture_frame"]),
                    ) in arriving_keys
                )
                snapshots[replay_frame] = state.clone()
        else:
            arrival_packets = arriving if mode in {"arrival", "recovery"} else []
            frame_diagnostics = state.process_frame(
                frame_id=frame_id,
                primary_packets=primary_by_capture.get(frame_id, []),
                support_packets=arrival_packets,
                allow_primary_reid=allow_primary_reid,
                allow_cross_view=allow_cross,
                primary_threshold=primary_reid_threshold,
                cross_threshold=cross_view_threshold,
            )
            for row in frame_diagnostics:
                row["pipeline"] = pipeline
                row["is_replay"] = 0
            associations.extend(frame_diagnostics)
            snapshots[frame_id] = state.clone()

        for row in sorted(detections_by_frame.get(frame_id, []), key=lambda item: int(item["local_track_id"])):
            local_track_id = int(row["local_track_id"])
            global_id = state.primary_local_to_global.get(local_track_id)
            if global_id is None:
                identity = state._new_identity()
                global_id = identity.global_id
                state.primary_local_to_global[local_track_id] = global_id
            prediction = {
                **dict(row),
                "pipeline": pipeline,
                "delay_frames": int(delay_frames),
                "global_id": int(global_id),
                "published_global_id": int(global_id),
            }
            predictions.append(prediction)
            published_signature.append((frame_id, local_track_id, global_id))
        snapshots[frame_id] = state.clone()
        if progress_callback is not None:
            progress_callback(frame_id, frame_end)

    # Processing later arrivals may update eventual state, but never the rows above.
    if mode in {"timestamped", "recovery", "arrival"}:
        for arrival_frame in range(frame_end + 1, frame_end + max(delay_frames, 0) + 1):
            arriving = support_by_arrival.get(arrival_frame, [])
            if not arriving:
                continue
            if mode == "timestamped":
                for packet in arriving:
                    known_support_by_capture[packet.capture_frame].append(packet)
                replay_start = min(packet.capture_frame for packet in arriving)
                state = snapshots[replay_start - 1].clone() if replay_start - 1 in snapshots else GlobalFusionState()
                for replay_frame in range(replay_start, frame_end + 1):
                    state.process_frame(
                        frame_id=replay_frame,
                        primary_packets=primary_by_capture.get(replay_frame, []),
                        support_packets=known_support_by_capture.get(replay_frame, []),
                        allow_primary_reid=allow_primary_reid,
                        allow_cross_view=allow_cross,
                        primary_threshold=primary_reid_threshold,
                        cross_threshold=cross_view_threshold,
                    )
                    snapshots[replay_frame] = state.clone()
            else:
                before = tuple(published_signature)
                state.process_frame(
                    frame_id=arrival_frame,
                    primary_packets=(),
                    support_packets=arriving,
                    allow_primary_reid=allow_primary_reid,
                    allow_cross_view=allow_cross,
                    primary_threshold=primary_reid_threshold,
                    cross_threshold=cross_view_threshold,
                )
                late_historical_mutations += int(before != tuple(published_signature))

    rewrites = int(tuple(published_signature) != tuple(
        (int(row["frame_id"]), int(row["local_track_id"]), int(row["published_global_id"]))
        for row in predictions
    ))
    for row in predictions:
        corrected = state.primary_local_to_global.get(
            int(row["local_track_id"]), int(row["published_global_id"])
        )
        row["corrected_global_id"] = int(corrected)
        row["published_corrected_mismatch"] = int(corrected != int(row["published_global_id"]))
    return GlobalFusionRunResult(
        tuple(predictions),
        tuple(messages),
        tuple(associations),
        state,
        rewrites,
        over_window_replays,
        late_historical_mutations,
    )


def select_precision_threshold(
    similarities: Sequence[float],
    labels: Sequence[int],
    *,
    minimum_precision: float = 0.95,
) -> dict[str, float | int]:
    """Select the threshold with highest recall under a precision constraint."""
    if len(similarities) != len(labels) or len(similarities) == 0:
        raise ValueError("threshold calibration requires aligned non-empty samples")
    values = np.asarray(similarities, dtype=np.float64)
    truth = np.asarray(labels, dtype=np.int8)
    positives = max(int(truth.sum()), 1)
    # Sorting once and evaluating cumulative counts at equal-score group ends
    # avoids rescanning every pair for every unique threshold.
    order = np.argsort(-values, kind="stable")
    sorted_values = values[order]
    sorted_truth = truth[order]
    cumulative_tp = np.cumsum(sorted_truth, dtype=np.int64)
    group_ends = np.flatnonzero(
        np.r_[sorted_values[:-1] != sorted_values[1:], True]
    )
    accepted = group_ends + 1
    true_positive = cumulative_tp[group_ends]
    false_positive = accepted - true_positive
    precision = true_positive / accepted
    recall = true_positive / positives
    eligible = precision >= float(minimum_precision)
    candidate_indices = np.flatnonzero(eligible) if np.any(eligible) else np.arange(len(group_ends))
    selected_index = max(
        (int(index) for index in candidate_indices),
        key=lambda index: (
            float(recall[index]),
            float(precision[index]),
            float(sorted_values[group_ends[index]]),
        ),
    )
    selected = (
        float(sorted_values[group_ends[selected_index]]),
        float(precision[selected_index]),
        float(recall[selected_index]),
        int(true_positive[selected_index]),
        int(false_positive[selected_index]),
    )
    return {
        "threshold": selected[0],
        "precision": selected[1],
        "recall": selected[2],
        "true_positive": selected[3],
        "false_positive": selected[4],
        "precision_gate_pass": int(selected[1] >= minimum_precision),
        "n_pairs": len(values),
        "n_positive": int(truth.sum()),
    }


def cluster_bootstrap_mean_difference(
    rows: Sequence[Mapping[str, object]],
    *,
    value_key: str,
    cluster_keys: tuple[str, ...] = ("sequence_id", "official_person_id"),
    samples: int = 2000,
    seed: int = 7,
) -> tuple[float, float]:
    """Cluster bootstrap CI for a paired episode-level difference."""
    grouped: dict[tuple[object, ...], list[float]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[key] for key in cluster_keys)].append(float(row[value_key]))
    clusters = sorted(grouped, key=repr)
    if not clusters:
        return 0.0, 0.0
    generator = np.random.default_rng(seed)
    estimates = []
    for _ in range(int(samples)):
        sampled = generator.choice(len(clusters), size=len(clusters), replace=True)
        values = [value for index in sampled for value in grouped[clusters[int(index)]]]
        estimates.append(float(np.mean(values)))
    return tuple(float(value) for value in np.quantile(estimates, [0.025, 0.975]))  # type: ignore[return-value]


def identity_metric_row(predictions: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Compute sequence-scoped IDF1, switches, and fragmentation."""
    if not predictions:
        return {"global_idf1": 0.0, "global_idsw": 0, "track_fragmentation": 0, "n_predictions": 0}
    gt_values = sorted(
        {(str(row.get("evaluation_scope", row["sequence_id"])), int(row["official_person_id"])) for row in predictions}
    )
    pred_values = sorted(
        {(str(row.get("evaluation_scope", row["sequence_id"])), int(row["global_id"])) for row in predictions}
    )
    gt_index = {value: index for index, value in enumerate(gt_values)}
    pred_index = {value: index for index, value in enumerate(pred_values)}
    counts = np.zeros((len(gt_values), len(pred_values)), dtype=np.int64)
    grouped: dict[tuple[str, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in predictions:
        scope = str(row.get("evaluation_scope", row["sequence_id"]))
        gt_key = (scope, int(row["official_person_id"]))
        pred_key = (scope, int(row["global_id"]))
        counts[gt_index[gt_key], pred_index[pred_key]] += 1
        grouped[gt_key].append(row)
    rows, columns = linear_sum_assignment(counts.max() - counts)
    idtp = int(counts[rows, columns].sum())
    total = len(predictions)
    idf1 = idtp / total
    switches = 0
    fragmentation = 0
    for values in grouped.values():
        ordered = sorted(values, key=lambda row: int(row["frame_id"]))
        ids = [int(row["global_id"]) for row in ordered]
        switches += sum(current != previous for previous, current in zip(ids, ids[1:]))
        fragmentation += max(len(set(ids)) - 1, 0)
    return {
        "global_idf1": float(idf1),
        "global_idsw": int(switches),
        "track_fragmentation": int(fragmentation),
        "idtp": idtp,
        "idfp": total - idtp,
        "idfn": total - idtp,
        "n_predictions": total,
    }


def build_gap_episode_metrics(
    predictions: Sequence[Mapping[str, object]],
    *,
    support_visible_frames: Mapping[tuple[str, int], set[int]],
    support_arrival_frames: Mapping[tuple[str, int], Sequence[tuple[int, int]]],
    delay_frames: int,
    post_window: int = 5,
) -> list[dict[str, object]]:
    """Measure global-ID survival across primary-view absence gaps."""
    grouped: dict[tuple[str, int], list[Mapping[str, object]]] = defaultdict(list)
    for row in predictions:
        grouped[(str(row.get("evaluation_scope", row["sequence_id"])), int(row["official_person_id"]))].append(row)
    result: list[dict[str, object]] = []
    for key, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda row: int(row["frame_id"]))
        frames = [int(row["frame_id"]) for row in ordered]
        row_by_frame = {int(row["frame_id"]): row for row in ordered}
        for pre_frame, post_frame in zip(frames, frames[1:]):
            gap_length = post_frame - pre_frame - 1
            if gap_length <= 0:
                continue
            gap_frames = set(range(pre_frame + 1, post_frame))
            support_frames = support_visible_frames.get(key, set()) & gap_frames
            if not support_frames:
                continue
            pre_id = int(row_by_frame[pre_frame]["global_id"])
            post_id = int(row_by_frame[post_frame]["global_id"])
            post_rows = [
                row_by_frame[frame]
                for frame in frames
                if post_frame <= frame < post_frame + int(post_window)
            ]
            arrival_pairs = support_arrival_frames.get(key, ())
            arrived = [(capture, arrival) for capture, arrival in arrival_pairs if capture in gap_frames and arrival <= post_frame]
            latest_capture = max((capture for capture, _ in arrived), default=None)
            result.append(
                {
                    "sequence_id": str(row_by_frame[pre_frame]["sequence_id"]),
                    "evaluation_scope": key[0],
                    "official_person_id": key[1],
                    "pre_frame": pre_frame,
                    "gap_start_frame": pre_frame + 1,
                    "gap_end_frame": post_frame - 1,
                    "post_frame": post_frame,
                    "gap_length_frames": gap_length,
                    "delay_frames": int(delay_frames),
                    "delay_over_gap_length": float(delay_frames / gap_length),
                    "support_coverage_fraction": len(support_frames) / gap_length,
                    "identity_survived": int(pre_id == post_id),
                    "reacquisition_delay_frames": 0,
                    "post_gap_same_id_fraction": (
                        sum(int(row["global_id"]) == pre_id for row in post_rows) / max(len(post_rows), 1)
                    ),
                    "arrived_before_primary_reacquisition": int(bool(arrived)),
                    "message_age_at_reacquisition": (
                        "" if latest_capture is None else post_frame - latest_capture
                    ),
                }
            )
    return result


def official_person_aas(
    primary_rows: Sequence[Mapping[str, object]],
    support_rows: Sequence[Mapping[str, object]],
    *,
    frame_consistent_only: bool,
) -> dict[str, object]:
    """Reproduce the official frame-mean AAS formula for GT-box person rows.

    With GT boxes, within-view IoU assignment is exact. Each frame contributes
    ``TA / (GA + FA + MA)`` as in the official ``mango_eval.py``.
    """
    primary_by_frame: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    support_by_frame: dict[int, list[Mapping[str, object]]] = defaultdict(list)
    for row in primary_rows:
        if not frame_consistent_only or int(row.get("frame_consistent_person", 0)):
            primary_by_frame[int(row["frame_id"])].append(row)
    for row in support_rows:
        if not frame_consistent_only or int(row.get("frame_consistent_person", 0)):
            support_by_frame[int(row["frame_id"])].append(row)
    frames = sorted(set(primary_by_frame) | set(support_by_frame))
    scores: list[float] = []
    total_gt = total_result = total_true = 0
    for frame in frames:
        first = primary_by_frame.get(frame, [])
        second = support_by_frame.get(frame, [])
        gt_pair_count = sum(
            int(a["official_person_id"]) == int(b["official_person_id"])
            for a in first
            for b in second
        )
        result_pair_count = sum(
            a.get("global_id", "") != ""
            and b.get("global_id", "") != ""
            and int(a["global_id"]) == int(b["global_id"])
            for a in first
            for b in second
        )
        true_pairs = 0
        for a in first:
            for b in second:
                if (
                    int(a["official_person_id"]) == int(b["official_person_id"])
                    and a.get("global_id", "") != ""
                    and b.get("global_id", "") != ""
                    and int(a["global_id"]) == int(b["global_id"])
                ):
                    true_pairs += 1
        ga = int(gt_pair_count)
        ra = int(result_pair_count)
        fa = ra - true_pairs
        ma = ga - true_pairs
        denominator = ga + fa + ma
        scores.append(0.0 if denominator <= 0 else true_pairs / denominator)
        total_gt += ga
        total_result += ra
        total_true += true_pairs
    return {
        "person_aas": float(np.mean(scores)) if scores else 0.0,
        "n_frames": len(frames),
        "gt_association_pairs": total_gt,
        "result_association_pairs": total_result,
        "true_association_pairs": total_true,
        "frame_consistent_only": int(frame_consistent_only),
    }
