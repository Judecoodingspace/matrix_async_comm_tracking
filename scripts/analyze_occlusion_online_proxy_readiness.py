#!/usr/bin/env python3
"""Evaluate whether online-observable proxies can predict support gain."""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence


FRAME_MS_DEFAULT = 500.0
EPS = 1e-12


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--matched-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-episode-rows", type=int, default=0)
    parser.add_argument("--max-frame-rows", type=int, default=0)
    parser.add_argument("--max-frame-model-rows", type=int, default=4000)
    parser.add_argument("--episode-gain-threshold", type=float, default=0.05)
    parser.add_argument("--high-gain-threshold", type=float, default=0.25)
    parser.add_argument("--frame-gain-threshold", type=float, default=0.0)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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
    return "" if value is None else f"{value:.{digits}f}"


def mean(values: Sequence[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def frame_ms_from_row(row: Mapping[str, str]) -> float:
    delay_ms = safe_float(row.get("delay_ms"))
    delay_frames = safe_float(row.get("delay_frames"))
    if delay_ms is not None and delay_frames is not None and delay_frames > 0:
        return delay_ms / delay_frames
    return FRAME_MS_DEFAULT


def relative_frame_index(row: Mapping[str, object]) -> int:
    frame_id = safe_int(row.get("frame_id"))
    start_frame = safe_int(row.get("start_frame"))
    if frame_id is None or start_frame is None:
        raise ValueError("frame_id and start_frame are required")
    return frame_id - start_frame


def group_key(row: Mapping[str, object]) -> str:
    return f"{float(row['delay_ms']):.3f}|{row['rho_bucket']}"


def build_frame_lookup(frame_rows: Sequence[Mapping[str, str]], *, max_rows: int = 0) -> dict[tuple[str, str, str, str], list[dict[str, object]]]:
    lookup: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    count = 0
    for row in frame_rows:
        frame_gain = safe_float(row.get("frame_gain"))
        delay_ms = safe_float(row.get("delay_ms"))
        person_id = row.get("person_id")
        start_frame = row.get("start_frame")
        end_frame = row.get("end_frame")
        if frame_gain is None or delay_ms is None or person_id is None or start_frame is None or end_frame is None:
            continue
        parsed: dict[str, object] = dict(row)
        parsed["frame_gain_value"] = frame_gain
        parsed["delay_ms_value"] = delay_ms
        parsed["relative_frame_index_value"] = relative_frame_index(row)
        key = (f"{delay_ms:.3f}", str(person_id), str(start_frame), str(end_frame))
        lookup[key].append(parsed)
        count += 1
        if max_rows and count >= max_rows:
            break
    return lookup


def _numeric_from_frames(frames: Sequence[Mapping[str, object]], key: str) -> list[float]:
    values: list[float] = []
    for frame in frames:
        value = safe_float(frame.get(key))
        if value is not None:
            values.append(value)
    return values


def early_frames(frames: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    output: list[Mapping[str, object]] = []
    for frame in frames:
        rel_fraction = relative_frame_fraction_from_frame(frame)
        if rel_fraction <= 0.25:
            output.append(frame)
    return output


def relative_frame_fraction_from_frame(row: Mapping[str, object]) -> float:
    rel_index = safe_float(row.get("relative_frame_index_value"))
    if rel_index is None:
        rel_index = float(relative_frame_index(row))
    episode_length = safe_float(row.get("episode_length"))
    if episode_length is None or episode_length <= 0:
        raise ValueError("episode_length must be positive")
    return rel_index / max(1.0, episode_length)


def build_episode_dataset(
    episode_rows: Sequence[Mapping[str, str]],
    frame_lookup: Mapping[tuple[str, str, str, str], Sequence[Mapping[str, object]]],
    *,
    positive_threshold: float,
    high_threshold: float,
    max_rows: int = 0,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in episode_rows:
        if row.get("eligible") != "1":
            continue
        delay_ms = safe_float(row.get("delay_ms"))
        during_gain = safe_float(row.get("during_gain"))
        if delay_ms is None or during_gain is None:
            continue
        delay_frames = safe_float(row.get("delay_frames")) or 0.0
        frame_ms = frame_ms_from_row(row)
        key = (
            f"{delay_ms:.3f}",
            str(row.get("person_id")),
            str(row.get("start_frame")),
            str(row.get("end_frame")),
        )
        frames = list(frame_lookup.get(key, []))
        early = early_frames(frames)
        early_arrived = _numeric_from_frames(early, "has_arrived_support")
        early_fresh = _numeric_from_frames(early, "is_fresh_support")
        early_ages = _numeric_from_frames(early, "latest_support_age_ms")
        no_support_fraction = safe_float(row.get("no_support_available_frame_fraction"))
        fresh_fraction = safe_float(row.get("fresh_support_frame_fraction"))
        mean_age_ms = safe_float(row.get("mean_latest_support_age_ms"))
        delay_s = delay_ms / 1000.0
        mean_age_s = (mean_age_ms / 1000.0) if mean_age_ms is not None else delay_s
        early_mean_age_s = (mean(early_ages) / 1000.0) if early_ages else delay_s
        early_arrived_fraction = mean(early_arrived) if early_arrived else 0.0
        early_fresh_fraction = mean(early_fresh) if early_fresh else 0.0
        early_no_support_fraction = 1.0 - early_arrived_fraction
        parsed = {
            "level": "episode",
            "row_id": len(output),
            "group_key": group_key({"delay_ms": delay_ms, "rho_bucket": row.get("rho_bucket", "")}),
            "delay_profile": row.get("delay_profile", ""),
            "delay_ms": f"{delay_ms:.3f}",
            "delay_s": fmt(delay_s),
            "delay_frames": fmt(delay_frames, 3),
            "person_id": row.get("person_id", ""),
            "start_frame": row.get("start_frame", ""),
            "end_frame": row.get("end_frame", ""),
            "episode_length": row.get("episode_length", ""),
            "rho_episode": fmt(safe_float(row.get("rho_episode"))),
            "rho_bucket": row.get("rho_bucket", ""),
            "during_gain": fmt(during_gain),
            "positive_episode_gain": int(during_gain > positive_threshold),
            "high_episode_gain": int(during_gain > high_threshold),
            "spillover_gain": fmt(safe_float(row.get("spillover_gain"))),
            "spillover_helpful": int((safe_float(row.get("spillover_gain")) or 0.0) > positive_threshold),
            "online_support_coverage_fraction": fmt(safe_float(row.get("online_support_coverage_fraction"))),
            "fresh_support_frame_fraction": fmt(fresh_fraction),
            "no_support_available_frame_fraction": fmt(no_support_fraction),
            "mean_latest_support_age_s": fmt(mean_age_s),
            "early_frame_count": len(early),
            "early_arrived_support_fraction": fmt(early_arrived_fraction),
            "early_fresh_support_fraction": fmt(early_fresh_fraction),
            "early_no_support_fraction": fmt(early_no_support_fraction),
            "early_mean_latest_support_age_s": fmt(early_mean_age_s),
            "early_occlusion_run_length_frames": len(early),
            "early_occlusion_run_length_s": fmt(len(early) * frame_ms / 1000.0),
        }
        output.append(parsed)
        if max_rows and len(output) >= max_rows:
            break
    return output


def build_frame_dataset(
    frame_rows: Sequence[Mapping[str, str]],
    *,
    positive_threshold: float,
    max_rows: int = 0,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in frame_rows:
        frame_gain = safe_float(row.get("frame_gain"))
        delay_ms = safe_float(row.get("delay_ms"))
        if frame_gain is None or delay_ms is None:
            continue
        rel_index = relative_frame_index(row)
        frame_ms = frame_ms_from_row(row)
        latest_age_ms = safe_float(row.get("latest_support_age_ms"))
        delay_s = delay_ms / 1000.0
        time_since_last_primary_seen_s = max(0.0, rel_index) * frame_ms / 1000.0
        filled_age_s = (
            latest_age_ms / 1000.0
            if latest_age_ms is not None
            else delay_s + time_since_last_primary_seen_s
        )
        episode_length = safe_float(row.get("episode_length")) or 1.0
        parsed = {
            "level": "frame",
            "row_id": len(output),
            "group_key": group_key({"delay_ms": delay_ms, "rho_bucket": row.get("rho_bucket", "")}),
            "delay_profile": row.get("delay_profile", ""),
            "delay_ms": f"{delay_ms:.3f}",
            "delay_s": fmt(delay_s),
            "delay_frames": fmt(safe_float(row.get("delay_frames")) or 0.0, 3),
            "person_id": row.get("person_id", ""),
            "start_frame": row.get("start_frame", ""),
            "end_frame": row.get("end_frame", ""),
            "frame_id": row.get("frame_id", ""),
            "episode_length": row.get("episode_length", ""),
            "rho_episode": fmt(safe_float(row.get("rho_episode"))),
            "rho_bucket": row.get("rho_bucket", ""),
            "relative_frame_index": rel_index,
            "relative_frame_fraction": fmt(rel_index / max(1.0, episode_length)),
            "time_since_last_primary_seen_s": fmt(time_since_last_primary_seen_s),
            "early_occlusion_run_length_frames": rel_index + 1,
            "early_occlusion_run_length_s": fmt((rel_index + 1) * frame_ms / 1000.0),
            "has_arrived_support": safe_int(row.get("has_arrived_support")) or 0,
            "is_fresh_support": safe_int(row.get("is_fresh_support")) or 0,
            "latest_support_age_s": fmt(filled_age_s),
            "frame_gain": fmt(frame_gain),
            "positive_frame_gain": int(frame_gain > positive_threshold),
        }
        output.append(parsed)
        if max_rows and len(output) >= max_rows:
            break
    return output


MODEL_FEATURES: dict[str, dict[str, list[str]]] = {
    "episode": {
        "M1_delay_only": ["delay_s"],
        "M2_episode_rho_oracle": ["rho_episode"],
        "M3_online_freshness": [
            "mean_latest_support_age_s",
            "fresh_support_frame_fraction",
            "no_support_available_frame_fraction",
        ],
        "M4_early_occlusion_proxy": [
            "early_arrived_support_fraction",
            "early_fresh_support_fraction",
            "early_no_support_fraction",
            "early_mean_latest_support_age_s",
            "early_occlusion_run_length_s",
        ],
        "M5_combined_online_proxy": [
            "delay_s",
            "mean_latest_support_age_s",
            "fresh_support_frame_fraction",
            "no_support_available_frame_fraction",
            "early_arrived_support_fraction",
            "early_no_support_fraction",
            "early_mean_latest_support_age_s",
            "early_occlusion_run_length_s",
        ],
    },
    "frame": {
        "M1_delay_only": ["delay_s"],
        "M2_episode_rho_oracle": ["rho_episode"],
        "M3_online_freshness": [
            "latest_support_age_s",
            "has_arrived_support",
            "is_fresh_support",
        ],
        "M4_early_occlusion_proxy": [
            "time_since_last_primary_seen_s",
            "early_occlusion_run_length_s",
            "relative_frame_fraction",
        ],
        "M5_combined_online_proxy": [
            "delay_s",
            "latest_support_age_s",
            "has_arrived_support",
            "is_fresh_support",
            "time_since_last_primary_seen_s",
            "early_occlusion_run_length_s",
            "relative_frame_fraction",
        ],
    },
}


TARGETS = {
    "episode": "positive_episode_gain",
    "frame": "positive_frame_gain",
}


def feature_matrix(rows: Sequence[Mapping[str, object]], features: Sequence[str]) -> list[list[float]]:
    matrix: list[list[float]] = []
    for row in rows:
        values: list[float] = []
        for feature in features:
            parsed = safe_float(row.get(feature))
            values.append(0.0 if parsed is None else parsed)
        matrix.append(values)
    return matrix


def target_vector(rows: Sequence[Mapping[str, object]], target: str) -> list[int]:
    return [1 if (safe_int(row.get(target)) or 0) > 0 else 0 for row in rows]


def standardize_train(matrix: Sequence[Sequence[float]]) -> tuple[list[float], list[float]]:
    if not matrix:
        return [], []
    n_features = len(matrix[0])
    means: list[float] = []
    stds: list[float] = []
    for index in range(n_features):
        values = [row[index] for row in matrix]
        m = sum(values) / len(values)
        variance = sum((value - m) ** 2 for value in values) / len(values)
        std = math.sqrt(variance)
        means.append(m)
        stds.append(std if std > EPS else 1.0)
    return means, stds


def apply_standardization(
    matrix: Sequence[Sequence[float]], means: Sequence[float], stds: Sequence[float]
) -> list[list[float]]:
    return [[(value - means[index]) / stds[index] for index, value in enumerate(row)] for row in matrix]


def fit_logistic_regression(
    matrix: Sequence[Sequence[float]],
    target: Sequence[int],
    *,
    iterations: int = 100,
    learning_rate: float = 0.15,
    l2: float = 0.01,
) -> dict[str, object]:
    if not matrix:
        return {"weights": [], "means": [], "stds": [], "constant_probability": 0.0}
    positive_rate = sum(target) / len(target)
    if positive_rate <= 0.0 or positive_rate >= 1.0:
        return {
            "weights": [],
            "means": [0.0 for _ in matrix[0]],
            "stds": [1.0 for _ in matrix[0]],
            "constant_probability": positive_rate,
        }
    means, stds = standardize_train(matrix)
    x = apply_standardization(matrix, means, stds)
    n_features = len(x[0])
    weights = [0.0 for _ in range(n_features + 1)]
    for _ in range(iterations):
        gradients = [0.0 for _ in weights]
        for values, label in zip(x, target):
            score = weights[0] + sum(weights[index + 1] * values[index] for index in range(n_features))
            pred = sigmoid(score)
            error = pred - label
            gradients[0] += error
            for index, value in enumerate(values):
                gradients[index + 1] += error * value
        scale = 1.0 / len(x)
        weights[0] -= learning_rate * gradients[0] * scale
        for index in range(1, len(weights)):
            regularized_gradient = gradients[index] * scale + l2 * weights[index]
            weights[index] -= learning_rate * regularized_gradient
    return {"weights": weights, "means": means, "stds": stds, "constant_probability": None}


def predict_probabilities(model: Mapping[str, object], matrix: Sequence[Sequence[float]]) -> list[float]:
    constant = model.get("constant_probability")
    if constant is not None:
        return [float(constant) for _ in matrix]
    weights = [float(value) for value in model["weights"]]  # type: ignore[index]
    means = [float(value) for value in model["means"]]  # type: ignore[index]
    stds = [float(value) for value in model["stds"]]  # type: ignore[index]
    x = apply_standardization(matrix, means, stds)
    output: list[float] = []
    for values in x:
        score = weights[0] + sum(weights[index + 1] * values[index] for index in range(len(values)))
        output.append(sigmoid(score))
    return output


def auc_score(labels: Sequence[int], scores: Sequence[float]) -> float | None:
    positives = sum(labels)
    negatives = len(labels) - positives
    if positives == 0 or negatives == 0:
        return None
    ordered = sorted(zip(scores, labels), key=lambda item: item[0])
    rank_sum = 0.0
    rank = 1
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and abs(ordered[end][0] - ordered[index][0]) <= 1e-12:
            end += 1
        average_rank = (rank + rank + (end - index) - 1) / 2.0
        positive_count = sum(label for _, label in ordered[index:end])
        rank_sum += positive_count * average_rank
        rank += end - index
        index = end
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def classification_metrics(labels: Sequence[int], scores: Sequence[float], *, threshold: float = 0.5) -> dict[str, float | None]:
    tp = fp = tn = fn = 0
    for label, score in zip(labels, scores):
        pred = 1 if score >= threshold else 0
        if pred == 1 and label == 1:
            tp += 1
        elif pred == 1 and label == 0:
            fp += 1
        elif pred == 0 and label == 0:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(labels) if labels else 0.0
    rmse = math.sqrt(sum((score - label) ** 2 for label, score in zip(labels, scores)) / len(labels)) if labels else 0.0
    return {
        "auc": auc_score(labels, scores),
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "rmse": rmse,
        "tp": float(tp),
        "fp": float(fp),
        "tn": float(tn),
        "fn": float(fn),
    }


def metric_row(prefix: str, metrics: Mapping[str, float | None]) -> dict[str, object]:
    return {
        f"{prefix}_auc": fmt(metrics.get("auc")),
        f"{prefix}_accuracy": fmt(metrics.get("accuracy")),
        f"{prefix}_precision": fmt(metrics.get("precision")),
        f"{prefix}_recall": fmt(metrics.get("recall")),
        f"{prefix}_f1": fmt(metrics.get("f1")),
        f"{prefix}_rmse": fmt(metrics.get("rmse")),
    }


def train_and_predict(
    rows: Sequence[Mapping[str, object]],
    features: Sequence[str],
    target: str,
    train_indices: Sequence[int],
    test_indices: Sequence[int],
) -> tuple[list[float], Mapping[str, object]]:
    train_rows = [rows[index] for index in train_indices]
    test_rows = [rows[index] for index in test_indices]
    train_matrix = feature_matrix(train_rows, features)
    train_target = target_vector(train_rows, target)
    model = fit_logistic_regression(train_matrix, train_target)
    test_matrix = feature_matrix(test_rows, features)
    return predict_probabilities(model, test_matrix), model


def group_cv_predictions(
    rows: Sequence[Mapping[str, object]],
    features: Sequence[str],
    target: str,
    *,
    level: str,
    model_name: str,
) -> tuple[list[float], list[dict[str, object]]]:
    by_group: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_group[str(row["group_key"])].append(index)
    predictions = [0.0 for _ in rows]
    fold_rows: list[dict[str, object]] = []
    all_indices = list(range(len(rows)))
    for group, test_indices in sorted(by_group.items()):
        test_set = set(test_indices)
        train_indices = [index for index in all_indices if index not in test_set]
        scores, _ = train_and_predict(rows, features, target, train_indices, test_indices)
        for index, score in zip(test_indices, scores):
            predictions[index] = score
        labels = target_vector([rows[index] for index in test_indices], target)
        metrics = classification_metrics(labels, scores)
        fold_rows.append(
            {
                "level": level,
                "model": model_name,
                "group_key": group,
                "n_train": len(train_indices),
                "n_test": len(test_indices),
                "positive_rate": fmt(sum(labels) / len(labels) if labels else 0.0),
                **metric_row("group", metrics),
            }
        )
    return predictions, fold_rows


def full_model_coefficients(
    rows: Sequence[Mapping[str, object]], features: Sequence[str], target: str
) -> dict[str, float]:
    model = fit_logistic_regression(feature_matrix(rows, features), target_vector(rows, target))
    if model.get("constant_probability") is not None:
        return {feature: 0.0 for feature in features}
    weights = [float(value) for value in model["weights"]]  # type: ignore[index]
    return {feature: weights[index + 1] for index, feature in enumerate(features)}


def compare_models(rows: Sequence[Mapping[str, object]], *, level: str) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, list[float]]]:
    target = TARGETS[level]
    comparison_rows: list[dict[str, object]] = []
    group_rows: list[dict[str, object]] = []
    oof_predictions: dict[str, list[float]] = {}
    for model_name, features in MODEL_FEATURES[level].items():
        matrix = feature_matrix(rows, features)
        labels = target_vector(rows, target)
        full_model = fit_logistic_regression(matrix, labels)
        full_scores = predict_probabilities(full_model, matrix)
        full_metrics = classification_metrics(labels, full_scores)
        cv_scores, fold_rows = group_cv_predictions(
            rows,
            features,
            target,
            level=level,
            model_name=model_name,
        )
        cv_metrics = classification_metrics(labels, cv_scores)
        coefficients = full_model_coefficients(rows, features, target)
        comparison_rows.append(
            {
                "level": level,
                "model": model_name,
                "target": target,
                "features": ";".join(features),
                "n_rows": len(rows),
                "n_positive": sum(labels),
                "positive_rate": fmt(sum(labels) / len(labels) if labels else 0.0),
                "n_groups": len({row["group_key"] for row in rows}),
                **metric_row("train", full_metrics),
                **metric_row("group_cv", cv_metrics),
                "coefficient_json": format_coefficients(coefficients),
            }
        )
        group_rows.extend(fold_rows)
        oof_predictions[f"{level}:{model_name}"] = cv_scores
    return comparison_rows, group_rows, oof_predictions


def balanced_group_sample(
    rows: Sequence[Mapping[str, object]],
    *,
    max_rows: int,
) -> list[Mapping[str, object]]:
    if max_rows <= 0 or len(rows) <= max_rows:
        return list(rows)
    by_group: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        by_group[str(row["group_key"])].append(row)
    groups = sorted(by_group)
    per_group = max(1, max_rows // len(groups))
    sampled: list[Mapping[str, object]] = []
    leftovers: list[Mapping[str, object]] = []
    for group in groups:
        group_rows = by_group[group]
        sampled.extend(group_rows[:per_group])
        leftovers.extend(group_rows[per_group:])
    remaining = max_rows - len(sampled)
    if remaining > 0:
        sampled.extend(leftovers[:remaining])
    return sampled[:max_rows]


def format_coefficients(coefficients: Mapping[str, float]) -> str:
    body = ",".join(f'"{key}":{value:.6f}' for key, value in coefficients.items())
    return "{" + body + "}"


def error_diagnostics(
    rows: Sequence[Mapping[str, object]],
    predictions: Mapping[str, list[float]],
    *,
    level: str,
    models: Sequence[str] = ("M1_delay_only", "M5_combined_online_proxy"),
) -> list[dict[str, object]]:
    target = TARGETS[level]
    grouped: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped[(str(row["delay_ms"]), str(row["rho_bucket"]), str(row.get("level", level)))].append(index)
    output: list[dict[str, object]] = []
    for model in models:
        scores = predictions.get(f"{level}:{model}", [])
        if not scores:
            continue
        for (delay_ms, rho_bucket, _), indices in sorted(grouped.items(), key=lambda item: (float(item[0][0]), item[0][1])):
            labels = [safe_int(rows[index].get(target)) or 0 for index in indices]
            group_scores = [scores[index] for index in indices]
            metrics = classification_metrics(labels, group_scores)
            output.append(
                {
                    "level": level,
                    "model": model,
                    "delay_ms": delay_ms,
                    "rho_bucket": rho_bucket,
                    "n_rows": len(indices),
                    "positive_rate": fmt(sum(labels) / len(labels) if labels else 0.0),
                    "mean_predicted_probability": fmt(mean(group_scores)),
                    "tp": int(metrics["tp"] or 0),
                    "fp": int(metrics["fp"] or 0),
                    "tn": int(metrics["tn"] or 0),
                    "fn": int(metrics["fn"] or 0),
                    "false_negative_rate": fmt((metrics["fn"] or 0.0) / ((metrics["fn"] or 0.0) + (metrics["tp"] or 0.0)) if ((metrics["fn"] or 0.0) + (metrics["tp"] or 0.0)) > 0 else 0.0),
                    "false_positive_rate": fmt((metrics["fp"] or 0.0) / ((metrics["fp"] or 0.0) + (metrics["tn"] or 0.0)) if ((metrics["fp"] or 0.0) + (metrics["tn"] or 0.0)) > 0 else 0.0),
                    **metric_row("group_cv", metrics),
                }
            )
    return output


def row_by_model(rows: Sequence[Mapping[str, object]], *, level: str, model: str) -> Mapping[str, object]:
    for row in rows:
        if row.get("level") == level and row.get("model") == model:
            return row
    return {}


def decision_from_results(comparison_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    m1 = row_by_model(comparison_rows, level="episode", model="M1_delay_only")
    m5 = row_by_model(comparison_rows, level="episode", model="M5_combined_online_proxy")
    m1_auc = safe_float(m1.get("group_cv_auc"))
    m5_auc = safe_float(m5.get("group_cv_auc"))
    m1_f1 = safe_float(m1.get("group_cv_f1")) or 0.0
    m5_f1 = safe_float(m5.get("group_cv_f1")) or 0.0
    m5_recall = safe_float(m5.get("group_cv_recall")) or 0.0
    auc_improvement = None if m1_auc is None or m5_auc is None else m5_auc - m1_auc
    f1_improvement = m5_f1 - m1_f1
    coefficients = parse_coefficients(str(m5.get("coefficient_json", "{}")))
    age_coef = coefficients.get("mean_latest_support_age_s")
    early_age_coef = coefficients.get("early_mean_latest_support_age_s")
    no_support_coef = coefficients.get("no_support_available_frame_fraction")
    signs_reasonable = (
        (age_coef is None or age_coef <= 0.0)
        and (early_age_coef is None or early_age_coef <= 0.0)
        and (no_support_coef is None or no_support_coef <= 0.0)
    )
    supported = (
        auc_improvement is not None
        and auc_improvement >= 0.05
        and f1_improvement >= 0.05
        and m5_recall >= 0.70
        and signs_reasonable
    )
    weak = (
        auc_improvement is not None
        and auc_improvement > 0.0
        and (m5_f1 > m1_f1 or m5_recall > (safe_float(m1.get("group_cv_recall")) or 0.0))
    )
    if supported:
        decision = "policy_readiness_supported"
    elif weak:
        decision = "online_proxy_weak"
    else:
        decision = "delay_only_sufficient_for_now"
    return {
        "decision": decision,
        "m1_episode_group_cv_auc": fmt(m1_auc),
        "m5_episode_group_cv_auc": fmt(m5_auc),
        "episode_auc_improvement": fmt(auc_improvement),
        "m1_episode_group_cv_f1": fmt(m1_f1),
        "m5_episode_group_cv_f1": fmt(m5_f1),
        "episode_f1_improvement": fmt(f1_improvement),
        "m5_episode_group_cv_recall": fmt(m5_recall),
        "mean_latest_support_age_s_coef": fmt(age_coef),
        "early_mean_latest_support_age_s_coef": fmt(early_age_coef),
        "no_support_available_frame_fraction_coef": fmt(no_support_coef),
        "key_signs_reasonable": int(signs_reasonable),
    }


def parse_coefficients(payload: str) -> dict[str, float]:
    payload = payload.strip()
    if not payload.startswith("{") or not payload.endswith("}"):
        return {}
    inner = payload[1:-1].strip()
    if not inner:
        return {}
    output: dict[str, float] = {}
    for part in inner.split(","):
        key, _, raw_value = part.partition(":")
        key = key.strip().strip('"')
        value = safe_float(raw_value)
        if key and value is not None:
            output[key] = value
    return output


def decision_markdown(decision: Mapping[str, object], comparison_rows: Sequence[Mapping[str, object]]) -> str:
    episode_models = [row for row in comparison_rows if row.get("level") == "episode"]
    frame_models = [row for row in comparison_rows if row.get("level") == "frame"]
    lines = [
        "# Online Proxy Readiness Decision",
        "",
        f"**Decision**: `{decision['decision']}`",
        "",
        "## Gate 1: Episode-Level Policy Readiness",
        "",
        f"- M1 delay-only group-CV AUC: {decision['m1_episode_group_cv_auc']}",
        f"- M5 combined online proxy group-CV AUC: {decision['m5_episode_group_cv_auc']}",
        f"- AUC improvement: {decision['episode_auc_improvement']}",
        f"- M1 delay-only group-CV F1: {decision['m1_episode_group_cv_f1']}",
        f"- M5 combined online proxy group-CV F1: {decision['m5_episode_group_cv_f1']}",
        f"- F1 improvement: {decision['episode_f1_improvement']}",
        f"- M5 recall: {decision['m5_episode_group_cv_recall']}",
        f"- Key coefficient signs reasonable: {decision['key_signs_reasonable']}",
        "",
        "## Episode Models",
        "",
        "| Model | group-CV AUC | group-CV F1 | group-CV recall | group-CV RMSE |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in episode_models:
        lines.append(
            f"| `{row['model']}` | {row['group_cv_auc']} | {row['group_cv_f1']} | {row['group_cv_recall']} | {row['group_cv_rmse']} |"
        )
    lines.extend(
        [
            "",
            "## Frame Models",
            "",
            "| Model | group-CV AUC | group-CV F1 | group-CV recall | group-CV RMSE |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in frame_models:
        lines.append(
            f"| `{row['model']}` | {row['group_cv_auc']} | {row['group_cv_f1']} | {row['group_cv_recall']} | {row['group_cv_rmse']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `policy_readiness_supported`: online proxies are strong enough to prepare value-based action selection.",
            "- `online_proxy_weak`: proxies add signal but are not yet strong enough for policy learning.",
            "- `delay_only_sufficient_for_now`: delay-only is currently as good as the online proxy set.",
        ]
    )
    return "\n".join(lines)


def maybe_read_matched_context(matched_dir: Path | None) -> None:
    if matched_dir is None:
        return
    expected = matched_dir / "boundary_gate_refined_decision.md"
    if expected.exists():
        expected.read_text(encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    matched_dir = args.matched_dir.expanduser().resolve() if args.matched_dir else None
    output_dir.mkdir(parents=True, exist_ok=True)
    maybe_read_matched_context(matched_dir)

    episode_rows_raw = read_rows(input_dir / "counterfactual_episode_gain.csv")
    frame_rows_raw = read_rows(input_dir / "temporal_boundary_frame_freshness.csv")
    frame_lookup = build_frame_lookup(frame_rows_raw, max_rows=args.max_frame_rows)
    episode_dataset = build_episode_dataset(
        episode_rows_raw,
        frame_lookup,
        positive_threshold=args.episode_gain_threshold,
        high_threshold=args.high_gain_threshold,
        max_rows=args.max_episode_rows,
    )
    frame_dataset = build_frame_dataset(
        frame_rows_raw,
        positive_threshold=args.frame_gain_threshold,
        max_rows=args.max_frame_rows,
    )

    comparison_rows: list[dict[str, object]] = []
    group_rows: list[dict[str, object]] = []
    predictions: dict[str, list[float]] = {}
    frame_model_dataset = balanced_group_sample(
        frame_dataset,
        max_rows=args.max_frame_model_rows,
    )
    for level, rows in (("episode", episode_dataset), ("frame", frame_model_dataset)):
        level_comparison, level_group_rows, level_predictions = compare_models(rows, level=level)
        comparison_rows.extend(level_comparison)
        group_rows.extend(level_group_rows)
        predictions.update(level_predictions)

    diagnostics = error_diagnostics(episode_dataset, predictions, level="episode")
    diagnostics.extend(error_diagnostics(frame_model_dataset, predictions, level="frame"))
    decision = decision_from_results(comparison_rows)

    write_rows(output_dir / "online_proxy_episode_dataset.csv", episode_dataset)
    write_rows(output_dir / "online_proxy_frame_dataset.csv", frame_dataset)
    write_rows(output_dir / "online_proxy_model_comparison.csv", comparison_rows)
    write_rows(output_dir / "online_proxy_group_cv.csv", group_rows)
    write_rows(output_dir / "online_proxy_error_diagnostics.csv", diagnostics)
    write_rows(output_dir / "online_proxy_decision_summary.csv", [decision])
    (output_dir / "online_proxy_decision.md").write_text(
        decision_markdown(decision, comparison_rows),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
