#!/usr/bin/env python3
"""Read-only V2-1 candidate impact audit; never issues authorization."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tracking.governance_v2 import ImpactError, audit_diff, validate_mapping  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, help="exact 40-character commit SHA")
    parser.add_argument("--target", required=True, help="exact 40-character commit SHA")
    parser.add_argument("--map", default=str(ROOT / "summary_md/governance/v2_1/DEPENDENCY_MAP.json"))
    parser.add_argument("--applicability", default=str(ROOT / "summary_md/governance/v2_1/MAP_APPLICABILITY.json"))
    parser.add_argument("--unknown-scope-review", help="optional exact per-diff review JSON; never inferred from the map")
    parser.add_argument("--output", help="new JSON path; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        mapping = validate_mapping(json.loads(Path(args.map).read_text(encoding="utf-8")))
        claim = json.loads(Path(args.applicability).read_text(encoding="utf-8"))
        review = json.loads(Path(args.unknown_scope_review).read_text(encoding="utf-8")) if args.unknown_scope_review else None
        result = audit_diff(ROOT, args.base, args.target, mapping, claim, review)
    except (ImpactError, OSError, ValueError, KeyError, TypeError) as exc:
        print("V2_1_IMPACT_AUDIT_ERROR=" + str(exc), file=sys.stderr)
        return 2
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with Path(args.output).open("x", encoding="utf-8") as handle:
            handle.write(payload)
    else:
        print(payload, end="")
    return 0 if result["candidate_verdict"] != "BLOCK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
