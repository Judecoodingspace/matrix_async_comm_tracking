#!/usr/bin/env python3
"""Verify recovery-epoch geometry semantics on the frozen development set only."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from src.tracking.route_a_geometry.g15c_validity import (  # noqa: E402
    CONDITION_FAILURE,
    INLIER_COUNT_FAILURE,
    INLIER_RATIO_FAILURE,
    RANK_FAILURE,
    classify_geometry,
    validate_gate_artifact,
)


EXPECTED_PROVIDER = "b8b65b881cc1627ff2e5f41f885f36473ebadf59f5e3f076240c9de1eee99a7d"
EXPECTED_CONFIG = "c7b6b2cd30238c174295f2b367f70f5b8a062cae7737abd8aca9ab9ded66eb04"
EXPECTED_PAIR_DENOMINATORS = {"45": 800, "29": 1400, "51": 860, "69": 1400, "25": 1000}
EXPECTED_PAIR_VALID = {"45": 800, "29": 1241, "51": 844, "69": 1274, "25": 763}
EXPECTED_DIRECTION_DENOMINATORS = {"1_to_2": 2730, "2_to_1": 2730}
EXPECTED_DIRECTION_VALID = {"1_to_2": 2508, "2_to_1": 2414}
EXPECTED_FAILURE_COUNTS = {
    RANK_FAILURE: 0,
    INLIER_COUNT_FAILURE: 3,
    INLIER_RATIO_FAILURE: 289,
    CONDITION_FAILURE: 294,
}
EXPECTED_ROWS = 5460
EXPECTED_VALID = 4922
EXPECTED_INVALID = 538
EXPECTED_MULTI_FAILURE_ROWS = 48
FORBIDDEN_PATH_PARTS = {"test", "val", "gt", "xml", "26-1", "26-2", "48-1", "48-2"}


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            stated = row.pop("record_digest", None)
            if canonical_digest(row) != stated:
                raise ValueError(f"record digest mismatch at line {line_number}")
            row["record_digest"] = stated
            rows.append(row)
    return rows


def assert_development_scope(row: dict[str, Any]) -> None:
    if row.get("pair_id") not in EXPECTED_PAIR_DENOMINATORS:
        raise ValueError(f"non-frozen development pair in ledger: {row.get('pair_id')}")
    for field in ("image_src_path_relative", "image_dst_path_relative"):
        parts = {part.lower() for part in Path(str(row.get(field, ""))).parts}
        if parts & FORBIDDEN_PATH_PARTS or "train" not in parts:
            raise ValueError(f"forbidden development path in {field}")


def compare(name: str, observed: Any, expected: Any) -> dict[str, Any]:
    return {"name": name, "observed": observed, "expected": expected, "pass": observed == expected}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gate_value = json.loads(args.gate.read_text(encoding="utf-8"))
    validate_gate_artifact(gate_value)
    rows = read_rows(args.ledger)
    keys = []
    pair_total: Counter[str] = Counter()
    pair_valid: Counter[str] = Counter()
    direction_total: Counter[str] = Counter()
    direction_valid: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    valid = invalid = unavailable = multi_failure = 0
    for row in rows:
        assert_development_scope(row)
        if row.get("provider_code_digest") != EXPECTED_PROVIDER or row.get("provider_config_digest") != EXPECTED_CONFIG:
            raise ValueError("provider/config digest differs from frozen scientific implementation")
        key = (row["pair_id"], row["frame_name"], row["direction"])
        keys.append(key)
        outcome = classify_geometry(row)
        pair_total[row["pair_id"]] += 1
        direction_total[row["direction"]] += 1
        if outcome.validity_status == "H_VALID":
            valid += 1
            pair_valid[row["pair_id"]] += 1
            direction_valid[row["direction"]] += 1
        elif outcome.validity_status == "H_INVALID":
            invalid += 1
        else:
            unavailable += 1
        failure_counts.update(outcome.failure_reasons)
        if len(outcome.failure_reasons) > 1:
            multi_failure += 1

    checks = [
        compare("total_rows", len(rows), EXPECTED_ROWS),
        compare("unique_keys", len(set(keys)), EXPECTED_ROWS),
        compare("H_VALID", valid, EXPECTED_VALID),
        compare("H_INVALID", invalid, EXPECTED_INVALID),
        compare("GEOMETRY_UNAVAILABLE", unavailable, 0),
        compare("pair_denominators", dict(pair_total), EXPECTED_PAIR_DENOMINATORS),
        compare("pair_valid", dict(pair_valid), EXPECTED_PAIR_VALID),
        compare("direction_denominators", dict(direction_total), EXPECTED_DIRECTION_DENOMINATORS),
        compare("direction_valid", dict(direction_valid), EXPECTED_DIRECTION_VALID),
        compare("failure_counts", {key: failure_counts[key] for key in EXPECTED_FAILURE_COUNTS}, EXPECTED_FAILURE_COUNTS),
        compare("multi_failure_rows", multi_failure, EXPECTED_MULTI_FAILURE_ROWS),
    ]
    report = {
        "audit": "DEVELOPMENT_SEMANTIC_EQUIVALENCE",
        "scope": "FROZEN_DEVELOPMENT_PAIRS_ONLY",
        "ledger": str(args.ledger.resolve()),
        "gate_artifact": str(args.gate.resolve()),
        "checks": checks,
        "all_checks_pass": all(item["pass"] for item in checks),
        "historical_row_digest_equivalence_claimed": False,
        "byte_identical_historical_artifact_recovery": "NOT_ESTABLISHED",
        "threshold_recalibration_performed": False,
        "heldout_pair_read_count": 0,
        "gt_xml_read_count": 0,
    }
    if args.output.exists():
        raise ValueError(f"refusing to overwrite semantic audit: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if report["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
