#!/usr/bin/env python3
"""C7 child boundary for synthetic proof and authorized real-input MVE."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tracking.mdmt_mia_c7_batch_b_package import atomic_write_json, atomic_write_jsonl
from tracking.mdmt_mia_c7_batch_b_schema import (
    ALLOWED_PARENT_ENV_KEYS,
    authority_bindings,
    inventory_generated_source,
    registered_cells,
    sha256_file,
    validate_mve_authorization,
)
from tracking.mdmt_mia_c7_batch_b_validator import read_jsonl


from tracking.mdmt_mia_c7_real_evidence import build_real_window_records

class C7ChildError(RuntimeError):
    pass


def _load(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C7ChildError("invalid child spec") from exc
    if not isinstance(value, dict):
        raise C7ChildError("child spec must be an object")
    return value


def _verify_authorities(spec: dict) -> None:
    if spec.get("authorities") != authority_bindings():
        raise C7ChildError("child authority mismatch")


def _environment_attestation(*, include_mve_bound_keys: bool = False) -> dict:
    bound_keys = [
        "PYTHONNOUSERSITE", "PYTHONHASHSEED", "PYTHONPATH",
        "MDMT_MIA_C7_CHILD_BOUNDARY",
    ]
    if include_mve_bound_keys:
        bound_keys.extend([
            "MDMT_MIA_C7_OBSERVATIONAL", "MDMT_MIA_C7_CAPACITY_BYTES",
            "MDMT_ROOT", "MIA_ROOT", "MIA_SOURCE_ROOT", "MIA_CONFIG",
            "MIA_RUN_INPUT_ROOT", "MIA_OUTPUT_ROOT", "DEVICE",
        ])
    return {
        "environment_keys": sorted(os.environ),
        "allowed_parent_environment": {
            key: os.environ[key] for key in ALLOWED_PARENT_ENV_KEYS if key in os.environ
        },
        "bound_environment": {
            key: os.environ.get(key) for key in bound_keys
        },
    }


def _run_git(*args: str, cwd: Path | str | None = None) -> str:
    """Run a git command and return stripped stdout."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd is not None else ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise C7ChildError("git command failed: {}".format(" ".join(args))) from exc
    return result.stdout.strip()


def _observe_git_identity(expected_root: Path | str) -> dict[str, str | bool]:
    """Observe actual repository identity and cleanliness.

    Returns the resolved repo root, current HEAD, and whether the worktree is
    clean.  The caller must reject any non-dry execution where the observed
    facts do not match the authorization or the expected repository root.
    """
    expected_root = Path(expected_root).resolve()
    repo_root = Path(_run_git("rev-parse", "--show-toplevel")).resolve()
    if repo_root != expected_root:
        raise C7ChildError(
            "execution repository root mismatch: {} != {}".format(
                repo_root, expected_root))
    head = _run_git("rev-parse", "HEAD")
    status = _run_git("status", "--porcelain", "--untracked-files=all")
    return {
        "repo_root": str(repo_root),
        "head": head,
        "worktree_clean": status == "",
    }


