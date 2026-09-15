#!/usr/bin/env python3
"""Fresh-process synthetic C6 fixture used by the production launch boundary."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import sys
import traceback
from pathlib import Path

import numpy as np


CELLS = (
    "pair_23__FIFO_mild",
    "pair_23__FIFO_strong",
    "pair_44__FIFO_moderate",
    "pair_66__FIFO_mild",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(canonical(value) + "\n")
    else:
        path.write_text(canonical(value) + "\n", encoding="utf-8")


def tiny_sequence():
    """Return the deterministic packet-shape contract, without runtime state."""
    suppressible = {
        "kind": "id_state",
        "source_state_version": 1,
        "payload": {"stage": "fixture", "remap_events": [], "confirmed_ids": []},
    }
    serviceable = {
        "kind": "id_state",
        "source_state_version": 2,
        "payload": {"stage": "fixture", "remap_events": [], "confirmed_ids": [42]},
    }
    supplement = {
        "kind": "supplement",
        "source_state_version": 3,
        "payload": {"stage": "fixture", "note": "unaffected-by-c6"},
    }
    wire = lambda value: len(canonical(value).encode("utf-8"))
    return {
        "schema_version": "C6_TINY_RUNTIME_FIXTURE_V2",
        "sequence_name": "tiny",
        "packets": [suppressible, serviceable, supplement],
        "same_frame_reuse_budget_bytes": wire(suppressible) + wire(supplement),
        "serviceable_confirmed_id_count": 10000,
        "synthetic_non_scientific": True,
    }


def _load_generated(root):
    path = Path(root) / "demo/utils/async_deadline_runtime.py"
    spec = importlib.util.spec_from_file_location("c6_tiny_generated_runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_origin(name):
    try:
        found = importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError):
        found = None
    try:
        version = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        version = "NOT_INSTALLED"
    return {"file": None if found is None else (found.origin or "NAMESPACE"), "version": version}


def _run_cell(spec, module, cell):
    output = Path(spec["output_root"]) / "cells" / cell
    runtime_root = output / "synthetic"
    c6_root = output / "c6"
    os.environ["MIA_C4_SERVICE_CONFIG"] = json.dumps(
        {
            "mode": "fifo",
            "condition": spec["service_conditions"][cell],
            "rate_logical_bytes_per_frame": int(spec["service_rates"][cell]),
            "ledger_enabled": True,
            "run_id": spec["run_id"],
            "pair_id": cell,
        }
    )
    os.environ["MIA_C6_SUPPRESSION_CONFIG"] = json.dumps(
        {"enabled": True, "run_id": spec["run_id"], "output_dir": str(c6_root)}
    )
    os.environ["MIA_PACKET_CENSUS_RUN_ID"] = spec["run_id"]
    runtime = module.PacketRuntime(output, "synthetic", cell)
    rows = np.empty((0, 6), dtype=np.float32)
    runtime.begin_frame(0, rows, rows, [], [])
    runtime.deliver_id_state(0, "fixture", rows, rows, rows, rows, [], [], [], [], 0, 0)
    provider = runtime._c5_context_provider
    runtime._c5_context_provider = lambda *_args: provider(rows, rows, ())
    try:
        # A large but opaque confirmed-ID vector forces multiple FIFO slices;
        # it carries no detector, tracker, GT, or scientific result values.
        confirmed = list(range(10000))
        runtime.deliver_id_state(0, "fixture", rows, rows, rows, rows, [], [], [], confirmed, 0, 0)
    finally:
        runtime._c5_context_provider = provider
    runtime.deliver_supplement(0, "fixture", rows, rows, rows, rows, [], [], [], [], rows, rows)
    for frame in range(1, 8):
        runtime.begin_frame(frame, rows, rows, [], [])
    runtime.finalize()
    decisions = runtime._c6_suppression.records
    terminals = runtime._census.terminals
    emissions = runtime._census.emissions
    ledger = runtime._c4_service._events
    by_packet = lambda row: canonical(row.get("packet_id"))
    decision_by_id = {by_packet(row): row for row in decisions}
    suppressed = [key for key, row in decision_by_id.items() if row.get("whole_packet_currently_non_applicable")]
    serviceable = [key for key, row in decision_by_id.items() if not row.get("whole_packet_currently_non_applicable")]
    slices = [
        row for row in ledger
        if row.get("event_type") == "service_slice" and by_packet(row) in serviceable
    ]
    serviceable_terminal = [
        row for row in terminals
        if by_packet(row) in serviceable
    ]
    status = {
        "schema_version": "C6_TINY_CELL_STATUS_V1",
        "cell": cell,
        "status": "PASS",
        "synthetic_non_scientific": True,
        "decision_count_for_suppressed": len(suppressed),
        "decision_count_for_serviceable": len(serviceable),
        "positive_service_slice_count": len(slices),
        "serviceable_terminal_classes": sorted(row.get("terminal_class") for row in serviceable_terminal),
        "suppression_event_count": sum(
            row.get("event_type") == "suppression" and by_packet(row) in suppressed for row in ledger
        ),
        "generated_runtime_origin": str(Path(module.__file__).resolve()),
    }
    if spec.get("fault") == "missing_cell_end" and cell == CELLS[-1]:
        return status
    _write_json(output / "C6_CHILD_CELL_STATUS.json", status, exclusive=True)
    return status


def run(spec):
    generated = Path(spec["generated_root"])
    if sha(Path(spec["fixture_path"])) != spec["fixture_sha256"]:
        raise RuntimeError("fixture source identity mismatch")
    module = _load_generated(generated)
    statuses = [_run_cell(spec, module, cell) for cell in spec["cells"]]
    fault = spec.get("fault", "")
    if fault == "missing_child_evidence":
        target = Path(spec["output_root"]) / "cells" / spec["cells"][0] / "synthetic"
        next(target.glob("packet_census_validation_*.json")).unlink()
    elif fault == "partial_child_evidence":
        target = Path(spec["output_root"]) / "cells" / spec["cells"][0] / "synthetic"
        ledger = next(target.glob("c4_service_ledger_*.jsonl"))
        ledger.write_text(ledger.read_text(encoding="utf-8")[:-17], encoding="utf-8")
    _write_json(
        Path(spec["output_root"]) / "C6_CHILD_STATUS.json",
        {
            "schema_version": "C6_TINY_CHILD_STATUS_V1",
            "status": "PASS",
            "cells": list(spec["cells"]),
            "cell_statuses": statuses,
            "fixture_sha256": spec["fixture_sha256"],
            "generated_root": str(generated),
            "generated_runtime_origin": str(Path(module.__file__).resolve()),
            "import_origins": {
                "mmcv": _module_origin("mmcv"),
                "mmdet": _module_origin("mmdet"),
                "mmtrack": _module_origin("mmtrack"),
                "utils.async_deadline_runtime": {
                    "file": str(Path(module.__file__).resolve()),
                    "generated_root": str(generated),
                },
            },
            "synthetic_non_scientific": True,
        },
        exclusive=True,
    )
    if fault == "nonzero_exit":
        return 7
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch-spec", required=True)
    args = parser.parse_args(argv)
    spec = json.loads(Path(args.launch_spec).read_text(encoding="utf-8"))
    try:
        return run(spec)
    except Exception as exc:
        try:
            _write_json(
                Path(spec["output_root"]) / "C6_CHILD_STATUS.json",
                {
                    "schema_version": "C6_TINY_CHILD_STATUS_V1",
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:240],
                    "synthetic_non_scientific": True,
                },
                exclusive=True,
            )
        except Exception:
            pass
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
