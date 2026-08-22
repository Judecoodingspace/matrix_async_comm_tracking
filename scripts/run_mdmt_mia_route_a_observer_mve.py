#!/usr/bin/env python3
"""Run the frozen seven-run Route-A observer-only MVE-0 matrix.

The script fails closed when the generated variant is not structurally
observer-only, when a run fails, or when core/feedback digests differ from
``DROP_LATE``.  It deliberately has no MVE-1 mode.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


CONDITIONS = ("DROP_LATE", "NAIVE_ARRIVAL", "ROUTE_A_OBSERVER_MVE")
REPEAT = ("48", "ROUTE_A_OBSERVER_MVE")
EVENT_FILES = (
    "source_observations.jsonl", "packet_events.jsonl", "receiver_snapshots.jsonl",
    "evidence_tubes.jsonl", "candidate_events.jsonl", "side_hypotheses.jsonl",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def prepare_input(root: Path, data_root: Path, pair_id: str) -> tuple[Path, Path]:
    input_root = root / "input"
    for view in ("1", "2"):
        sequence = "{}-{}".format(pair_id, view)
        target = data_root / "test" / view / sequence
        link = input_root / view / sequence
        link.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_dir():
            raise FileNotFoundError("missing frozen MDMT input: {}".format(target))
        if not link.exists():
            link.symlink_to(target)
        xml_target = data_root / "new_xml" / view / (sequence + ".xml")
        xml_link = input_root / "xml" / (sequence + ".xml")
        xml_link.parent.mkdir(parents=True, exist_ok=True)
        if not xml_target.is_file():
            raise FileNotFoundError("missing frozen MDMT XML: {}".format(xml_target))
        if not xml_link.exists():
            xml_link.symlink_to(xml_target)
    return input_root, input_root / "xml"


def verify_variant(variant_root: Path) -> dict[str, Any]:
    manifest_path = variant_root / "route_a_observer_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("mve") != "MVE-0" or manifest.get("mve1_enabled") != 0:
        raise RuntimeError("variant is not MVE-0-only")
    if not all(manifest.get("structure_audit", {}).values()):
        raise RuntimeError("variant structure audit did not pass")
    for relative, expected in manifest["sha256"].items():
        actual = digest(variant_root / relative)
        if actual != expected:
            raise RuntimeError("variant digest mismatch: {}".format(relative))
    return manifest


def seed_detector_cache(args: argparse.Namespace, pair_id: str) -> None:
    """Generate a detector-only cache with frozen v8 before any MVE condition."""
    seed_root = args.output_root / "detector_cache_seed" / ("pair_{}".format(pair_id))
    seed_root.mkdir(parents=True)
    input_root, xml_root = prepare_input(seed_root, args.data_root, pair_id)
    env = os.environ.copy()
    env.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "7",
        "PYTHONPATH": "{}:{}{}".format(args.cache_source_root, args.cache_source_root / "demo/utils", ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""),
        "MPLCONFIGDIR": str(seed_root / "matplotlib"),
        "MIA_DETECTION_CACHE_ROOT": str(args.output_root / "detector_cache"),
        "MIA_DETECTION_CACHE_MODE": "write",
        "MIA_CASCADE_EDGE_CUT": "0", "MIA_CASCADE_SHADOW": "0", "MIA_CASCADE_LOGGING": "0",
    })
    command = [
        str(args.python), str(args.cache_source_root / "demo/supplement_MIA.py"),
        "--config", str(args.config), "--input", str(input_root / "1") + "/",
        "--xml_dir", str(xml_root) + "/", "--result_dir", str(seed_root / "author_results"),
        "--method", "detector_cache_seed_{}".format(pair_id),
        "--output", str(seed_root / "view1"), "--output2", str(seed_root / "view2"), "--device", args.device,
    ]
    (seed_root / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
    completed = subprocess.run(command, cwd=seed_root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (seed_root / "author.log").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode:
        raise RuntimeError("detector cache seed failed for Pair {}".format(pair_id))
    cache_files = sorted((args.output_root / "detector_cache").glob("*.npz"))
    if not cache_files:
        raise RuntimeError("detector cache seed produced no .npz files for Pair {}".format(pair_id))
    (seed_root / "cache_seed_manifest.json").write_text(json.dumps({
        "pair_id": pair_id, "cache_mode": "write", "cache_file_count_after_seed": len(cache_files),
        "cache_sha256": {path.name: digest(path) for path in cache_files},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_one(args: argparse.Namespace, pair_id: str, condition: str, attempt: int) -> Path:
    attempt_root = args.output_root / "attempts" / ("pair_{}".format(pair_id)) / condition / ("attempt_{}".format(attempt))
    if attempt_root.exists():
        raise RuntimeError("refusing to mix/reuse attempt directory: {}".format(attempt_root))
    attempt_root.mkdir(parents=True)
    input_root, xml_root = prepare_input(attempt_root, args.data_root, pair_id)
    observer_root = attempt_root / "observer"
    author_root = attempt_root / "author_results"
    env = os.environ.copy()
    env.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": "{}:{}{}".format(args.variant_root, args.variant_root / "demo/utils", ":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""),
        "MPLCONFIGDIR": str(attempt_root / "matplotlib"),
        "MIA_DETECTION_CACHE_ROOT": str(args.detector_cache_root),
        "MIA_DETECTION_CACHE_MODE": "read",
        "MIA_CASCADE_EDGE_CUT": "0",
        "MIA_CASCADE_SHADOW": "0",
        "MIA_CASCADE_LOGGING": "0",
        "MIA_ROUTE_A_OUTPUT_DIR": str(observer_root),
        "MIA_ROUTE_A_CONDITION": condition,
        "MIA_ROUTE_A_DELAY_FRAMES": "5",
    })
    command = [
        str(args.python), str(args.variant_root / "demo/supplement_MIA.py"),
        "--config", str(args.config), "--input", str(input_root / "1") + "/",
        "--xml_dir", str(xml_root) + "/", "--result_dir", str(author_root),
        "--method", "route_a_{}_{}".format(condition.lower(), pair_id),
        "--output", str(attempt_root / "view1"), "--output2", str(attempt_root / "view2"),
        "--device", args.device,
    ]
    (attempt_root / "command.json").write_text(json.dumps(command, indent=2) + "\n", encoding="utf-8")
    completed = subprocess.run(command, cwd=attempt_root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (attempt_root / "author.log").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode:
        (attempt_root / "attempt_status.json").write_text(json.dumps({"status": "ABORTED", "returncode": completed.returncode}) + "\n", encoding="utf-8")
        raise RuntimeError("author MIA failed: {}; see {}".format(completed.returncode, attempt_root / "author.log"))
    required = [observer_root / "manifest.json", observer_root / "hard_assertions.csv", observer_root / "core_feedback_digests.jsonl"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("observer run did not finalize required artifacts: {}".format(missing))
    (attempt_root / "attempt_status.json").write_text(json.dumps({"status": "COMPLETE", "returncode": 0}) + "\n", encoding="utf-8")
    return observer_root


def aggregate(output_root: Path, runs: list[tuple[str, str, int, Path]], variant_manifest: dict[str, Any]) -> None:
    combined: dict[str, list[dict[str, Any]]] = {name: [] for name in EVENT_FILES}
    summaries: list[dict[str, Any]] = []
    assertions: list[dict[str, str]] = []
    digest_rows: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    for pair_id, condition, attempt, run_root in runs:
        manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
        if manifest["cross_view_geometry_gate"] != "FAIL" or manifest["zero_cross_view_candidates"] != 1:
            raise RuntimeError("MVE-0 geometry fail-closed boundary violated")
        if manifest["identity_oracle_read_count"] != 0:
            raise RuntimeError("observer oracle read detected")
        summaries.append({"pair_id": pair_id, "condition": condition, "attempt": attempt, **manifest["counts"]})
        for row in load_jsonl(run_root / "core_feedback_digests.jsonl"):
            digest_rows[(pair_id, condition, attempt)] = digest_rows.get((pair_id, condition, attempt), []) + [row]
        for name in EVENT_FILES:
            combined[name].extend(load_jsonl(run_root / name))
        with (run_root / "hard_assertions.csv").open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                assertions.append({"pair_id": pair_id, "condition": condition, "attempt": str(attempt), **row})
    for name, rows in combined.items():
        with (output_root / name).open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, sort_keys=True) + "\n")
    fieldnames = sorted({key for row in summaries for key in row})
    with (output_root / "condition_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summaries)
    with (output_root / "hard_assertions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("pair_id", "condition", "attempt", "assertion", "status", "detail"))
        writer.writeheader()
        writer.writerows(assertions)

    invariance: list[dict[str, Any]] = []
    for pair_id in ("26", "48"):
        reference = digest_rows[(pair_id, "DROP_LATE", 1)]
        for condition, attempt in (("NAIVE_ARRIVAL", 1), ("ROUTE_A_OBSERVER_MVE", 1)):
            current = digest_rows[(pair_id, condition, attempt)]
            equal = int(reference == current)
            invariance.append({"pair_id": pair_id, "condition": condition, "attempt": attempt,
                               "reference_condition": "DROP_LATE", "core_and_feedback_digest_equal": equal,
                               "reference_frame_count": len(reference), "condition_frame_count": len(current)})
            if not equal:
                raise RuntimeError("core/feedback invariance failed for pair {} {}".format(pair_id, condition))
    repeat = digest_rows[("48", "ROUTE_A_OBSERVER_MVE", 2)]
    first = digest_rows[("48", "ROUTE_A_OBSERVER_MVE", 1)]
    equal = int(first == repeat)
    invariance.append({"pair_id": "48", "condition": "ROUTE_A_OBSERVER_MVE", "attempt": 2,
                       "reference_condition": "ROUTE_A_OBSERVER_MVE", "core_and_feedback_digest_equal": equal,
                       "reference_frame_count": len(first), "condition_frame_count": len(repeat)})
    if not equal:
        raise RuntimeError("Pair-48 Route-A exact repeat failed")
    with (output_root / "tracker_invariance.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(invariance[0]))
        writer.writeheader()
        writer.writerows(invariance)

    geometry = {
        "cross_view_geometry_gate": "FAIL", "status": "NOT_APPLICABLE_GEOMETRY_FAIL_CLOSED",
        "mve1_executed": 0, "candidate_count": 0,
        "reason": "No independently causal transform was supplied; the observer emitted no cross-view candidates.",
    }
    (output_root / "geometry_provenance.json").write_text(json.dumps(geometry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "experiment_id": "exp_20260822_001_mdmt_mia_route_a_observer_mve", "mve": "MVE-0",
        "run_count": len(runs), "conditions": list(CONDITIONS), "pairs": ["26", "48"], "delay_frames": 5,
        "seed": 7, "cross_view_geometry_gate": "FAIL", "mve1_executed": 0,
        "variant_manifest_digest": hashlib.sha256(json.dumps(variant_manifest, sort_keys=True).encode()).hexdigest(),
    }
    (output_root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--cache-source-root", type=Path,
                        default=Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v8"))
    parser.add_argument("--mia-root", type=Path, default=Path("/mnt/data/yzm/experiments/mdmt_mia_official"))
    parser.add_argument("--data-root", type=Path, default=Path("/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking"))
    parser.add_argument("--config", type=Path, default=Path("/mnt/data/yzm/experiments/mdmt_mia_official/run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py"))
    parser.add_argument("--detector-cache-root", type=Path, default=None)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    args.output_root = args.output_root.resolve()
    args.variant_root = args.variant_root.resolve()
    args.cache_source_root = args.cache_source_root.resolve()
    args.mia_root = args.mia_root.resolve()
    args.data_root = args.data_root.resolve()
    args.config = args.config.resolve()
    args.python = args.mia_root / ".conda-env/bin/python"
    if args.detector_cache_root is None:
        args.detector_cache_root = args.output_root / "detector_cache"
    else:
        args.detector_cache_root = args.detector_cache_root.resolve()
    if args.output_root.exists():
        raise SystemExit("refusing an existing output root to prevent mixed attempts: {}".format(args.output_root))
    for required in (args.variant_root, args.cache_source_root, args.python, args.config):
        if not required.exists():
            raise SystemExit("missing required path: {}".format(required))
    args.output_root.mkdir(parents=True)
    variant_manifest = verify_variant(args.variant_root)
    runs: list[tuple[str, str, int, Path]] = []
    try:
        for pair_id in ("26", "48"):
            seed_detector_cache(args, pair_id)
        for pair_id in ("26", "48"):
            for condition in CONDITIONS:
                runs.append((pair_id, condition, 1, run_one(args, pair_id, condition, 1)))
        runs.append((REPEAT[0], REPEAT[1], 2, run_one(args, REPEAT[0], REPEAT[1], 2)))
        aggregate(args.output_root, runs, variant_manifest)
    except BaseException:
        (args.output_root / "RUN_ABORTED").write_text("MVE-0 aborted; no decision may be drawn.\n", encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
