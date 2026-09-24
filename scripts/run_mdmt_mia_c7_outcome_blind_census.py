#!/usr/bin/env python3
"""C7 Batch B parent launcher and atomic packaging boundary.

Real execution requires a separate, exact full-domain authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


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
from tracking.mdmt_mia_c7_batch_b_schema import (
    full_census_child_spec,
    registered_cells,
    validate_full_census_authorization,
    ALLOWED_PARENT_ENV_KEYS,
    REGISTERED_SOURCE_RELATIVE_PATHS,
    authority_bindings,
    sha256_file,
)
from tracking.mdmt_mia_c7_batch_b_validator import (
    C7BatchBValidationError, read_json, read_jsonl,
    validate_committed_package, validate_manifest,
)


CHILD_PATH = ROOT / "scripts/run_mdmt_mia_c7_real_child.py"


class C7LauncherError(RuntimeError):
    pass


def source_hash_inventory(repo_root: Path | str = ROOT) -> dict[str, str]:
    root = Path(repo_root).resolve(strict=True)
    return {
        key: sha256_file((root / relative).resolve(strict=True))
        for key, relative in sorted(REGISTERED_SOURCE_RELATIVE_PATHS.items())
    }


def build_frozen_manifest(
    *, run_id: str, output_root: Path | str, batch_b_implementation_sha: str,
    input_identity: Mapping[str, Any], config_identity: Mapping[str, Any],
    synthetic_non_scientific: bool,
    generated_source_root: Path | str | None = None,
) -> dict[str, Any]:
    return build_batch_b_manifest(
        run_id=run_id,
        output_root=output_root,
        batch_b_implementation_sha=batch_b_implementation_sha,
        source_hashes=source_hash_inventory(ROOT),
        input_identity=input_identity,
        config_identity=config_identity,
        synthetic_non_scientific=synthetic_non_scientific,
        repo_root=ROOT if not synthetic_non_scientific else None,
        wrapper_path=(ROOT / REGISTERED_SOURCE_RELATIVE_PATHS["wrapper"]),
        generated_source_root=generated_source_root,
    )


def controlled_environment(
    parent_environment: Mapping[str, str] | None = None,
) -> dict[str, str]:
    parent = os.environ if parent_environment is None else parent_environment
    environment = {
        key: str(parent[key]) for key in ALLOWED_PARENT_ENV_KEYS if key in parent
    }
    environment.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(SRC),
        "MDMT_MIA_C7_CHILD_BOUNDARY": "1",
    })
    return environment


def execute_synthetic_launch(
    *, output_root: Path | str, manifest: Mapping[str, Any],
    window_sources: Mapping[str, Path | str],
) -> dict[str, Any]:
    """Run the child/writer/validator/selector path using synthetic inputs only."""
    if manifest.get("synthetic_non_scientific") is not True:
        raise C7LauncherError("synthetic launch requires synthetic manifest")
    validate_manifest(manifest)
    output = Path(output_root).resolve()
    operational = output / "operational"
    operational.mkdir(parents=True, exist_ok=True)
    expected_ids = [cell["cell_id"] for cell in manifest.get("cells", ())]
    if set(window_sources) != set(expected_ids):
        raise C7LauncherError("synthetic launch requires one window source per manifest cell")
    cell_statuses = []
    cell_seals_reproduced = []
    for cell in manifest["cells"]:
        cell_id = cell["cell_id"]
        child_root = operational / "child" / cell_id
        child_spec = {
            "schema_version": "C7_CHILD_SPEC_V1",
            "mode": "SYNTHETIC_NON_SCIENTIFIC",
            "synthetic_non_scientific": True,
            "authorities": authority_bindings(),
            "run_id": manifest.get("run_id"),
            "cell": dict(cell),
            "window_source": str(Path(window_sources[cell_id]).resolve()),
            "output_root": str(child_root),
        }
        spec_path = operational / "child_spec_{}.json".format(cell_id)
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
        if (child_status.get("status") != "PASS"
                or child_status.get("real_input_executed") is not False):
            raise C7LauncherError("synthetic child status mismatch")
        windows = read_jsonl(child_root / "windows.jsonl")
        result = write_cell_transaction(
            output_root=output,
            manifest=manifest,
            cell=cell,
            expected_frame_domain=manifest["authorized_frame_domains"][cell_id],
            windows=windows,
            synthetic_non_scientific=True,
        )
        cell_statuses.append(result["status"])
        cell_seals_reproduced.append(result["seal_reproduced"] is True)
    package_result = write_selection_package(output_root=output, manifest=manifest)
    result = {
        "schema_version": "C7_SYNTHETIC_E2E_STATUS_V1",
        "status": "PASS",
        "synthetic_non_scientific": True,
        "child_status": "PASS",
        "cell_transaction_status": (
            "COMMITTED" if set(cell_statuses) == {"COMMITTED"} else "RESUMED"),
        "package_transaction_status": package_result["status"],
        "seal_reproduced": bool(
            all(cell_seals_reproduced) and package_result["seal_reproduced"]),
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


def _observe_repository() -> str:
    """Observe actual clean Git authority before real materialization."""
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args], cwd=ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, check=True)
        return completed.stdout.strip()
    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() != ROOT.resolve():
            raise C7LauncherError("full Census repository root mismatch")
        head = git("rev-parse", "HEAD")
        if git("status", "--porcelain", "--untracked-files=all"):
            raise C7LauncherError("full Census worktree must be clean")
        return head
    except subprocess.CalledProcessError as exc:
        raise C7LauncherError("full Census Git identity observation failed") from exc


def plan_full_census_children(
    authorization: Mapping[str, Any], *, authorization_path: Path | str,
    authorization_sha256: str,
) -> list[dict[str, Any]]:
    """Freeze all 21 child specs before launching any cell."""
    return [full_census_child_spec(
        authorization, cell=cell, authorization_path=authorization_path,
        authorization_sha256=authorization_sha256)
        for cell in registered_cells()]


def _check_real_child_status(
    status: Mapping[str, Any], spec: Mapping[str, Any], *, head: str,
) -> None:
    cell = spec["cell"]
    windows_path = Path(spec["output_root"]) / "windows.jsonl"
    required = {
        "schema_version": "C7_CHILD_STATUS_V1",
        "status": "EXECUTED",
        "mode": "REAL_C7_EVIDENCE_CELL",
        "synthetic_non_scientific": False,
        "real_input_executed": True,
        "wrapper_returncode": 0,
        "authorization_valid": True,
        "implementation_head_matched": True,
        "observed_repository_root": str(ROOT.resolve()),
        "environment_boundary_passed": True,
        "generated_source_materialized": True,
        "observed_execution_harness_head": head,
        "observed_worktree_clean": True,
        "census_authorization_sha256": spec["parent_census_authorization_sha256"],
        "census_run_id": spec["run_id"],
        "stable_cell_index": spec["stable_cell_index"],
        "generated_source_inventory_stable": True,
        "real_c7_windows_validated": True,
        "real_c7_window_count": cell["frame_count"],
    }
    if any(status.get(key) != value for key, value in required.items()):
        raise C7LauncherError("full Census child structural status mismatch")
    if not windows_path.is_file() or status.get("real_c7_windows_sha256") != sha256_file(windows_path):
        raise C7LauncherError("full Census child windows digest mismatch")


def execute_full_census(authorization_path: Path | str) -> dict[str, Any]:
    """Run exactly 21 real cells in frozen order; fail-stop without resume."""
    path = Path(authorization_path)
    if str(path) != str(path.resolve()) or not path.is_file():
        raise C7LauncherError("full Census authorization path must be canonical")
    head = _observe_repository()
    try:
        raw_authorization = path.read_bytes()
        digest = hashlib.sha256(raw_authorization).hexdigest()
        authorization = json.loads(raw_authorization.decode("utf-8"))
        validate_full_census_authorization(
            authorization, execution_harness_head=head, execution_root=ROOT,
            require_fresh_root=True)
    except (ValueError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C7LauncherError("full Census authorization validation failed") from exc
    output = Path(authorization["output_root"])
    specs = plan_full_census_children(
        authorization, authorization_path=path, authorization_sha256=digest)
    if len(specs) != 21 or [spec["cell"] for spec in specs] != list(registered_cells()):
        raise C7LauncherError("full Census plan is not the exact registered domain")
    manifest = build_frozen_manifest(
        run_id=authorization["run_id"], output_root=output,
        batch_b_implementation_sha=head,
        input_identity=authorization["input_identity"],
        config_identity=authorization["config_identity"],
        synthetic_non_scientific=False,
        generated_source_root=output / "operational" / "child")
    validate_manifest(manifest)
    output.mkdir(parents=True, exist_ok=False)
    operational = output / "operational"
    operational.mkdir()
    atomic_write_json(operational / "CENSUS_LAUNCH_STATUS.json", {
        "schema_version": "C7_FULL_CENSUS_LAUNCH_STATUS_V1",
        "status": "RUNNING", "run_id": authorization["run_id"],
        "authorization_sha256": digest, "committed_cell_count": 0,
    })
    for index, spec in enumerate(specs):
        cell = spec["cell"]
        cell_id = cell["cell_id"]
        if sha256_file(path) != digest:
            raise C7LauncherError("full Census authorization changed during execution")
        spec_path = operational / ("child_spec_{}.json".format(cell_id))
        atomic_write_json(spec_path, spec)
        completed = subprocess.run(
            [sys.executable, str(CHILD_PATH), "--spec", str(spec_path)],
            cwd=ROOT, env=controlled_environment(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, check=False)
        if completed.returncode != 0:
            raise C7LauncherError("full Census child failed at {}".format(cell_id))
        try:
            status = read_json(Path(spec["output_root"]) / "CHILD_STATUS.json")
        except C7BatchBValidationError as exc:
            raise C7LauncherError("full Census child status absent or invalid") from exc
        _check_real_child_status(status, spec, head=head)
        windows = read_jsonl(Path(spec["output_root"]) / "windows.jsonl")
        transaction = write_cell_transaction(
            output_root=output, manifest=manifest, cell=cell,
            expected_frame_domain=manifest["authorized_frame_domains"][cell_id],
            windows=windows, synthetic_non_scientific=False)
        if transaction.get("status") != "COMMITTED" or transaction.get("seal_reproduced") is not True:
            raise C7LauncherError("full Census cell commit failed at {}".format(cell_id))
        atomic_write_json(operational / "CENSUS_LAUNCH_STATUS.json", {
            "schema_version": "C7_FULL_CENSUS_LAUNCH_STATUS_V1",
            "status": "RUNNING", "run_id": authorization["run_id"],
            "authorization_sha256": digest, "committed_cell_count": index + 1,
        })
    package = write_selection_package(output_root=output, manifest=manifest)
    if package.get("status") != "COMMITTED" or package.get("seal_reproduced") is not True:
        raise C7LauncherError("full Census package was not freshly committed")
    validation = validate_committed_package(output / "package")
    if (validation.get("status") != "PASS"
            or validation.get("all_21_cell_seals_verified") is not True
            or validation.get("inventory_reproduced") is not True
            or validation.get("seal_reproduced") is not True
            or validation.get("terminal_marker_valid") is not True):
        raise C7LauncherError("full Census package validation failed")
    result = {
        "schema_version": "C7_FULL_CENSUS_LAUNCH_STATUS_V1",
        "status": "COMMITTED", "run_id": authorization["run_id"],
        "authorization_sha256": digest, "committed_cell_count": 21,
    }
    atomic_write_json(operational / "CENSUS_LAUNCH_STATUS.json", result)
    return result


def _load(path: Path | str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise C7LauncherError("launch spec must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--spec")
    group.add_argument("--authorization")
    args = parser.parse_args(argv)
    if args.authorization:
        execute_full_census(args.authorization)
        return 0
    spec = _load(args.spec)
    if spec.get("mode") != "SYNTHETIC_NON_SCIENTIFIC":
        raise C7LauncherError("Batch B CLI execution is synthetic-only")
    manifest = _load(spec["manifest_path"])
    execute_synthetic_launch(
        output_root=spec["output_root"],
        manifest=manifest,
        window_sources=spec["window_sources"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
