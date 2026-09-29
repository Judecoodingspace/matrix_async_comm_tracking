#!/usr/bin/env python3
"""Run the 28 small synthetic V2-3 artifact qualification cases."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "tests/test_governance_v2_artifacts.py"
CASES = {
    "Q1_COMPLETED_STRUCTURAL_PASS": "test_completed_failed_and_negative_science_label_are_structural_only",
    "Q2_FAILED_STRUCTURAL_PASS": "test_completed_failed_and_negative_science_label_are_structural_only",
    "Q3_NEGATIVE_SCIENCE_LABEL_IRRELEVANT": "test_completed_failed_and_negative_science_label_are_structural_only",
    "Q4_MISSING_ARTIFACT_BLOCKS": "test_absent_failed_and_incomplete_block_finalization",
    "Q5_STRUCTURAL_FAIL_BLOCKS": "test_absent_failed_and_incomplete_block_finalization",
    "Q6_INTERRUPTION_BEFORE_MARKER": "test_marker_last_interruption_refinalization_and_lock",
    "Q7_REFINALIZATION_OR_CONCURRENT_REFUSED": "test_marker_last_interruption_refinalization_and_lock",
    "Q8_C1_C6_ALL_PASS": "test_reuse_c1_to_c6_and_plain_record",
    "Q9_WRONG_ATTEMPT_IDENTITY": "test_reuse_c1_to_c6_and_plain_record",
    "Q10_A1_UNRESOLVED_READ": "test_verified_a2_is_sticky_but_a1_can_resume",
    "Q11_A2_VERIFIED_CONTENT_MISMATCH": "test_verified_a2_is_sticky_but_a1_can_resume",
    "Q12_RAW_A2_BLOCK": "test_raw_a2_incident_blocks_inherited_correction_even_after_restore",
    "Q13_PROVENANCE_MISMATCH": "test_reuse_c1_to_c6_and_plain_record",
    "Q14_EXACT_BUT_NOT_APPLICABLE_CLASS_B": "test_reuse_c1_to_c6_and_plain_record",
    "Q15_V2_1_UNRESOLVED_BLOCK": "test_unresolved_v21_reference_refuses_reuse",
    "Q16_NORMALIZED_CORRECTION_INHERITS_RAW": "test_correction_inherits_raw_and_purpose_scoped_supersession",
    "Q17_PURPOSE_SCOPED_SUPERSESSION": "test_correction_inherits_raw_and_purpose_scoped_supersession",
    "Q18_OUT_OF_DOMAIN_IGNORED": "test_correction_inherits_raw_and_purpose_scoped_supersession",
    "Q19_AMBIGUOUS_LINEAGE_BLOCK": "test_correction_inherits_raw_and_purpose_scoped_supersession",
    "Q20_DERIVED_PACKAGE_DISAGREEMENT": "test_derived_package_disagreement_does_not_override_authoritative_root",
    "Q21_INHERITED_LAYER_TIER1": "test_inherited_tier3_layer_becomes_tier1_while_live_child_uses_it",
    "Q22_TIER2_AUDIT_HOLD": "test_tier2_audit_hold_and_tier3_regenerability",
    "Q23_TIER3_REGENERABILITY": "test_tier2_audit_hold_and_tier3_regenerability",
    "Q24_NO_IMPLICIT_ADOPTION": "test_absent_failed_and_incomplete_block_finalization",
    "Q25_EXPLICIT_ADOPTION_DEEP_CHECK": "test_explicit_adoption_verifies_content_and_formal_rehashes",
    "Q26_FORMAL_AUTHORITY_BOUNDARY": "test_explicit_adoption_verifies_content_and_formal_rehashes",
    "Q27_PLAIN_FILE_CONSUMER_RECORD": "test_unknown_schema_and_independent_consumer_anchor",
    "Q28_EXACT_GIT_REFERENCE_ONLY": "test_git_exact_commit_and_branch_rejected",
}


def qualify(output_root: Path) -> dict:
    output = Path(output_root).resolve()
    if ROOT in output.parents or output == ROOT:
        raise ValueError("qualification output must be outside repository")
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, "-m", "pytest", "-v", str(TEST),
               "--basetemp", str(output / "pytest")]
    completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    passed = set(re.findall(r"test_(\w+)(?:\[[^\]]+\])? PASSED", completed.stdout))
    observed = {"test_" + name for name in passed}
    cases = {name: {"result": "PASS" if test in observed else "FAIL", "test": test}
             for name, test in CASES.items()}
    result = {"schema_version": "GOVERNANCE_V2_3_SYNTHETIC_QUALIFICATION_V1",
              "synthetic_non_scientific": True, "timestamp": datetime.now(timezone.utc).isoformat(),
              "result": "PASS" if completed.returncode == 0
              and all(row["result"] == "PASS" for row in cases.values()) else "FAIL",
              "test_returncode": completed.returncode, "case_count": len(cases), "cases": cases,
              "test_stdout_tail": completed.stdout[-3000:], "test_stderr_tail": completed.stderr[-1000:]}
    (output / "qualification.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = qualify(args.output_root)
    print(json.dumps({"result": result["result"], "case_count": result["case_count"],
                      "output": str(Path(args.output_root).resolve())}, sort_keys=True))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
