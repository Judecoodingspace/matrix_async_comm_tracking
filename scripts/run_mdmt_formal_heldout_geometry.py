#!/usr/bin/env python3
"""Prepared, never-run formal Pair 26/48 executor for Attempt 004."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import cv2

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.tracking.route_a_geometry import (  # noqa: E402
    KAPPA_MAX,
    N_MIN,
    R_MIN,
    classify_geometry,
    estimate_homography,
)
from src.tracking.route_a_geometry.formal_row_contract import (  # noqa: E402
    FORMAL_ATTEMPT_ID,
    build_formal_row,
    canonical_digest,
    serialize_formal_row,
    validate_schema_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--input-contract", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--output-ledger", type=Path, required=True)
    parser.add_argument("--provider-digest", required=True)
    parser.add_argument("--estimator-config-digest", required=True)
    parser.add_argument("--g15c-gate-digest", required=True)
    parser.add_argument("--input-contract-digest", required=True)
    parser.add_argument("--execution-spec-digest", required=True)
    parser.add_argument("--repaired-formal-source-commit", required=True)
    parser.add_argument("--preexecution-lock-record-commit", required=True)
    return parser.parse_args()


def load_contract(path: Path, expected_digest: str) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    payload = dict(contract)
    stated = payload.pop("input_contract_digest", None)
    if canonical_digest(payload) != stated or stated != expected_digest:
        raise RuntimeError("formal input contract digest mismatch")
    return contract


def provenance(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "frozen_N_min": N_MIN,
        "frozen_R_min": R_MIN,
        "frozen_kappa_max": KAPPA_MAX,
        "provider_digest": args.provider_digest,
        "estimator_config_digest": args.estimator_config_digest,
        "G15c_gate_digest": args.g15c_gate_digest,
        "input_contract_digest": args.input_contract_digest,
        "execution_spec_digest": args.execution_spec_digest,
        "repaired_formal_source_commit": args.repaired_formal_source_commit,
        "preexecution_lock_record_commit": args.preexecution_lock_record_commit,
    }


def image_paths(data_root: Path, entry: dict[str, Any], frame_name: str, direction: str) -> tuple[Path, Path]:
    left = data_root / entry["view_1_relative"] / frame_name
    right = data_root / entry["view_2_relative"] / frame_name
    return (left, right) if direction == "1_to_2" else (right, left)


def main() -> int:
    args = parse_args()
    authorization = json.loads(args.authorization.resolve().read_text(encoding="utf-8"))
    if (
        authorization.get("authorized") is not True
        or authorization.get("audit_verdict") != "PASS"
        or authorization.get("attempt_id") != FORMAL_ATTEMPT_ID
        or authorization.get("child_spawn_count") not in {0, 1}
    ):
        raise SystemExit("formal executor lacks valid prestart authorization")
    validate_schema_manifest(json.loads(args.schema.resolve().read_text(encoding="utf-8")))
    contract = load_contract(args.input_contract.resolve(), args.input_contract_digest)
    data_root = args.data_root.resolve()
    if data_root != Path(contract["dataset_root_resolved"]).resolve():
        raise SystemExit("formal data root differs from input contract")
    if args.output_ledger.exists():
        raise SystemExit("formal ledger already exists")
    args.output_ledger.parent.mkdir(parents=True, exist_ok=False)
    row_count = 0
    seen: set[tuple[str, str, str]] = set()
    with args.output_ledger.open("x", encoding="utf-8") as handle:
        for pair_id in contract["pair_ids"]:
            entry = contract["pairs"][pair_id]
            left_root = data_root / entry["view_1_relative"]
            right_root = data_root / entry["view_2_relative"]
            left_names = sorted(p.name for p in left_root.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg"})
            right_names = sorted(p.name for p in right_root.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg"})
            if left_names != right_names or len(left_names) != entry["frame_count"]:
                raise RuntimeError(f"Pair {pair_id} metadata differs from input contract")
            if canonical_digest(left_names) != entry["frame_name_set_digest"]:
                raise RuntimeError(f"Pair {pair_id} filename-set digest differs from input contract")
            for frame_name in left_names:
                for direction in contract["directions"]:
                    key = (pair_id, frame_name, direction)
                    if key in seen:
                        raise RuntimeError(f"duplicate formal key: {key}")
                    seen.add(key)
                    source_path, target_path = image_paths(data_root, entry, frame_name, direction)
                    source = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
                    target = cv2.imread(str(target_path), cv2.IMREAD_COLOR)
                    estimated = estimate_homography(source, target)
                    validity = classify_geometry(estimated)
                    core = {
                        "pair_id": pair_id,
                        "frame_name": frame_name,
                        "direction": direction,
                        "H_available": bool(estimated["H_available"]),
                        "H_valid": validity.H_valid,
                        "validity_status": validity.validity_status,
                        "failure_reasons": list(validity.failure_reasons),
                        "matrix_rank": estimated["matrix_rank"],
                        "num_tentative_matches": estimated["num_tentative_matches"],
                        "num_unique_matches": estimated["num_unique_matches"],
                        "num_ransac_inliers": estimated["num_ransac_inliers"],
                        "inlier_ratio": estimated["inlier_ratio"],
                        "condition_number": estimated["condition_number"],
                    }
                    row = build_formal_row(core, provenance(args))
                    handle.write(serialize_formal_row(row))
                    handle.flush()
                    row_count += 1
    if row_count != 2000 or len(seen) != 2000:
        raise RuntimeError(f"formal full-denominator invariant failed: {row_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
