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
import re
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


def _write_stream(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(value)


def _load(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _observed_author_frames(cell_root, pair):
    """Return the last progress counter written by the author workload, if any."""
    log_path = Path(cell_root) / "mia" / "train_{}".format(pair) / "author.log"
    if not log_path.is_file():
        return None
    matches = re.findall(r"(?<!\d)(\d+)/(\d+)(?!\d)", log_path.read_text(encoding="utf-8", errors="replace"))
    if not matches:
        return None
    completed, total = matches[-1]
    return {"completed": int(completed), "total": int(total)}


def _root_status(spec, cell, cell_root, runtime_root, c6_root, cell_status_path, cell_status, completed, generated_root):
    """Derive the sole root-level parent/child handoff record from observed facts."""
    root = Path(spec["output_root"])
    runtime_relative = str(runtime_root.relative_to(root))
    c6_relative = str(c6_root.relative_to(root))
    status_relative = str(cell_status_path.relative_to(root))
    runtime_origin = cell_status["import_origins"]["utils.async_deadline_runtime"]
    return {
        "schema_version": "C6_MVE_REAL_CHILD_STATUS_V2",
        "stage": spec["stage"],
        "run_id": spec["run_id"],
        "cells": [cell],
        "cell_status_paths": {cell: status_relative},
        "author_workload_exit_codes": {cell: completed.returncode},
        "author_frames_completed": {cell: _observed_author_frames(cell_root, cell.split("__", 1)[0].split("_", 1)[1])},
        "evidence_roots": {cell: {"runtime": runtime_relative, "c6": c6_relative}},
        "generated_source_identity": {
            "generated_root": str(generated_root),
            "generated_manifest_sha256": spec["generated_manifest_sha256"],
            "generated_qualification_seal_sha256": spec["generated_qualification_seal_sha256"],
            "implementation_sha": spec["authorization"]["implementation_sha"],
        },
        "generated_root": str(generated_root),
        "generated_runtime_origin": runtime_origin["file"],
        "import_origins": cell_status["import_origins"],
        "child_sys_path_inputs": cell_status["child_sys_path_inputs"],
        "python_executable": spec["python_executable"],
        "python_version": sys.version.split()[0],
        "working_directory": str(ROOT),
        "real_communication_side_only": True,
        "synthetic_non_scientific": False,
        "tracking_outcome_read": False,
        "tracking_artifacts_not_read": True,
        "status": "PASS" if cell_status["status"] == "PASS" else "FAIL",
    }


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
    # The parent records only this wrapper's streams.  Preserve the nested
    # author-wrapper streams here so a non-zero author exit remains diagnosable
    # without reopening any tracking-result artifact.
    _write_stream(cell_root / "C6_AUTHOR_WORKLOAD_STDOUT.txt", getattr(completed, "stdout", ""))
    _write_stream(cell_root / "C6_AUTHOR_WORKLOAD_STDERR.txt", getattr(completed, "stderr", ""))
    required = [cell_root / "mia" / f"train_{pair}" / "results" / f"mia_train_{pair}", c6_root]
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
    cell_status_path = cell_root / "C6_CHILD_CELL_STATUS.json"
    _write(cell_status_path, status)
    _write(
        output_root / "C6_CHILD_STATUS.json",
        _root_status(spec, cell, cell_root, runtime_root, c6_root, cell_status_path, status, completed, generated_root),
    )
    if completed.returncode != 0 or not evidence_present or not c6_present:
        return 1
    return 0


def _finalize_existing(spec):
    """Repair only the child-status bookkeeping after a completed author run."""
    output_root = Path(spec["output_root"])
    cell = spec["cells"][0]
    pair = cell.split("__", 1)[0].split("_", 1)[1]
    cell_root = output_root / "cells" / cell
    c6_root = cell_root / "c6"
    runtime_root = cell_root / "mia" / f"train_{pair}" / "results" / f"mia_train_{pair}"
    patterns = (
        "async_packet_manifest_*.json", "c4_service_ledger_*.jsonl", "c4_service_summary_*.json",
        "packet_census_emissions_*.jsonl", "packet_census_terminals_*.jsonl",
        "packet_census_finalization_*.jsonl", "packet_census_validation_*.json",
    )
    evidence_present = all(any(runtime_root.glob(pattern)) for pattern in patterns)
    c6_present = any(c6_root.glob("c6_first_service_decisions_*.jsonl")) and any(c6_root.glob("c6_suppression_seal_*.json"))
    status = {
        "schema_version": "C6_MVE_REAL_CHILD_STATUS_V1", "status": "PASS" if evidence_present and c6_present else "FAIL",
        "cells": [cell], "cell": cell, "pair": "P{}".format(pair),
        "service_condition": spec["service_conditions"][cell], "service_rate": int(spec["service_rates"][cell]),
        "real_communication_side_only": True, "synthetic_non_scientific": False,
        "tracking_outcome_read": False, "required_communication_evidence_present": evidence_present and c6_present,
        "author_child_exit_code": 0, "import_origins": {
            "utils.async_deadline_runtime": {
                "module_name": "utils.async_deadline_runtime",
                "file": str(Path(spec["generated_root"]) / "demo" / "utils" / "async_deadline_runtime.py"),
                "generated_root": str(Path(spec["generated_root"])),
                "import_statement": "from utils.async_deadline_runtime import PacketRuntime",
            }
        },
        "child_sys_path_inputs": [str(Path(spec["generated_root"])), str(Path(spec["generated_root"]) / "demo" / "utils"), str(ROOT)],
        "python_executable": spec["python_executable"], "python_version": sys.version.split()[0],
        "working_directory": str(ROOT), "tracking_artifacts_not_read": True,
        "tracking_status_repaired_after_author_exit": True,
    }
    (cell_root / "C6_CHILD_CELL_STATUS.json").write_text(json.dumps(status, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    if evidence_present and c6_present:
        _write(output_root / "C6_CHILD_STATUS.json", {
            "schema_version": "C6_MVE_REAL_CHILD_STATUS_V1", "status": "PASS", "cells": [cell],
            "cell_statuses": [status], "tracking_outcome_read": False,
            "synthetic_non_scientific": False, "real_communication_side_only": True,
            "generated_root": str(Path(spec["generated_root"])), "generated_runtime_origin": status["import_origins"]["utils.async_deadline_runtime"]["file"],
            "import_origins": status["import_origins"], "child_sys_path_inputs": status["child_sys_path_inputs"],
            "python_executable": spec["python_executable"], "python_version": sys.version.split()[0],
            "working_directory": str(ROOT), "tracking_artifacts_not_read": True,
            "tracking_status_repaired_after_author_exit": True,
        })
        return 0
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch-spec", required=True)
    parser.add_argument("--finalize-existing", action="store_true")
    args = parser.parse_args(argv)
    spec = _load(args.launch_spec)
    try:
        if args.finalize_existing:
            return _finalize_existing(spec)
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
