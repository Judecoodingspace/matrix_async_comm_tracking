#!/usr/bin/env python3
"""Create Team A V2-1 evidence from committed diffs; never run science."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tracking.governance_v2 import audit_diff, validate_mapping  # noqa: E402

CASES = {
    "Q1_REAL_L1": "ec8be0bc7098da015956b7e9fe56dbe21bb6a9f6",
    "Q2_REAL_L2": "f484ac5b886e68393c581936f1e764d4d08366d8",
    "Q3_REAL_DYNAMIC_UNMAPPED": "0aa88ea1d02d9cfe1d81f923cf4a73c2dd6062dc",
}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output_dir)
    if output.exists() or output.is_symlink():
        parser.error("output directory must be fresh")
    data = ROOT / "summary_md/governance/v2_1"
    mapping = validate_mapping(json.loads((data / "DEPENDENCY_MAP.json").read_text()))
    claim = json.loads((data / "MAP_APPLICABILITY.json").read_text())
    results = {}
    for label, target in CASES.items():
        base = subprocess.check_output(["git", "rev-parse", target + "^"], cwd=str(ROOT), text=True).strip()
        results[label] = audit_diff(ROOT, base, target, mapping, claim)
    q1, q2, q3 = (results[name] for name in CASES)
    kinds = lambda row: {item["evidence_id"]: item["classification"] for item in row["evidence_inheritance"]}
    assert q1["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert q1["unmapped_unknown_paths"] == []
    assert kinds(q1)["C7_FIFO_MECHANISM"] == "INHERITABLE"
    assert kinds(q1)["C7_CAPACITY_PROPAGATION"] == "INHERITABLE"
    assert kinds(q1)["C7_ELIGIBILITY_RECONSTRUCTION"] == "INHERITABLE"
    assert q2["candidate_verdict"] == "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"
    assert q2["unmapped_unknown_paths"] == []
    assert kinds(q2)["C7_ELIGIBILITY_RECONSTRUCTION"] == "NON_INHERITABLE"
    assert kinds(q2)["C7_FIFO_MECHANISM"] == "INHERITABLE"
    assert kinds(q2)["C7_CAPACITY_PROPAGATION"] == "INHERITABLE"
    assert q3["candidate_verdict"] == "BLOCK"
    assert any(item["reason"] == "DYNAMIC_DEPENDENCY_UNMAPPED"
               for item in q3["unmapped_unknown_paths"])
    output.mkdir(parents=True)
    for label, result in results.items():
        (output / (label + "_CHANGE_IMPACT_MANIFEST.json")).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"schema_version": "GOVERNANCE_V2_1_TEAM_A_QUALIFICATION_V1",
               "role": "TEAM_A_SELF_CHECK_NOT_INDEPENDENT_APPROVAL",
               "dependency_mapping_identity": mapping["dependency_mapping_identity"],
               "mapping_digest": mapping["mapping_digest"],
               "cases": {name: {"target_sha": case["target_implementation_sha"],
                                "verdict": case["candidate_verdict"],
                                "unmapped_count": len(case["unmapped_unknown_paths"])}
                         for name, case in results.items()},
               "result": "TEAM_A_SELF_CHECK_PASS"}
    (output / "QUALIFICATION_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("TEAM_A_SELF_CHECK_PASS Q1=REAL_L1 Q2=REAL_L2 Q3=UNMAPPED_BLOCK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
