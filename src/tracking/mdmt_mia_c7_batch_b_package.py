"""Atomic M7 writers, manifests, seals, and resume behavior for C7 Batch B."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
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
    ALLOWED_PARENT_ENV_KEYS,
    REGISTERED_SOURCE_RELATIVE_PATHS,
    SELECTION_SCHEMA,
    SOURCE_HASH_KEYS,
    VALIDATED_WINDOW_SCHEMA,
    authority_bindings,
    authorized_frame_domains,
    canonical_json,
    canonical_sha256,
    registered_cells,
    registered_file_class_id,
    sha256_file,
    validate_registered_communication_content,
)
from .mdmt_mia_c7_batch_b_validator import (
    C7BatchBValidationError,
    read_json,
    read_jsonl,
    reconstruct_verified_cell_inventory,
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


def _git_text(repo_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise C7BatchBPackageError("registered provenance Git preflight failed") from exc
    return completed.stdout.strip()


def _canonical_file(path: Path | str, label: str) -> Path:
    try:
        resolved = Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise C7BatchBPackageError("{} is not a resolvable file".format(label)) from exc
    if not resolved.is_file():
        raise C7BatchBPackageError("{} is not a file".format(label))
    return resolved


def _require_within(path: Path, root: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise C7BatchBPackageError(
            "{} escapes registered repository root".format(label)) from exc


def _registered_file_identity(
    identity: Mapping[str, Any], *, label: str, expected_kind: str,
) -> dict[str, Any]:
    if not isinstance(identity, Mapping) or frozenset(identity) != {"kind", "files"}:
        raise C7BatchBPackageError("registered {} identity schema mismatch".format(label))
    if identity.get("kind") != expected_kind:
        raise C7BatchBPackageError("registered {} identity kind mismatch".format(label))
    files = identity.get("files")
    if not isinstance(files, list) or not files:
        raise C7BatchBPackageError("registered {} files are missing".format(label))
    file_class_id = registered_file_class_id(expected_kind)
    observed = []
    seen = set()
    for index, row in enumerate(files):
        if not isinstance(row, Mapping) or frozenset(row) != {"path", "sha256"}:
            raise C7BatchBPackageError("registered {} file schema mismatch".format(label))
        path = _canonical_file(row.get("path", ""), "{} file {}".format(label, index))
        if str(path) in seen:
            raise C7BatchBPackageError("duplicate registered {} file".format(label))
        seen.add(str(path))
        # Read bytes once, hash those bytes, parse/validate those same bytes.
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise C7BatchBPackageError("registered {} file unreadable".format(label)) from exc
        actual = hashlib.sha256(raw).hexdigest()
        if row.get("sha256") != actual:
            raise C7BatchBPackageError("registered {} digest mismatch".format(label))
        try:
            validate_registered_communication_content(
                raw, class_id=file_class_id,
                label="{} file {}".format(label, index))
        except ValueError as exc:
            raise C7BatchBPackageError(
                "registered {} file content failed communication-only validation: {}".format(
                    label, exc)) from exc
        observed.append({"path": str(path), "sha256": actual})
    observed.sort(key=lambda row: row["path"])
    return {
        "kind": expected_kind,
        "files": observed,
        "digest": canonical_sha256(observed),
    }


def _registered_provenance(
    *, repo_root: Path | str, claimed_implementation_sha: str,
    claimed_source_hashes: Mapping[str, str] | None,
    wrapper_path: Path | str | None, generated_source_root: Path | str | None,
    input_identity: Mapping[str, Any], config_identity: Mapping[str, Any],
) -> tuple[str, dict[str, str], dict[str, str], dict[str, Any], dict[str, Any],
           dict[str, Any], dict[str, Any]]:
    try:
        root = Path(repo_root).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise C7BatchBPackageError("registered repository root is invalid") from exc
    observed_root = Path(_git_text(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if observed_root != root:
        raise C7BatchBPackageError("registered repository root is not canonical Git root")
    observed_head = _git_text(root, "rev-parse", "HEAD")
    claimed = _require_sha(
        claimed_implementation_sha, "Batch B implementation SHA", 40)
    if claimed != observed_head:
        raise C7BatchBPackageError("registered implementation SHA differs from actual Git HEAD")
    if _git_text(root, "status", "--porcelain", "--untracked-files=all"):
        raise C7BatchBPackageError("registered provenance requires a clean worktree")

    expected_wrapper = (root / REGISTERED_SOURCE_RELATIVE_PATHS["wrapper"]).resolve(strict=True)
    _require_within(expected_wrapper, root, "registered wrapper")
    wrapper = expected_wrapper if wrapper_path is None else _canonical_file(
        wrapper_path, "registered wrapper")
    if wrapper != expected_wrapper:
        raise C7BatchBPackageError("registered wrapper path differs from frozen source inventory")
    source_paths = {}
    source_hashes = {}
    for key, relative in sorted(REGISTERED_SOURCE_RELATIVE_PATHS.items()):
        path = wrapper if key == "wrapper" else _canonical_file(
            root / relative, "registered source {}".format(key))
        _require_within(path, root, "registered source {}".format(key))
        source_paths[key] = str(path)
        source_hashes[key] = sha256_file(path)
    if claimed_source_hashes is not None and dict(claimed_source_hashes) != source_hashes:
        raise C7BatchBPackageError("registered source hashes differ from actual files")

    if generated_source_root is None:
        raise C7BatchBPackageError("registered generated-source root is required")
    generated = Path(generated_source_root).resolve()
    repository_identity = {
        "mode": "REGISTERED_C7",
        "repo_root": str(root),
        "git_head": observed_head,
        "worktree_clean": True,
    }
    execution_paths = {
        "wrapper_path": str(wrapper),
        "wrapper_sha256": source_hashes["wrapper"],
        "generated_source_root": str(generated),
        "generated_source_lifecycle": "MATERIALIZED_DURING_REAL_CHILD",
        "generated_source_sha256": None,
    }
    bound_input = _registered_file_identity(
        input_identity, label="input", expected_kind="REGISTERED_C7_INPUT_FILES_V1")
    bound_config = _registered_file_identity(
        config_identity, label="config", expected_kind="REGISTERED_C7_CONFIG_FILES_V1")
    return (
        observed_head, source_hashes, source_paths, repository_identity,
        execution_paths, bound_input, bound_config,
    )


def build_batch_b_manifest(
    *, run_id: str, output_root: Path | str, batch_b_implementation_sha: str,
    source_hashes: Mapping[str, str] | None, input_identity: Mapping[str, Any],
    config_identity: Mapping[str, Any], synthetic_non_scientific: bool,
    repo_root: Path | str | None = None, wrapper_path: Path | str | None = None,
    generated_source_root: Path | str | None = None,
) -> dict[str, Any]:
    """Build the immutable 21-cell authority/provenance manifest."""
    if not isinstance(synthetic_non_scientific, bool):
        raise C7BatchBPackageError("synthetic marker must be boolean")
    if synthetic_non_scientific:
        if not isinstance(source_hashes, Mapping) or frozenset(source_hashes) != SOURCE_HASH_KEYS:
            raise C7BatchBPackageError("source hash inventory mismatch")
        checked_hashes = {
            key: _require_sha(value, "{} source hash".format(key))
            for key, value in sorted(source_hashes.items())
        }
        implementation_sha = _require_sha(
            batch_b_implementation_sha, "Batch B implementation SHA", 40)
        source_paths: dict[str, str] = {}
        repository_identity = {
            "mode": "SYNTHETIC_NON_SCIENTIFIC",
            "repo_root": None,
            "git_head": implementation_sha,
            "worktree_clean": None,
        }
        execution_paths = {
            "wrapper_path": None,
            "wrapper_sha256": None,
            "generated_source_root": None,
            "generated_source_lifecycle": "SYNTHETIC_NON_SCIENTIFIC",
            "generated_source_sha256": None,
        }
        bound_input = dict(input_identity)
        bound_config = dict(config_identity)
    else:
        if repo_root is None:
            raise C7BatchBPackageError("registered repository root is required")
        (
            implementation_sha, checked_hashes, source_paths,
            repository_identity, execution_paths, bound_input, bound_config,
        ) = _registered_provenance(
            repo_root=repo_root,
            claimed_implementation_sha=batch_b_implementation_sha,
            claimed_source_hashes=source_hashes,
            wrapper_path=wrapper_path,
            generated_source_root=generated_source_root,
            input_identity=input_identity,
            config_identity=config_identity,
        )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "batch_b_schema_version": BATCH_B_SCHEMA_VERSION,
        "run_id": str(run_id),
        "synthetic_non_scientific": synthetic_non_scientific,
        "authorities": authority_bindings(),
        "batch_b_implementation_sha": implementation_sha,
        "source_hashes": checked_hashes,
        "source_paths": source_paths,
        "repository_identity": repository_identity,
        "execution_paths": execution_paths,
        "environment_allowlist": list(ALLOWED_PARENT_ENV_KEYS),
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
        "transaction_domain_kind": (
            "SYNTHETIC_NON_SCIENTIFIC" if synthetic_non_scientific else "REGISTERED_C7"),
        "authorized_frame_domains": authorized_frame_domains(synthetic_non_scientific),
        "input_identity": bound_input,
        "config_identity": bound_config,
        "output_root": str(Path(output_root).resolve()),
        "expected_cell_artifacts": [
            "windows.jsonl", "cell_aggregate.json", "cell_qualification.json",
            "cell_manifest.json", "cell_validation.json", "cell_inventory.json",
            "cell_seal.json", "CELL_COMMITTED.json",
        ],
        "expected_package_artifacts": [
            "package_manifest.json", "cell_qualifications.jsonl", "C7_SELECTION.json",
            "verified_cell_inventory.json", "package_validation.json",
            "package_inventory.json", "package_seal.json", "PACKAGE_COMMITTED.json",
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
        "transaction_domain_kind": manifest.get("transaction_domain_kind"),
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
    manifest_cells = manifest.get("cells", ())
    if dict(cell) not in manifest_cells:
        raise C7BatchBPackageError("cell is not an exact member of manifest domain")
    authorized_domain = manifest.get("authorized_frame_domains", {}).get(cell.get("cell_id"))
    if list(expected_frame_domain) != authorized_domain:
        raise C7BatchBPackageError("caller frame domain differs from manifest authority")
    if synthetic_non_scientific is not manifest.get("synthetic_non_scientific"):
        raise C7BatchBPackageError("synthetic/scientific transaction domain mismatch")
    cells_root = root / "cells"
    cells_root.mkdir(parents=True, exist_ok=True)
    final = cells_root / str(cell["cell_id"])
    staging = cells_root / ".{}.staging".format(cell["cell_id"])

    if final.exists():
        if not (final / "CELL_COMMITTED.json").is_file():
            _quarantine(final, "missing-terminal")
        else:
            try:
                validation = validate_committed_cell(final, expected_manifest=manifest)
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
    final_validation = validate_committed_cell(final, expected_manifest=manifest)
    return {**final_validation, "status": "COMMITTED", "cell_root": str(final)}


def write_selection_package(
    *, output_root: Path | str, manifest: Mapping[str, Any],
    qualifications: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive selection only from the exact manifest-bound sealed cell set."""
    root = Path(output_root)
    validate_manifest(manifest)
    if qualifications is not None:
        raise C7BatchBPackageError(
            "caller-supplied qualifications are not authoritative package inputs")
    verified_inventory, sealed_qualifications = reconstruct_verified_cell_inventory(
        root, manifest)
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
        selection = select_qualified_cell(manifest, sealed_qualifications)
        atomic_write_json(staging / "package_manifest.json", manifest)
        atomic_write_jsonl(staging / "cell_qualifications.jsonl", sealed_qualifications)
        atomic_write_json(staging / "C7_SELECTION.json", selection)
        atomic_write_json(staging / "verified_cell_inventory.json", verified_inventory)
        disk_manifest = read_json(staging / "package_manifest.json")
        disk_qualifications = read_jsonl(staging / "cell_qualifications.jsonl")
        disk_selection = read_json(staging / "C7_SELECTION.json")
        disk_verified_inventory = read_json(staging / "verified_cell_inventory.json")
        rebuilt_inventory, rebuilt_qualifications = reconstruct_verified_cell_inventory(
            root, disk_manifest)
        if (disk_verified_inventory != rebuilt_inventory
                or disk_qualifications != rebuilt_qualifications):
            raise C7BatchBPackageError("sealed-cell inventory changed during package staging")
        selection_validation = validate_selection(
            disk_manifest, disk_qualifications, disk_selection)
        package_validation = {
            "schema_version": PACKAGE_VALIDATION_SCHEMA,
            "status": "PASS",
            "run_id": disk_manifest.get("run_id"),
            "manifest_sha256": canonical_sha256(disk_manifest),
            "qualification_count": len(disk_qualifications),
            "verified_cell_inventory_sha256": canonical_sha256(disk_verified_inventory),
            "all_21_cell_seals_verified": True,
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
            "verified_cell_inventory_sha256": sha256_file(
                staging / "verified_cell_inventory.json"),
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