def _load_authorization(spec: dict, *, observed_head: str) -> dict:
    auth_path = spec.get("mve_authorization_path")
    if not auth_path:
        raise C7ChildError("MVE authorization path is required for non-dry execution")
    try:
        authorization = json.loads(Path(auth_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C7ChildError("invalid MVE authorization file") from exc
    try:
        return validate_mve_authorization(
            authorization, execution_harness_head=observed_head)
    except ValueError as exc:
        raise C7ChildError("MVE authorization validation failed: {}".format(exc)) from exc


def _validate_authorization_scope(spec: dict, authorization: dict) -> None:
    cells_by_id = {cell["cell_id"]: cell for cell in registered_cells()}
    expected_cell = cells_by_id[authorization["mve_cell_id"]]
    cell = spec.get("cell")
    if not isinstance(cell, dict) or set(cell) != set(expected_cell):
        raise C7ChildError("MVE child cell schema does not match canonical registered cell")
    for key, expected_value in expected_cell.items():
        if cell[key] != expected_value:
            raise C7ChildError(
                "MVE child cell {} does not match canonical registered cell".format(key))
    checks = [
        (authorization["mve_run_id"], spec.get("run_id"), "run_id"),
        (authorization["mve_cell_id"], cell["cell_id"], "cell_id"),
        (authorization["pair_id"], cell["pair_id"], "pair_id"),
        (authorization["capacity_id"], cell["capacity_id"], "capacity_id"),
        (authorization["split"], spec.get("split"), "split"),
        (authorization["output_root"], str(Path(spec["output_root"]).resolve()), "output_root"),
    ]
    for auth_value, spec_value, label in checks:
        if auth_value != spec_value:
            raise C7ChildError(
                "MVE authorization {} mismatch: {} != {}".format(
                    label, auth_value, spec_value))

    if spec.get("mode") != "REAL_C7_EVIDENCE_CELL":
        raise C7ChildError("MVE authorization requires REAL_C7_EVIDENCE_CELL mode")


def _materialize_generated_source(authorization: dict, *, c7_evidence: bool = False) -> dict:
    """Run the authorized generated-source preparer and inventory result."""
    preparer_path = Path(authorization["generated_source_preparer_identity"]["canonical_path"])
    resources = authorization["execution_resources"]
    mia_root = Path(resources["mia_root"]).resolve()
    source_root = (mia_root / "variants" / "packetized_active_sync").resolve()
    variant_root = Path(resources["mia_source_root"])
    runtime_source = SRC / "tracking/mdmt_mia_async_deadline_runtime.py"

    expected_sha256 = authorization["generated_source_preparer_identity"]["sha256"]
    if not preparer_path.is_file() or sha256_file(preparer_path) != expected_sha256:
        raise C7ChildError("generated-source preparer identity mismatch")
    if not source_root.is_dir():
        raise C7ChildError(
            "generated-source base root does not exist: {}".format(source_root))
    if not (source_root / "demo" / "supplement_MIA.py").is_file():
        raise C7ChildError("generated-source base entry does not exist")
    if variant_root.exists():
        raise C7ChildError("generated source root already exists: {}".format(variant_root))

    command = [
            sys.executable,
            str(preparer_path),
            "--source-root", str(source_root),
            "--variant-root", str(variant_root),
            "--runtime-source", str(runtime_source),
            "--copy-source",
    ]
    if c7_evidence:
        command.append("--c7-evidence")
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise C7ChildError(
            "generated-source preparer failed: {}".format(completed.stderr))

    inventory = inventory_generated_source(variant_root)
    if inventory["file_count"] == 0:
        raise C7ChildError("generated source root is empty after materialization")
    return inventory


def _build_wrapper_environment(spec: dict, authorization: dict) -> dict[str, str]:
    """Build explicit wrapper environment from validated authorization."""
    cell = spec.get("cell", {})
    resources = authorization["execution_resources"]

    # Start from allowlisted parent keys only.
    environment = {
        key: os.environ[key] for key in ALLOWED_PARENT_ENV_KEYS if key in os.environ
    }
    environment.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(SRC),
        "MDMT_MIA_C7_CHILD_BOUNDARY": "1",
        "MDMT_MIA_C7_OBSERVATIONAL": "1",
        "MDMT_MIA_C7_CAPACITY_BYTES": str(cell["capacity_bytes"]),
        "MDMT_ROOT": str(Path(resources["mdmt_root"]).resolve()),
        "MIA_ROOT": str(Path(resources["mia_root"]).resolve()),
        "MIA_SOURCE_ROOT": str(Path(resources["mia_source_root"]).resolve()),
        "MIA_CONFIG": str(Path(resources["mia_config_path"]).resolve()),
        "MIA_RUN_INPUT_ROOT": str(Path(resources["mia_run_input_root"]).resolve()),
        "MIA_OUTPUT_ROOT": str(Path(resources["mia_output_root"]).resolve()),
        "DEVICE": str(resources["device"]),
    })
    if spec.get("mode") == "REAL_C7_EVIDENCE_CELL":
        environment.update({
            "MIA_C7_SERVICE_CONFIG": json.dumps({
                "schema_version": "C7_REGISTERED_FIFO_SERVICE_V1",
                "mode": "fifo",
                "capacity_id": cell["capacity_id"],
                "rate_logical_bytes_per_frame": cell["capacity_bytes"],
                "ledger_enabled": True,
                "run_id": spec["run_id"],
                "pair_id": cell["pair_id"],
            }, sort_keys=True, separators=(",", ":")),
            "MIA_C7_EVIDENCE_ROOT": str(
                Path(spec["output_root"]).resolve() / "raw_c7"),
        })
    return environment


