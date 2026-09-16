#!/usr/bin/env python3
"""Real C6 communication-side child adapter for the accepted author launcher.

This process delegates the actual data-path execution to the frozen
``run_mdmt_mia_author_sync.sh`` entry point.  It only records communication
evidence provenance and never opens tracking metric/result artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")


def _load(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _run(spec):
    output_root = Path(spec["output_root"])
    cell = spec["cells"][0]
    pair = cell.split("__", 1)[0].split("_", 1)[1]
    cell_root = output_root / "cells" / cell
    c6_root = cell_root / "c6"
    c6_root.mkdir(parents=True, exist_ok=False)
    generated_root = Path(spec["generated_root"]).resolve()
    mia_root = generated_root.parents[1]
    child_env = dict(os.environ)
    for key in tuple(child_env):
        if key.startswith("MIA_") or key in {"DEVICE", "PYTHONHASHSEED", "PYTHONNOUSERSITE", "PYTHONPATH", "MPLCONFIGDIR"}:
            child_env.pop(key, None)
    child_env.update({str(k): str(v) for k, v in spec["child_environment"].items()})
    child_env.update({
        "MIA_ROOT": str(mia_root),
        "MIA_SOURCE_ROOT": str(generated_root),
        "MIA_OUTPUT_ROOT": str(cell_root),
        "MIA_RUN_INPUT_ROOT": str(output_root / "run_input" / cell),
        "MIA_C4_SERVICE_CONFIG": json.dumps({
            "mode": "fifo",
            "condition": spec["service_conditions"][cell],
            "rate_logical_bytes_per_frame": int(spec["service_rates"][cell]),
            "ledger_enabled": True,
            "run_id": spec["run_id"],
            "pair_id": pair,
        }, sort_keys=True, separators=(",", ":")),
        "MIA_C6_SUPPRESSION_CONFIG": json.dumps({
            "enabled": True,
            "run_id": spec["run_id"],
            "output_dir": str(c6_root),
        }, sort_keys=True, separators=(",", ":")),
        "MIA_PACKET_CENSUS_RUN_ID": spec["run_id"],
        "MIA_ACTIVE_PACKET_STAGES": "all",
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "MPLCONFIGDIR": str(output_root / "_runtime_cache" / "matplotlib"),
        "PYTHONPATH": os.pathsep.join((str(generated_root), str(generated_root / "demo" / "utils"), str(ROOT))),
    })
    command = ["bash", str(ROOT / "scripts" / "run_mdmt_mia_author_sync.sh"), "mia", "train", pair]
    completed = subprocess.run(command, cwd=str(ROOT), env=child_env, capture_output=True, text=True, check=False)
    required = [
        cell_root / "mia" / "train_{}" / "results" / "mia_train_{}".format(pair, pair),
        c6_root,
    ]
    runtime_root = required[0]
    communication_patterns = (
        "async_packet_manifest_*.json", "c4_service_ledger_*.jsonl", "c4_service_summary_*.json",
        "packet_census_emissions_*.jsonl", "packet_census_terminals_*.jsonl",
        "packet_census_finalization_*.jsonl", "packet_census_validation_*.json",
    )
    evidence_present = all(any(runtime_root.glob(pattern)) for pattern in communication_patterns)
    c6_present = any(c6_root.glob("c6_first_service_decisions_*.jsonl")) and any(c6_root.glob("c6_suppression_seal_*.json"))
    status = {
        "schema_version": "C6_MVE_REAL_CHILD_STATUS_V1",
        "status": "PASS" if completed.returncode == 0 and evidence_present and c6_present else "FAIL",
        "cells": [cell],
        "cell": cell,
        "pair": "P{}".format(pair),
        "service_condition": spec["service_conditions"][cell],
        "service_rate": int(spec["service_rates"][cell]),
        "real_communication_side_only": True,
        "synthetic_non_scientific": False,
        "tracking_outcome_read": False,
        "required_communication_evidence_present": evidence_present and c6_present,
        "author_child_exit_code": completed.returncode,
        "import_origins": {
            "utils.async_deadline_runtime": {
                "module_name": "utils.async_deadline_runtime",
                "file": str(generated_root / "demo" / "utils" / "async_deadline_runtime.py"),
                "generated_root": str(generated_root),
                "import_statement": "from utils.async_deadline_runtime import PacketRuntime",
            }
        },
        "child_sys_path_inputs": [str(generated_root), str(generated_root / "demo" / "utils"), str(ROOT)],
        "python_executable": spec["python_executable"],
        "python_version": sys.version.split()[0],
        "working_directory": str(ROOT),
        "tracking_artifacts_not_read": True,
    }
    _write(cell_root / "C6_CHILD_CELL_STATUS.json", status)
    if completed.returncode != 0 or not evidence_present or not c6_present:
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch-spec", required=True)
    args = parser.parse_args(argv)
    spec = _load(args.launch_spec)
    try:
        return _run(spec)
    except Exception as exc:
        output_root = Path(spec["output_root"])
        cell = spec["cells"][0]
        try:
            _write(output_root / "cells" / cell / "C6_CHILD_CELL_STATUS.json", {
                "schema_version": "C6_MVE_REAL_CHILD_STATUS_V1",
                "status": "FAIL", "error_type": type(exc).__name__, "error": str(exc)[:300],
                "real_communication_side_only": True, "synthetic_non_scientific": False,
                "tracking_outcome_read": False,
            })
        except Exception:
            pass
        print("C6 real child failed: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
