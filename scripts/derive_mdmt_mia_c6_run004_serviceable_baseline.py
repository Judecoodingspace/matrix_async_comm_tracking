#!/usr/bin/env python3
"""Read-only, fail-closed C6 Run004 serviceable-byte baseline derivation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class BaselineError(RuntimeError):
    pass


PACKET_ID_KEYS = frozenset(("census_run_id", "sequence_name", "runtime_instance_id", "emission_ordinal"))
CELL_ORDER = ("pair_23__FIFO_mild", "pair_23__FIFO_strong", "pair_44__FIFO_moderate", "pair_66__FIFO_mild")
RUN_ID = "c5_shadow_census_20260914_004"
CONTRACT_AUTHORITY = "989ee15285866b119a643f1f1ccdf52d2d02009f"
PLAN_AUTHORITY = "93f44de70c4540afa0f3044aa066a0ed894648e9"
RUN_END_SHA256 = "d0941f0c487c0e63324f999d9cdb2101f7013fa15b229459b09f272bdd3f9a05"
SHADOW_SEAL_SHA256 = {"pair_23__FIFO_mild": "d46e0a910ecb2cbe0cce5cb5131ee6dea010fdd34d8194a2dbab562dca0688b9", "pair_23__FIFO_strong": "bd53485bcdd93b7b276426900360d7341333bf960ad714f8776831473c098226", "pair_44__FIFO_moderate": "ec530381f35090812dd60130246c367e2873b72c337a849fd10c3b63e407deab", "pair_66__FIFO_mild": "063ba60e148d04b90bf9fbc60353e685d0caf2d38fc45ec10e28b633e9d435a9"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _strict_json(raw):
    def no_duplicates(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BaselineError("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=no_duplicates)
    except (TypeError, ValueError) as exc:
        raise BaselineError("malformed JSON") from exc


def _jsonl(path):
    if not Path(path).is_file():
        raise BaselineError("missing evidence file: {}".format(path))
    records = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line:
            value = _strict_json(line)
            if not isinstance(value, dict):
                raise BaselineError("non-object JSONL record at {}".format(number))
            records.append(value)
    return records


def packet_key(packet_id):
    if not isinstance(packet_id, dict) or set(packet_id) != PACKET_ID_KEYS:
        raise BaselineError("invalid packet identity")
    if not isinstance(packet_id["emission_ordinal"], int) or packet_id["emission_ordinal"] < 1:
        raise BaselineError("invalid packet emission ordinal")
    return _canonical(packet_id)


def _classification_index(rows):
    index = {}
    for row in rows:
        # Shadow owns the classification and byte size, not the wire digest.
        required = {"packet_id", "channel", "whole_packet_currently_non_applicable", "JSON_WIRE_BYTES", "frame", "schema_version"}
        if not isinstance(row, dict) or not required <= set(row) or row["channel"] != "id_state":
            raise BaselineError("incomplete or invalid classification")
        key = packet_key(row["packet_id"])
        if key in index:
            raise BaselineError("duplicate classification packet key")
        if not isinstance(row["whole_packet_currently_non_applicable"], bool):
            raise BaselineError("invalid classification boolean")
        if not isinstance(row["JSON_WIRE_BYTES"], int) or row["JSON_WIRE_BYTES"] < 0:
            raise BaselineError("invalid classification bytes")
        index[key] = row
    return index


def derive_serviceable_bytes(shadow_rows, ledger_rows):
    """Exact packet-key join: each classified packet has zero-or-more positive slices."""
    classes = _classification_index(shadow_rows)
    served = dict.fromkeys(classes, 0)
    for row in ledger_rows:
        if row.get("event_type") != "service_slice" or row.get("channel") != "id_state":
            continue
        required = {"packet_id", "bytes_served", "JSON_WIRE_BYTES", "wire_digest"}
        if not required <= set(row):
            raise BaselineError("incomplete service slice")
        key = packet_key(row["packet_id"])
        if key not in classes:
            raise BaselineError("service slice has no classification")
        if not isinstance(row["bytes_served"], int) or row["bytes_served"] <= 0:
            raise BaselineError("invalid service slice bytes")
        cls = classes[key]
        if cls["JSON_WIRE_BYTES"] != row["JSON_WIRE_BYTES"]:
            raise BaselineError("classification/service byte reconciliation failure")
        served[key] += row["bytes_served"]
        if served[key] > cls["JSON_WIRE_BYTES"]:
            raise BaselineError("service exceeds wire bytes")
    return sum(served[key] for key, row in classes.items() if not row["whole_packet_currently_non_applicable"])


def derive_cell(shadow_rows, ledger_rows, emissions, census_rows):
    classes = _classification_index(shadow_rows)
    terminals = {}
    for row in census_rows:
        if row.get("record_type") != "PACKET_TERMINAL" or row.get("channel") != "id_state":
            continue
        key = packet_key(row.get("packet_id"))
        if key in terminals:
            raise BaselineError("duplicate id-state census terminal")
        terminals[key] = row
    emitted = {packet_key(row.get("packet_id")): row for row in emissions
               if row.get("record_type") == "PACKET_EMISSION" and row.get("channel") == "id_state"}
    # Started/classified packets are a subset: horizon-pending emissions need
    # not have reached TRUE first service and therefore need no Shadow row.
    if not set(classes) <= set(emitted) or not set(classes) <= set(terminals):
        raise BaselineError("classified packet lacks census lifecycle identity")
    for key, cls in classes.items():
        if cls["JSON_WIRE_BYTES"] != emitted[key].get("JSON_WIRE_BYTES"):
            raise BaselineError("Shadow/census emission byte contradiction")
    return {"classification_count": len(classes),
            "serviceable_packet_count": sum(not x["whole_packet_currently_non_applicable"] for x in classes.values()),
            "serviceable_id_state_serviced_bytes": derive_serviceable_bytes(shadow_rows, ledger_rows),
            "classification_digest": _sha([classes[key] for key in sorted(classes)])}


def _find_one(root, pattern):
    paths = sorted(Path(root).glob(pattern))
    if len(paths) != 1:
        raise BaselineError("expected exactly one {} under {}".format(pattern, root))
    return paths[0]


def _raw_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _verify_authority(source, authorization_path, expected_run_id=RUN_ID, expected_seals=SHADOW_SEAL_SHA256, expected_run_end=RUN_END_SHA256):
    run_end = source / "RUN_END.json"
    if not run_end.is_file() or _raw_sha256(run_end) != expected_run_end:
        raise BaselineError("RUN_END authority mismatch")
    end = _strict_json(run_end.read_text(encoding="utf-8"))
    if end.get("run_id") != expected_run_id or end.get("status") != "COMPLETE" or end.get("scientific_cell_count") != 4:
        raise BaselineError("RUN_END status mismatch")
    auth = _strict_json(Path(authorization_path).read_text(encoding="utf-8"))
    if auth.get("run_id") != expected_run_id or not auth.get("issued_for_exact_run"):
        raise BaselineError("Run004 authorization mismatch")
    for cell in CELL_ORDER:
        seal = _find_one(source / "shadow" / cell, "c5_shadow_seal_*.json")
        if _raw_sha256(seal) != expected_seals[cell]:
            raise BaselineError("Shadow seal authority mismatch: " + cell)


def derive_run004(run004_root, output_dir, contract_sha, plan_sha, authorization_path=None,
                  expected_run_id=RUN_ID, expected_seals=SHADOW_SEAL_SHA256, expected_run_end=RUN_END_SHA256):
    source, target = Path(run004_root).resolve(), Path(output_dir).resolve()
    if not source.is_dir():
        raise BaselineError("Run004 evidence root does not exist")
    if target == source or source in target.parents:
        raise BaselineError("refusing to write inside Run004 evidence root")
    if target.exists():
        raise BaselineError("exclusive output root already exists")
    if expected_run_id == RUN_ID and (contract_sha != CONTRACT_AUTHORITY or plan_sha != PLAN_AUTHORITY):
        raise BaselineError("Contract/Plan authority mismatch")
    if authorization_path is None:
        authorization_path = Path(__file__).resolve().parents[1] / "summary_md/communication/c5_shadow_census_formal_execution_authorization/C5_SHADOW_CENSUS_EXECUTION_AUTHORIZATION_RUN_004.json"
    _verify_authority(source, authorization_path, expected_run_id, expected_seals, expected_run_end)
    cells = []
    for cell in CELL_ORDER:
        shadow_root, runtime_root = source / "shadow" / cell, source / "runtime" / cell
        if not shadow_root.is_dir() or not runtime_root.is_dir(): raise BaselineError("missing required cell: {}".format(cell))
        cells.append({"cell": cell, **derive_cell(
            _jsonl(_find_one(shadow_root, "c5_shadow_records_*.jsonl")),
            _jsonl(_find_one(runtime_root, "**/c4_service_ledger_*.jsonl")),
            _jsonl(_find_one(runtime_root, "**/packet_census_emissions_*.jsonl")),
            _jsonl(_find_one(runtime_root, "**/packet_census_terminals_*.jsonl")))})
    context = {"schema_version": "C6_RUN004_BASELINE_CONTEXT_V1", "contract_sha": str(contract_sha),
               "plan_sha": str(plan_sha), "cell_order": list(CELL_ORDER), "source_evidence_root_name": source.name}
    results = {"schema_version": "C6_RUN004_BASELINE_RESULTS_V1", "cells": cells,
               "total_serviceable_id_state_serviced_bytes": sum(x["serviceable_id_state_serviced_bytes"] for x in cells), "status": "PASS"}
    payload = {"context_sha256": _sha(context), "results_sha256": _sha(results), "cell_order": list(CELL_ORDER), "status": "PASS"}
    seal = {"schema_version": "C6_RUN004_BASELINE_SEAL_V1", "sealed_payload": payload, "seal_sha256": _sha(payload)}
    target.mkdir(parents=True, exist_ok=False)
    for name, value in (("C6_RUN004_BASELINE_CONTEXT.json", context), ("C6_RUN004_BASELINE_RESULTS.json", results), ("C6_RUN004_BASELINE_SEAL.json", seal)):
        (target / name).write_text(_canonical(value) + "\n", encoding="utf-8")
    (target / "C6_RUN004_BASELINE_REPORT.md").write_text("# C6 Run004 Serviceable Baseline\n\nMechanical derivation status: PASS.\n", encoding="utf-8")
    return {"context": context, "results": results, "seal": seal}


def preflight_run004(run004_root, contract_sha, plan_sha, authorization_path=None):
    """Structural-only real-evidence compatibility check; does not derive totals."""
    source = Path(run004_root).resolve()
    if contract_sha != CONTRACT_AUTHORITY or plan_sha != PLAN_AUTHORITY:
        raise BaselineError("Contract/Plan authority mismatch")
    if authorization_path is None:
        authorization_path = Path(__file__).resolve().parents[1] / "summary_md/communication/c5_shadow_census_formal_execution_authorization/C5_SHADOW_CENSUS_EXECUTION_AUTHORIZATION_RUN_004.json"
    _verify_authority(source, authorization_path)
    required_shadow = {"packet_id", "channel", "JSON_WIRE_BYTES", "whole_packet_currently_non_applicable", "frame", "schema_version"}
    required_ledger = {"packet_id", "channel", "event_type", "bytes_served", "JSON_WIRE_BYTES", "wire_digest"}
    for cell in CELL_ORDER:
        shadow = _jsonl(_find_one(source / "shadow" / cell, "c5_shadow_records_*.jsonl"))
        ledger = _jsonl(_find_one(source / "runtime" / cell, "**/c4_service_ledger_*.jsonl"))
        emissions = _jsonl(_find_one(source / "runtime" / cell, "**/packet_census_emissions_*.jsonl"))
        terminals = _jsonl(_find_one(source / "runtime" / cell, "**/packet_census_terminals_*.jsonl"))
        if not shadow or not emissions or not terminals or any(not required_shadow <= set(row) for row in shadow):
            raise BaselineError("Shadow/census structural schema mismatch")
        if any(row.get("event_type") == "service_slice" and row.get("channel") == "id_state" and not required_ledger <= set(row) for row in ledger):
            raise BaselineError("ledger structural schema mismatch")
        for row in shadow: packet_key(row["packet_id"])
    return {"status": "PASS", "mode": "STRUCTURAL_ONLY", "cell_count": len(CELL_ORDER)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run004-evidence-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--contract-sha", required=True)
    parser.add_argument("--plan-sha", required=True)
    parser.add_argument("--authorization-path")
    args = parser.parse_args(argv)
    print(_canonical(derive_run004(args.run004_evidence_root, args.output_dir, args.contract_sha, args.plan_sha, args.authorization_path)))


if __name__ == "__main__":
    main()
