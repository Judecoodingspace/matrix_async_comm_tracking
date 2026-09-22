"""Atomic M7 writers, manifests, seals, and resume behavior for C7 Batch B."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from .mdmt_mia_c7_batch_b import aggregate_cell, qualify_cell, select_qualified_cell
from .mdmt_mia_c7_batch_b_schema import (
    BATCH_A_SEMANTICS_SCHEMA,
    BATCH_A_VALIDATION_SCHEMA,
    BATCH_B_SCHEMA_VERSION,
    CAPACITY_DOMAIN,
    CELL_ARTIFACTS_BEFORE_COMMIT,
    CELL_COMMIT_SCHEMA,
    CELL_INVENTORY_SCHEMA,
    CELL_MANIFEST_SCHEMA,
    CELL_SEAL_SCHEMA,
    FORBIDDEN_OUTCOME_FAMILIES,
    MANIFEST_SCHEMA,
    PACKAGE_ARTIFACTS_BEFORE_COMMIT,
    PACKAGE_COMMIT_SCHEMA,
    PACKAGE_INVENTORY_SCHEMA,
    PACKAGE_SEAL_SCHEMA,
    PACKAGE_VALIDATION_SCHEMA,
    PAIR_DOMAIN,
    SELECTION_SCHEMA,
    SOURCE_HASH_KEYS,
    VALIDATED_WINDOW_SCHEMA,
    authority_bindings,
    canonical_json,
    canonical_sha256,
    registered_cells,
    sha256_file,
)
from .mdmt_mia_c7_batch_b_validator import (
    C7BatchBValidationError,
    read_json,
    read_jsonl,
    validate_cell_files,
    validate_committed_cell,
    validate_committed_package,
    validate_manifest,
    validate_selection,
)


class C7BatchBPackageError(RuntimeError):
    """Raised for transaction, authority, resume, or seal failures."""


_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _require_sha(value: Any, label: str, length: int = 64) -> str:
    pattern = _HEX40 if length == 40 else _HEX64
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise C7BatchBPackageError("{} must be a lowercase SHA-{}".format(label, length * 4))
    return value


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".c7-batch-b-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path | str, value: Any) -> None:
    _atomic_write(
        Path(path),
        (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"),
    )


def atomic_write_jsonl(path: Path | str, records: Sequence[Mapping[str, Any]]) -> None:
    payload = "".join(canonical_json(record) + "\n" for record in records).encode("utf-8")
    _atomic_write(Path(path), payload)


def _inventory(root: Path, names: Sequence[str], schema_version: str) -> dict[str, Any]:
    files = []
    for name in sorted(names):
        path = root / name
        if not path.is_file():
            raise C7BatchBPackageError("missing staged artifact: {}".format(name))
        files.append({
            "path": name,
            "sha256": sha256_file(path),
            "byte_count": path.stat().st_size,
        })
    return {"schema_version": schema_version, "files": files}


def _quarantine(path: Path, reason: str) -> Path:
    for index in range(1, 10000):
        target = path.with_name("{}.quarantine-{}-{:04d}".format(path.name, reason, index))
        if not target.exists():
            os.replace(path, target)
            return target
    raise C7BatchBPackageError("unable to allocate quarantine path")


def build_batch_b_manifest(
    *, run_id: str, output_root: Path | str, batch_b_implementation_sha: str,
    source_hashes: Mapping[str, str], input_identity: Mapping[str, Any],
    config_identity: Mapping[str, Any], synthetic_non_scientific: bool,
) -> dict[str, Any]:
    """Build the immutable 21-cell authority/provenance manifest."""
    if frozenset(source_hashes) != SOURCE_HASH_KEYS:
        raise C7BatchBPackageError("source hash inventory mismatch")
    checked_hashes = {
        key: _require_sha(value, "{} source hash".format(key))
        for key, value in sorted(source_hashes.items())
    }
    implementation_sha = _require_sha(
        batch_b_implementation_sha, "Batch B implementation SHA", 40)
    if not isinstance(synthetic_non_scientific, bool):
        raise C7BatchBPackageError("synthetic marker must be boolean")
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "batch_b_schema_version": BATCH_B_SCHEMA_VERSION,
        "run_id": str(run_id),
        "synthetic_non_scientific": synthetic_non_scientific,
        "authorities": authority_bindings(),
        "batch_b_implementation_sha": implementation_sha,
        "source_hashes": checked_hashes,
        "schema_identities": {
            "batch_a_semantics": BATCH_A_SEMANTICS_SCHEMA,
            "batch_a_validation": BATCH_A_VALIDATION_SCHEMA,
            "validated_window": VALIDATED_WINDOW_SCHEMA,
            "selection": SELECTION_SCHEMA,
        },
        "registered_pair_domain": [
            {"pair_id": pair_id, "frame_count": frame_count}
            for pair_id, frame_count in PAIR_DOMAIN],
        "registered_capacity_domain": [
            {"capacity_id": capacity_id, "capacity_bytes": capacity_bytes}
            for capacity_id, capacity_bytes in CAPACITY_DOMAIN],
        "cells": list(registered_cells()),
        "input_identity": dict(input_identity),
        "config_identity": dict(config_identity),
        "output_root": str(Path(output_root).resolve()),
        "expected_cell_artifacts": [
            "windows.jsonl", "cell_aggregate.json", "cell_qualification.json",
            "cell_manifest.json", "cell_validation.json", "cell_inventory.json",
            "cell_seal.json", "CELL_COMMITTED.json",
        ],
        "expected_package_artifacts": [
            "package_manifest.json", "cell_qualifications.jsonl", "C7_SELECTION.json",
            "package_validation.json", "package_inventory.json", "package_seal.json",
            "PACKAGE_COMMITTED.json",
        ],
        "outcome_firewall_forbidden_families": list(FORBIDDEN_OUTCOME_FAMILIES),
    }
    validate_manifest(manifest)
    return manifest


def build_cell_manifest(
    *, manifest: Mapping[str, Any], cell: Mapping[str, Any],
    expected_frame_domain: Sequence[int], synthetic_non_scientific: bool,
) -> dict[str, Any]:
    return {
        "schema_version": CELL_MANIFEST_SCHEMA,
        "run_id": manifest.get("run_id"),
        "cell": dict(cell),
        "expected_frame_domain": list(expected_frame_domain),
        "batch_b_manifest_sha256": canonical_sha256(manifest),
        "authorities": dict(manifest.get("authorities", {})),
        "source_hashes": dict(manifest.get("source_hashes", {})),
        "schema_identities": dict(manifest.get("schema_identities", {})),
        "input_identity": dict(manifest.get("input_identity", {})),
        "config_identity": dict(manifest.get("config_identity", {})),
        "synthetic_non_scientific": bool(synthetic_non_scientific),
        "expected_artifacts": list(manifest.get("expected_cell_artifacts", ())),
    }


def write_cell_transaction(
    *, output_root: Path | str, manifest: Mapping[str, Any], cell: Mapping[str, Any],
    expected_frame_domain: Sequence[int], windows: Sequence[Mapping[str, Any]],
    synthetic_non_scientific: bool,
) -> dict[str, Any]:
    """Write, reread, validate, seal, and atomically commit one cell."""
    root = Path(output_root)
    validate_manifest(manifest)
    cells_root = root / "cells"
    cells_root.mkdir(parents=True, exist_ok=True)
    final = cells_root / str(cell["cell_id"])
    staging = cells_root / ".{}.staging".format(cell["cell_id"])
    manifest_sha = canonical_sha256(manifest)

    if final.exists():
        if not (final / "CELL_COMMITTED.json").is_file():
            _quarantine(final, "missing-terminal")
        else:
            try:
                validation = validate_committed_cell(
                    final, expected_manifest_sha256=manifest_sha)
            except C7BatchBValidationError as exc:
                raise C7BatchBPackageError("existing final cell is invalid or mismatched") from exc
            return {**validation, "status": "SKIPPED_VALID_SEALED", "cell_root": str(final)}
    if staging.exists():
        _quarantine(staging, "incomplete-staging")
    staging.mkdir()
    try:
        cell_manifest = build_cell_manifest(
            manifest=manifest, cell=cell, expected_frame_domain=expected_frame_domain,
            synthetic_non_scientific=synthetic_non_scientific)
        aggregate = aggregate_cell(
            run_id=str(manifest.get("run_id")), cell=cell,
            expected_frame_domain=expected_frame_domain, validated_windows=windows)
        qualification = qualify_cell(aggregate)
        atomic_write_jsonl(staging / "windows.jsonl", windows)
        atomic_write_json(staging / "cell_aggregate.json", aggregate)
        atomic_write_json(staging / "cell_qualification.json", qualification)
        atomic_write_json(staging / "cell_manifest.json", cell_manifest)
        validation = validate_cell_files(staging)
        atomic_write_json(staging / "cell_validation.json", validation)
        inventory = _inventory(
            staging, CELL_ARTIFACTS_BEFORE_COMMIT, CELL_INVENTORY_SCHEMA)
        atomic_write_json(staging / "cell_inventory.json", inventory)
        payload = {
            "run_id": cell_manifest["run_id"],
            "cell_id": cell["cell_id"],
            "cell_manifest_sha256": sha256_file(staging / "cell_manifest.json"),
            "inventory_sha256": canonical_sha256(inventory),
            "status": "VALIDATED",
        }
        seal = {
            "schema_version": CELL_SEAL_SCHEMA,
            "sealed_payload": payload,
            "seal_sha256": canonical_sha256(payload),
        }
        atomic_write_json(staging / "cell_seal.json", seal)
        terminal = {
            "schema_version": CELL_COMMIT_SCHEMA,
            "status": "COMMITTED",
            "cell_id": cell["cell_id"],
            "inventory_sha256": payload["inventory_sha256"],
            "seal_sha256": seal["seal_sha256"],
        }
        atomic_write_json(staging / "CELL_COMMITTED.json", terminal)
        os.replace(staging, final)
    except Exception:
        if staging.exists():
            _quarantine(staging, "failed-transaction")
        raise
    final_validation = validate_committed_cell(final, expected_manifest_sha256=manifest_sha)
    return {**final_validation, "status": "COMMITTED", "cell_root": str(final)}


def write_selection_package(
    *, output_root: Path | str, manifest: Mapping[str, Any],
    qualifications: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Atomically write the all-21 synthetic/mechanical selection package."""
    root = Path(output_root)
    validate_manifest(manifest)
    final = root / "package"
    staging = root / ".package.staging"
    if final.exists():
        if not (final / "PACKAGE_COMMITTED.json").is_file():
            _quarantine(final, "missing-terminal")
        else:
            try:
                validation = validate_committed_package(final)
            except C7BatchBValidationError as exc:
                raise C7BatchBPackageError("existing final package is invalid or mismatched") from exc
            if validation.get("manifest_sha256") != canonical_sha256(manifest):
                raise C7BatchBPackageError("existing package manifest mismatch")
            return {**validation, "status": "SKIPPED_VALID_SEALED", "package_root": str(final)}
    if staging.exists():
        _quarantine(staging, "incomplete-staging")
    staging.mkdir(parents=True)
    try:
        selection = select_qualified_cell(manifest, qualifications)
        atomic_write_json(staging / "package_manifest.json", manifest)
        atomic_write_jsonl(staging / "cell_qualifications.jsonl", qualifications)
        atomic_write_json(staging / "C7_SELECTION.json", selection)
        disk_manifest = read_json(staging / "package_manifest.json")
        disk_qualifications = read_jsonl(staging / "cell_qualifications.jsonl")
        disk_selection = read_json(staging / "C7_SELECTION.json")
        selection_validation = validate_selection(
            disk_manifest, disk_qualifications, disk_selection)
        package_validation = {
            "schema_version": PACKAGE_VALIDATION_SCHEMA,
            "status": "PASS",
            "run_id": disk_manifest.get("run_id"),
            "manifest_sha256": canonical_sha256(disk_manifest),
            "qualification_count": len(disk_qualifications),
            "selection_validation": selection_validation,
            "outcome_firewall": "PASS",
        }
        atomic_write_json(staging / "package_validation.json", package_validation)
        inventory = _inventory(
            staging, PACKAGE_ARTIFACTS_BEFORE_COMMIT, PACKAGE_INVENTORY_SCHEMA)
        atomic_write_json(staging / "package_inventory.json", inventory)
        payload = {
            "run_id": manifest.get("run_id"),
            "manifest_sha256": sha256_file(staging / "package_manifest.json"),
            "selection_sha256": sha256_file(staging / "C7_SELECTION.json"),
            "inventory_sha256": canonical_sha256(inventory),
            "status": "VALIDATED",
        }
        seal = {
            "schema_version": PACKAGE_SEAL_SCHEMA,
            "sealed_payload": payload,
            "seal_sha256": canonical_sha256(payload),
        }
        atomic_write_json(staging / "package_seal.json", seal)
        atomic_write_json(staging / "PACKAGE_COMMITTED.json", {
            "schema_version": PACKAGE_COMMIT_SCHEMA,
            "status": "COMMITTED",
            "inventory_sha256": payload["inventory_sha256"],
            "seal_sha256": seal["seal_sha256"],
        })
        os.replace(staging, final)
    except Exception:
        if staging.exists():
            _quarantine(staging, "failed-transaction")
        raise
    final_validation = validate_committed_package(final)
    return {**final_validation, "status": "COMMITTED", "package_root": str(final)}
