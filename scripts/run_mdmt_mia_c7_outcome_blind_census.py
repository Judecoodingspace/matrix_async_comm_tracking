#!/usr/bin/env python3
"""C7 Batch B parent launcher and atomic packaging boundary.

The CLI in this implementation phase accepts synthetic/non-scientific inputs
only.  Real-path command construction is implemented in the child and can be
mechanically dry-run, but real input execution requires separate governance.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tracking.mdmt_mia_c7_batch_b_package import (
    atomic_write_json,
    build_batch_b_manifest,
    write_cell_transaction,
    write_selection_package,
)
from tracking.mdmt_mia_c7_batch_b_schema import authority_bindings, sha256_file
from tracking.mdmt_mia_c7_batch_b_validator import read_json, read_jsonl


CHILD_PATH = ROOT / "scripts/run_mdmt_mia_c7_real_child.py"


class C7LauncherError(RuntimeError):
    pass


def source_hash_inventory() -> dict[str, str]:
    aggregator = ROOT / "src/tracking/mdmt_mia_c7_batch_b.py"
    return {
        "runtime": sha256_file(ROOT / "src/tracking/mdmt_mia_async_deadline_runtime.py"),
        "batch_a_producer": sha256_file(ROOT / "src/tracking/mdmt_mia_c7_census.py"),
        "batch_a_validator": sha256_file(ROOT / "src/tracking/mdmt_mia_c7_validator.py"),
        "batch_b_schema": sha256_file(ROOT / "src/tracking/mdmt_mia_c7_batch_b_schema.py"),
        "batch_b_aggregator": sha256_file(aggregator),
        "batch_b_selector": sha256_file(aggregator),
        "batch_b_validator": sha256_file(ROOT / "src/tracking/mdmt_mia_c7_batch_b_validator.py"),
        "batch_b_package": sha256_file(ROOT / "src/tracking/mdmt_mia_c7_batch_b_package.py"),
        "launcher": sha256_file(Path(__file__)),
        "child": sha256_file(CHILD_PATH),
    }


def build_frozen_manifest(
    *, run_id: str, output_root: Path | str, batch_b_implementation_sha: str,
    input_identity: Mapping[str, Any], config_identity: Mapping[str, Any],
    synthetic_non_scientific: bool,
) -> dict[str, Any]:
    return build_batch_b_manifest(
        run_id=run_id,
        output_root=output_root,
        batch_b_implementation_sha=batch_b_implementation_sha,
        source_hashes=source_hash_inventory(),
        input_identity=input_identity,
        config_identity=config_identity,
        synthetic_non_scientific=synthetic_non_scientific,
    )


def controlled_environment() -> dict[str, str]:
    environment = {
        key: value for key, value in os.environ.items()
        if not key.startswith("MIA_") and not key.startswith("MDMT_MIA_C6")
    }
    environment.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(SRC),
    })
    return environment


def execute_synthetic_launch(
    *, output_root: Path | str, manifest: Mapping[str, Any],
    synthetic_cell: Mapping[str, Any], expected_frame_domain: Sequence[int],
    window_source: Path | str, qualifications: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run the child/writer/validator/selector path using synthetic inputs only."""
    if manifest.get("synthetic_non_scientific") is not True:
        raise C7LauncherError("synthetic launch requires synthetic manifest")
    output = Path(output_root).resolve()
    operational = output / "operational"
    child_root = operational / "child"
    operational.mkdir(parents=True, exist_ok=True)
    child_spec = {
        "schema_version": "C7_CHILD_SPEC_V1",
        "mode": "SYNTHETIC_NON_SCIENTIFIC",
        "synthetic_non_scientific": True,
        "authorities": authority_bindings(),
        "run_id": manifest.get("run_id"),
        "cell": dict(synthetic_cell),
        "window_source": str(Path(window_source).resolve()),
        "output_root": str(child_root),
    }
    spec_path = operational / "child_spec.json"
    atomic_write_json(spec_path, child_spec)
    completed = subprocess.run(
        [sys.executable, str(CHILD_PATH), "--spec", str(spec_path)],
        cwd=ROOT,
        env=controlled_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise C7LauncherError("synthetic child failed")
    child_status = read_json(child_root / "CHILD_STATUS.json")
    if child_status.get("status") != "PASS" or child_status.get("real_input_executed") is not False:
        raise C7LauncherError("synthetic child status mismatch")
    windows = read_jsonl(child_root / "windows.jsonl")
    cell_result = write_cell_transaction(
        output_root=output,
        manifest=manifest,
        cell=synthetic_cell,
        expected_frame_domain=expected_frame_domain,
        windows=windows,
        synthetic_non_scientific=True,
    )
    package_result = write_selection_package(
        output_root=output, manifest=manifest, qualifications=qualifications)
    result = {
        "schema_version": "C7_SYNTHETIC_E2E_STATUS_V1",
        "status": "PASS",
        "synthetic_non_scientific": True,
        "child_status": "PASS",
        "cell_transaction_status": cell_result["status"],
        "package_transaction_status": package_result["status"],
        "seal_reproduced": bool(
            cell_result["seal_reproduced"] and package_result["seal_reproduced"]),
        "real_input_executed": False,
    }
    atomic_write_json(operational / "SYNTHETIC_E2E_STATUS.json", result)
    return result


def dry_run_real_launcher_path(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Mechanically exercise the real parent/child/wrapper path without execution."""
    child_spec = dict(spec)
    child_spec["mode"] = "REAL_C7_CELL"
    child_spec["dry_run"] = True
    child_spec["real_c7_scientific_input_execution_authorized"] = False
    child_spec["authorities"] = authority_bindings()
    output_root = Path(child_spec["output_root"]).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    spec_path = output_root / "real_path_dry_run_spec.json"
    atomic_write_json(spec_path, child_spec)
    completed = subprocess.run(
        [sys.executable, str(CHILD_PATH), "--spec", str(spec_path)],
        cwd=ROOT,
        env=controlled_environment(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise C7LauncherError("real launcher path dry-run failed")
    status = read_json(output_root / "CHILD_STATUS.json")
    if status.get("status") != "PATH_VALID" or status.get("real_input_executed") is not False:
        raise C7LauncherError("real launcher path dry-run status mismatch")
    return status


def _load(path: Path | str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise C7LauncherError("launch spec must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    args = parser.parse_args(argv)
    spec = _load(args.spec)
    if spec.get("mode") != "SYNTHETIC_NON_SCIENTIFIC":
        raise C7LauncherError("Batch B CLI execution is synthetic-only")
    manifest = _load(spec["manifest_path"])
    qualifications = read_jsonl(spec["qualification_source"])
    execute_synthetic_launch(
        output_root=spec["output_root"],
        manifest=manifest,
        synthetic_cell=spec["cell"],
        expected_frame_domain=spec["expected_frame_domain"],
        window_source=spec["window_source"],
        qualifications=qualifications,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
