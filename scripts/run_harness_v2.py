#!/usr/bin/env python3
"""Harness v2 readiness CLI: read, validate, classify, rehearse, report."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from tracking.harness_v2 import (  # noqa: E402
    AuthorityBinding,
    HarnessError,
    classify_repository_state,
    compute_platform_identity,
    readiness_check,
    sha256_file,
    validate_evidence_root_agreement,
)


PLATFORM_AUTHORITY_PATH = ROOT / "summary_md/communication/harness_v2/PLATFORM_AUTHORITY_V2.json"
QUALIFICATION_EVIDENCE_PATH = ROOT / "summary_md/communication/harness_v2/PLATFORM_QUALIFICATION_EVIDENCE_V2.json"
FORMAL_PATH = ROOT / "scripts/run_mdmt_mia_c6_formal.py"
RUNNER_PATH = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"
CHILD_PATH = ROOT / "scripts/run_mdmt_mia_c6_real_child.py"
WRAPPER_PATH = ROOT / "scripts/run_mdmt_mia_author_sync.sh"
FAKE_AUTHOR_PATH = ROOT / "tests/fixtures/fake_mdmt_mia_c6_author.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _read_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HarnessError("{}_INVALID".format(label)) from exc
    if not isinstance(value, dict):
        raise HarnessError("{}_INVALID".format(label))
    return value


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def platform_components() -> dict[str, str]:
    return {
        "operator": str(FORMAL_PATH),
        "launcher": str(RUNNER_PATH),
        "real_child": str(CHILD_PATH),
        "wrapper": str(WRAPPER_PATH),
        "harness_core": str(ROOT / "src/tracking/harness_v2.py"),
        "validator_sources": str(RUNNER_PATH),
    }


def current_platform_identity() -> dict:
    return compute_platform_identity(platform_components())


def _write_exclusive_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(_canonical(value) + "\n")


def _prepare_rehearsal_inputs(rehearsal_root: Path, formal, runner) -> tuple[dict, Path]:
    """Create isolated non-authoritative source/data for the fake author only."""
    input_root = rehearsal_root.parent / "_inputs" / rehearsal_root.name
    if input_root.exists() or input_root.is_symlink():
        raise HarnessError("ATTEMPT_NAMESPACE_OCCUPIED")
    environment = formal.platform_environment()
    runtime_origin = Path(environment["runtime_origin"]["file"])
    if not runtime_origin.is_file() or not FAKE_AUTHOR_PATH.is_file():
        raise HarnessError("REHEARSAL_INPUT_UNAVAILABLE")
    generated_root = input_root / "mia-root/variants/harness-v2-rehearsal"
    utils_root = generated_root / "demo/utils"
    utils_root.mkdir(parents=True)
    shutil.copy2(runtime_origin, utils_root / "async_deadline_runtime.py")
    shutil.copy2(FAKE_AUTHOR_PATH, generated_root / "demo/supplement_MIA.py")
    mia_root = generated_root.parents[1]
    python_path = mia_root / ".conda-env/bin/python"
    python_path.parent.mkdir(parents=True)
    python_path.symlink_to(environment["python_executable"])
    config = mia_root / "run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py"
    config.parent.mkdir(parents=True)
    config.write_text("# Harness v2 non-scientific rehearsal\n", encoding="utf-8")
    mdmt_root = input_root / "mdmt"
    cells = formal.pkg()["cells"]
    for cell in cells:
        pair = str(cell["pair"])
        pair = pair[1:] if pair.startswith("P") else pair
        for path in (mdmt_root / "train/1/{}-1".format(pair), mdmt_root / "train/2/{}-2".format(pair)):
            path.mkdir(parents=True, exist_ok=True)
        for camera in ("1", "2"):
            xml = mdmt_root / "new_xml" / camera / "{}-{}.xml".format(pair, camera)
            xml.parent.mkdir(parents=True, exist_ok=True)
            xml.write_text("<non_scientific_rehearsal/>\n", encoding="utf-8")
    checkpoint = mdmt_root / "checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"harness-v2-non-scientific")
    generated_root = generated_root.resolve()
    mdmt_root = mdmt_root.resolve()
    input_root = input_root.resolve()
    inventory = [
        {"relative_path": path.relative_to(generated_root).as_posix(), "raw_sha256": sha256_file(path)}
        for path in sorted((item for item in generated_root.rglob("*") if item.is_file()), key=lambda item: str(item))
    ]
    manifest_path = input_root / "generated-manifest.json"
    _write_exclusive_json(manifest_path, {
        "generated_source_root": str(generated_root),
        "implementation_sha": runner.MVE_IMPLEMENTATION_SHA,
        "generated_source_inventory": inventory,
        "temporary": True,
        "non_scientific": True,
        "non_authoritative": True,
    })
    seal_path = input_root / "generated-seal.json"
    _write_exclusive_json(seal_path, {
        "status": "PLATFORM_REHEARSAL_NON_SCIENTIFIC",
        "temporary": True,
        "non_authoritative": True,
    })
    candidate_path = input_root / "inactive-rehearsal-authorization.json"
    _write_exclusive_json(candidate_path, formal.candidate(False))
    return {
        "generated_root": str(generated_root),
        "generated_manifest_path": str(manifest_path.resolve()),
        "generated_manifest_sha256": sha256_file(manifest_path),
        "generated_qualification_seal_path": str(seal_path.resolve()),
        "generated_qualification_seal_sha256": sha256_file(seal_path),
        "mdmt_root": str(mdmt_root),
        "author_record_root": str((input_root / "author-records").resolve()),
    }, candidate_path.resolve()


def run_exact_rehearsal(rehearsal_root: Path) -> dict:
    """Run the real Operator→Launcher→Child→Wrapper path with a fake author."""
    if rehearsal_root.is_absolute():
        try:
            logical_root = rehearsal_root.resolve().relative_to(ROOT).as_posix()
        except ValueError as exc:
            raise HarnessError("NON_CANONICAL_EXECUTION_ROOT") from exc
    else:
        logical_root = rehearsal_root.as_posix()
    formal = _load_module(FORMAL_PATH, "harness_v2_formal_operator")
    runner = _load_module(RUNNER_PATH, "harness_v2_production_launcher")
    context, candidate_path = _prepare_rehearsal_inputs(Path(logical_root), formal, runner)
    authorization = _read_object(candidate_path, "FORMAL_AUTHORIZATION_CANDIDATE")
    result = formal.operator(
        authorization, candidate_path, qualification_root=Path(logical_root),
        rehearsal=True, rehearsal_context=context,
    )
    root = ROOT / logical_root
    records = {}
    evidence_roots = {}
    for cell in formal.pkg()["cells"]:
        record_path = Path(context["author_record_root"]) / (cell["cell"] + ".json")
        record = _read_object(record_path, "REHEARSAL_AUTHOR_RECORD")
        records[cell["cell"]] = record
        pair = str(cell["pair"])
        pair = pair[1:] if pair.startswith("P") else pair
        validator_root = root / "cells" / cell["cell"] / "cells" / cell["cell"] / "mia" / "train_{}".format(pair) / "results" / "mia_train_{}".format(pair)
        evidence_roots[cell["cell"]] = str(validate_evidence_root_agreement(
            root, Path(record["result_dir"]) / "mia_train_{}".format(pair), validator_root,
        ))
    report = {
        "schema_version": "HARNESS_V2_REHEARSAL_REPORT_V1",
        "temporary": True,
        "synthetic_non_scientific": True,
        "non_authoritative": True,
        "logical_root": logical_root,
        "canonical_root": str(root.resolve()),
        "REAL_SUBPROCESS_USED": "YES",
        "REAL_WRAPPER_USED": "YES",
        "REAL_CWD_CHANGE_EXERCISED": "YES",
        "REAL_EVIDENCE_WRITER_USED": "YES",
        "REAL_VALIDATOR_USED": "YES",
        "NO_NESTED_CWD_REBASE_ARTIFACT": "YES",
        "PRODUCER_EVIDENCE_ROOT_EQUALS_VALIDATOR_EVIDENCE_ROOT": "YES",
        "NO_EXECUTION_PATH_FIRST_EXERCISED_IN_FORMAL": "YES",
        "cells": [cell["cell"] for cell in formal.pkg()["cells"]],
        "author_records": records,
        "evidence_roots": evidence_roots,
        "formal_terminal": result["terminal"],
    }
    _write_exclusive_json(root / "HARNESS_V2_REHEARSAL_REPORT.json", report)
    return report


def _candidate_binding(science_path: Path, platform: dict, candidate_path: Path, attempt_id: str) -> AuthorityBinding:
    candidate = _read_object(candidate_path, "FORMAL_AUTHORIZATION_CANDIDATE")
    if candidate.get("execution_authorized") is not False or candidate.get("formal_allowed") is not False:
        raise HarnessError("FORMAL_AUTHORIZATION_CANDIDATE_INVALID")
    science_sha = sha256_file(science_path)
    if candidate.get("science_authority_sha256") not in (None, science_sha):
        raise HarnessError("FORMAL_AUTHORIZATION_CANDIDATE_INVALID")
    if candidate.get("platform_v2_sha") not in (None, platform["platform_v2_sha"]):
        raise HarnessError("FORMAL_AUTHORIZATION_CANDIDATE_INVALID")
    return AuthorityBinding(science_sha, platform["platform_v2_sha"], attempt_id)


def qualify(args: argparse.Namespace) -> int:
    science_path = Path(args.science_authority)
    platform_path = Path(args.platform_authority)
    candidate_path = Path(args.formal_authorization_candidate)
    platform = _read_object(platform_path, "PLATFORM_AUTHORITY")
    current = current_platform_identity()
    if platform != current:
        raise HarnessError("PLATFORM_AUTHORITY_INVALID")
    binding = _candidate_binding(science_path, platform, candidate_path, args.attempt_id)
    evidence = _read_object(QUALIFICATION_EVIDENCE_PATH, "PLATFORM_QUALIFICATION_EVIDENCE") if QUALIFICATION_EVIDENCE_PATH.is_file() else None
    attempt_root = ROOT / "formal_attempts" / args.attempt_id
    state = classify_repository_state(
        ROOT,
        [ROOT / "scripts", ROOT / "src", ROOT / "tests", ROOT / "summary_md/communication/harness_v2"],
        {platform_path: sha256_file(platform_path)},
        attempt_root,
    )
    verdict = readiness_check(binding, platform, evidence, state)
    if verdict.get("FORMAL_READY") != "YES":
        print("FORMAL_READY = NO")
        print("BLOCKER = {}".format(verdict["BLOCKER"]))
        return 1
    rehearsal_root = Path(args.rehearsal_root) if args.rehearsal_root else Path("outputs/harness_v2_rehearsals") / args.attempt_id
    report = run_exact_rehearsal(rehearsal_root)
    if report["formal_terminal"].get("status") != "PASS":
        print("FORMAL_READY = NO")
        print("BLOCKER = EXACT_REHEARSAL_FAILED")
        return 1
    print("FORMAL_READY = YES")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    command = subparsers.add_parser("qualify")
    command.add_argument("--science-authority", required=True)
    command.add_argument("--platform-authority", default=str(PLATFORM_AUTHORITY_PATH))
    command.add_argument("--formal-authorization-candidate", required=True)
    command.add_argument("--attempt-id", required=True)
    command.add_argument("--rehearsal-root")
    args = parser.parse_args(argv)
    try:
        return qualify(args)
    except HarnessError as exc:
        print("FORMAL_READY = NO")
        print("BLOCKER = {}".format(exc))
        return 1
    except Exception as exc:  # fail closed without exposing a traceback as a verdict
        print("FORMAL_READY = NO")
        print("BLOCKER = HARNESS_INTERNAL_ERROR")
        print("{}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
