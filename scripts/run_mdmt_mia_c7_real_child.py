#!/usr/bin/env python3
"""C7 child boundary for synthetic proof and future authorized real execution."""

from __future__ import annotations

import argparse
import json
import os
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
    sha256_file,
)
from tracking.mdmt_mia_c7_batch_b_validator import read_jsonl


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


def _environment_attestation() -> dict:
    return {
        "environment_keys": sorted(os.environ),
        "allowed_parent_environment": {
            key: os.environ[key] for key in ALLOWED_PARENT_ENV_KEYS if key in os.environ
        },
        "bound_environment": {
            key: os.environ.get(key) for key in (
                "PYTHONNOUSERSITE", "PYTHONHASHSEED", "PYTHONPATH",
                "MDMT_MIA_C7_CHILD_BOUNDARY",
            )
        },
    }


def build_real_wrapper_command(spec: dict) -> tuple[list[str], dict[str, str]]:
    """Build the real author-wrapper path without reading any result artifact."""
    _verify_authorities(spec)
    if spec.get("mode") != "REAL_C7_CELL":
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
            **_environment_attestation(),
        }
        atomic_write_json(output_root / "CHILD_STATUS.json", status)
        return status
    if mode != "REAL_C7_CELL":
        raise C7ChildError("unsupported child mode")
    command, controlled = build_real_wrapper_command(spec)
    if spec.get("dry_run") is True:
        status = {
            "schema_version": "C7_CHILD_STATUS_V1",
            "status": "PATH_VALID",
            "mode": mode,
            "synthetic_non_scientific": False,
            "wrapper_command": command,
            "controlled_environment_keys": sorted(controlled),
            "real_input_executed": False,
            **_environment_attestation(),
        }
        atomic_write_json(output_root / "CHILD_STATUS.json", status)
        return status
    raise C7ChildError(
        "non-dry REAL_C7_CELL execution is unconditionally blocked in Batch B")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    args = parser.parse_args(argv)
    execute_child(_load(args.spec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