def _execute_wrapper(spec: dict, authorization: dict, *, observed_head: str) -> dict:
    """Execute the authorized wrapper with explicit environment and resources."""
    _verify_authorities(spec)
    try:
        validate_mve_authorization(
            authorization, execution_harness_head=observed_head)
    except ValueError as exc:
        raise C7ChildError(
            "MVE launch resource validation failed: {}".format(exc)) from exc
    _validate_authorization_scope(spec, authorization)
    cell = spec.get("cell", {})
    pair_id = str(cell.get("pair_id", ""))
    if pair_id not in {"P23", "P44", "P66"}:
        raise C7ChildError("unregistered real pair")

    wrapper = Path(authorization["wrapper_identity"]["canonical_path"]).resolve()
    expected_sha256 = authorization["wrapper_identity"]["sha256"]
    if not wrapper.is_file() or sha256_file(wrapper) != expected_sha256:
        raise C7ChildError("author wrapper identity mismatch")

    environment = _build_wrapper_environment(spec, authorization)
    command = [str(wrapper), "mia", authorization["split"], pair_id[1:]]

    output_root = Path(spec["output_root"]).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def build_real_wrapper_command(spec: dict) -> tuple[list[str], dict[str, str]]:
    """Build the real author-wrapper path without reading any result artifact."""
    _verify_authorities(spec)
    if spec.get("mode") not in {"REAL_C7_CELL", "REAL_C7_EVIDENCE_CELL"}:
        raise C7ChildError("real wrapper command requires REAL_C7_CELL mode")
    cell = spec.get("cell", {})
    pair_id = str(cell.get("pair_id", ""))
    if pair_id not in {"P23", "P44", "P66"}:
        raise C7ChildError("unregistered real pair")
    wrapper = Path(spec.get("author_wrapper_path", "")).resolve()
    if not wrapper.is_file() or sha256_file(wrapper) != spec.get("author_wrapper_sha256"):
        raise C7ChildError("author wrapper identity mismatch")
    environment = {
        key: os.environ[key] for key in ALLOWED_PARENT_ENV_KEYS if key in os.environ
    }
    environment.update({
        "MIA_OUTPUT_ROOT": str(Path(spec["author_output_root"]).resolve()),
        "MIA_SOURCE_ROOT": str(Path(spec["generated_source_root"]).resolve()),
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "MDMT_MIA_C7_OBSERVATIONAL": "1",
        "MDMT_MIA_C7_CAPACITY_BYTES": str(cell["capacity_bytes"]),
    })
    command = [str(wrapper), "mia", str(spec.get("split", "train")), pair_id[1:]]
    return command, environment


