#!/usr/bin/env python3
"""Render C4 or execute it only through a sealed, fail-closed authorization."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_AUTHORITY = "24778f49ec9c913aadf95199343b12a75fd4078d"
IMPLEMENTATION_PLAN_AUTHORITY = "cd8c1f94c88faaf63e106827bfcb095a518de49d"
IMPLEMENTATION_BASE_AUTHORITY = "a1c069c5a934730225c03ef44b1adc3ff8adc828"
EXPECTED_CENSUS_SHA256 = "ab2440e1776cdd30ba8f793bc5da713580343ac342db29e153653cdf1bc2421a"
AUTHORIZATION_ROLE = "C4_MVE_EXECUTION_AUTHORIZATION"
MATRIX_ROLE = "C4_BASELINE_QUALIFICATION_MVE_MATRIX"
PAIRS = ("23", "44", "66")
CONDITIONS = (
    "Unlimited", "FIFO_mild", "FIFO_moderate", "FIFO_strong", "Y10_d1", "Y11_d1",
)
FIFO_RATES = {"FIFO_mild": 31987, "FIFO_moderate": 26148, "FIFO_strong": 16649}
ZERO_DELAYS = {"local": 0, "homography": 0, "id_state": 0, "supplement": 0}
BRIDGE_DELAYS = {
    "Y10_d1": {"local": 0, "homography": 0, "id_state": 1, "supplement": 0},
    "Y11_d1": {"local": 0, "homography": 0, "id_state": 1, "supplement": 1},
}


class ExecutionGateError(RuntimeError):
    """Raised before dataset access when execution material is not exact."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ExecutionGateError(f"{label} is unreadable: {path}: {error}") from error
    if not isinstance(value, dict):
        raise ExecutionGateError(f"{label} must be a JSON object: {path}")
    return value


def _resolved_absolute(value: object, label: str) -> Path:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        raise ExecutionGateError(f"{label} must be absolute")
    resolved = path.resolve()
    if str(path) != str(resolved):
        raise ExecutionGateError(f"{label} must already be canonical (no symlink alias)")
    return resolved


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _repository_state(root: Path) -> dict[str, object]:
    def git(*arguments: str) -> str:
        return subprocess.check_output(
            ["git", *arguments], cwd=root, text=True, stderr=subprocess.STDOUT).strip()

    return {
        "head": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "clean": not bool(git("status", "--short")),
    }


def render_condition(condition: str, run_id: str, pair_id: str) -> dict[str, object]:
    if pair_id not in PAIRS:
        raise ValueError("C4 runner accepts only frozen pairs 23/44/66")
    if condition not in CONDITIONS:
        raise ValueError("unknown or unauthorized C4 condition")
    if condition == "Unlimited":
        service = {"mode": "unlimited", "condition": condition,
                   "rate_logical_bytes_per_frame": None, "ledger_enabled": True,
                   "run_id": run_id, "pair_id": pair_id}
        delays = dict(ZERO_DELAYS)
    elif condition in FIFO_RATES:
        service = {"mode": "fifo", "condition": condition,
                   "rate_logical_bytes_per_frame": FIFO_RATES[condition], "ledger_enabled": True,
                   "run_id": run_id, "pair_id": pair_id}
        delays = dict(ZERO_DELAYS)
    else:
        service = {"mode": "disabled", "condition": condition,
                   "rate_logical_bytes_per_frame": None, "ledger_enabled": False,
                   "run_id": run_id, "pair_id": pair_id}
        delays = dict(BRIDGE_DELAYS[condition])
    return {
        "pair_id": pair_id,
        "condition": condition,
        "service_config": service,
        "delay_map": delays,
    }


def render_matrix(run_id: str, pairs=PAIRS, conditions=CONDITIONS) -> list[dict[str, object]]:
    selected_pairs = tuple(str(value) for value in pairs)
    selected_conditions = tuple(str(value) for value in conditions)
    if len(set(selected_pairs)) != len(selected_pairs) or any(value not in PAIRS for value in selected_pairs):
        raise ValueError("matrix contains a duplicate or unauthorized pair")
    if len(set(selected_conditions)) != len(selected_conditions) \
            or any(value not in CONDITIONS for value in selected_conditions):
        raise ValueError("matrix contains a duplicate or unauthorized condition")
    return [render_condition(condition, run_id, pair_id)
            for pair_id in selected_pairs for condition in selected_conditions]


