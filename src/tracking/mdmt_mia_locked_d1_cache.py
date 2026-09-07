"""Canonical detector-cache support; never enables packetized live fallback."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, Mapping

from tracking.mdmt_mia_locked_d1_package import LockedD1Error, atomic_json, sha256_file


def cache_key(image: Path) -> str:
    return hashlib.sha256(str(image.expanduser().resolve()).encode("utf-8")).hexdigest() + ".npz"


def enumerate_images(view_roots: Iterable[Path]) -> dict[str, Path]:
    rows: dict[str, Path] = {}
    for root in view_roots:
        for image in sorted(root.iterdir()):
            if image.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            resolved = image.resolve(strict=True)
            key = cache_key(resolved)
            if key in rows and rows[key] != resolved:
                raise LockedD1Error("detector cache-key collision")
            rows[key] = resolved
    if not rows:
        raise LockedD1Error("empty detector cache population")
    return rows


def packetized_cache_environment(cache_root: Path) -> dict[str, str]:
    return {"MIA_DETECTION_CACHE_ROOT": str(cache_root.resolve()), "MIA_DETECTION_CACHE_MODE": "read"}


def validate_packetized_cache_environment(env: Mapping[str, str], cache_root: Path) -> None:
    if dict(env) != packetized_cache_environment(cache_root):
        raise LockedD1Error("packetized cache must be canonical read-only; no fallback")


def validate_reference_environment(env: Mapping[str, str]) -> None:
    if "MIA_DETECTION_CACHE_ROOT" in env or "MIA_DETECTION_CACHE_MODE" in env:
        raise LockedD1Error("reference must retain live detector semantics")


def seal_cache(cache_root: Path, expected: Mapping[str, Path], *, identity: Mapping[str, object]) -> str:
    actual = {entry.name: entry for entry in cache_root.glob("*.npz") if entry.is_file()}
    if set(actual) != set(expected):
        raise LockedD1Error("detector cache completeness mismatch")
    manifest = {"state": "COMPLETE", "identity": dict(identity),
                "entries": {key: {"image": str(expected[key]), "sha256": sha256_file(actual[key])}
                            for key in sorted(expected)}}
    digest = atomic_json(cache_root / "cache_manifest.json", manifest)
    for item in actual.values():
        if item.is_symlink():
            raise LockedD1Error("cache symlink forbidden")
        item.chmod(0o444)
    cache_root.chmod(0o555)
    return digest