def execute_child(spec: dict) -> dict:
    _verify_authorities(spec)
    output_root = Path(spec.get("output_root", "")).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    mode = spec.get("mode")
    if mode == "SYNTHETIC_NON_SCIENTIFIC":
        if spec.get("synthetic_non_scientific") is not True:
            raise C7ChildError("synthetic marker missing")
        records = read_jsonl(spec.get("window_source"))
        atomic_write_jsonl(output_root / "windows.jsonl", records)
        status = {
            "schema_version": "C7_CHILD_STATUS_V1",
            "status": "PASS",
            "mode": mode,
            "synthetic_non_scientific": True,
            "window_count": len(records),
            "windows_sha256": sha256_file(output_root / "windows.jsonl"),
            "real_input_executed": False,
            **_environment_attestation(include_mve_bound_keys=False),
        }
        atomic_write_json(output_root / "CHILD_STATUS.json", status)
        return status
    if mode not in {"REAL_C7_CELL", "REAL_C7_EVIDENCE_CELL"}:
        raise C7ChildError("unsupported child mode")
    real_evidence = mode == "REAL_C7_EVIDENCE_CELL"
    if spec.get("dry_run") is True:
        command, controlled = build_real_wrapper_command(spec)
        status = {
            "schema_version": "C7_CHILD_STATUS_V1",
            "status": "PATH_VALID",
            "mode": mode,
            "synthetic_non_scientific": False,
            "wrapper_command": command,
            "controlled_environment_keys": sorted(controlled),
            "real_input_executed": False,
            **_environment_attestation(include_mve_bound_keys=True),
        }
        atomic_write_json(output_root / "CHILD_STATUS.json", status)
        return status

    # Non-dry REAL_C7_CELL requires an exact MVE authorization artifact.
    if not spec.get("mve_authorization_path"):
        raise C7ChildError("MVE authorization path is required for non-dry execution")
    if "execution_harness_head" in spec:
        raise C7ChildError("caller execution_harness_head is forbidden")
    observed_git = _observe_git_identity(ROOT)
    if observed_git["worktree_clean"] is not True:
        raise C7ChildError("execution worktree must be clean")
    authorization = _load_authorization(spec, observed_head=str(observed_git["head"]))
    _validate_authorization_scope(spec, authorization)

    pre_inventory = _materialize_generated_source(
        authorization, c7_evidence=real_evidence)

    wrapper_result = _execute_wrapper(
        spec, authorization, observed_head=str(observed_git["head"]))

    # Re-inventory generated source to detect unexpected post-execution mutation.
    post_inventory = inventory_generated_source(
        authorization["execution_resources"]["mia_source_root"])
    if post_inventory["inventory_sha256"] != pre_inventory["inventory_sha256"]:
        raise C7ChildError("generated source inventory changed during wrapper execution")
    real_windows = None
    if wrapper_result["returncode"] == 0 and real_evidence:
        raw_path = Path(spec["output_root"]).resolve() / "raw_c7" / "raw_observer.json"
        try:
            raw_run = json.loads(raw_path.read_text(encoding="utf-8"))
            real_windows = build_real_window_records(
                raw_run, run_id=spec["run_id"], cell=spec["cell"])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError,
                ValueError, KeyError, TypeError) as exc:
            raise C7ChildError("real C7 observer evidence is absent or invalid") from exc
        atomic_write_jsonl(Path(spec["output_root"]) / "windows.jsonl", real_windows)

    resources = authorization["execution_resources"]
    mia_output_root = Path(resources["mia_output_root"]).resolve()
    pair_number = authorization["pair_id"][1:]
    run_directory = "{}_{}".format(authorization["split"], pair_number)
    outcome_quarantine = {
        "result_dir": str(mia_output_root / "mia" / run_directory / "results"),
        "view1_output": str(mia_output_root / "mia" / run_directory / "view1"),
        "view2_output": str(mia_output_root / "mia" / run_directory / "view2"),
    }

    status = {
        "schema_version": "C7_CHILD_STATUS_V1",
        "status": "EXECUTED" if wrapper_result["returncode"] == 0 else "WRAPPER_FAILED",
        "mode": mode,
        "synthetic_non_scientific": False,
        "real_input_executed": True,
        "wrapper_returncode": wrapper_result["returncode"],
        "wrapper_command": wrapper_result["command"],
        "implementation_head_matched": True,
        "observed_repository_root": observed_git["repo_root"],
        "observed_execution_harness_head": observed_git["head"],
        "observed_worktree_clean": observed_git["worktree_clean"],
        "authorization_valid": True,
        "generated_source_materialized": True,
        "generated_source_inventory_stable": True,
        "generated_source_inventory": pre_inventory,
        "outcome_quarantine_paths": outcome_quarantine,
        "environment_boundary_passed": True,
        "real_c7_windows_validated": real_windows is not None,
        "real_c7_window_count": 0 if real_windows is None else len(real_windows),
        "real_c7_windows_sha256": (
            None if real_windows is None else sha256_file(Path(spec["output_root"]) / "windows.jsonl")),
        **_environment_attestation(include_mve_bound_keys=True),
    }
    atomic_write_json(output_root / "CHILD_STATUS.json", status)

    if wrapper_result["returncode"] != 0:
        raise C7ChildError(
            "wrapper execution failed with status {}".format(
                wrapper_result["returncode"]))
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    args = parser.parse_args(argv)
    execute_child(_load(args.spec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
