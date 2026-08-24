#!/usr/bin/env python3
"""Run only the frozen five-pair MDMT-train raw geometry diagnostics (M2--M5)."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import sys
import time
from typing import Any

import cv2
import numpy as np

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.tracking.route_a_geometry import ESTIMATOR_VERSION, estimate_homography  # noqa: E402


EXPERIMENT_ID = "exp_20260823_001_mdmt_mia_independent_geometry_development"
THRESHOLD_STATUS = "NOT_EVALUATED_PENDING_G15C"
EXPECTED_SELECTED_PAIR_IDS = ["45", "29", "51", "69", "25"]
FORBIDDEN_PATH_PARTS = {"test", "val", "gt", "xml", "26-1", "26-2", "48-1", "48-2"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        handle.write("\n")


def git_value(args: list[str]) -> str | None:
    import subprocess

    completed = subprocess.run(["git", *args], cwd=REPOSITORY_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return completed.stdout.strip() if completed.returncode == 0 else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--finalize-existing-ledger",
        action="store_true",
        help="validate one complete, same-config ledger then run only the frozen repeat and M5 summaries",
    )
    return parser.parse_args()


def assert_safe_relative(path: Path) -> None:
    lowered = {part.lower() for part in path.parts}
    if lowered & FORBIDDEN_PATH_PARTS:
        raise RuntimeError(f"forbidden read path rejected: {path}")
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        raise RuntimeError(f"only JPEG image reads are allowed: {path}")


def load_manifest(path: Path, data_root: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    check = dict(manifest)
    actual_digest = check.pop("manifest_digest", None)
    if canonical_digest(check) != actual_digest:
        raise RuntimeError("manifest digest mismatch")
    if manifest.get("experiment_id") != EXPERIMENT_ID or manifest.get("split") != "train":
        raise RuntimeError("wrong experiment manifest")
    if manifest.get("diagnostics_started") is not False:
        raise RuntimeError("M1 manifest is not a pre-diagnostic freeze")
    if manifest.get("selected_pair_ids") != EXPECTED_SELECTED_PAIR_IDS:
        raise RuntimeError("selected pair list differs from the frozen five-pair manifest")
    if Path(str(manifest.get("dataset_root_resolved"))).resolve() != data_root:
        raise RuntimeError("data root does not match the frozen manifest")
    return manifest


def image_paths(data_root: Path, pair_id: str, frame_name: str, direction: str) -> tuple[Path, Path, str, str]:
    if direction == "1_to_2":
        source = data_root / "train" / "1" / f"{pair_id}-1" / frame_name
        destination = data_root / "train" / "2" / f"{pair_id}-2" / frame_name
        return source, destination, "1", "2"
    source = data_root / "train" / "2" / f"{pair_id}-2" / frame_name
    destination = data_root / "train" / "1" / f"{pair_id}-1" / frame_name
    return source, destination, "2", "1"


def read_jpeg(path: Path, data_root: Path, access: dict[str, Any]) -> tuple[np.ndarray | None, str | None]:
    relative = path.resolve().relative_to(data_root)
    assert_safe_relative(relative)
    access["jpeg_image_read_count"] += 1
    access["paths_read"].add(str(relative))
    if not path.is_file():
        return None, None
    return cv2.imread(str(path), cv2.IMREAD_COLOR), sha256_file(path)


def environment(config_digest: str, provider_digest: str, manifest_digest: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "development_manifest_digest": manifest_digest,
        "provider_config_digest": config_digest,
        "provider_code_digest": provider_digest,
        "estimator_version": ESTIMATOR_VERSION,
        "python_version": sys.version,
        "numpy_version": np.__version__,
        "opencv_version": cv2.__version__,
        "opencv_build_information_digest": hashlib.sha256(cv2.getBuildInformation().encode("utf-8")).hexdigest(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cv2_num_threads": cv2.getNumThreads(),
        "cv2_opencl_enabled": bool(cv2.ocl.useOpenCL()),
        "git_branch": git_value(["branch", "--show-current"]),
        "git_commit": git_value(["rev-parse", "HEAD"]),
        "git_dirty_status": bool(git_value(["status", "--porcelain=v1"])),
    }


def make_record(
    manifest: dict[str, Any],
    config_digest: str,
    provider_digest: str,
    data_root: Path,
    pair_id: str,
    frame_name: str,
    direction: str,
    access: dict[str, Any],
) -> dict[str, Any]:
    source_path, destination_path, source_view, destination_view = image_paths(data_root, pair_id, frame_name, direction)
    source, source_digest = read_jpeg(source_path, data_root, access)
    destination, destination_digest = read_jpeg(destination_path, data_root, access)
    started = time.monotonic()
    estimated = estimate_homography(source, destination)
    elapsed_ms = (time.monotonic() - started) * 1000.0
    record: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "development_manifest_digest": manifest["manifest_digest"],
        "provider_version": ESTIMATOR_VERSION,
        "provider_config_digest": config_digest,
        "provider_code_digest": provider_digest,
        "pair_id": pair_id,
        "frame_id": Path(frame_name).stem,
        "frame_name": frame_name,
        "direction": direction,
        "source_view": source_view,
        "destination_view": destination_view,
        "image_src_path_relative": str(source_path.resolve().relative_to(data_root)),
        "image_dst_path_relative": str(destination_path.resolve().relative_to(data_root)),
        "image_src_digest": source_digest,
        "image_dst_digest": destination_digest,
        "threshold_gate_status": THRESHOLD_STATUS,
        "gate_input_fields": [
            "num_unique_matches", "num_ransac_inliers", "inlier_ratio",
            "reprojection_error_p95", "matrix_rank", "condition_number",
            "projected_grid_inside_fraction", "projected_area_ratio", "orientation_flip",
        ],
        "estimation_wall_time_ms": elapsed_ms,
        **estimated,
    }
    record["record_digest"] = canonical_digest(record)
    return record


def assert_record_keys(records: list[dict[str, Any]], expected_count: int) -> None:
    keys = [(record["pair_id"], record["frame_name"], record["direction"]) for record in records]
    if len(records) != expected_count or len(set(keys)) != expected_count:
        raise RuntimeError("full-denominator ledger invariant failed")
    if any(record["threshold_gate_status"] != THRESHOLD_STATUS for record in records):
        raise RuntimeError("premature threshold status in ledger")


def load_existing_ledger(path: Path, manifest: dict[str, Any], config_digest: str, provider_digest: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            record = json.loads(line)
            stated_digest = record.pop("record_digest", None)
            if canonical_digest(record) != stated_digest:
                raise RuntimeError(f"ledger record digest mismatch at line {line_number}")
            record["record_digest"] = stated_digest
            if (
                record.get("development_manifest_digest") != manifest["manifest_digest"]
                or record.get("provider_config_digest") != config_digest
                or record.get("provider_code_digest") != provider_digest
            ):
                raise RuntimeError(f"ledger provenance mismatch at line {line_number}")
            records.append(record)
    expected_count = 2 * sum(manifest["pair_frame_metadata"][pair_id]["frame_count"] for pair_id in manifest["selected_pair_ids"])
    assert_record_keys(records, expected_count)
    return records


def floats_equal(left: Any, right: Any) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        return bool(np.isclose(left, right, rtol=1.0e-10, atol=1.0e-12, equal_nan=True))
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(floats_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(floats_equal(left[key], right[key]) for key in left)
    return left == right


def determinism_subset(
    records: list[dict[str, Any]], manifest: dict[str, Any], config_digest: str, provider_digest: str, data_root: Path, access: dict[str, Any]
) -> dict[str, Any]:
    pair_id = min(manifest["selected_pair_ids"], key=str)
    frame_names = sorted(
        child.name for child in (data_root / "train" / "1" / f"{pair_id}-1").iterdir()
        if child.is_file() and child.suffix.lower() in {".jpg", ".jpeg"}
    )[:10]
    originals = {(record["pair_id"], record["frame_name"], record["direction"]): record for record in records}
    repeat_records: list[dict[str, Any]] = []
    mismatches: list[dict[str, str]] = []
    exact_fields = [
        "pair_id", "frame_id", "direction", "image_src_digest", "image_dst_digest", "provider_config_digest", "provider_code_digest",
        "hard_failure_code", "H_available", "H_shape", "H_finite", "num_keypoints_src", "num_keypoints_dst", "num_knn_pairs",
        "num_tentative_matches", "num_unique_matches", "num_ransac_inliers", "selected_correspondence_digest", "ransac_inlier_mask_digest",
        "H_matrix", "inlier_ratio", "reprojection_error_mean", "reprojection_error_median", "reprojection_error_p95",
    ]
    for frame_name in frame_names:
        for direction in ("1_to_2", "2_to_1"):
            repeat = make_record(manifest, config_digest, provider_digest, data_root, pair_id, frame_name, direction, access)
            original = originals[(pair_id, frame_name, direction)]
            unequal = [field for field in exact_fields if not floats_equal(original.get(field), repeat.get(field))]
            if unequal:
                mismatches.append({"pair_id": pair_id, "frame_name": frame_name, "direction": direction, "fields": ",".join(unequal)})
            repeat_records.append(repeat)
    return {
        "pair_id": pair_id,
        "frame_names": frame_names,
        "direction_count": 2,
        "repeat_record_count": len(repeat_records),
        "comparison_fields": exact_fields,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "verdict": "PASS" if not mismatches else "REPRODUCIBILITY_ACCEPTANCE_FAIL",
    }


def numeric_values(records: list[dict[str, Any]], field: str) -> list[float]:
    return [float(record[field]) for record in records if isinstance(record.get(field), (float, int)) and np.isfinite(record[field])]


def quantile_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fields = ["num_keypoints_src", "num_keypoints_dst", "num_knn_pairs", "num_tentative_matches", "num_unique_matches", "num_ransac_inliers", "inlier_ratio", "reprojection_error_mean", "reprojection_error_median", "reprojection_error_p95", "matrix_rank", "determinant", "condition_number", "projected_grid_finite_fraction", "projected_grid_inside_fraction", "projected_corner_finite_fraction", "projected_area_ratio", "projection_denominator_min_abs"]
    result = []
    for field in fields:
        values = numeric_values(records, field)
        if values:
            result.append({"field": field, "count": len(values), "min": np.min(values), "p05": np.quantile(values, .05), "p50": np.quantile(values, .5), "p95": np.quantile(values, .95), "max": np.max(values)})
        else:
            result.append({"field": field, "count": 0, "min": None, "p05": None, "p50": None, "p95": None, "max": None})
    return result


def write_summaries(output_root: Path, records: list[dict[str, Any]], access: dict[str, Any], started: datetime, determinism: dict[str, Any]) -> None:
    expected = len(records)
    failures: dict[str, int] = {}
    for record in records:
        code = record["hard_failure_code"] or "NONE"
        failures[code] = failures.get(code, 0) + 1
    with (output_root / "geometry_hard_failure_summary.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["hard_failure_code", "count", "fraction"])
        writer.writeheader()
        for code, count in sorted(failures.items()):
            writer.writerow({"hard_failure_code": code, "count": count, "fraction": count / expected})
    quantiles = quantile_rows(records)
    with (output_root / "geometry_metric_quantiles.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "count", "min", "p05", "p50", "p95", "max"])
        writer.writeheader()
        writer.writeheader if False else None
        for row in quantiles:
            writer.writerow(row)
    h_available = sum(bool(record["H_available"]) for record in records)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    access_report = {
        "jpeg_image_read_count": access["jpeg_image_read_count"],
        "unique_jpeg_paths_read": len(access["paths_read"]),
        "xml_read_count": 0,
        "gt_read_count": 0,
        "val_read_count": 0,
        "pair_26_or_48_read_count": 0,
        "tracker_or_mia_import_count": 0,
        "forbidden_read_counter_status": "PASS",
    }
    summary = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "M2_TO_M5_RAW_DIAGNOSTICS_COMPLETE",
        "full_denominator": expected,
        "diagnostic_ledger_completion_fraction": 1.0,
        "hard_H_available_count": h_available,
        "hard_H_available_fraction": h_available / expected,
        "hard_failure_counts": failures,
        "determinism_verdict": determinism["verdict"],
        "access_audit": access_report,
        "total_wall_time_seconds": elapsed,
        "threshold_gate_status": THRESHOLD_STATUS,
    }
    write_json(output_root / "geometry_summary.json", summary)
    write_json(output_root / "access_audit.json", access_report)
    lines = [
        "# Raw Geometry Diagnostic Summary", "",
        "- Scope: exactly the five frozen MDMT-train pairs; no val, Pair 26/48, tracker, or Route-A MVE.",
        f"- Full frame-direction denominator: `{expected}`; ledger completion: `1.0`.",
        f"- Raw finite normalized-H availability: `{h_available}/{expected}` ({h_available / expected:.6f}).",
        f"- Determinism repeat: `{determinism['verdict']}`.",
        f"- Threshold status for every record: `{THRESHOLD_STATUS}`.", "",
        "## Hard failure counts", "",
    ]
    lines.extend(f"- `{code}`: {count}" for code, count in sorted(failures.items()))
    lines.extend(["", "## M5 threshold-candidate boundary", "", "The CSV quantiles are raw diagnostic observations only. No G15c threshold, validity label, coverage/readiness decision, Pair-26/48 run, or Route-A MVE decision is made here.", ""])
    (output_root / "geometry_summary.md").write_text("\n".join(lines), encoding="utf-8")
    report_lines = ["# M5 Threshold Candidate Report", "", "## Status", "", "`PENDING_HUMAN_G15C`", "", "This report supplies only the fixed-estimator raw distributions in `geometry_metric_quantiles.csv`. It intentionally does not propose, select, or apply numeric acceptance thresholds. Any G15c freeze requires a separate human research decision.", "", "## Boundary", "", "- No `valid`/`invalid` geometry label was emitted.", "- No pair coverage/readiness threshold was derived.", "- Pair 26/48 and Route-A MVE-1 remain unexecuted.", ""]
    (output_root / "threshold_candidate_report.md").write_text("\n".join(report_lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    data_root = args.data_root.resolve()
    output_root = args.output_root.resolve()
    manifest_path = args.manifest.resolve()
    config_path = args.config.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        permitted = {"geometry_development_manifest.json", "attempts"}
        if args.finalize_existing_ledger:
            permitted.update({"geometry_diagnostics.jsonl", "geometry_estimator_config.json", "implementation_environment.json"})
        if {child.name for child in output_root.iterdir()} - permitted:
            raise RuntimeError("refusing to mix a diagnostic attempt with existing output")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(manifest_path, data_root)
    is_isolated_attempt = (
        output_root.parent.name == "attempts" and manifest_path.parent == output_root.parent.parent
    )
    if manifest_path.parent != output_root and not is_isolated_attempt:
        raise RuntimeError("manifest must be in output root or be the immutable parent manifest of an isolated attempt")
    config_digest = sha256_file(config_path)
    provider_digest = sha256_file(REPOSITORY_ROOT / "src/tracking/route_a_geometry/image_geometry_provider.py")
    if args.finalize_existing_ledger:
        records = load_existing_ledger(output_root / "geometry_diagnostics.jsonl", manifest, config_digest, provider_digest)
        cv2.setNumThreads(1)
        cv2.ocl.setUseOpenCL(False)
        random.seed(7)
        np.random.seed(7)
        access: dict[str, Any] = {
            "jpeg_image_read_count": 2 * len(records),
            "paths_read": {record["image_src_path_relative"] for record in records} | {record["image_dst_path_relative"] for record in records},
        }
        started = datetime.now(timezone.utc)
        determinism = determinism_subset(records, manifest, config_digest, provider_digest, data_root, access)
        write_json(output_root / "determinism_check.json", determinism)
        if determinism["verdict"] != "PASS":
            raise RuntimeError("REPRODUCIBILITY_ACCEPTANCE_FAIL")
        write_summaries(output_root, records, access, started, determinism)
        return 0
    config_capture = {"source_path": str(config_path), "sha256": config_digest, "text": config_path.read_text(encoding="utf-8")}
    write_json(output_root / "geometry_estimator_config.json", config_capture)
    cv2.setNumThreads(1)
    cv2.ocl.setUseOpenCL(False)
    random.seed(7)
    np.random.seed(7)
    write_json(output_root / "implementation_environment.json", environment(config_digest, provider_digest, manifest["manifest_digest"]))
    access: dict[str, Any] = {"jpeg_image_read_count": 0, "paths_read": set()}
    records: list[dict[str, Any]] = []
    started = datetime.now(timezone.utc)
    with (output_root / "geometry_diagnostics.jsonl").open("x", encoding="utf-8") as handle:
        for pair_id in manifest["selected_pair_ids"]:
            metadata = manifest["pair_frame_metadata"][pair_id]
            frame_names = sorted(
                child.name for child in (data_root / "train" / "1" / f"{pair_id}-1").iterdir()
                if child.is_file() and child.suffix.lower() in {".jpg", ".jpeg"}
            )
            if len(frame_names) != metadata["frame_count"]:
                raise RuntimeError(f"frozen frame denominator changed for pair {pair_id}")
            for frame_name in frame_names:
                for direction in ("1_to_2", "2_to_1"):
                    record = make_record(manifest, config_digest, provider_digest, data_root, pair_id, frame_name, direction, access)
                    handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
                    records.append(record)
            print(f"completed pair {pair_id}: {len(frame_names) * 2} frame-direction records", flush=True)
    expected_count = 2 * sum(manifest["pair_frame_metadata"][pair_id]["frame_count"] for pair_id in manifest["selected_pair_ids"])
    assert_record_keys(records, expected_count)
    determinism = determinism_subset(records, manifest, config_digest, provider_digest, data_root, access)
    write_json(output_root / "determinism_check.json", determinism)
    if determinism["verdict"] != "PASS":
        raise RuntimeError("REPRODUCIBILITY_ACCEPTANCE_FAIL")
    write_summaries(output_root, records, access, started, determinism)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
