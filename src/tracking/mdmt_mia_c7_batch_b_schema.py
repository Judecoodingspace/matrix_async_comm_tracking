"""Declarative schemas and frozen authorities for C7 Batch B.

This module intentionally contains no aggregation, qualification, selection,
or validation decisions.  Producer and independent validator may share only
these declarations and canonical serialization helpers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


BATCH_B_SCHEMA_VERSION = "C7_BATCH_B_SCHEMA_V1"
VALIDATED_WINDOW_SCHEMA = "C7_VALIDATED_WINDOW_V1"
NO_STALE_VALIDATION_SCHEMA = "C7_NO_STALE_VALIDATION_V1"
NO_STALE_RAW_OBSERVATION_SCHEMA = "C7_NO_STALE_RAW_OBSERVATION_V1"
CELL_AGGREGATE_SCHEMA = "C7_CELL_AGGREGATE_V1"
CELL_QUALIFICATION_SCHEMA = "C7_CELL_QUALIFICATION_V1"
SELECTION_SCHEMA = "C7_SELECTION_V1"
MANIFEST_SCHEMA = "C7_BATCH_B_MANIFEST_V1"
CELL_MANIFEST_SCHEMA = "C7_CELL_MANIFEST_V1"
CELL_VALIDATION_SCHEMA = "C7_CELL_VALIDATION_V1"
CELL_INVENTORY_SCHEMA = "C7_CELL_INVENTORY_V1"
CELL_SEAL_SCHEMA = "C7_CELL_SEAL_V1"
CELL_COMMIT_SCHEMA = "C7_CELL_COMMIT_V1"
PACKAGE_VALIDATION_SCHEMA = "C7_PACKAGE_VALIDATION_V1"
VERIFIED_CELL_INVENTORY_SCHEMA = "C7_VERIFIED_CELL_INVENTORY_V1"
PACKAGE_INVENTORY_SCHEMA = "C7_PACKAGE_INVENTORY_V1"
PACKAGE_SEAL_SCHEMA = "C7_PACKAGE_SEAL_V1"
PACKAGE_COMMIT_SCHEMA = "C7_PACKAGE_COMMIT_V1"

FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY = (
    "f484ac5b886e68393c581936f1e764d4d08366d8"
)
BATCH_A_FREEZE_AUTHORITY = "a588d526511994ba52ba1cad74a9c0a3cb4f00b4"
SPECIFICATION_CONTENT_AUTHORITY = "67f9b07a00141d380952f6a6cc9ae23f34c1cd7d"
SPECIFICATION_FREEZE_COMMIT = "0eda32c58871c1ec4b5b194c0c33608d7dd2a777"
IMPLEMENTATION_PLAN_COMMIT = "b850b7fcbc026fbcb49de7c85cf9b43c41adcc0b"
IMPLEMENTATION_PLAN_SHA256 = (
    "6b7aeedf0b4215cd57b332fb9720d33e636d854230565d69ea6c8d3af3bc7465"
)

BATCH_A_SEMANTICS_SCHEMA = "C7_CORE_SEMANTICS_V3"
BATCH_A_VALIDATION_SCHEMA = "C7_CORE_VALIDATION_V3"

PAIR_DOMAIN = (
    ("P23", 700),
    ("P44", 360),
    ("P66", 300),
)
CAPACITY_DOMAIN = (
    ("P20", 16649),
    ("P30", 20147),
    ("P40", 25456),
    ("P50", 26148),
    ("P60", 28109),
    ("P70", 29620),
    ("P80", 31987),
)

T_COUNT = 5
T_DENOMINATOR = 20
GLOBAL_MULTIPLIER = 60
CONDITIONAL_MULTIPLIER = 4

CELL_ARTIFACTS_BEFORE_COMMIT = (
    "cell_aggregate.json",
    "cell_manifest.json",
    "cell_qualification.json",
    "cell_validation.json",
    "windows.jsonl",
)
CELL_AUTHORITATIVE_FILES = tuple(sorted(CELL_ARTIFACTS_BEFORE_COMMIT + (
    "CELL_COMMITTED.json",
    "cell_inventory.json",
    "cell_seal.json",
)))
PACKAGE_ARTIFACTS_BEFORE_COMMIT = (
    "C7_SELECTION.json",
    "cell_qualifications.jsonl",
    "package_manifest.json",
    "package_validation.json",
    "verified_cell_inventory.json",
)
PACKAGE_AUTHORITATIVE_FILES = tuple(sorted(PACKAGE_ARTIFACTS_BEFORE_COMMIT + (
    "PACKAGE_COMMITTED.json",
    "package_inventory.json",
    "package_seal.json",
)))

FORBIDDEN_OUTCOME_FAMILIES = (
    "idf1",
    "idsw",
    "mota",
    "hota",
    "tracking_metric",
    "tracking_accuracy",
    "tracking accuracy",
    "tracking_outcome",
    "tracking outcome",
    "detection_quality",
    "detection quality",
    "evaluation/mdmt_mia_paper",
    "scientific_result",
    "scientific result",
)
SOURCE_HASH_KEYS = frozenset({
    "runtime", "batch_a_producer", "batch_a_validator", "batch_b_schema",
    "batch_b_aggregator", "batch_b_selector", "batch_b_validator",
    "batch_b_package", "launcher", "child", "packet_definitions",
    "generated_source_preparer", "wrapper",
})

# Declarative only: producer and validator independently resolve and hash these
# paths for REGISTERED_C7 provenance.
REGISTERED_SOURCE_RELATIVE_PATHS = {
    "runtime": "src/tracking/mdmt_mia_async_deadline_runtime.py",
    "batch_a_producer": "src/tracking/mdmt_mia_c7_census.py",
    "batch_a_validator": "src/tracking/mdmt_mia_c7_validator.py",
    "batch_b_schema": "src/tracking/mdmt_mia_c7_batch_b_schema.py",
    "batch_b_aggregator": "src/tracking/mdmt_mia_c7_batch_b.py",
    "batch_b_selector": "src/tracking/mdmt_mia_c7_batch_b.py",
    "batch_b_validator": "src/tracking/mdmt_mia_c7_batch_b_validator.py",
    "batch_b_package": "src/tracking/mdmt_mia_c7_batch_b_package.py",
    "launcher": "scripts/run_mdmt_mia_c7_outcome_blind_census.py",
    "child": "scripts/run_mdmt_mia_c7_real_child.py",
    "packet_definitions": "src/tracking/mdmt_mia_packets.py",
    "generated_source_preparer": "scripts/prepare_mdmt_mia_async_packet_variant.py",
    "wrapper": "scripts/run_mdmt_mia_author_sync.sh",
}

ALLOWED_PARENT_ENV_KEYS = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TMPDIR",
    "CUDA_VISIBLE_DEVICES",
    "LD_LIBRARY_PATH",
    "NVIDIA_VISIBLE_DEVICES",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_cell_id(pair_id: str, capacity_id: str) -> str:
    return "{}__{}".format(pair_id, capacity_id)


def registered_cells() -> tuple[dict[str, Any], ...]:
    cells = []
    for pair_order, (pair_id, frame_count) in enumerate(PAIR_DOMAIN):
        for capacity_order, (capacity_id, capacity_bytes) in enumerate(CAPACITY_DOMAIN):
            cells.append({
                "cell_id": stable_cell_id(pair_id, capacity_id),
                "pair_id": pair_id,
                "frame_count": frame_count,
                "capacity_id": capacity_id,
                "capacity_bytes": capacity_bytes,
                "stable_pair_order": pair_order,
                "stable_capacity_order": capacity_order,
            })
    return tuple(cells)


REGISTERED_CELL_IDS = tuple(cell["cell_id"] for cell in registered_cells())


def authorized_frame_domains(synthetic_non_scientific: bool) -> dict[str, list[int]]:
    """Return the manifest-bound frame domain for every registered cell."""
    return {
        cell["cell_id"]: ([0] if synthetic_non_scientific else list(range(cell["frame_count"])))
        for cell in registered_cells()
    }


def authority_bindings() -> dict[str, str]:
    return {
        "specification_content_authority": SPECIFICATION_CONTENT_AUTHORITY,
        "specification_freeze_commit": SPECIFICATION_FREEZE_COMMIT,
        "implementation_plan_commit": IMPLEMENTATION_PLAN_COMMIT,
        "implementation_plan_sha256": IMPLEMENTATION_PLAN_SHA256,
        "frozen_batch_a_implementation_authority": (
            FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY),
        "batch_a_freeze_authority": BATCH_A_FREEZE_AUTHORITY,
    }


def contains_forbidden_outcome_content(value: Any) -> bool:
    """Recursively scan artifact keys, string values, and path-like content."""
    if isinstance(value, Mapping):
        return any(
            contains_forbidden_outcome_content(str(key))
            or contains_forbidden_outcome_content(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(contains_forbidden_outcome_content(item) for item in value)
    if isinstance(value, str):
        normalized = value.casefold().replace("\\", "/")
        return any(token in normalized for token in FORBIDDEN_OUTCOME_FAMILIES)
    return False
