#!/usr/bin/env python3
"""Outcome-blind attempt acceptance and population-validity sealing CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tracking.mdmt_mia_locked_d1_validity import (produce_artifact_validation,
    produce_runtime_gates_checked, produce_y00_reference_parity,
    seal_attempt_acceptance, seal_measurement_validity, validate_attempt)


def main() -> None:
    parser = argparse.ArgumentParser(); commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect-attempt")
    inspect_parser.add_argument("--attempt-manifest", type=Path, required=True)
    inspect_parser.add_argument("--expected-authority", type=Path, required=True)
    for command in ("validate-artifacts", "check-runtime-gates", "check-y00-parity", "seal-attempt"):
        commands.add_parser(command).add_argument("--request", type=Path, required=True)
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
    common = dict(batch_root=Path(request["batch_root"]), population=request["population"],
        batch_id=request["batch_id"], pair=request["pair"], attempt_root=Path(request["attempt_root"]))
    if arguments.command == "validate-artifacts":
        print(produce_artifact_validation(**common, logical_condition=request["logical_condition"],
            prediction_artifacts=[Path(p) for p in request["prediction_artifacts"]],
            source_mda_gt=[Path(p) for p in request["source_mda_gt"]],
            minimal_mechanism_trace=Path(request["minimal_mechanism_trace"]) if request.get("minimal_mechanism_trace") else None,
            packet_trace=Path(request["packet_trace"]) if request.get("packet_trace") else None,
            runtime_packet_trace=Path(request["runtime_packet_trace"]) if request.get("runtime_packet_trace") else None,
            runtime_manifests=[Path(p) for p in request["runtime_manifests"]])); return
    if arguments.command == "check-runtime-gates":
        print(produce_runtime_gates_checked(**common, logical_condition=request["logical_condition"],
            runtime_manifests=[Path(p) for p in request["runtime_manifests"]],
            runtime_packet_trace=Path(request["runtime_packet_trace"]) if request.get("runtime_packet_trace") else None)); return
    if arguments.command == "check-y00-parity":
        print(produce_y00_reference_parity(**common, reference_attempt_root=Path(request["reference_attempt_root"]),
            reference_artifacts=[Path(p) for p in request["reference_artifacts"]], packetized_artifacts=[Path(p) for p in request["packetized_artifacts"]])) ; return
    print(seal_attempt_acceptance(**common, logical_condition=request["logical_condition"],
        artifact_validation_evidence=Path(request["artifact_validation_evidence"]),
        runtime_gate_evidence=Path(request["runtime_gate_evidence"]),
        y00_parity_evidence=Path(request["y00_parity_evidence"]) if request.get("y00_parity_evidence") else None))


if __name__ == "__main__": main()
