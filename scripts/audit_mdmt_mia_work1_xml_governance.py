#!/usr/bin/env python3
"""Validate Work 1 XML-governance evidence without opening XML or GT data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.tracking.mdmt_mia_work1_xml_governance import (
    GovernanceGateError,
    audit_static_oracle_firewall,
    build_abc_initialization_equality,
    validate_abc_initialization_equality,
    validate_claim_output,
    validate_initialization_boundary,
    validate_initialization_provenance,
    validate_runtime_oracle_firewall,
    write_gate_result,
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="gate", required=True)

    provenance = subparsers.add_parser("g-xml1")
    provenance.add_argument("--expected-record", type=Path, required=True)
    provenance.add_argument("--observed-record", type=Path, required=True)

    equality = subparsers.add_parser("g-xml2")
    equality.add_argument("--audit-record", type=Path, required=True)

    build_equality = subparsers.add_parser("build-g-xml2")
    build_equality.add_argument("--a-record", type=Path, required=True)
    build_equality.add_argument("--b-record", type=Path, required=True)
    build_equality.add_argument("--c-record", type=Path, required=True)
    build_equality.add_argument("--xml-manifest", type=Path, required=True)
    build_equality.add_argument("--pair-id", type=int, required=True)
    build_equality.add_argument("--audit-record", type=Path, required=True)

    static = subparsers.add_parser("g-xml3-static")
    static.add_argument("--source", type=Path, action="append", required=True)
    static.add_argument("--schema-record", type=Path)

    dynamic = subparsers.add_parser("g-xml3-dynamic")
    dynamic.add_argument("--audit-record", type=Path, required=True)

    boundary = subparsers.add_parser("g-xml4")
    boundary.add_argument("--audit-record", type=Path, required=True)

    claim = subparsers.add_parser("g-xml5")
    claim.add_argument("--output-record", type=Path, required=True)

    for child in (provenance, equality, build_equality, static, dynamic, boundary, claim):
        child.add_argument("--result", type=Path, required=True)

    args = parser.parse_args()
    try:
        if args.gate == "g-xml1":
            result = validate_initialization_provenance(_load(args.expected_record), _load(args.observed_record))
        elif args.gate == "g-xml2":
            result = validate_abc_initialization_equality(_load(args.audit_record))
        elif args.gate == "build-g-xml2":
            payload = build_abc_initialization_equality(
                {"A": _load(args.a_record), "B": _load(args.b_record), "C": _load(args.c_record)},
                _load(args.xml_manifest), args.pair_id,
            )
            args.audit_record.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = validate_abc_initialization_equality(payload)
        elif args.gate == "g-xml3-static":
            fields = [] if args.schema_record is None else _load(args.schema_record).get("declared_fields", [])
            result = audit_static_oracle_firewall(args.source, fields)
        elif args.gate == "g-xml3-dynamic":
            result = validate_runtime_oracle_firewall(_load(args.audit_record))
        elif args.gate == "g-xml4":
            result = validate_initialization_boundary(_load(args.audit_record))
        else:
            result = validate_claim_output(_load(args.output_record))
    except GovernanceGateError as error:
        write_gate_result(args.result, {"gate": args.gate, "status": "FAIL", "failure_label": error.label, "detail": error.detail})
        raise SystemExit(error.label) from error
    write_gate_result(args.result, result)


if __name__ == "__main__":
    main()
