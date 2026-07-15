"""Support marginal-value audit helpers for MATRIX Stage A experiments."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Mapping, Sequence

from tracking.matrix_gt import MatrixTraceRow


AUDIT_EVENT_SUBSETS: tuple[str, ...] = (
    "proximity",
    "crossing_like",
    "high_motion",
    "support_only",
    "normal",
)

WEIGHT_BUCKETS: tuple[str, ...] = (
    "weight_eq_0",
    "weight_0_0p1",
    "weight_0p1_0p25",
    "weight_0p25_1",
)


def trace_key(row: MatrixTraceRow) -> tuple[int, int]:
    return int(row.frame_id), int(row.person_id)


def align_pipeline_traces(
    rows: Sequence[MatrixTraceRow],
    *,
    required_pipelines: Sequence[str],
) -> list[dict[str, object]]:
    """Align trace rows by `(frame_id, person_id)` across required pipelines."""
    grouped: dict[tuple[int, int], dict[str, MatrixTraceRow]] = defaultdict(dict)
    for row in rows:
        grouped[trace_key(row)][str(row.pipeline)] = row

    aligned: list[dict[str, object]] = []
    for key in sorted(grouped):
        by_pipeline = grouped[key]
        if any(pipeline not in by_pipeline for pipeline in required_pipelines):
            continue
        first = by_pipeline[required_pipelines[0]]
        record: dict[str, object] = {
            "frame_id": int(first.frame_id),
            "person_id": int(first.person_id),
            "event_tags": "|".join(first.event_tags),
            "primary_visible": int(first.primary_visible),
            "support_visible_count": int(first.support_visible_count),
        }
        for pipeline in required_pipelines:
            row = by_pipeline[pipeline]
            record[f"{pipeline}_pred_id"] = int(row.pred_id)
            record[f"{pipeline}_idsw_event"] = int(row.idsw_event)
        aligned.append(record)
    return aligned


def weight_bucket(value: float) -> str:
    weight = float(value)
    if weight <= 0.0:
        return "weight_eq_0"
    if weight <= 0.10:
        return "weight_0_0p1"
    if weight <= 0.25:
        return "weight_0p1_0p25"
    return "weight_0p25_1"


def aggregate_gate_by_key(
    diagnostics: Sequence[Mapping[str, object]],
    *,
    trace_rows: Sequence[MatrixTraceRow] = (),
) -> dict[tuple[str, int, int], dict[str, object]]:
    """Aggregate support gate diagnostics by `(pipeline, eval_frame, person_id)`."""
    future_primary: dict[tuple[str, int], list[tuple[int, int]]] = defaultdict(list)
    for row in trace_rows:
        if row.primary_visible:
            future_primary[(str(row.pipeline), int(row.person_id))].append((int(row.frame_id), int(row.pred_id)))
    for key in list(future_primary):
        future_primary[key] = sorted(future_primary[key])

    grouped: dict[tuple[str, int, int], dict[str, object]] = {}
    for row in diagnostics:
        pipeline = str(row["pipeline"])
        eval_frame = int(row["eval_frame"])
        person_id = int(row["person_id"])
        key = (pipeline, eval_frame, person_id)
        bucket = grouped.setdefault(
            key,
            {
                "support_observations": 0,
                "accepted": 0,
                "rejected": 0,
                "candidate_gate": 0,
                "ambiguity_margin": 0,
                "none": 0,
                "weight_eq_0": 0,
                "weight_0_0p1": 0,
                "weight_0p1_0p25": 0,
                "weight_0p25_1": 0,
                "weight_sum": 0.0,
                "max_final_weight": 0.0,
                "primary_confirmed": 0,
            },
        )
        accepted = int(row.get("accepted", 0))
        final_weight = float(row.get("final_weight", row.get("update_weight", 0.0)))
        reject_reason = str(row.get("reject_reason", "none"))
        assigned_track_id = int(row.get("assigned_track_id", -1))
        group = grouped[key]
        group["support_observations"] = int(group["support_observations"]) + 1
        group["accepted"] = int(group["accepted"]) + accepted
        group["rejected"] = int(group["rejected"]) + int(not accepted)
        group[reject_reason] = int(group.get(reject_reason, 0)) + 1
        bucket_name = weight_bucket(final_weight)
        group[bucket_name] = int(group[bucket_name]) + 1
        group["weight_sum"] = float(group["weight_sum"]) + final_weight
        group["max_final_weight"] = max(float(group["max_final_weight"]), final_weight)
        if accepted:
            confirmed = any(
                frame_id > eval_frame and pred_id == assigned_track_id
                for frame_id, pred_id in future_primary.get((pipeline, person_id), [])
            )
            group["primary_confirmed"] = int(group["primary_confirmed"]) + int(confirmed)

    for group in grouped.values():
        total = int(group["support_observations"])
        group["mean_final_weight"] = float(group["weight_sum"]) / total if total else 0.0
    return grouped


def classify_support_marginal_value(
    aligned_row: Mapping[str, object],
    *,
    risk_pipeline: str,
    gate_summary: Mapping[str, object] | None,
    drop_pipeline: str = "drop_delayed",
    uncertain_pipeline: str = "timestamped_uncertain_fusion",
) -> str:
    """Classify a row's local support marginal effect into one audit category."""
    risk_switch = int(aligned_row[f"{risk_pipeline}_idsw_event"])
    drop_switch = int(aligned_row[f"{drop_pipeline}_idsw_event"])
    uncertain_switch = int(aligned_row[f"{uncertain_pipeline}_idsw_event"])
    tags = set(str(aligned_row.get("event_tags", "")).split("|"))
    gate = gate_summary or {}
    accepted = int(gate.get("accepted", 0))
    rejected = int(gate.get("rejected", 0))
    max_weight = float(gate.get("max_final_weight", 0.0))

    if risk_switch < drop_switch or risk_switch < uncertain_switch:
        return "helpful_support"
    if accepted > 0 and (risk_switch > drop_switch or risk_switch > uncertain_switch):
        return "harmful_accept"
    high_value_context = bool(tags.intersection({"support_only", "proximity", "crossing_like", "high_motion"}))
    weak_or_rejected = bool(rejected > 0 or (accepted > 0 and max_weight <= 0.10))
    if high_value_context and weak_or_rejected and uncertain_switch <= risk_switch:
        return "over_reject_or_underweight"
    return "neutral"


def category_summary(rows: Sequence[Mapping[str, object]], *, group_fields: Sequence[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], dict[str, object]] = {}
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        group = grouped.setdefault(
            key,
            {
                **{field: row[field] for field in group_fields},
                "rows": 0,
                "helpful_support": 0,
                "harmful_accept": 0,
                "over_reject_or_underweight": 0,
                "neutral": 0,
            },
        )
        category = str(row["category"])
        group["rows"] = int(group["rows"]) + 1
        group[category] = int(group[category]) + 1

    summary = []
    for group in grouped.values():
        rows_total = int(group["rows"])
        helpful = int(group["helpful_support"])
        harmful = int(group["harmful_accept"])
        weak = int(group["over_reject_or_underweight"])
        group["net_helpful_minus_harmful_weak"] = helpful - harmful - weak
        group["helpful_rate"] = f"{(helpful / rows_total) if rows_total else 0.0:.6f}"
        group["harmful_rate"] = f"{(harmful / rows_total) if rows_total else 0.0:.6f}"
        group["weak_or_rejected_rate"] = f"{(weak / rows_total) if rows_total else 0.0:.6f}"
        summary.append(dict(group))
    return sorted(summary, key=lambda row: tuple(str(row[field]) for field in group_fields))


def finite_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default
