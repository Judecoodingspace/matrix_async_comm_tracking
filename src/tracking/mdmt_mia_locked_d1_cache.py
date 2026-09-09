"""Canonical detector-cache support; never enables packetized live fallback."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np

from tracking.mdmt_mia_locked_d1_package import (LockedD1Error, TRAIN_PAIRS, VAL_PAIRS, _materialize, _profile,
    atomic_json, canonical_json, condition_core_records, load_formal_train_authorization, load_formal_val_authorization,
    reference_core_records, sha256_bytes, sha256_file, validate_source_mda_registry)


TRAIN_CACHE_PROFILE = "locked-d1-train-10-pair-cache-write-v1"
VAL_CACHE_PROFILE = "locked-d1-val-5-pair-cache-write-v1"


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


def validate_cache_npz(path: Path) -> None:
    try:
        with np.load(str(path), allow_pickle=False) as archive:
            if set(archive.files) != {"class_count", "class_0", "class_1", "class_2"}:
                raise LockedD1Error("detector cache NPZ schema mismatch")
            count = archive["class_count"]
            if count.shape != (1,) or count.dtype != np.dtype("int32") or int(count[0]) != 3:
                raise LockedD1Error("detector cache class_count mismatch")
            for index in range(3):
                boxes = archive["class_" + str(index)]
                if boxes.ndim != 2 or boxes.shape[1] != 5 or not np.isfinite(boxes).all():
                    raise LockedD1Error("detector cache bbox array invalid")
    except (OSError, ValueError, KeyError) as exc:
        raise LockedD1Error("detector cache NPZ unreadable") from exc


def seal_cache(cache_root: Path, expected: Mapping[str, Path], *, identity: Mapping[str, object]) -> str:
    actual = {entry.name: entry for entry in cache_root.glob("*.npz") if entry.is_file()}
    if set(actual) != set(expected):
        raise LockedD1Error("detector cache completeness mismatch")
    if any(item.is_symlink() for item in actual.values()):
        raise LockedD1Error("cache symlink forbidden")
    for item in actual.values():
        validate_cache_npz(item)
    manifest = {"state": "COMPLETE", "identity": dict(identity),
                "entries": {key: {"image": str(expected[key]), "sha256": sha256_file(actual[key])}
                            for key in sorted(expected)}}
    digest = atomic_json(cache_root / "cache_manifest.json", manifest)
    for item in actual.values():
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
        validate_cache_npz(item)
    digest = sha256_file(path)
    static = authority.get("authority_static")
    if not isinstance(static, Mapping) or static.get("cache_manifest_sha256") != digest:
        raise LockedD1Error("formal Train cache digest is not bound into authority")
    return {"cache_manifest_sha256": digest, "entry_count": len(entries)}


def derive_train_cache_seed_profiles(batch_root: Path, execution_static: Mapping[str, object]) -> list[dict[str, object]]:
    """Derive the only permitted cache-write calls from the sealed packetized profile.

    There is deliberately no caller-selected pair, split, condition, shell, or loop.  A
    cache write is the Y00 materialization for every registered Train pair, with a unique
    cache-seed attempt root and the cache mode changed from canonical read to write.
    """
    argv, environment = _profile(execution_static, "packetized", "Y00")
    profiles: list[dict[str, object]] = []
    for index, pair in enumerate(TRAIN_PAIRS, 1):
        attempt_root = str((batch_root / "cache_seed" / "attempt_001" / ("pair_%02d_%s" % (index, pair))).resolve())
        materialized_argv, materialized_env = _materialize(argv, environment, pair=pair, condition="Y00",
            attempt_template=attempt_root, cache_root="{cache_root}", role="PACKETIZED")
        if materialized_env.get("MIA_DETECTION_CACHE_MODE") != "read":
            raise LockedD1Error("canonical packetized cache profile must start read-only")
        materialized_env["MIA_DETECTION_CACHE_MODE"] = "write"
        profiles.append({"pair": pair, "argv": materialized_argv, "environment": materialized_env})
    return profiles


def _validated_train_cache_profiles(batch_root: Path, bound: Mapping[str, object]) -> list[dict[str, object]]:
    execution = bound.get("execution_static")
    seed = bound.get("cache_seed")
    if not isinstance(execution, Mapping) or not isinstance(seed, Mapping):
        raise LockedD1Error("formal cache inputs missing")
    if seed.get("profile") != TRAIN_CACHE_PROFILE or set(seed) != {"profile", "commands"}:
        raise LockedD1Error("formal cache seed profile is not canonical")
    commands = seed.get("commands")
    expected = derive_train_cache_seed_profiles(batch_root, execution)
    if commands != expected:
        raise LockedD1Error("formal cache seed commands are not the fixed Train profile")
    return expected


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
    images = bound.get("cache_images")
    if not isinstance(source, Mapping) or not isinstance(static, Mapping) or not isinstance(images, list):
        raise LockedD1Error("formal cache inputs missing")
    validate_source_mda_registry(source, "train")
    core = {"records": condition_core_records("train", batch_root.name, source_mda=source, authority_static=static),
            "reference_records": reference_core_records("train", batch_root.name, source_mda=source, authority_static=static)}
    core_sha = sha256_bytes(canonical_json(core))
    expected: dict[str, Path] = {}
    for row in images:
        if not isinstance(row, Mapping) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise LockedD1Error("formal cache image binding invalid")
        declared_image = Path(str(row["path"]))
        if declared_image.is_symlink():
            raise LockedD1Error("formal Val cache source image symlink forbidden")
        image = declared_image.resolve(strict=True)
        if sha256_file(image) != row["sha256"]: raise LockedD1Error("formal cache source image hash mismatch")
        key = cache_key(image)
        if key in expected: raise LockedD1Error("formal cache duplicate image key")
        expected[key] = image
    profiles = _validated_train_cache_profiles(batch_root, bound)
    cache_root = batch_root / "detector_cache"
    if cache_root.exists(): raise LockedD1Error("formal cache root collision")
    cache_root.mkdir(parents=True, exist_ok=False)
    cache_root_text = str(cache_root.resolve())
    rendered = [{"pair": row["pair"], "argv": [item.replace("{cache_root}", cache_root_text) for item in row["argv"]],
                 "environment": {str(key): str(value).replace("{cache_root}", cache_root_text)
                                 for key, value in row["environment"].items()}} for row in profiles]
    for row in rendered:
        env = row["environment"]
        if (env.get("MIA_DETECTION_CACHE_ROOT") != str(cache_root.resolve())
                or env.get("MIA_DETECTION_CACHE_MODE") != "write" or env.get("PYTHONHASHSEED") != "7"):
            raise LockedD1Error("formal cache seed must write only to its sealed root")
        transient = Path(str(env["MIA_OUTPUT_ROOT"]))
        allowed_root = (batch_root / "cache_seed" / "attempt_001").resolve()
        if transient.parent != allowed_root or transient.is_symlink():
            raise LockedD1Error("formal cache seed transient output root mismatch")
        try:
            result = runner(list(row["argv"]), cwd=Path.cwd(), env=dict(env), check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if transient.exists():
                shutil.rmtree(transient)
        if getattr(result, "returncode", 1):
            raise LockedD1Error("formal cache seed author failed for Train pair " + str(row["pair"]))
    manifest_sha = seal_cache(cache_root, expected, identity={"population": "train", "condition_core_sha256": core_sha,
        "formal_authorization_sha256": authorization_sha})
    binding = {"source_mda": dict(source), "authority_static": {**dict(static), "cache_manifest_sha256": manifest_sha},
        "execution_static": bound.get("execution_static"), "cache_static": {"cache_manifest_path": str((cache_root / "cache_manifest.json").resolve()),
        "cache_manifest_sha256": manifest_sha}}
    binding_sha = atomic_json(batch_root / "CACHE_BINDING.json", binding)
    return {"cache_manifest_sha256": manifest_sha, "cache_binding_sha256": binding_sha, "entry_count": len(expected)}


def verify_sealed_val_cache(batch_root: Path, authority: Mapping[str, object]) -> dict[str, object]:
    """Verify a sealed Val-only cache without consulting Train artifacts or outcomes."""
    import json
    path = batch_root / "detector_cache" / "cache_manifest.json"
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise LockedD1Error("formal Val cache manifest missing") from exc
    if not isinstance(manifest, dict) or manifest.get("state") != "COMPLETE":
        raise LockedD1Error("formal Val cache is not complete")
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or identity.get("population") != "val":
        raise LockedD1Error("formal Val cache population mismatch")
    if identity.get("condition_core_sha256") != authority.get("condition_core_sha256"):
        raise LockedD1Error("formal Val cache condition-core mismatch")
    if identity.get("formal_authorization_sha256") != authority.get("formal_authorization_sha256"):
        raise LockedD1Error("formal Val cache authorization mismatch")
    entries = manifest.get("entries")
    if not isinstance(entries, dict) or not entries:
        raise LockedD1Error("formal Val cache entries missing")
    cache_root = path.parent
    actual = {item.name for item in cache_root.glob("*.npz") if item.is_file()}
    if actual != set(entries):
        raise LockedD1Error("formal Val cache completeness mismatch")
    for key, entry in entries.items():
        if not isinstance(key, str) or not isinstance(entry, dict):
            raise LockedD1Error("formal Val cache entry schema invalid")
        item = cache_root / key
        image = str(entry.get("image", "")).replace("\\", "/")
        if "/val/" not in image.lower():
            raise LockedD1Error("formal Val cache contains non-Val image")
        if item.is_symlink() or not item.is_file() or entry.get("sha256") != sha256_file(item):
            raise LockedD1Error("formal Val cache entry mismatch")
        validate_cache_npz(item)
    digest = sha256_file(path)
    static = authority.get("authority_static")
    if not isinstance(static, Mapping) or static.get("cache_manifest_sha256") != digest:
        raise LockedD1Error("formal Val cache digest is not bound into authority")
    return {"cache_manifest_sha256": digest, "entry_count": len(entries)}


def derive_val_cache_seed_profiles(batch_root: Path, execution_static: Mapping[str, object]) -> list[dict[str, object]]:
    """Derive exactly five Val/Y00 cache-write calls; no caller-selected split or pair exists."""
    argv, environment = _profile(execution_static, "packetized", "Y00")
    profiles: list[dict[str, object]] = []
    for index, pair in enumerate(VAL_PAIRS, 1):
        attempt_root = str((batch_root / "cache_seed" / "attempt_001" / ("pair_%02d_%s" % (index, pair))).resolve())
        materialized_argv, materialized_env = _materialize(argv, environment, pair=pair, condition="Y00",
            attempt_template=attempt_root, cache_root="{cache_root}", role="PACKETIZED")
        lowered_argv = [item.lower() for item in materialized_argv]
        if "val" not in lowered_argv or "train" in lowered_argv:
            raise LockedD1Error("formal Val cache argv must bind the Val split")
        if materialized_env.get("MIA_DETECTION_CACHE_MODE") != "read":
            raise LockedD1Error("canonical packetized cache profile must start read-only")
        materialized_env["MIA_DETECTION_CACHE_MODE"] = "write"
        profiles.append({"pair": pair, "argv": materialized_argv, "environment": materialized_env})
    return profiles


def _validated_val_cache_profiles(batch_root: Path, bound: Mapping[str, object]) -> list[dict[str, object]]:
    execution = bound.get("execution_static")
    seed = bound.get("cache_seed")
    if not isinstance(execution, Mapping) or not isinstance(seed, Mapping):
        raise LockedD1Error("formal Val cache inputs missing")
    if seed.get("profile") != VAL_CACHE_PROFILE or set(seed) != {"profile", "commands"}:
        raise LockedD1Error("formal Val cache seed profile is not canonical")
    expected = derive_val_cache_seed_profiles(batch_root, execution)
    if seed.get("commands") != expected:
        raise LockedD1Error("formal cache seed commands are not the fixed Val profile")
    return expected


def seed_authorized_val_cache(batch_root: Path, authorization_path: Path, *, implementation_sha: str,
                              runner=subprocess.run) -> dict[str, object]:
    """Seed and seal only the five-pair Val detector cache under one Val authority."""
    authorization, authorization_sha = load_formal_val_authorization(
        authorization_path, implementation_sha=implementation_sha)
    bound = authorization["bound_inputs"]
    if (authorization.get("package_root") != str(batch_root.resolve())
            or batch_root.name != authorization.get("batch_id")
            or not batch_root.name.startswith("locked_d1_val_batch_")):
        raise LockedD1Error("formal Val cache package identity mismatch")
    source, static = bound.get("source_mda"), bound.get("authority_static")
    images = bound.get("cache_images")
    if not isinstance(source, Mapping) or not isinstance(static, Mapping) or not isinstance(images, list):
        raise LockedD1Error("formal Val cache inputs missing")
    if source.get("population") != "val":
        raise LockedD1Error("formal Val Source-MDA population mismatch")
    validate_source_mda_registry(source, "val")
    core = {"records": condition_core_records("val", batch_root.name, source_mda=source, authority_static=static),
            "reference_records": reference_core_records("val", batch_root.name, source_mda=source, authority_static=static)}
    core_sha = sha256_bytes(canonical_json(core))
    expected: dict[str, Path] = {}
    represented_pairs: set[str] = set()
    for row in images:
        if (not isinstance(row, Mapping) or row.get("population") != "val"
                or str(row.get("pair")) not in VAL_PAIRS or not isinstance(row.get("path"), str)
                or not isinstance(row.get("sha256"), str)):
            raise LockedD1Error("formal Val cache image binding invalid")
        image = Path(str(row["path"])).resolve(strict=True)
        normalized = str(image).replace("\\", "/").lower()
        if "/val/" not in normalized or sha256_file(image) != row["sha256"]:
            raise LockedD1Error("formal Val cache source image binding mismatch")
        pair = str(row["pair"])
        if not any(part in {pair, "1-" + pair, "2-" + pair} for part in image.parts):
            raise LockedD1Error("formal Val cache image/pair mismatch")
        key = cache_key(image)
        if key in expected:
            raise LockedD1Error("formal Val cache duplicate image key")
        expected[key] = image
        represented_pairs.add(pair)
    if represented_pairs != set(VAL_PAIRS):
        raise LockedD1Error("formal Val cache image population incomplete")
    profiles = _validated_val_cache_profiles(batch_root, bound)
    cache_root = batch_root / "detector_cache"
    if cache_root.exists():
        raise LockedD1Error("formal Val cache root collision")
    cache_root.mkdir(parents=True, exist_ok=False)
    cache_root_text = str(cache_root.resolve())
    rendered = [{"pair": row["pair"], "argv": [item.replace("{cache_root}", cache_root_text) for item in row["argv"]],
                 "environment": {str(key): str(value).replace("{cache_root}", cache_root_text)
                                 for key, value in row["environment"].items()}} for row in profiles]
    for row in rendered:
        env = row["environment"]
        if (env.get("MIA_DETECTION_CACHE_ROOT") != cache_root_text
                or env.get("MIA_DETECTION_CACHE_MODE") != "write" or env.get("PYTHONHASHSEED") != "7"):
            raise LockedD1Error("formal Val cache seed must write only to its sealed root")
        transient = Path(str(env["MIA_OUTPUT_ROOT"]))
        allowed_root = (batch_root / "cache_seed" / "attempt_001").resolve()
        if transient.parent != allowed_root or transient.is_symlink():
            raise LockedD1Error("formal Val cache seed transient output root mismatch")
        result = None
        try:
            result = runner(list(row["argv"]), cwd=Path.cwd(), env=dict(env), check=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            if transient.exists():
                shutil.rmtree(transient)
        if getattr(result, "returncode", 1):
            raise LockedD1Error("formal cache seed author failed for Val pair " + str(row["pair"]))
    manifest_sha = seal_cache(cache_root, expected, identity={"population": "val", "condition_core_sha256": core_sha,
        "formal_authorization_sha256": authorization_sha})
    binding = {"source_mda": dict(source), "authority_static": {**dict(static), "cache_manifest_sha256": manifest_sha},
        "execution_static": bound.get("execution_static"), "cache_static": {
        "cache_manifest_path": str((cache_root / "cache_manifest.json").resolve()),
        "cache_manifest_sha256": manifest_sha}}
    binding_sha = atomic_json(batch_root / "CACHE_BINDING.json", binding)
    return {"cache_manifest_sha256": manifest_sha, "cache_binding_sha256": binding_sha,
            "entry_count": len(expected), "population": "val"}
