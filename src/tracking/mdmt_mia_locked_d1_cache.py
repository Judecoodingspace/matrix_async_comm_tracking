"""Canonical detector-cache support; never enables packetized live fallback."""
from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import Iterable, Mapping

from tracking.mdmt_mia_locked_d1_package import (LockedD1Error, atomic_json, canonical_json,
    condition_core_records, load_formal_train_authorization, reference_core_records, sha256_bytes, sha256_file)


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


def verify_sealed_train_cache(batch_root: Path, authority: Mapping[str, object]) -> dict[str, object]:
    """Verify the sealed cache used by a formal Train package without touching detector outputs."""
    import json
    path = batch_root / "detector_cache" / "cache_manifest.json"
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise LockedD1Error("formal Train cache manifest missing") from exc
    if not isinstance(manifest, dict) or manifest.get("state") != "COMPLETE":
        raise LockedD1Error("formal Train cache is not complete")
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or identity.get("population") != "train":
        raise LockedD1Error("formal Train cache population mismatch")
    if identity.get("condition_core_sha256") != authority.get("condition_core_sha256"):
        raise LockedD1Error("formal Train cache condition-core mismatch")
    if identity.get("formal_authorization_sha256") != authority.get("formal_authorization_sha256"):
        raise LockedD1Error("formal Train cache authorization mismatch")
    entries = manifest.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise LockedD1Error("formal Train cache entries missing")
    cache_root = path.parent
    for key, entry in entries.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            raise LockedD1Error("formal Train cache entry schema invalid")
        item = cache_root / key
        if item.is_symlink() or not item.is_file() or entry.get("sha256") != sha256_file(item):
            raise LockedD1Error("formal Train cache entry mismatch")
    digest = sha256_file(path)
    static = authority.get("authority_static")
    if not isinstance(static, Mapping) or static.get("cache_manifest_sha256") != digest:
        raise LockedD1Error("formal Train cache digest is not bound into authority")
    return {"cache_manifest_sha256": digest, "entry_count": len(entries)}


def seed_authorized_train_cache(batch_root: Path, authorization_path: Path, *, implementation_sha: str,
                                runner=subprocess.run) -> dict[str, object]:
    """Run only the cache command fixed in an authorization, then seal its exact key set.

    The authorization supplies resolved image paths and expected image hashes; no CLI image
    selection or fallback cache source exists.
    """
    authorization, authorization_sha = load_formal_train_authorization(authorization_path, implementation_sha=implementation_sha)
    bound = authorization["bound_inputs"]
    if authorization.get("package_root") != str(batch_root.resolve()):
        raise LockedD1Error("formal cache package identity mismatch")
    source, static = bound.get("source_mda"), bound.get("authority_static")
    images, seed = bound.get("cache_images"), bound.get("cache_seed")
    if not isinstance(source, Mapping) or not isinstance(static, Mapping) or not isinstance(images, list) or not isinstance(seed, Mapping):
        raise LockedD1Error("formal cache inputs missing")
    core = {"records": condition_core_records("train", batch_root.name, source_mda=source, authority_static=static),
            "reference_records": reference_core_records("train", batch_root.name, source_mda=source, authority_static=static)}
    core_sha = sha256_bytes(canonical_json(core))
    expected: dict[str, Path] = {}
    for row in images:
        if not isinstance(row, Mapping) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise LockedD1Error("formal cache image binding invalid")
        image = Path(str(row["path"])).resolve(strict=True)
        if sha256_file(image) != row["sha256"]: raise LockedD1Error("formal cache source image hash mismatch")
        key = cache_key(image)
        if key in expected: raise LockedD1Error("formal cache duplicate image key")
        expected[key] = image
    argv, environment = seed.get("argv"), seed.get("environment")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        raise LockedD1Error("formal cache seed argv invalid")
    if not isinstance(environment, Mapping) or environment.get("PYTHONHASHSEED") != "7":
        raise LockedD1Error("formal cache seed environment invalid")
    cache_root = batch_root / "detector_cache"
    if cache_root.exists(): raise LockedD1Error("formal cache root collision")
    cache_root.mkdir(parents=True, exist_ok=False)
    values = {"cache_root": str(cache_root.resolve())}
    try:
        command = [item.format(**values) for item in argv]
        env = {str(key): str(value).format(**values) for key, value in environment.items()}
    except (KeyError, ValueError) as exc:
        raise LockedD1Error("formal cache seed uses unapproved placeholder") from exc
    if env.get("MIA_DETECTION_CACHE_ROOT") != str(cache_root.resolve()) or env.get("MIA_DETECTION_CACHE_MODE") != "write":
        raise LockedD1Error("formal cache seed must write only to its sealed root")
    result = runner(command, cwd=Path.cwd(), env=env, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if getattr(result, "returncode", 1): raise LockedD1Error("formal cache seed process failed")
    manifest_sha = seal_cache(cache_root, expected, identity={"population": "train", "condition_core_sha256": core_sha,
        "formal_authorization_sha256": authorization_sha})
    binding = {"source_mda": dict(source), "authority_static": {**dict(static), "cache_manifest_sha256": manifest_sha},
        "execution_static": bound.get("execution_static"), "cache_static": {"cache_manifest_path": str((cache_root / "cache_manifest.json").resolve()),
        "cache_manifest_sha256": manifest_sha}}
    binding_sha = atomic_json(batch_root / "CACHE_BINDING.json", binding)
    return {"cache_manifest_sha256": manifest_sha, "cache_binding_sha256": binding_sha, "entry_count": len(expected)}
