#!/usr/bin/env python3
"""Static/passivity audit and strict A/B/C full-core trace comparison."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.tracking.mdmt_mia_work1_core_comparison import (
    CoreComparisonError,
    audit_launch_command_diff,
    audit_source,
    compare_artifact_pairs,
    compare_repeat_records,
    compare_trace_files,
    load_trace,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    compare = sub.add_parser("compare")
    compare.add_argument("--a", type=Path, required=True)
    compare.add_argument("--b", type=Path, required=True)
    compare.add_argument("--c", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    compare.add_argument("--pair-id", type=int, required=True)
    compare.add_argument("--expected-frame-count", type=int, required=True)
    repeat = sub.add_parser("repeat")
    repeat.add_argument("--first", type=Path, required=True)
    repeat.add_argument("--second", type=Path, required=True)
    repeat.add_argument("--role", choices=("A", "B", "C"), required=True)
    repeat.add_argument("--pair-id", type=int, required=True)
    repeat.add_argument("--expected-frame-count", type=int, required=True)
    repeat.add_argument("--output", type=Path, required=True)
    parent = sub.add_parser("parent-parity")
    parent.add_argument("--parent-artifact", type=Path, action="append", required=True)
    parent.add_argument("--a-traced-artifact", type=Path, action="append", required=True)
    parent.add_argument("--output", type=Path, required=True)
    launch = sub.add_parser("launch-diff")
    launch.add_argument("--execution-spec", type=Path, required=True)
    launch.add_argument("--output", type=Path, required=True)
    source_manifest = sub.add_parser("source-manifest")
    source_manifest.add_argument("--manifest", type=Path, required=True)
    source_manifest.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    source_manifest.add_argument("--output", type=Path, required=True)
    static = sub.add_parser("static")
    static.add_argument("--source", type=Path, action="append", required=True)
    static.add_argument("--protected", type=Path, action="append", default=[])
    static.add_argument("--expected-sha256", action="append", default=[])
    static.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "compare":
            result = compare_trace_files(
                args.a, args.b, args.c, args.output, expected_pair_id=args.pair_id,
                expected_frame_ids=range(args.expected_frame_count),
            )
            if result["CORE_OUTPUT_DIFF"] or result["TRACKER_MUTATION_COUNT_FROM_OBSERVER"]:
                raise SystemExit("DYNAMIC_M2_NON_INTERFERENCE_FAIL")
            return
        if args.command == "repeat":
            result = compare_repeat_records(
                load_trace(args.first), load_trace(args.second), expected_role=args.role,
                expected_pair_id=args.pair_id, expected_frame_ids=range(args.expected_frame_count),
            )
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if result["EXACT_REPEAT_DIFF"]:
                raise SystemExit("EXACT_COMPARISON_DETERMINISM_BLOCKER")
            return
        if args.command == "parent-parity":
            result = compare_artifact_pairs(args.parent_artifact, args.a_traced_artifact)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if result["PARENT_VS_A_TRACED_OUTPUT_DIFF"]:
                raise SystemExit("A_PARENT_VS_A_TRACED_RUNTIME_PARITY_FAIL")
            return
        if args.command == "launch-diff":
            specification = json.loads(args.execution_spec.read_text(encoding="utf-8"))
            commands = {key: value for key, value in specification["command_templates"].items() if key != "not_executed"}
            result = audit_launch_command_diff(commands)
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return
        if args.command == "source-manifest":
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            expected = manifest.get("files")
            if not isinstance(expected, dict) or not expected:
                raise CoreComparisonError("source manifest has no file hashes")
            records = []
            for relative, expected_digest in sorted(expected.items()):
                path = args.repository_root / relative
                actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
                records.append({"path": relative, "expected_sha256": expected_digest,
                                "actual_sha256": actual_digest, "equal": actual_digest == expected_digest})
            mismatch_count = sum(not record["equal"] for record in records)
            result = {"status": "PASS" if mismatch_count == 0 else "FAIL",
                      "SOURCE_MANIFEST_MISMATCH_COUNT": mismatch_count, "records": records}
            args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if mismatch_count:
                raise SystemExit("DYNAMIC_M2_SOURCE_PROVENANCE_FAIL")
            return
    except CoreComparisonError as error:
        if hasattr(args, "output"):
            args.output.write_text(json.dumps({"status": "FAIL", "detail": str(error)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise SystemExit("FULL_CORE_COMPARISON_VALIDITY_FAIL") from error
    if len(args.protected) != len(args.expected_sha256):
        raise SystemExit("protected path/hash cardinality mismatch")
    result = audit_source(args.source, dict(zip(args.protected, args.expected_sha256)))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if result["status"] != "PASS":
        raise SystemExit("FULL_CORE_INSTRUMENTATION_STATIC_AUDIT_FAIL")


if __name__ == "__main__":
    main()
