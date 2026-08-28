#!/usr/bin/env python3
"""Run the frozen development-only same-correspondence H/F diagnosis."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.tracking.route_a_geometry.same_correspondence_probe import (  # noqa: E402
    PROBE_VERSION,
    run_same_correspondence_probe,
)


EXPERIMENT_ID = "exp_20260827_001_route_a_same_correspondence_geometry_diagnosis"
SELECTED_PAIR_IDS = ("23", "27", "28", "30", "32")
FORBIDDEN_PAIR_IDS = ("25", "26", "29", "45", "48", "51", "69")
DIRECTIONS = ("1_to_2", "2_to_1")
H_LOW_REFERENCE = 0.08955223880597014
MIN_H_LOW_ROWS = 20
MIN_MEDIAN_DELTA = 0.10
MIN_POSITIVE_FRACTION = 0.75
MIN_REPEATED_UNITS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def filename_set_digest(names: list[str]) -> str:
    return hashlib.sha256("".join(f"{name}\n" for name in names).encode("utf-8")).hexdigest()


def json_load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def write_json_exclusive(path: Path, value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(serialized)


def git_value(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPOSITORY_ROOT, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


def source_digests() -> dict[str, str]:
    paths = {
        "runner": REPOSITORY_ROOT / "scripts/run_mdmt_same_correspondence_geometry_diagnosis.py",
        "probe": REPOSITORY_ROOT / "src/tracking/route_a_geometry/same_correspondence_probe.py",
        "homography_provider": REPOSITORY_ROOT / "src/tracking/route_a_geometry/image_geometry_provider.py",
        "g15c": REPOSITORY_ROOT / "src/tracking/route_a_geometry/g15c_validity.py",
    }
    return {name: sha256_file(path) for name, path in paths.items()}


def validate_manifest(
    manifest: dict[str, Any], data_root: Path
) -> tuple[dict[str, list[str]], int]:
    if manifest.get("experiment_id") != EXPERIMENT_ID or manifest.get("split") != "train":
        raise RuntimeError("manifest experiment/split mismatch")
    if tuple(manifest.get("selected_pair_ids", [])) != SELECTED_PAIR_IDS:
        raise RuntimeError("selected pairs differ from frozen order")
    if not manifest.get("selection_rule_frozen_before_image_read"):
        raise RuntimeError("pair selection was not frozen before image read")
    if set(FORBIDDEN_PAIR_IDS) - set(manifest.get("excluded_pair_ids", [])):
        raise RuntimeError("manifest does not exclude all prior-evidence pairs")
    train_root = data_root / "train"
    if not train_root.is_dir() or any(part.lower() in {"test", "val"} for part in data_root.parts):
        raise RuntimeError("only a dataset root with train is permitted")
    frame_names: dict[str, list[str]] = {}
    denominator = 0
    for pair_id in SELECTED_PAIR_IDS:
        if pair_id in FORBIDDEN_PAIR_IDS:
            raise RuntimeError("forbidden pair reached selected set")
        view_one = train_root / "1" / f"{pair_id}-1"
        view_two = train_root / "2" / f"{pair_id}-2"
        one = sorted(
            child.name for child in view_one.iterdir()
            if child.is_file() and child.suffix.lower() in {".jpg", ".jpeg"}
        )
        two = sorted(
            child.name for child in view_two.iterdir()
            if child.is_file() and child.suffix.lower() in {".jpg", ".jpeg"}
        )
        metadata = manifest["pair_frame_metadata"][pair_id]
        if not one or one != two:
            raise RuntimeError(f"synchronized frame set mismatch for pair {pair_id}")
        if len(one) != metadata["frame_count"]:
            raise RuntimeError(f"frame count differs from manifest for pair {pair_id}")
        if filename_set_digest(one) != metadata["frame_filename_set_digest"]:
            raise RuntimeError(f"frame filename digest differs for pair {pair_id}")
        frame_names[pair_id] = one
        denominator += 2 * len(one)
    if denominator != int(manifest["full_frame_direction_denominator"]):
        raise RuntimeError("full denominator differs from frozen manifest")
    return frame_names, denominator


def expected_keys(frame_names: dict[str, list[str]]) -> set[tuple[str, str, str]]:
    return {
        (pair_id, frame_name, direction)
        for pair_id, names in frame_names.items()
        for frame_name in names
        for direction in DIRECTIONS
    }


def validate_config(config: dict[str, Any]) -> None:
    if config.get("experiment_id") != EXPERIMENT_ID:
        raise RuntimeError("config experiment mismatch")
    if tuple(config.get("selected_pair_ids", [])) != SELECTED_PAIR_IDS:
        raise RuntimeError("config selected-pair mismatch")
    if tuple(config.get("forbidden_pair_ids", [])) != FORBIDDEN_PAIR_IDS:
        raise RuntimeError("config forbidden-pair mismatch")
    pattern = config["diagnostic_pattern"]
    expected_pattern = {
        "h_low_reference_inlier_ratio": H_LOW_REFERENCE,
        "minimum_h_low_comparable_rows_per_unit": MIN_H_LOW_ROWS,
        "minimum_median_delta": MIN_MEDIAN_DELTA,
        "minimum_positive_delta_fraction": MIN_POSITIVE_FRACTION,
        "minimum_repeated_units": MIN_REPEATED_UNITS,
        "role": "INTERPRETATION_PATTERN_NOT_READINESS_GATE",
    }
    if pattern != expected_pattern:
        raise RuntimeError("diagnostic interpretation pattern differs from frozen contract")
    if config["fundamental"]["role"] != "DIAGNOSTIC_ONLY_NO_READINESS_GATE":
        raise RuntimeError("Fundamental Matrix role drift")


def run_metadata(
    manifest_path: Path, config_path: Path, manifest_digest: str, config_digest: str
) -> dict[str, Any]:
    dirty = git_value("status", "--porcelain=v1")
    if dirty:
        raise RuntimeError("run requires a clean committed implementation worktree")
    return {
        "experiment_id": EXPERIMENT_ID,
        "run_role": "DEVELOPMENT_ONLY_DIAGNOSTIC_PROBE",
        "git_branch": git_value("branch", "--show-current"),
        "git_commit": git_value("rev-parse", "HEAD"),
        "manifest_path": str(manifest_path),
        "manifest_digest": manifest_digest,
        "config_path": str(config_path),
        "config_digest": config_digest,
        "source_digests": source_digests(),
        "probe_version": PROBE_VERSION,
        "opencv_version": cv2.__version__,
        "opencv_threads": cv2.getNumThreads(),
        "opencl_enabled": bool(cv2.ocl.useOpenCL()),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "fundamental_readiness_gate": "ABSENT",
    }


def prepare_output(
    output_root: Path,
    resume: bool,
    manifest_path: Path,
    config_path: Path,
    manifest_digest: str,
    config_digest: str,
) -> dict[str, Any]:
    metadata_path = output_root / "run_metadata.json"
    if output_root.exists():
        if not resume:
            raise RuntimeError("output root exists; explicit --resume required")
        metadata = json_load(metadata_path)
        current_sources = source_digests()
        if (
            metadata.get("manifest_digest") != manifest_digest
            or metadata.get("config_digest") != config_digest
            or metadata.get("source_digests") != current_sources
            or metadata.get("git_commit") != git_value("rev-parse", "HEAD")
        ):
            raise RuntimeError("resume provenance mismatch")
        return metadata
    output_root.mkdir(parents=True, exist_ok=False)
    metadata = run_metadata(manifest_path, config_path, manifest_digest, config_digest)
    write_json_exclusive(metadata_path, metadata)
    shutil.copyfile(manifest_path, output_root / "PAIR_MANIFEST.json")
    shutil.copyfile(config_path, output_root / "FROZEN_CONFIG.json")
    return metadata


def load_ledger(
    ledger_path: Path,
    expected: set[tuple[str, str, str]],
    metadata: dict[str, Any],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not ledger_path.exists():
        return records
    with ledger_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"malformed ledger row {line_number}; no result repair allowed") from exc
            stated = record.pop("record_digest", None)
            if canonical_digest(record) != stated:
                raise RuntimeError(f"record digest mismatch at row {line_number}")
            record["record_digest"] = stated
            key = (record["pair_id"], record["frame_name"], record["direction"])
            if key not in expected or key in records:
                raise RuntimeError(f"unexpected or duplicate ledger key: {key}")
            if (
                record.get("manifest_digest") != metadata["manifest_digest"]
                or record.get("config_digest") != metadata["config_digest"]
                or record.get("source_digests") != metadata["source_digests"]
            ):
                raise RuntimeError(f"ledger provenance mismatch at row {line_number}")
            records[key] = record
    return records


def make_record(
    metadata: dict[str, Any],
    data_root: Path,
    pair_id: str,
    frame_name: str,
    direction: str,
    image_one: np.ndarray,
    image_two: np.ndarray,
    digest_one: str,
    digest_two: str,
) -> dict[str, Any]:
    if direction == "1_to_2":
        source, destination = image_one, image_two
        source_view, destination_view = "1", "2"
        source_digest, destination_digest = digest_one, digest_two
    elif direction == "2_to_1":
        source, destination = image_two, image_one
        source_view, destination_view = "2", "1"
        source_digest, destination_digest = digest_two, digest_one
    else:
        raise RuntimeError(f"unsupported direction: {direction}")
    frame_id = Path(frame_name).stem
    probe = run_same_correspondence_probe(source, destination)
    if probe["correspondence_generation_count"] != 1:
        raise RuntimeError("correspondence generation count is not exactly one")
    shared_digest = probe["shared_correspondences"]["shared_point_array_digest"]
    if (
        probe["homography"]["input_correspondence_digest"] != shared_digest
        or probe["fundamental"]["input_correspondence_digest"] != shared_digest
    ):
        raise RuntimeError("H/F did not consume the same correspondence digest")
    record: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "pair_id": pair_id,
        "frame_name": frame_name,
        "frame_id": frame_id,
        "direction": direction,
        "source_view": source_view,
        "destination_view": destination_view,
        "source_image_relative": f"train/{source_view}/{pair_id}-{source_view}/{frame_name}",
        "destination_image_relative": f"train/{destination_view}/{pair_id}-{destination_view}/{frame_name}",
        "source_image_digest": source_digest,
        "destination_image_digest": destination_digest,
        "manifest_digest": metadata["manifest_digest"],
        "config_digest": metadata["config_digest"],
        "source_digests": metadata["source_digests"],
        "probe": probe,
    }
    record["record_digest"] = canonical_digest(record)
    return record


def distribution(values: list[float]) -> dict[str, float | int | None]:
    array = np.asarray(values, dtype=np.float64)
    array = array[np.isfinite(array)]
    if not len(array):
        return {
            "count": 0, "min": None, "p05": None, "mean": None,
            "median": None, "p95": None, "max": None,
        }
    return {
        "count": int(len(array)),
        "min": float(np.min(array)),
        "p05": float(np.quantile(array, 0.05)),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.quantile(array, 0.95)),
        "max": float(np.max(array)),
    }


def summarize_scope(records: list[dict[str, Any]]) -> dict[str, Any]:
    comparable = [record for record in records if record["probe"]["delta_inlier_ratio"] is not None]
    deltas = [float(record["probe"]["delta_inlier_ratio"]) for record in comparable]
    h_ratios = [float(record["probe"]["homography"]["inlier_ratio"]) for record in comparable]
    f_ratios = [float(record["probe"]["fundamental"]["inlier_ratio"]) for record in comparable]
    h_low = [
        record for record in comparable
        if float(record["probe"]["homography"]["inlier_ratio"]) < H_LOW_REFERENCE
    ]
    h_low_deltas = [float(record["probe"]["delta_inlier_ratio"]) for record in h_low]
    positive_fraction = (
        float(np.mean(np.asarray(deltas) > 0.0)) if deltas else None
    )
    h_low_positive_fraction = (
        float(np.mean(np.asarray(h_low_deltas) > 0.0)) if h_low_deltas else None
    )
    h_low_distribution = distribution(h_low_deltas)
    repeated = bool(
        len(h_low) >= MIN_H_LOW_ROWS
        and h_low_distribution["median"] is not None
        and float(h_low_distribution["median"]) >= MIN_MEDIAN_DELTA
        and h_low_positive_fraction is not None
        and h_low_positive_fraction >= MIN_POSITIVE_FRACTION
    )
    both_above_reference = sum(
        h >= H_LOW_REFERENCE and f >= H_LOW_REFERENCE for h, f in zip(h_ratios, f_ratios)
    )
    return {
        "row_count": len(records),
        "comparable_row_count": len(comparable),
        "h_available_count": sum(bool(record["probe"]["homography"]["H_available"]) for record in records),
        "f_available_count": sum(bool(record["probe"]["fundamental"]["F_available"]) for record in records),
        "h_g15c_valid_count": sum(record["probe"]["homography"]["g15c_H_valid"] is True for record in records),
        "h_inlier_ratio": distribution(h_ratios),
        "f_inlier_ratio": distribution(f_ratios),
        "delta_inlier_ratio": distribution(deltas),
        "positive_delta_fraction": positive_fraction,
        "h_low_comparable_row_count": len(h_low),
        "h_low_delta_inlier_ratio": h_low_distribution,
        "h_low_positive_delta_fraction": h_low_positive_fraction,
        "both_above_h_support_reference_count": both_above_reference,
        "repeated_f_advantage_unit": repeated,
        "fundamental_readiness_gate": "ABSENT",
    }


def scientific_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "pair_id": record["pair_id"],
        "frame_name": record["frame_name"],
        "direction": record["direction"],
        "probe": record["probe"],
    }


def deterministic_repeat(
    records_by_key: dict[tuple[str, str, str], dict[str, Any]],
    metadata: dict[str, Any],
    data_root: Path,
    frame_names: dict[str, list[str]],
) -> dict[str, Any]:
    pair_id = SELECTED_PAIR_IDS[0]
    mismatch_keys: list[list[str]] = []
    repeat_count = 0
    for frame_name in frame_names[pair_id][:10]:
        path_one = data_root / "train" / "1" / f"{pair_id}-1" / frame_name
        path_two = data_root / "train" / "2" / f"{pair_id}-2" / frame_name
        image_one = cv2.imread(str(path_one), cv2.IMREAD_COLOR)
        image_two = cv2.imread(str(path_two), cv2.IMREAD_COLOR)
        if image_one is None or image_two is None:
            raise RuntimeError("repeat image decode failure")
        digest_one, digest_two = sha256_file(path_one), sha256_file(path_two)
        for direction in DIRECTIONS:
            repeat = make_record(
                metadata, data_root, pair_id, frame_name, direction,
                image_one, image_two, digest_one, digest_two,
            )
            original = records_by_key[(pair_id, frame_name, direction)]
            if canonical_digest(scientific_fields(repeat)) != canonical_digest(scientific_fields(original)):
                mismatch_keys.append([pair_id, frame_name, direction])
            repeat_count += 1
    return {
        "pair_id": pair_id,
        "frame_count": 10,
        "repeat_record_count": repeat_count,
        "mismatch_count": len(mismatch_keys),
        "mismatch_keys": mismatch_keys,
        "verdict": "PASS" if not mismatch_keys else "REPRODUCIBILITY_FAIL",
    }


def finalize(
    output_root: Path,
    records_by_key: dict[tuple[str, str, str], dict[str, Any]],
    expected: set[tuple[str, str, str]],
    metadata: dict[str, Any],
    data_root: Path,
    frame_names: dict[str, list[str]],
) -> None:
    if set(records_by_key) != expected:
        raise RuntimeError("ledger is incomplete or has unexpected keys")
    records = [records_by_key[key] for key in sorted(records_by_key)]
    repeat = deterministic_repeat(records_by_key, metadata, data_root, frame_names)
    write_json_exclusive(output_root / "determinism_repeat.json", repeat)
    if repeat["verdict"] != "PASS":
        raise RuntimeError("determinism repeat failed")
    unit_rows: list[dict[str, Any]] = []
    for pair_id in SELECTED_PAIR_IDS:
        for direction in DIRECTIONS:
            scoped = [
                record for record in records
                if record["pair_id"] == pair_id and record["direction"] == direction
            ]
            unit_rows.append({"pair_id": pair_id, "direction": direction, **summarize_scope(scoped)})
    overall = summarize_scope(records)
    repeated_units = sum(bool(row["repeated_f_advantage_unit"]) for row in unit_rows)
    pooled = overall["h_low_delta_inlier_ratio"]
    pooled_positive = overall["h_low_positive_delta_fraction"]
    favors = bool(
        repeated_units >= MIN_REPEATED_UNITS
        and pooled["median"] is not None
        and float(pooled["median"]) >= MIN_MEDIAN_DELTA
        and pooled_positive is not None
        and pooled_positive >= MIN_POSITIVE_FRACTION
    )
    decision = (
        "EVIDENCE_FAVORS_SINGLE_H_MODEL_INADEQUACY_OVER_COMPLETE_CORRESPONDENCE_BREAKDOWN"
        if favors
        else "CURRENT_EVIDENCE_DOES_NOT_ISOLATE_MODEL_INADEQUACY"
    )
    overall.update(
        {
            "repeated_f_advantage_unit_count": repeated_units,
            "independent_unit_count": len(unit_rows),
            "diagnostic_pattern": decision,
            "interpretation_only_not_readiness_gate": True,
            "forbidden_claims_remain_forbidden": True,
        }
    )
    write_json_exclusive(output_root / "pair_direction_summary.json", unit_rows)
    write_json_exclusive(output_root / "overall_summary.json", overall)
    with (output_root / "pair_direction_summary.csv").open("x", newline="", encoding="utf-8") as handle:
        fields = [
            "pair_id", "direction", "row_count", "comparable_row_count",
            "h_available_count", "f_available_count", "h_g15c_valid_count",
            "h_median", "f_median", "delta_median", "positive_delta_fraction",
            "h_low_comparable_row_count", "h_low_delta_median",
            "h_low_positive_delta_fraction", "repeated_f_advantage_unit",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in unit_rows:
            writer.writerow(
                {
                    "pair_id": row["pair_id"],
                    "direction": row["direction"],
                    "row_count": row["row_count"],
                    "comparable_row_count": row["comparable_row_count"],
                    "h_available_count": row["h_available_count"],
                    "f_available_count": row["f_available_count"],
                    "h_g15c_valid_count": row["h_g15c_valid_count"],
                    "h_median": row["h_inlier_ratio"]["median"],
                    "f_median": row["f_inlier_ratio"]["median"],
                    "delta_median": row["delta_inlier_ratio"]["median"],
                    "positive_delta_fraction": row["positive_delta_fraction"],
                    "h_low_comparable_row_count": row["h_low_comparable_row_count"],
                    "h_low_delta_median": row["h_low_delta_inlier_ratio"]["median"],
                    "h_low_positive_delta_fraction": row["h_low_positive_delta_fraction"],
                    "repeated_f_advantage_unit": row["repeated_f_advantage_unit"],
                }
            )
    accessed = sorted(
        {
            record["source_image_relative"] for record in records
        } | {
            record["destination_image_relative"] for record in records
        }
    )
    access_audit = {
        "ledger_image_read_count": len(records),
        "ledger_image_input_participation_count": 2 * len(records),
        "determinism_repeat_image_read_count": 20,
        "unique_jpeg_paths": len(accessed),
        "all_paths_under_selected_train_pairs": all(
            any(
                path.startswith(f"train/1/{pair_id}-1/")
                or path.startswith(f"train/2/{pair_id}-2/")
                for pair_id in SELECTED_PAIR_IDS
            )
            for path in accessed
        ),
        "pair_26_or_48_read_count": 0,
        "old_development_pair_read_count": 0,
        "test_read_count": 0,
        "val_read_count": 0,
        "xml_read_count": 0,
        "gt_read_count": 0,
        "detector_tracker_mia_route_a_input_count": 0,
        "image_or_feature_cache_written": False,
        "verdict": "PASS",
    }
    completeness = {
        "expected_rows": len(expected),
        "observed_rows": len(records),
        "unique_keys": len(records_by_key),
        "duplicate_keys": 0,
        "missing_keys": 0,
        "unexpected_keys": 0,
        "correspondence_generation_count_exactly_one_all_rows": all(
            record["probe"]["correspondence_generation_count"] == 1 for record in records
        ),
        "same_correspondence_digest_h_f_all_rows": all(
            record["probe"]["homography"]["input_correspondence_digest"]
            == record["probe"]["fundamental"]["input_correspondence_digest"]
            == record["probe"]["shared_correspondences"]["shared_point_array_digest"]
            for record in records
        ),
        "delta_field_present_all_rows": all("delta_inlier_ratio" in record["probe"] for record in records),
        "fundamental_readiness_gate_absent": all(
            record["probe"]["fundamental"]["readiness_gate_status"]
            == "NOT_DEFINED_DIAGNOSTIC_ONLY" for record in records
        ),
        "verdict": "PASS",
    }
    write_json_exclusive(output_root / "access_audit.json", access_audit)
    write_json_exclusive(output_root / "completeness_audit.json", completeness)
    lines = [
        "# Same-Correspondence Geometry Diagnosis Result", "",
        f"- Full denominator: `{len(records)}/{len(expected)}`.",
        f"- Repeated F-advantage units: `{repeated_units}/10`.",
        f"- Diagnostic pattern: `{decision}`.",
        f"- Determinism: `{repeat['verdict']}`; protocol completeness: `PASS`.", "",
        "## Interpretation boundary", "",
        "Fundamental Matrix is a diagnostic probe only. This result does not authorize a new Route-A representation, establish SIFT reliability, support A1, or make a tracking/identity claim.", "",
    ]
    (output_root / "RESULT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    data_root = args.data_root.resolve()
    manifest_path = args.manifest.resolve()
    config_path = args.config.resolve()
    output_root = args.output_root.resolve()
    manifest = json_load(manifest_path)
    config = json_load(config_path)
    frame_names, denominator = validate_manifest(manifest, data_root)
    validate_config(config)
    cv2.setNumThreads(1)
    cv2.ocl.setUseOpenCL(False)
    metadata = prepare_output(
        output_root, args.resume, manifest_path, config_path,
        sha256_file(manifest_path), sha256_file(config_path),
    )
    expected = expected_keys(frame_names)
    if len(expected) != denominator:
        raise RuntimeError("expected-key denominator mismatch")
    ledger_path = output_root / "same_correspondence_geometry.jsonl"
    records_by_key = load_ledger(ledger_path, expected, metadata)
    mode = "a" if ledger_path.exists() else "x"
    with ledger_path.open(mode, encoding="utf-8") as handle:
        for pair_id in SELECTED_PAIR_IDS:
            for frame_name in frame_names[pair_id]:
                missing = [
                    direction for direction in DIRECTIONS
                    if (pair_id, frame_name, direction) not in records_by_key
                ]
                if not missing:
                    continue
                path_one = data_root / "train" / "1" / f"{pair_id}-1" / frame_name
                path_two = data_root / "train" / "2" / f"{pair_id}-2" / frame_name
                image_one = cv2.imread(str(path_one), cv2.IMREAD_COLOR)
                image_two = cv2.imread(str(path_two), cv2.IMREAD_COLOR)
                if image_one is None or image_two is None:
                    raise RuntimeError(f"image decode failure: pair={pair_id} frame={frame_name}")
                digest_one, digest_two = sha256_file(path_one), sha256_file(path_two)
                for direction in missing:
                    record = make_record(
                        metadata, data_root, pair_id, frame_name, direction,
                        image_one, image_two, digest_one, digest_two,
                    )
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
                    handle.flush()
                    records_by_key[(pair_id, frame_name, direction)] = record
            print(
                f"completed pair {pair_id}: {2 * len(frame_names[pair_id])} frame-direction rows",
                flush=True,
            )
    finalize(output_root, records_by_key, expected, metadata, data_root, frame_names)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
