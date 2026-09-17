#!/usr/bin/env python3
"""C6 Formal operator over the qualified public one-cell launcher."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "summary_md/communication/c6_pre_formal_platform_qualification/C6_FORMAL_EXECUTION_PACKAGE.json"
PLATFORM_MANIFEST_PATH = ROOT / "summary_md/communication/c6_pre_formal_platform_qualification/C6_PLATFORM_QUALIFICATION_MANIFEST.json"
RUNNER_PATH = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"
AUTHOR_WRAPPER_PATH = ROOT / "scripts/run_mdmt_mia_author_sync.sh"
MANIFEST_PATH = ROOT / "summary_md/communication/c6_generated_author_source_qualification_corrective/C6_GENERATED_AUTHOR_SOURCE_MANIFEST.json"
QUALIFICATION_SEAL_PATH = ROOT / "summary_md/communication/c6_generated_author_source_qualification_corrective/C6_GENERATED_AUTHOR_SOURCE_QUALIFICATION_SEAL.json"
BASELINE_SEAL_PATH = ROOT / "summary_md/communication/c6_run004_serviceable_baseline_derivation/C6_RUN004_BASELINE_DERIVATION_SEAL.json"
PROGRESS_NAME = "C6_FORMAL_PROGRESS.json"
RUN_ROOT_DIRECTORY = "_formal_runs"
FORMAL_METRICS = (
    "B_avoided",
    "serviceable_id_state_serviced_bytes_treatment",
    "serviceable_id_state_serviced_bytes_baseline",
    "delta_B_serviceable",
)
CELL_KEYS = frozenset((
    "cell", "pair", "role", "service_condition", "service_rate",
    "serviceable_id_state_serviced_bytes_baseline", "evidence_shape_profile", "output_root",
))
AUTHORIZATION_KEYS = frozenset((
    "schema_version", "stage", "execution_authorized", "formal_allowed",
    "contract_sha", "plan_sha", "authorities", "platform_qualification_authority",
    "metrics", "cells", "retry_policy", "storage_policy", "environment_binding",
    "tracking_outcome_read_allowed", "science_adaptation_allowed",
))
PACKAGE_KEYS = frozenset((
    "schema_version", "stage", "contract_sha", "plan_sha", "authorities", "metrics",
    "cells", "roots", "retry_policy", "run_protocol", "storage_policy",
    "mve_attempt2_evidence_sha", "mve_execution_base_sha", "execution_authorized",
    "formal_allowed", "tracking_outcome_read_allowed",
))


class FormalGateError(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _strict_json_bytes(raw, label):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise FormalGateError("duplicate JSON key in {}".format(label))
            value[key] = item
        return value

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, ValueError, TypeError) as exc:
        raise FormalGateError("malformed {}".format(label)) from exc
    if not isinstance(value, dict):
        raise FormalGateError("{} must be a JSON object".format(label))
    return value


def _read_json(path, label="artifact"):
    try:
        return _strict_json_bytes(Path(path).read_bytes(), label)
    except OSError as exc:
        raise FormalGateError("missing or unreadable {}".format(label)) from exc


def _write_exclusive(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(_canonical(value) + "\n")
    return path


def load_runner():
    spec = importlib.util.spec_from_file_location("c6_formal_public_real_cell_runner", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def platform_environment():
    manifest = _read_json(PLATFORM_MANIFEST_PATH, "platform qualification manifest")
    environment = manifest.get("environment")
    if not isinstance(environment, dict):
        raise FormalGateError("platform environment binding is missing")
    return environment


def pkg():
    runner = load_runner()
    if _sha256(PACKAGE_PATH) != runner.FORMAL_PACKAGE_SHA256:
        raise FormalGateError("Formal package SHA256 mismatch")
    package = _read_json(PACKAGE_PATH, "Formal execution package")
    if set(package) != PACKAGE_KEYS:
        raise FormalGateError("Formal package schema mismatch")
    if package["schema_version"] != "C6_FORMAL_EXECUTION_PACKAGE_V1" or package["stage"] != "C6_FORMAL":
        raise FormalGateError("Formal package identity mismatch")
    if package["execution_authorized"] is not False or package["formal_allowed"] is not False:
        raise FormalGateError("Formal package must not self-authorize execution")
    if package["tracking_outcome_read_allowed"] is not False:
        raise FormalGateError("Formal package tracking embargo mismatch")
    cells = package.get("cells")
    if not isinstance(cells, list) or len(cells) != 4 or any(set(cell) != CELL_KEYS for cell in cells):
        raise FormalGateError("Formal package cell schema mismatch")
    order = [cell["cell"] for cell in cells]
    roots = [cell["output_root"] for cell in cells]
    if len(set(order)) != 4 or len(set(roots)) != 4 or package.get("roots") != roots:
        raise FormalGateError("Formal package cell/root uniqueness mismatch")
    if tuple(package.get("metrics", ())) != FORMAL_METRICS:
        raise FormalGateError("Formal package metric contract mismatch")
    return package


def candidate(live=False):
    if type(live) is not bool:
        raise FormalGateError("candidate live flag must be boolean")
    package = pkg()
    runner = load_runner()
    return {
        "schema_version": "C6_FORMAL_AUTHORIZATION_V1",
        "stage": "C6_FORMAL",
        "execution_authorized": live,
        "formal_allowed": live,
        "contract_sha": package["contract_sha"],
        "plan_sha": package["plan_sha"],
        "authorities": package["authorities"],
        "platform_qualification_authority": runner.PLATFORM_QUALIFICATION_AUTHORITY_SHA,
        "metrics": package["metrics"],
        "cells": package["cells"],
        "retry_policy": package["retry_policy"],
        "storage_policy": package["storage_policy"],
        "environment_binding": platform_environment(),
        "tracking_outcome_read_allowed": False,
        "science_adaptation_allowed": False,
    }


def validate(authorization, live=True):
    if type(live) is not bool or not isinstance(authorization, dict) or set(authorization) != AUTHORIZATION_KEYS:
        raise FormalGateError("Formal authorization schema mismatch")
    expected = candidate(live)
    if authorization != expected:
        raise FormalGateError("Formal authorization does not match the frozen contract")
    if type(authorization["execution_authorized"]) is not bool or authorization["execution_authorized"] is not live:
        raise FormalGateError("Formal execution_authorized activation mismatch")
    if type(authorization["formal_allowed"]) is not bool or authorization["formal_allowed"] is not live:
        raise FormalGateError("Formal formal_allowed activation mismatch")
    return pkg()


def _runtime_preflight(environment):
    if sys.executable != environment.get("python_executable"):
        raise FormalGateError("platform Python executable mismatch")
    if os.environ.get("PYTHONHASHSEED") != environment.get("PYTHONHASHSEED"):
        raise FormalGateError("platform PYTHONHASHSEED mismatch")
    if os.environ.get("PYTHONNOUSERSITE") != environment.get("PYTHONNOUSERSITE"):
        raise FormalGateError("platform PYTHONNOUSERSITE mismatch")
    if str(Path.cwd()) != environment.get("cwd"):
        raise FormalGateError("platform working directory mismatch")


def _resolved_root(path):
    path = Path(path)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _require_exclusive_roots(roots):
    resolved = [_resolved_root(root) for root in roots]
    if len(resolved) != len(set(resolved)):
        raise FormalGateError("Formal cell roots collide")
    if any(path.exists() or path.is_symlink() for path in resolved):
        raise FormalGateError("Formal cell output root is occupied")
    return resolved


def _nearest_existing_parent(path):
    candidate_path = Path(path)
    while not candidate_path.exists() and candidate_path != candidate_path.parent:
        candidate_path = candidate_path.parent
    if not candidate_path.exists():
        raise FormalGateError("target filesystem is unavailable")
    return candidate_path


def _storage_preflight(package, roots):
    threshold = package["storage_policy"].get("minimum_free_bytes")
    if type(threshold) is not int or threshold <= 0:
        raise FormalGateError("Formal minimum-free-bytes policy is invalid")
    filesystems = {_nearest_existing_parent(_resolved_root(root)) for root in roots}
    if any(shutil.disk_usage(path).free < threshold for path in filesystems):
        raise FormalGateError("insufficient free space for Formal execution")


def _live_run_root(package):
    """Derive one exclusive lifecycle root from the frozen cell attempt identity."""
    resolved = [_resolved_root(cell["output_root"]) for cell in package["cells"]]
    attempt_ids = {path.name for path in resolved}
    cell_parents = {path.parent.parent for path in resolved}
    expected_cells = {cell["cell"] for cell in package["cells"]}
    observed_cells = {path.parent.name for path in resolved}
    if (
        len(attempt_ids) != 1
        or len(cell_parents) != 1
        or observed_cells != expected_cells
        or any(not attempt or "/" in attempt or "\\" in attempt for attempt in attempt_ids)
    ):
        raise FormalGateError("Formal cell roots do not encode one coherent attempt identity")
    return next(iter(cell_parents)) / RUN_ROOT_DIRECTORY / next(iter(attempt_ids))


def _derive_roots(package, qualification_no_data, qualification_root=None):
    production_roots = [cell["output_root"] for cell in package["cells"]]
    if qualification_no_data:
        if qualification_root is None:
            raise FormalGateError("qualification root is required")
        run_root = Path(qualification_root)
        if run_root.exists() or run_root.is_symlink():
            raise FormalGateError("qualification root must not exist")
        cell_roots = {cell["cell"]: str((run_root / "cell_runs" / cell["cell"]).resolve()) for cell in package["cells"]}
        if {_resolved_root(root) for root in cell_roots.values()} & {_resolved_root(root) for root in production_roots}:
            raise FormalGateError("qualification root aliases a production root")
    else:
        run_root = _live_run_root(package)
        cell_roots = {cell["cell"]: cell["output_root"] for cell in package["cells"]}
        if run_root.exists() or run_root.is_symlink():
            raise FormalGateError("Formal run root is occupied")
    _require_exclusive_roots(cell_roots.values())
    return run_root, cell_roots


def build_cell_launch_spec(mode, cell, output_root, authorization_path, runner=None):
    if mode not in ("QUALIFICATION", "LIVE"):
        raise FormalGateError("unknown Formal operator mode")
    runner = runner or load_runner()
    package = pkg()
    environment = platform_environment()
    qualification = mode == "QUALIFICATION"
    if qualification:
        parent_path = ""
        parent_sha = _sha256(PACKAGE_PATH)
        parent_policy = "PLATFORM_QUALIFICATION"
        execution_mode = "SYNTHETIC_NO_DATA"
        fixture_path = runner.SYNTHETIC_REAL_CELL_CHILD_PATH
    else:
        if authorization_path is None or not Path(authorization_path).is_file():
            raise FormalGateError("persisted live Formal authorization is required")
        parent_path = str(authorization_path)
        parent_sha = _sha256(authorization_path)
        parent_policy = "C6_FORMAL"
        execution_mode = "REAL_CHILD"
        fixture_path = runner.REAL_CHILD_PATH
    real_cell_authorization = {
        "schema_version": "C6_REAL_CELL_EXECUTION_AUTHORIZATION_V1",
        "stage": "C6_REAL_CELL",
        "execution_authorized": True,
        "run_scope": "EXACTLY_ONE_C6_CELL",
        "parent_policy": parent_policy,
        "parent_authorization_path": parent_path,
        "parent_authorization_sha256": parent_sha,
        "execution_mode": execution_mode,
        "cell": cell["cell"],
        "pair": cell["pair"],
        "role": cell["role"],
        "service_condition": cell["service_condition"],
        "service_rate": cell["service_rate"],
        "serviceable_id_state_serviced_bytes_baseline": cell["serviceable_id_state_serviced_bytes_baseline"],
        "evidence_shape_profile": cell["evidence_shape_profile"],
        "output_root": str(output_root),
        "formal_package_sha256": _sha256(PACKAGE_PATH),
        "implementation_sha": package["authorities"]["implementation_sha"],
        "generated_source_manifest_sha256": package["authorities"]["generated_source_manifest_sha256"],
        "generated_source_qualification_seal_sha256": package["authorities"]["generated_source_qualification_seal_sha256"],
        "real_child_sha256": package["authorities"]["real_child_sha256"],
        "forensic_logging_qualification_path": package["authorities"]["forensic_logging_qualification_path"],
        "forensic_logging_qualification_sha256": package["authorities"]["forensic_logging_qualification_sha256"],
        "science_adaptation_allowed": False,
        "tracking_outcome_read_allowed": False,
        "formal_aggregation_allowed": False,
    }
    return {
        "schema_version": "C6_PRODUCTION_LAUNCH_SPEC_V1",
        "stage": "C6_REAL_CELL",
        "run_id": "c6-formal-{}-{}".format(mode.lower(), cell["cell"]),
        "authorization": real_cell_authorization,
        "output_root": str(output_root),
        "logical_output_root": str(output_root),
        "generated_root": environment["generated_root"],
        "generated_manifest_path": str(MANIFEST_PATH),
        "generated_manifest_sha256": _sha256(MANIFEST_PATH),
        "generated_qualification_seal_path": str(QUALIFICATION_SEAL_PATH),
        "generated_qualification_seal_sha256": _sha256(QUALIFICATION_SEAL_PATH),
        "fixture_path": str(fixture_path),
        "fixture_sha256": _sha256(fixture_path),
        "production_launcher_path": str(RUNNER_PATH),
        "production_launcher_sha256": _sha256(RUNNER_PATH),
        "author_wrapper_path": str(AUTHOR_WRAPPER_PATH),
        "author_wrapper_sha256": _sha256(AUTHOR_WRAPPER_PATH),
        "orchestration_path": str(Path(__file__).resolve()),
        "orchestration_sha256": _sha256(Path(__file__).resolve()),
        "cells": [cell["cell"]],
        "service_rates": {cell["cell"]: cell["service_rate"]},
        "service_conditions": {cell["cell"]: cell["service_condition"]},
        "expected_baseline_derivation_seal_sha256": _sha256(BASELINE_SEAL_PATH),
        "python_executable": environment["python_executable"],
        "working_directory": environment["cwd"],
        "child_environment": {"PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0"},
        "fault": "",
        "prelaunch_negative_tests": {"formal_operator_preflight": True},
        "evidence_shape_profile": "REAL_C6_CELL",
        "expected_deterministic_core_sha256": "",
    }


def _write_progress(path, progress, state, cell="", cell_state=None, detail=""):
    if cell_state is not None:
        progress["cells"][cell] = cell_state
    progress["state"] = state
    progress["current_cell"] = cell
    progress["detail"] = detail
    progress["history"].append({"state": state, "cell": cell, "cell_state": cell_state or ""})
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(_canonical(progress) + "\n", encoding="utf-8")
    temporary.replace(path)


def _validated_cell_result(runner, result, spec, cell, mode):
    root = _resolved_root(spec["output_root"])
    validator = _read_json(root / "C6_REAL_CELL_VALIDATOR_OUTPUT.json", "real-cell validator output")
    aggregation = _read_json(root / "C6_REAL_CELL_AGGREGATION_OUTPUT.json", "real-cell aggregation output")
    terminal = _read_json(root / "C6_RUN_TERMINAL.json", "real-cell terminal")
    if validator.get("status") != "PASS" or validator.get("tracking_outcome_read") is not False:
        raise FormalGateError("real-cell validator did not pass")
    reports = validator.get("cells")
    if not isinstance(reports, list) or len(reports) != 1 or reports[0].get("cell") != cell["cell"]:
        raise FormalGateError("real-cell validator identity mismatch")
    if aggregation.get("status") != "PASS" or aggregation.get("tracking_outcome_read") is not False:
        raise FormalGateError("real-cell aggregation did not pass")
    if aggregation.get("aggregate", {}).get("cell") != cell["cell"]:
        raise FormalGateError("real-cell aggregation identity mismatch")
    if terminal.get("state") != "RUN_END" or terminal.get("run_id") != spec["run_id"]:
        raise FormalGateError("real-cell terminal is not RUN_END")
    quantities = aggregation.get("quantities")
    if not isinstance(quantities, dict) or quantities != result.get("quantities"):
        raise FormalGateError("real-cell persisted quantity mismatch")
    if mode == "QUALIFICATION":
        serviceable = runner.recompute_real_mve_quantities(result.get("evidence", []))
        if serviceable["B_avoided"] != quantities.get("B_avoided"):
            raise FormalGateError("qualification communication quantity mismatch")
        treatment = serviceable["serviceable_id_state_serviced_bytes_treatment"]
    else:
        treatment = quantities.get("serviceable_id_state_serviced_bytes_treatment")
    if type(quantities.get("B_avoided")) is not int or type(treatment) is not int:
        raise FormalGateError("Formal communication quantity type mismatch")
    baseline = cell["serviceable_id_state_serviced_bytes_baseline"]
    return {
        "cell": cell["cell"], "pair": cell["pair"], "role": cell["role"],
        "service_condition": cell["service_condition"], "service_rate": cell["service_rate"],
        "serviceable_id_state_serviced_bytes_baseline": baseline,
        "B_avoided": quantities["B_avoided"],
        "serviceable_id_state_serviced_bytes_treatment": treatment,
        "delta_B_serviceable": treatment - baseline,
        "mechanical_validity": "PASS", "tracking_outcome_read": False,
        "synthetic_non_scientific": mode == "QUALIFICATION",
    }


def operator(authorization, authorization_path, qualification_no_data=False, qualification_root=None, launcher=None):
    mode = "QUALIFICATION" if qualification_no_data else "LIVE"
    package = validate(authorization, live=not qualification_no_data)
    environment = platform_environment()
    _runtime_preflight(environment)
    run_root, cell_roots = _derive_roots(package, qualification_no_data, qualification_root)
    if not qualification_no_data:
        _storage_preflight(package, cell_roots.values())
    run_root.mkdir(parents=True)
    progress_path = run_root / PROGRESS_NAME
    order = [cell["cell"] for cell in package["cells"]]
    progress = {
        "schema_version": "C6_FORMAL_PROGRESS_V2", "mode": mode, "state": "", "current_cell": "",
        "cell_order": order, "cells": {cell: "NOT_STARTED" for cell in order}, "history": [], "detail": "",
        "tracking_outcome_read": False, "synthetic_non_scientific": qualification_no_data,
    }
    auth_sha = _sha256(authorization_path)
    start = {
        "schema_version": "C6_FORMAL_RUN_START_V1", "mode": mode, "authorization_sha256": auth_sha,
        "cell_order": order, "cell_roots": cell_roots, "tracking_outcome_read": False,
        "synthetic_non_scientific": qualification_no_data, "status": "STARTED",
    }
    _write_exclusive(run_root / "C6_FORMAL_RUN_START.json", start)
    _write_progress(progress_path, progress, "FORMAL_RUN_START")
    runner = load_runner()
    launch = launcher or runner.launch_c6_stage
    rows = []
    current_cell = ""
    try:
        for cell in package["cells"]:
            current_cell = cell["cell"]
            _write_progress(progress_path, progress, "FORMAL_CELL_RUNNING", current_cell, "RUNNING")
            spec = build_cell_launch_spec(mode, cell, cell_roots[current_cell], authorization_path, runner)
            result = launch(spec)
            _write_progress(progress_path, progress, "FORMAL_CELL_CHILD_COMPLETED", current_cell, "CHILD_COMPLETED")
            _write_progress(progress_path, progress, "FORMAL_CELL_VALIDATING", current_cell, "VALIDATING")
            rows.append(_validated_cell_result(runner, result, spec, cell, mode))
            _write_progress(progress_path, progress, "FORMAL_CELL_VALID", current_cell, "VALID")
        current_cell = ""
        _write_progress(progress_path, progress, "FORMAL_AGGREGATING")
        aggregation = {
            "schema_version": "C6_FORMAL_AGGREGATION_V1", "mode": mode, "metrics": list(package["metrics"]),
            "cell_order": order, "cells": rows, "mechanical_validity": "PASS", "tracking_outcome_read": False,
            "synthetic_non_scientific": qualification_no_data, "status": "PASS",
        }
        aggregation_path = _write_exclusive(run_root / "C6_FORMAL_AGGREGATION.json", aggregation)
        seal_payload = {
            "schema_version": "C6_FORMAL_SEAL_PAYLOAD_V1", "mode": mode, "authorization_sha256": auth_sha,
            "run_start_sha256": _sha256(run_root / "C6_FORMAL_RUN_START.json"),
            "aggregation_sha256": _sha256(aggregation_path),
            "cell_terminal_sha256": {
                cell["cell"]: _sha256(_resolved_root(cell_roots[cell["cell"]]) / "C6_RUN_TERMINAL.json")
                for cell in package["cells"]
            },
            "tracking_outcome_read": False, "status": "PASS",
        }
        seal = {"schema_version": "C6_FORMAL_SEAL_V1", "sealed_payload": seal_payload, "seal_sha256": _digest(seal_payload)}
        seal_path = _write_exclusive(run_root / "C6_FORMAL_SEAL.json", seal)
        _write_progress(progress_path, progress, "FORMAL_VALID")
        terminal = {
            "schema_version": "C6_FORMAL_RUN_END_V1", "mode": mode, "state": "FORMAL_RUN_END", "status": "PASS",
            "cell_order": order, "seal_sha256": _sha256(seal_path), "tracking_outcome_read": False,
            "synthetic_non_scientific": qualification_no_data,
        }
        _write_exclusive(run_root / "C6_FORMAL_RUN_END.json", terminal)
        _write_progress(progress_path, progress, "FORMAL_RUN_END")
        return {"root": str(run_root), "progress": progress, "aggregation": aggregation, "seal": seal, "terminal": terminal}
    except Exception as exc:
        if current_cell:
            progress["cells"][current_cell] = "FAILED_QUARANTINED"
        _write_progress(
            progress_path, progress, "FORMAL_FAILED_QUARANTINED", current_cell,
            progress["cells"].get(current_cell) if current_cell else None,
            "{}: {}".format(type(exc).__name__, exc),
        )
        raise


def _read_progress(root):
    path = Path(root) / PROGRESS_NAME
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FormalGateError("Formal progress artifact is unavailable") from exc
    _strict_json_bytes(raw, "Formal progress artifact")
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization")
    parser.add_argument("--qualification-no-data", action="store_true")
    parser.add_argument("--qualification-root")
    parser.add_argument("--progress")
    args = parser.parse_args(argv)
    if args.progress:
        if args.authorization or args.qualification_no_data or args.qualification_root:
            parser.error("--progress cannot be combined with execution arguments")
        sys.stdout.buffer.write(_read_progress(args.progress))
        return 0
    if not args.authorization:
        parser.error("--authorization is required")
    if bool(args.qualification_no_data) != bool(args.qualification_root):
        parser.error("qualification mode requires both --qualification-no-data and --qualification-root")
    authorization_path = Path(args.authorization)
    authorization = _read_json(authorization_path, "Formal authorization")
    result = operator(
        authorization, authorization_path, qualification_no_data=args.qualification_no_data,
        qualification_root=Path(args.qualification_root) if args.qualification_root else None,
    )
    print(_canonical(result["terminal"]))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FormalGateError, RuntimeError, ValueError, OSError) as exc:
        print("{}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        raise SystemExit(1)
