#!/usr/bin/env python3
"""Outcome-blind attempt acceptance and population-validity sealing CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tracking.mdmt_mia_locked_d1_validity import (seal_attempt_acceptance,
    seal_measurement_validity, validate_attempt)


def main() -> None:
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect-attempt")
    inspect_parser.add_argument("--attempt-manifest", type=Path, required=True)
    inspect_parser.add_argument("--expected-authority", type=Path, required=True)
    seal_parser = commands.add_parser("seal-attempt")
    seal_parser.add_argument("--request", type=Path, required=True)
    population_parser = commands.add_parser("seal-population")
    population_parser.add_argument("--batch-root", type=Path, required=True)
    population_parser.add_argument("--population", choices=("train", "val"), required=True)
    population_parser.add_argument("--batch-id", required=True)
    arguments = parser.parse_args()
    if arguments.command == "inspect-attempt":
        attempt = json.loads(arguments.attempt_manifest.read_text())
        authority = json.loads(arguments.expected_authority.read_text())
        print(json.dumps(validate_attempt(attempt, authority), sort_keys=True)); return
    if arguments.command == "seal-population":
        print(seal_measurement_validity(batch_root=arguments.batch_root,
            population=arguments.population, batch_id=arguments.batch_id)); return
    request = json.loads(arguments.request.read_text())
    print(seal_attempt_acceptance(batch_root=Path(request["batch_root"]),
        population=request["population"], batch_id=request["batch_id"], pair=request["pair"],
        logical_condition=request["logical_condition"], attempt_root=Path(request["attempt_root"]),
        prediction_artifacts=[Path(path) for path in request["prediction_artifacts"]],
        source_mda_gt=[Path(path) for path in request["source_mda_gt"]],
        minimal_mechanism_trace=Path(request["minimal_mechanism_trace"])
            if request.get("minimal_mechanism_trace") else None,
        packet_trace=Path(request["packet_trace"]) if request.get("packet_trace") else None,
        runtime_manifests=[Path(path) for path in request.get("runtime_manifests", [])],
        artifact_validated=request.get("artifact_validated") is True,
        runtime_gates_checked=request.get("runtime_gates_checked") is True,
        y00_reference_parity_checked=request.get("y00_reference_parity_checked")))


if __name__ == "__main__": main()
