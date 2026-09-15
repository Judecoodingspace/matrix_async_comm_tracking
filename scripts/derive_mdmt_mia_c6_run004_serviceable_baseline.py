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
        required = {"packet_id", "channel", "whole_packet_currently_non_applicable", "JSON_WIRE_BYTES", "wire_digest"}
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
        for field in ("JSON_WIRE_BYTES", "wire_digest"):
            if field in cls and cls.get(field) != row.get(field):
                raise BaselineError("classification/service reconciliation failure")
        served[key] += row["bytes_served"]
        if served[key] > cls["JSON_WIRE_BYTES"]:
            raise BaselineError("service exceeds wire bytes")
    return sum(served[key] for key, row in classes.items() if not row["whole_packet_currently_non_applicable"])


def derive_cell(shadow_rows, ledger_rows, census_rows):
    classes = _classification_index(shadow_rows)
    terminals = {}
    for row in census_rows:
        if row.get("record_type") != "PACKET_TERMINAL" or row.get("channel") != "id_state":
            continue
        key = packet_key(row.get("packet_id"))
        if key in terminals:
            raise BaselineError("duplicate id-state census terminal")
        terminals[key] = row
    if set(classes) != set(terminals):
        raise BaselineError("classification/census packet key mismatch")
    return {"classification_count": len(classes),
            "serviceable_packet_count": sum(not x["whole_packet_currently_non_applicable"] for x in classes.values()),
            "serviceable_id_state_serviced_bytes": derive_serviceable_bytes(shadow_rows, ledger_rows),
            "classification_digest": _sha([classes[key] for key in sorted(classes)])}


def _find_one(root, pattern):
    paths = sorted(Path(root).glob(pattern))
    if len(paths) != 1:
        raise BaselineError("expected exactly one {} under {}".format(pattern, root))
    return paths[0]


def derive_run004(run004_root, output_dir, contract_sha, plan_sha):
    source, target = Path(run004_root).resolve(), Path(output_dir).resolve()
    if not source.is_dir():
        raise BaselineError("Run004 evidence root does not exist")
    if target == source or source in target.parents:
        raise BaselineError("refusing to write inside Run004 evidence root")
    if target.exists():
        raise BaselineError("exclusive output root already exists")
    cells = []
    for cell in CELL_ORDER:
        root = source / cell
        if not root.is_dir():
            raise BaselineError("missing required cell: {}".format(cell))
        cells.append({"cell": cell, **derive_cell(
            _jsonl(_find_one(root, "**/c5_first_service_decisions_*.jsonl")),
            _jsonl(_find_one(root, "**/service_ledger_*.jsonl")),
            _jsonl(_find_one(root, "**/packet_census_terminals_*.jsonl")))})
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run004-evidence-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--contract-sha", required=True)
    parser.add_argument("--plan-sha", required=True)
    args = parser.parse_args(argv)
    print(_canonical(derive_run004(args.run004_evidence_root, args.output_dir, args.contract_sha, args.plan_sha)))


if __name__ == "__main__":
    main()