def render_commands(cells: list[dict[str, object]], output_root: Path) -> list[dict[str, object]]:
    rendered = []
    for cell in cells:
        pair_id, condition = str(cell["pair_id"]), str(cell["condition"])
        cell_root = output_root / condition / ("train_" + pair_id)
        rendered.append({
            **cell,
            "cell_id": f"pair_{pair_id}__{condition}",
            "environment": {
                "MIA_C4_SERVICE_CONFIG": json.dumps(
                    cell["service_config"], sort_keys=True, separators=(",", ":")),
                "MIA_ASYNC_CHANNEL_DELAYS": json.dumps(
                    cell["delay_map"], sort_keys=True, separators=(",", ":")),
                "MIA_PACKET_CENSUS_RUN_ID": "c4-baseline-qualification",
                "MIA_OUTPUT_ROOT": str(cell_root),
                "PYTHONNOUSERSITE": "1",
            },
            "author_command": ["bash", "scripts/run_mdmt_mia_author_sync.sh", "mia", "train", pair_id],
            "execution_authorized": False,
        })
    return rendered


def build_matrix_manifest(run_id: str, output_root: Path, cache_root: str | None,
                          implementation_sha: str) -> dict[str, object]:
    cells = []
    for rendered in render_matrix(run_id):
        pair_id = str(rendered["pair_id"])
        condition = str(rendered["condition"])
        mode = str(rendered["service_config"]["mode"])
        cells.append({
            "cell_id": f"pair_{pair_id}__{condition}",
            "pair_id": pair_id,
            "condition": condition,
            "service_mode": "fixed_delay" if mode == "disabled" else mode,
            "rate_logical_bytes_per_frame": rendered["service_config"][
                "rate_logical_bytes_per_frame"],
            "delay_map": rendered["delay_map"],
            "implementation_sha": implementation_sha,
            "contract_sha": CONTRACT_AUTHORITY,
            "plan_sha": IMPLEMENTATION_PLAN_AUTHORITY,
            "run_id": run_id,
            "output_dir": str(output_root / condition / ("train_" + pair_id)),
            "cache_root": cache_root,
            "execution_authorized": False,
        })
    return {
        "document_role": MATRIX_ROLE,
        "scientific_cell_count": len(cells),
        "cells": cells,
    }


def _require_equal(document: dict[str, object], field: str, expected: object,
                   label: str = "authorization") -> None:
    if document.get(field) != expected:
        raise ExecutionGateError(
            f"{label}.{field} mismatch: expected {expected!r}, got {document.get(field)!r}")


