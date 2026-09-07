"""Outcome-blind storage preflight and manifest accounting."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Mapping

from tracking.mdmt_mia_locked_d1_package import LockedD1Error

REQUIRED_FREE_BYTES = {"train": 200_000_000_000, "val": 150_000_000_000}
PEAK_ENVELOPE_BYTES = {"train": 120_000_000_000, "val": 65_000_000_000}
FORBIDDEN_STORAGE_FIELDS = frozenset(("mda", "D_ID", "R_edge", "C_comp", "bootstrap", "gate", "direction", "mechanism_positive"))


def preflight(population: str, available_bytes: int, projected_bytes: int) -> dict[str, object]:
    if population not in REQUIRED_FREE_BYTES:
        raise LockedD1Error("unknown storage population")
    if available_bytes < REQUIRED_FREE_BYTES[population]:
        raise LockedD1Error("STORAGE_PREFLIGHT_INSUFFICIENT_FREE_SPACE")
    return {"population": population, "available_bytes": available_bytes, "required_free_bytes": REQUIRED_FREE_BYTES[population],
            "projected_bytes": projected_bytes, "peak_envelope_bytes": PEAK_ENVELOPE_BYTES[population],
            "STORAGE_BUDGET_REVIEW_REQUIRED": projected_bytes > PEAK_ENVELOPE_BYTES[population]}


def filesystem_available(path: Path) -> int:
    return os.statvfs(path).f_bavail * os.statvfs(path).f_frsize


def ensure_storage_fields(record: Mapping[str, object]) -> None:
    forbidden = FORBIDDEN_STORAGE_FIELDS & set(record)
    if forbidden:
        raise LockedD1Error("storage manifest contains scientific field: " + ",".join(sorted(forbidden)))
    required = {"path", "artifact_class", "bytes", "file_count", "retention_class", "shared", "dependency_flags"}
    if not required <= set(record):
        raise LockedD1Error("storage manifest record incomplete")


def artifact_record(path: Path, *, artifact_class: str, retention_class: str, shared: bool,
                    dependency_flags: Iterable[str], attempt: str | None = None,
                    condition: str | None = None) -> dict[str, object]:
    files = [p for p in path.rglob("*") if p.is_file()] if path.exists() else []
    record = {"path": str(path), "artifact_class": artifact_class, "bytes": sum(p.stat().st_size for p in files),
              "file_count": len(files), "retention_class": retention_class, "shared": shared,
              "dependency_flags": sorted(set(dependency_flags)), "attempt": attempt, "condition": condition}
    ensure_storage_fields(record)
    return record
