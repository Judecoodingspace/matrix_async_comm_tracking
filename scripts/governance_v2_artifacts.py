#!/usr/bin/env python3
"""Thin CLI for local V2-3 artifact operations; no scientific execution."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tracking import governance_v2_artifacts as artifacts  # noqa: E402


def _json(path: str) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("finalize", "inspect", "check-reuse", "create-correction", "check-cleanup-eligibility"):
        p = sub.add_parser(name)
        p.add_argument("--attempts-root", type=Path, required=True)
        p.add_argument("--attempt-id", required=True)
        if name in {"finalize", "create-correction", "check-reuse"}:
            p.add_argument("--repo-root", type=Path, required=True)
        if name in {"finalize", "create-correction"}:
            p.add_argument("--declaration", required=True)
        if name in {"inspect", "create-correction", "check-reuse", "check-cleanup-eligibility"}:
            p.add_argument("--node-id", default="initial")
        if name == "check-reuse":
            p.add_argument("--request", required=True,
                           help="JSON with purpose, consumption_class, anchor, expected_artifacts, expected_provenance, v2_1_applicability")
            p.add_argument("--consumer-record", type=Path, required=True)
        if name == "check-cleanup-eligibility":
            p.add_argument("--artifact-path", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "finalize":
            result = artifacts.finalize(args.attempts_root, args.attempt_id,
                                        _json(args.declaration), repo_root=args.repo_root,
                                        adopt=True, authority_boundary=True)
        elif args.command == "inspect":
            result = artifacts.inspect(args.attempts_root, args.attempt_id, args.node_id)
        elif args.command == "create-correction":
            result = artifacts.create_correction(args.attempts_root, args.attempt_id, args.node_id,
                                                 _json(args.declaration), repo_root=args.repo_root)
        elif args.command == "check-reuse":
            request = _json(args.request)
            required = {"purpose", "consumption_class", "anchor", "expected_artifacts",
                        "expected_provenance", "v2_1_applicability"}
            if set(request) != required:
                raise ValueError("reuse request schema mismatch")
            result = artifacts.check_reuse(args.attempts_root, args.attempt_id, args.node_id,
                                           consumer_record=args.consumer_record,
                                           repo_root=args.repo_root, **request)
        else:
            result = artifacts.check_cleanup_eligibility(args.attempts_root, args.attempt_id,
                                                         args.node_id, args.artifact_path)
    except (artifacts.ArtifactError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "BLOCK", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("decision", "REUSE_ADMISSIBLE") != "BLOCK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
