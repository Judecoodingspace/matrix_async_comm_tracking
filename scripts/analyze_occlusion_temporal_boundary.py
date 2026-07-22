#!/usr/bin/env python3
"""Analyze temporal harm boundary from paired occlusion counterfactual outputs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--bootstrap-iterations", type=int, default=300)
    return parser.parse_args()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_rows(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
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


def _safe_float(value: object) -> float | None:
    if value in ("", None):
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        return None
    return parsed


def _coverage_bucket(value: float) -> str:
    if value < 0.25:
        return "[0,0.25)"
    if value < 0.5:
        return "[0.25,0.5)"
    if value < 0.75:
        return "[0.5,0.75)"
    return "[0.75,1]"


def _eligible_episode_rows(rows: Sequence[Mapping[str, str]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        gain = _safe_float(row.get("during_gain"))
        delay_ms = _safe_float(row.get("delay_ms"))
        coverage = _safe_float(row.get("online_support_coverage_fraction"))
        expired = _safe_float(row.get("fraction_rho_remaining_ge_1"))
        if row.get("eligible") != "1" or gain is None or delay_ms is None:
            continue
        parsed = dict(row)
        parsed["during_gain_value"] = float(gain)
        parsed["delay_s"] = float(delay_ms) / 1000.0
        parsed["online_support_coverage_value"] = coverage
        parsed["expired_fraction_value"] = expired
        mean_age = _safe_float(row.get("mean_latest_support_age_ms"))
        no_support = _safe_float(row.get("no_support_available_frame_fraction"))
        parsed["mean_latest_support_age_s"] = None if mean_age is None else mean_age / 1000.0
        parsed["no_support_available_value"] = no_support
        output.append(parsed)
    return output


def _cell_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        coverage = row.get("online_support_coverage_value")
        coverage_bucket = "missing" if coverage is None else _coverage_bucket(float(coverage))
        grouped[(str(row["delay_ms"]), str(row["rho_bucket"]), coverage_bucket)].append(row)

    output: list[dict[str, object]] = []
    for (delay_ms, rho_bucket, coverage_bucket), group in sorted(
        grouped.items(), key=lambda item: (float(item[0][0]), item[0][1], item[0][2])
    ):
        gains = [float(row["during_gain_value"]) for row in group]
        coverages = [
            float(row["online_support_coverage_value"])
            for row in group
            if row.get("online_support_coverage_value") is not None
        ]
        expired = [
            float(row["expired_fraction_value"])
            for row in group
            if row.get("expired_fraction_value") is not None
        ]
        ages = [
            float(row["mean_latest_support_age_s"]) * 1000.0
            for row in group
            if row.get("mean_latest_support_age_s") is not None
        ]
        output.append(
            {
                "delay_ms": delay_ms,
                "rho_bucket": rho_bucket,
                "coverage_bucket": coverage_bucket,
                "n_episodes": len(group),
                "mean_during_gain": f"{sum(gains) / len(gains):.6f}",
                "fraction_positive_gain": f"{sum(gain > 0 for gain in gains) / len(gains):.6f}",
                "mean_online_support_coverage_fraction": f"{sum(coverages) / len(coverages):.6f}" if coverages else "",
                "mean_fraction_rho_remaining_ge_1": f"{sum(expired) / len(expired):.6f}" if expired else "",
                "mean_latest_support_age_ms": f"{sum(ages) / len(ages):.3f}" if ages else "",
            }
        )
    return output


def _design_matrix(
    rows: Sequence[Mapping[str, object]],
    feature_names: Sequence[str],
    feature_fn: Callable[[Mapping[str, object]], Sequence[float | None]],
) -> tuple[np.ndarray, np.ndarray, list[Mapping[str, object]]]:
    selected_rows: list[Mapping[str, object]] = []
    x_rows: list[list[float]] = []
    y_values: list[float] = []
    for row in rows:
        features = list(feature_fn(row))
        if any(value is None or not math.isfinite(float(value)) for value in features):
            continue
        selected_rows.append(row)
        x_rows.append([1.0] + [float(value) for value in features])
        y_values.append(float(row["during_gain_value"]))
    if not x_rows:
        return np.empty((0, len(feature_names) + 1)), np.empty((0,)), []
    return np.asarray(x_rows, dtype=float), np.asarray(y_values, dtype=float), selected_rows


def _fit(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    return coef, x @ coef


def _metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    err = pred - y
    mae = float(np.mean(np.abs(err))) if len(y) else float("nan")
    rmse = float(np.sqrt(np.mean(err ** 2))) if len(y) else float("nan")
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
    r2 = 0.0 if ss_tot == 0.0 else 1.0 - ss_res / ss_tot
    return {"mae": mae, "rmse": rmse, "r2": r2}


def _group_cv(
    rows: Sequence[Mapping[str, object]],
    feature_names: Sequence[str],
    feature_fn: Callable[[Mapping[str, object]], Sequence[float | None]],
) -> dict[str, object]:
    groups: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[(str(row["delay_ms"]), str(row["rho_bucket"]))].append(row)
    errors: list[float] = []
    abs_errors: list[float] = []
    tested = 0
    for key, test_rows in groups.items():
        train_rows = [row for group_key, group in groups.items() if group_key != key for row in group]
        x_train, y_train, _ = _design_matrix(train_rows, feature_names, feature_fn)
        x_test, y_test, _ = _design_matrix(test_rows, feature_names, feature_fn)
        if len(y_train) <= len(feature_names) + 1 or len(y_test) == 0:
            continue
        coef, _ = _fit(x_train, y_train)
        pred = x_test @ coef
        errors.extend((pred - y_test).tolist())
        abs_errors.extend(np.abs(pred - y_test).tolist())
        tested += 1
    if not errors:
        return {"group_cv_rmse": "", "group_cv_mae": "", "n_tested_cells": tested}
    return {
        "group_cv_rmse": f"{float(np.sqrt(np.mean(np.asarray(errors) ** 2))):.6f}",
        "group_cv_mae": f"{float(np.mean(abs_errors)):.6f}",
        "n_tested_cells": tested,
    }


def _bootstrap_coefficients(
    x: np.ndarray,
    y: np.ndarray,
    names: Sequence[str],
    *,
    seed: int,
    iterations: int,
) -> dict[str, dict[str, float]]:
    if len(y) <= len(names) + 1:
        return {}
    rng = random.Random(int(seed))
    n = len(y)
    samples: dict[str, list[float]] = {name: [] for name in ("intercept", *names)}
    for _ in range(int(iterations)):
        indices = [rng.randrange(n) for _ in range(n)]
        coef, _ = _fit(x[indices, :], y[indices])
        for name, value in zip(samples, coef):
            samples[name].append(float(value))
    intervals: dict[str, dict[str, float]] = {}
    for name, values in samples.items():
        values.sort()
        lo = values[max(0, int(0.025 * (len(values) - 1)))]
        hi = values[min(len(values) - 1, int(0.975 * (len(values) - 1)))]
        intervals[name] = {"low": lo, "high": hi}
    return intervals


def _model_specs() -> list[tuple[str, tuple[str, ...], Callable[[Mapping[str, object]], Sequence[float | None]]]]:
    return [
        ("M1_delay_only", ("delay_s",), lambda row: (row["delay_s"],)),
        (
            "M2_coverage_only",
            ("online_support_coverage",),
            lambda row: (row.get("online_support_coverage_value"),),
        ),
        (
            "M3_delay_plus_coverage",
            ("delay_s", "online_support_coverage"),
            lambda row: (row["delay_s"], row.get("online_support_coverage_value")),
        ),
        (
            "M4_delay_coverage_interaction",
            ("delay_s", "online_support_coverage", "delay_x_coverage"),
            lambda row: (
                row["delay_s"],
                row.get("online_support_coverage_value"),
                None
                if row.get("online_support_coverage_value") is None
                else float(row["delay_s"]) * float(row["online_support_coverage_value"]),
            ),
        ),
        (
            "M5_delay_expired_interaction",
            ("delay_s", "fraction_rho_remaining_ge_1", "delay_x_expired"),
            lambda row: (
                row["delay_s"],
                row.get("expired_fraction_value"),
                None
                if row.get("expired_fraction_value") is None
                else float(row["delay_s"]) * float(row["expired_fraction_value"]),
            ),
        ),
        (
            "M6_delay_publish_freshness",
            ("delay_s", "mean_latest_support_age_s", "no_support_available_fraction"),
            lambda row: (
                row["delay_s"],
                row.get("mean_latest_support_age_s"),
                row.get("no_support_available_value"),
            ),
        ),
    ]


def _fit_models(
    rows: Sequence[Mapping[str, object]],
    *,
    seed: int,
    bootstrap_iterations: int,
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for model_index, (name, feature_names, feature_fn) in enumerate(_model_specs()):
        x, y, selected = _design_matrix(rows, feature_names, feature_fn)
        if len(y) == 0:
            output.append(
                {
                    "model": name,
                    "features": ",".join(feature_names),
                    "n_rows": 0,
                    "r2": "",
                    "rmse": "",
                    "mae": "",
                    "coefficients_json": "{}",
                    "coefficient_ci_json": "{}",
                    "group_cv_rmse": "",
                    "group_cv_mae": "",
                    "n_tested_cells": 0,
                }
            )
            continue
        coef, pred = _fit(x, y)
        metric = _metrics(y, pred)
        names = ("intercept", *feature_names)
        coefficients = {coef_name: float(value) for coef_name, value in zip(names, coef)}
        ci = _bootstrap_coefficients(
            x,
            y,
            feature_names,
            seed=seed + model_index * 1009,
            iterations=bootstrap_iterations,
        )
        cv = _group_cv(selected, feature_names, feature_fn)
        output.append(
            {
                "model": name,
                "features": ",".join(feature_names),
                "n_rows": len(y),
                "r2": f"{metric['r2']:.6f}",
                "rmse": f"{metric['rmse']:.6f}",
                "mae": f"{metric['mae']:.6f}",
                "coefficients_json": json.dumps(coefficients, sort_keys=True),
                "coefficient_ci_json": json.dumps(ci, sort_keys=True),
                **cv,
            }
        )
    return output


def _float_field(row: Mapping[str, object], key: str) -> float | None:
    value = row.get(key)
    if value in ("", None):
        return None
    return float(value)


def _decision_lines(
    rows: Sequence[Mapping[str, object]],
    cell_rows: Sequence[Mapping[str, object]],
    model_rows: Sequence[Mapping[str, object]],
) -> list[str]:
    delay_rho_groups: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        delay_rho_groups[(str(row["delay_ms"]), str(row["rho_bucket"]))] += 1
    eligible_delay_rho_cells = {
        key: count for key, count in delay_rho_groups.items() if count >= 5
    }
    eligible_delay_rho_coverage_cells = [
        row for row in cell_rows if int(row["n_episodes"]) >= 5
    ]
    covered_delays = {key[0] for key in eligible_delay_rho_cells}
    covered_rho = {key[1] for key in eligible_delay_rho_cells}
    covered_coverage = {row["coverage_bucket"] for row in eligible_delay_rho_coverage_cells}
    coverage_ready = (
        len(eligible_delay_rho_cells) >= 15
        and len(eligible_delay_rho_coverage_cells) >= 15
        and len(covered_delays) >= 4
        and len(covered_rho) >= 3
        and len(covered_coverage) >= 3
    )

    by_model = {row["model"]: row for row in model_rows}
    m1 = by_model.get("M1_delay_only", {})
    m4 = by_model.get("M4_delay_coverage_interaction", {})
    m1_rmse = _float_field(m1, "group_cv_rmse") or _float_field(m1, "rmse")
    m4_rmse = _float_field(m4, "group_cv_rmse") or _float_field(m4, "rmse")
    m1_r2 = _float_field(m1, "r2")
    m4_r2 = _float_field(m4, "r2")

    decision = "boundary_underdetermined"
    if coverage_ready and m1_rmse is not None and m4_rmse is not None and m1_r2 is not None and m4_r2 is not None:
        if m4_rmse <= 0.95 * m1_rmse and m4_r2 >= m1_r2 + 0.05:
            decision = "joint_temporal_boundary"
        elif m4_rmse >= 0.98 * m1_rmse:
            decision = "absolute_delay_boundary"
        else:
            decision = "boundary_inconclusive"

    return [
        "# Occlusion Temporal Boundary Decision",
        "",
        f"**Decision**: `{decision}`",
        "",
        "## Coverage Gate",
        "",
        f"- Eligible episode rows: {len(rows)}",
        f"- Delay-rho cells with n>=5: {len(eligible_delay_rho_cells)}",
        f"- Delay-rho-coverage cells with n>=5: {len(eligible_delay_rho_coverage_cells)}",
        f"- Covered delay levels: {len(covered_delays)}",
        f"- Covered rho buckets: {len(covered_rho)}",
        f"- Covered coverage buckets: {len(covered_coverage)}",
        "",
        "## Model Gate",
        "",
        f"- M1 delay-only RMSE: {'' if m1_rmse is None else f'{m1_rmse:.6f}'}",
        f"- M4 delay+coverage interaction RMSE: {'' if m4_rmse is None else f'{m4_rmse:.6f}'}",
        f"- M1 R2: {'' if m1_r2 is None else f'{m1_r2:.6f}'}",
        f"- M4 R2: {'' if m4_r2 is None else f'{m4_r2:.6f}'}",
        "",
        "## Interpretation",
        "",
        "- `absolute_delay_boundary`: absolute delay explains gain nearly as well as the joint model.",
        "- `joint_temporal_boundary`: coverage/availability adds measurable information beyond delay.",
        "- `boundary_underdetermined`: data coverage is still too sparse for a boundary claim.",
        "- `boundary_inconclusive`: coverage is sufficient but the compared model signals disagree.",
    ]


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    episode_path = input_dir / "counterfactual_episode_gain.csv"
    if not episode_path.is_file():
        raise FileNotFoundError(f"Missing counterfactual episode file: {episode_path}")
    rows = _eligible_episode_rows(_read_rows(episode_path))
    cell_rows = _cell_summary(rows)
    model_rows = _fit_models(
        rows,
        seed=args.seed,
        bootstrap_iterations=args.bootstrap_iterations,
    )

    _write_rows(output_dir / "temporal_boundary_cell_summary.csv", cell_rows)
    _write_rows(output_dir / "temporal_boundary_model_comparison.csv", model_rows)
    (output_dir / "temporal_boundary_decision.md").write_text(
        "\n".join(_decision_lines(rows, cell_rows, model_rows)),
        encoding="utf-8",
    )
    print(f"Wrote temporal boundary analysis to {output_dir}")


if __name__ == "__main__":
    main()