def validate_execution_material(authorization_path: Path, authorization_sha256: str, *,
                                repository_state: dict[str, object] | None = None) -> dict[str, object]:
    """Validate all launch authority before creating an output directory."""
    authorization_path = authorization_path.expanduser().resolve()
    if not re.fullmatch(r"[0-9a-f]{64}", authorization_sha256):
        raise ExecutionGateError("authorization SHA-256 must be a lowercase 64-hex digest")
    if sha256(authorization_path) != authorization_sha256:
        raise ExecutionGateError("execution authorization SHA-256 mismatch")
    authorization = _load_json(authorization_path, "execution authorization")
    for field, expected in (
        ("document_role", AUTHORIZATION_ROLE),
        ("authorization_status", "AUTHORIZED"),
        ("mve_execution_authorized", True),
        ("pre_execution_closure_status", "COMPLETE"),
        ("contract_authority", CONTRACT_AUTHORITY),
        ("implementation_plan_authority", IMPLEMENTATION_PLAN_AUTHORITY),
        ("implementation_base_authority", IMPLEMENTATION_BASE_AUTHORITY),
        ("census_computed_sha256", EXPECTED_CENSUS_SHA256),
        ("census_sha256_match", True),
        ("holdout_completion_verified", True),
        ("unlimited_comparator_rendering", "FRESH_C4_UNLIMITED_RUN"),
        ("scientific_cell_count", 18),
    ):
        _require_equal(authorization, field, expected)

    implementation_sha = str(authorization.get("implementation_authority", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", implementation_sha):
        raise ExecutionGateError("authorization.implementation_authority must be a full Git SHA")
    state = repository_state if repository_state is not None else _repository_state(ROOT)
    if state.get("head") != implementation_sha:
        raise ExecutionGateError("execution worktree HEAD differs from authorized implementation SHA")
    if state.get("branch") != "impl/20260910-communication-c4-baseline-qualification":
        raise ExecutionGateError("execution worktree is on the wrong branch")
    if state.get("clean") is not True:
        raise ExecutionGateError("execution worktree must be clean")
    worktree = _resolved_absolute(authorization.get("implementation_worktree"),
                                  "implementation_worktree")
    if worktree != ROOT.resolve():
        raise ExecutionGateError("authorization names a different implementation worktree")

    matrix_path = _resolved_absolute(authorization.get("matrix_manifest_path"),
                                     "matrix_manifest_path")
    if not matrix_path.is_file():
        raise ExecutionGateError("matrix manifest is missing")
    _require_equal(authorization, "matrix_manifest_sha256", sha256(matrix_path))
    matrix = _load_json(matrix_path, "matrix manifest")
    _require_equal(matrix, "document_role", MATRIX_ROLE, "matrix")
    _require_equal(matrix, "scientific_cell_count", 18, "matrix")

    run_id = str(authorization.get("run_id", ""))
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{7,127}", run_id) \
            or "candidate" in run_id or "tmp" in run_id:
        raise ExecutionGateError("run_id is missing, ambiguous, or non-canonical")
    output_root = _resolved_absolute(authorization.get("output_root"), "output_root")
    run_input_root = _resolved_absolute(authorization.get("run_input_root"), "run_input_root")
    cache_value = authorization.get("cache_root")
    cache_mode = str(authorization.get("cache_mode", ""))
    if cache_value in (None, "NONE"):
        cache_root = None
        if cache_mode != "off":
            raise ExecutionGateError("cache_root NONE requires cache_mode=off")
    else:
        cache_root = _resolved_absolute(cache_value, "cache_root")
        if cache_mode != "read":
            raise ExecutionGateError("a frozen cache root may be used only in read mode")
        if not cache_root.is_dir():
            raise ExecutionGateError("read-only cache root is missing")
    if output_root.exists() and any(output_root.iterdir()):
        raise ExecutionGateError("output_root is not empty")
    if run_input_root.exists() and any(run_input_root.iterdir()):
        raise ExecutionGateError("run_input_root is not empty")
    write_roots = [output_root, run_input_root]
    if cache_root is not None:
        if _is_within(cache_root, output_root) or _is_within(output_root, cache_root):
            raise ExecutionGateError("cache_root overlaps output_root")
    forbidden_values = authorization.get("forbidden_write_roots")
    if not isinstance(forbidden_values, list) or not forbidden_values:
        raise ExecutionGateError("authorization must list Holdout/Val forbidden_write_roots")
    forbidden_roots = [_resolved_absolute(value, "forbidden_write_root")
                       for value in forbidden_values]
    for write_root in write_roots:
        if any(_is_within(write_root, forbidden) or _is_within(forbidden, write_root)
               for forbidden in forbidden_roots):
            raise ExecutionGateError(f"write root overlaps forbidden authority: {write_root}")

    source_root = _resolved_absolute(authorization.get("mia_source_root"), "mia_source_root")
    dataset_root = _resolved_absolute(authorization.get("dataset_root"), "dataset_root")
    mia_root = _resolved_absolute(authorization.get("mia_root"), "mia_root")
    for path, label in ((source_root, "mia_source_root"), (dataset_root, "dataset_root"),
                        (mia_root, "mia_root")):
        if not path.is_dir():
            raise ExecutionGateError(f"{label} is missing")
    source_manifest = _resolved_absolute(
        authorization.get("source_variant_manifest_path"), "source_variant_manifest_path")
    source_runtime = source_root / "demo/utils/async_deadline_runtime.py"
    mia_config = mia_root / "run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py"
    checkpoint = dataset_root / \
        "checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth"
    author_python = mia_root / ".conda-env/bin/python"
    for path, hash_field in (
        (source_manifest, "source_variant_manifest_sha256"),
        (source_runtime, "source_runtime_sha256"),
        (ROOT / "src/tracking/mdmt_mia_async_deadline_runtime.py", "repository_runtime_sha256"),
        (ROOT / "scripts/run_mdmt_mia_author_sync.sh", "author_runner_sha256"),
        (Path(__file__).resolve(), "c4_runner_sha256"),
        (mia_config, "mia_config_sha256"),
        (checkpoint, "checkpoint_sha256"),
        (author_python, "author_python_sha256"),
    ):
        if not path.is_file():
            raise ExecutionGateError(f"authorized source file is missing: {path}")
        _require_equal(authorization, hash_field, sha256(path))
    if authorization.get("source_runtime_sha256") != authorization.get("repository_runtime_sha256"):
        raise ExecutionGateError("generated author source does not contain the authorized PacketRuntime")
    _require_equal(authorization, "mia_config", str(mia_config))
    _require_equal(authorization, "checkpoint", str(checkpoint))
    _require_equal(authorization, "author_python", str(author_python))

    cells = matrix.get("cells")
    if not isinstance(cells, list) or len(cells) != 18:
        raise ExecutionGateError("matrix must contain exactly 18 cells")
    expected = build_matrix_manifest(
        run_id, output_root, str(cache_root) if cache_root is not None else None,
        implementation_sha)["cells"]
    by_id = {}
    for cell in cells:
        if not isinstance(cell, dict) or not isinstance(cell.get("cell_id"), str):
            raise ExecutionGateError("each matrix cell must be an identified JSON object")
        if cell["cell_id"] in by_id:
            raise ExecutionGateError("matrix contains duplicate cell_id")
        by_id[cell["cell_id"]] = cell
    required_fields = tuple(expected[0])
    for expected_cell in expected:
        actual = by_id.get(expected_cell["cell_id"])
        if actual is None:
            raise ExecutionGateError(f"matrix is missing {expected_cell['cell_id']}")
        for field in required_fields:
            if actual.get(field) != expected_cell[field]:
                raise ExecutionGateError(
                    f"matrix {expected_cell['cell_id']} field {field} is not frozen exactly")
    if set(by_id) != {str(cell["cell_id"]) for cell in expected}:
        raise ExecutionGateError("matrix contains an unauthorized scientific cell")

    device = str(authorization.get("device", ""))
    if not device:
        raise ExecutionGateError("authorization must freeze a device")
    gpu_required = authorization.get("gpu_required")
    cuda_visible_devices = authorization.get("cuda_visible_devices")
    if gpu_required is True:
        if not device.startswith("cuda:") or not isinstance(cuda_visible_devices, str) \
                or not re.fullmatch(r"[0-9]+(?:,[0-9]+)*", cuda_visible_devices):
            raise ExecutionGateError("GPU execution requires exact CUDA device visibility")
    elif gpu_required is False:
        if device != "cpu" or cuda_visible_devices not in (None, ""):
            raise ExecutionGateError("CPU execution must not expose an authorized CUDA device")
    else:
        raise ExecutionGateError("authorization must freeze gpu_required as a boolean")
    seed = authorization.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ExecutionGateError("authorization must freeze an integer seed")
    return {
        "authorization": authorization,
        "authorization_sha256": authorization_sha256,
        "matrix": matrix,
        "cells": [by_id[str(cell["cell_id"])] for cell in expected],
        "run_id": run_id,
        "output_root": output_root,
        "run_input_root": run_input_root,
        "cache_root": cache_root,
        "cache_mode": cache_mode,
        "mia_root": mia_root,
        "mia_config": mia_config,
        "mia_source_root": source_root,
        "dataset_root": dataset_root,
        "device": device,
        "gpu_required": gpu_required,
        "cuda_visible_devices": cuda_visible_devices,
        "seed": seed,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_exclusive_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _validate_cell_outputs(cell_root: Path, pair_id: str, condition: str) -> None:
    result_root = cell_root / "mia" / ("train_" + pair_id) / "results" \
        / ("mia_train_" + pair_id)
    missing = [str(result_root / f"{pair_id}-{view}.json") for view in (1, 2)
               if not (result_root / f"{pair_id}-{view}.json").is_file()]
    if missing:
        raise ExecutionGateError("cell completed without required result JSON: " + ",".join(missing))
    manifests = sorted(cell_root.rglob("async_packet_manifest_*.json"))
    if len(manifests) < 2:
        raise ExecutionGateError("cell completed without both PacketRuntime manifests")
    if condition == "Unlimited" or condition.startswith("FIFO_"):
        for path in manifests:
            manifest = _load_json(path, "PacketRuntime manifest")
            if manifest.get("c4_service_status") != "COMPLETE":
                raise ExecutionGateError(f"C4 service evidence is incomplete: {path}")


def _launch(command: list[str], *, cwd: Path, environment: dict[str, str]) -> int:
    process = subprocess.Popen(command, cwd=cwd, env=environment, start_new_session=True)
    try:
        return process.wait()
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        raise


def execute_authorized_matrix(
        material: dict[str, object], *,
        launcher: Callable[..., int] | None = None,
        output_validator: Callable[[Path, str, str], None] | None = None) -> None:
    """Execute exactly the validated 18 cells; no selection or resume is accepted."""
    launch = launcher or _launch
    validate_output = output_validator or _validate_cell_outputs
    cells = material["cells"]
    for cell in cells:
        cell_root = Path(str(cell["output_dir"]))
        if cell_root.exists() or cell_root.is_symlink():
            raise ExecutionGateError(f"refusing to overwrite cell output: {cell_root}")
    output_root = material["output_root"]
    output_root.mkdir(parents=True, exist_ok=True)
    run_start = {
        "run_id": material["run_id"],
        "implementation_authority": material["authorization"]["implementation_authority"],
        "matrix_manifest_sha256": material["authorization"]["matrix_manifest_sha256"],
        "execution_authorization_sha256": material["authorization_sha256"],
        "scientific_cell_count": 18,
        "status": "RUNNING",
        "started_at_utc": _utc_now(),
    }
    _write_exclusive_json(output_root / "RUN_START.json", run_start)
    run_end = {**run_start, "status": "FAILED", "finished_at_utc": None,
               "failure_reason": ""}
    try:
        for index, cell in enumerate(cells, start=1):
            pair_id = str(cell["pair_id"])
            condition = str(cell["condition"])
            cell_root = Path(str(cell["output_dir"]))
            cell_root.mkdir(parents=True, exist_ok=False)
            start = {
                "attempt_id": "attempt_001",
                "cell_id": cell["cell_id"],
                "pair_id": pair_id,
                "condition": condition,
                "implementation_authority": material["authorization"]["implementation_authority"],
                "matrix_manifest_sha256": material["authorization"]["matrix_manifest_sha256"],
                "execution_authorization_sha256": material["authorization_sha256"],
                "status": "RUNNING",
                "started_at_utc": _utc_now(),
            }
            _write_exclusive_json(cell_root / "ATTEMPT_START.json", start)
            rendered = render_condition(condition, str(material["run_id"]), pair_id)
            environment = os.environ.copy()
            for key in tuple(environment):
                if key.startswith("MIA_") or key in {
                        "DEVICE", "PYTHONHASHSEED", "PYTHONNOUSERSITE", "PYTHONPATH",
                        "MPLCONFIGDIR", "CUDA_VISIBLE_DEVICES"}:
                    environment.pop(key, None)
            environment.update({
                "MIA_ROOT": str(material["mia_root"]),
                "MIA_SOURCE_ROOT": str(material["mia_source_root"]),
                "MIA_CONFIG": str(material["mia_config"]),
                "MDMT_ROOT": str(material["dataset_root"]),
                "MIA_OUTPUT_ROOT": str(cell_root),
                "MIA_RUN_INPUT_ROOT": str(
                    material["run_input_root"] / condition / ("train_" + pair_id)),
                "MIA_ACTIVE_PACKET_STAGES": "all",
                "MIA_C4_SERVICE_CONFIG": json.dumps(
                    rendered["service_config"], sort_keys=True, separators=(",", ":")),
                "MIA_ASYNC_CHANNEL_DELAYS": json.dumps(
                    rendered["delay_map"], sort_keys=True, separators=(",", ":")),
                "MIA_PACKET_CENSUS_RUN_ID": str(material["run_id"]),
                "MIA_DETECTION_CACHE_MODE": str(material["cache_mode"]),
                "DEVICE": str(material["device"]),
                "PYTHONHASHSEED": str(material["seed"]),
                "PYTHONNOUSERSITE": "1",
                "MPLCONFIGDIR": str(material["output_root"] / "_runtime_cache/matplotlib"),
            })
            if material["cache_root"] is not None:
                environment["MIA_DETECTION_CACHE_ROOT"] = str(material["cache_root"])
            if material["cuda_visible_devices"]:
                environment["CUDA_VISIBLE_DEVICES"] = str(material["cuda_visible_devices"])
            command = ["bash", "scripts/run_mdmt_mia_author_sync.sh", "mia", "train", pair_id]
            end = {**start, "status": "FAILED", "finished_at_utc": None,
                   "exit_code": None, "failure_reason": ""}
            try:
                print(f"[C4 {index}/18] pair={pair_id} condition={condition}", flush=True)
                returncode = launch(command, cwd=ROOT, environment=environment)
                end["exit_code"] = returncode
                if returncode != 0:
                    raise ExecutionGateError(f"author runner exited with status {returncode}")
                validate_output(cell_root, pair_id, condition)
                end["status"] = "COMPLETE"
            except BaseException as error:
                end["failure_reason"] = f"{type(error).__name__}:{error}"
                raise
            finally:
                end["finished_at_utc"] = _utc_now()
                _write_exclusive_json(cell_root / "ATTEMPT_END.json", end)
        run_end["status"] = "COMPLETE"
    except BaseException as error:
        run_end["failure_reason"] = f"{type(error).__name__}:{error}"
        raise
    finally:
        run_end["finished_at_utc"] = _utc_now()
        _write_exclusive_json(output_root / "RUN_END.json", run_end)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="render only; never execute")
    mode.add_argument("--execute-authorized", action="store_true",
                      help="execute only after validating a sealed authorization JSON")
    parser.add_argument("--execution-authorization", type=Path)
    parser.add_argument("--authorization-sha256")
    parser.add_argument("--pair", action="append", choices=PAIRS)
    parser.add_argument("--condition", action="append", choices=CONDITIONS)
    parser.add_argument("--run-id", default="c4-baseline-qualification-candidate")
    parser.add_argument("--output-root", type=Path,
                        default=Path("outputs/c4_baseline_qualification_BLOCKED"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        if args.execution_authorization is not None or args.authorization_sha256 is not None:
            raise SystemExit("dry-run must not accept execution authorization")
        cells = render_matrix(args.run_id, args.pair or PAIRS, args.condition or CONDITIONS)
        payload = {
            "document_role": "C4_IMPLEMENTATION_ONLY_RENDERING",
            "contract_authority": CONTRACT_AUTHORITY,
            "implementation_plan_authority": IMPLEMENTATION_PLAN_AUTHORITY,
            "implementation_base_authority": IMPLEMENTATION_BASE_AUTHORITY,
            "scientific_cell_count": len(cells),
            "dataset_execution_authorized": False,
            "gpu_execution_authorized": False,
            "unlimited_comparator_rendering": "DEFERRED_TO_MVE_EXECUTION_MATERIAL",
            "cells": render_commands(cells, args.output_root),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if args.execution_authorization is None or args.authorization_sha256 is None:
        raise SystemExit(
            "DATASET_LEVEL_C4_MVE_NOT_AUTHORIZED: authorization path and SHA-256 are required")
    if args.pair or args.condition or args.run_id != "c4-baseline-qualification-candidate" \
            or args.output_root != Path("outputs/c4_baseline_qualification_BLOCKED"):
        raise SystemExit("authorized execution forbids CLI matrix/root overrides")
    try:
        material = validate_execution_material(
            args.execution_authorization, args.authorization_sha256)
        execute_authorized_matrix(material)
    except ExecutionGateError as error:
        raise SystemExit(f"C4_EXECUTION_GATE_BLOCKED: {error}") from error


if __name__ == "__main__":
    main()
