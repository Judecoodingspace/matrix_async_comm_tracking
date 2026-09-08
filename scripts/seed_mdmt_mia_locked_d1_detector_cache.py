#!/usr/bin/env python3
"""Authorized Train cache lifecycle; no Val mode and no caller-selected image set."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from tracking.mdmt_mia_locked_d1_cache import seed_authorized_train_cache, verify_sealed_train_cache
from tracking.mdmt_mia_locked_d1_package import (LockedD1Error, load_formal_train_authorization,
    load_sealed_package)


def _head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    if result.returncode: raise LockedD1Error("cannot resolve implementation SHA")
    if subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=False).stdout.strip():
        raise LockedD1Error("formal cache seeding requires a clean worktree")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--formal-authorization", type=Path, required=True)
    parser.add_argument("action", choices=("seed", "verify"))
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    if arguments.action == "seed":
        if not arguments.execute: raise SystemExit("FORMAL_TRAIN_CACHE_SEED_REQUIRES_EXPLICIT_EXECUTE")
        result = seed_authorized_train_cache(arguments.package_root, arguments.formal_authorization, implementation_sha=_head())
        print("FORMAL_TRAIN_CACHE_SEALED")
        print(result["cache_manifest_sha256"])
        return
    _, authorization_sha = load_formal_train_authorization(arguments.formal_authorization, implementation_sha=_head())
    _, authority, _ = load_sealed_package(arguments.package_root, "train", arguments.package_root.name)
    if authority.get("formal_authorization_sha256") != authorization_sha:
        raise LockedD1Error("cache/package authorization binding mismatch")
    result = verify_sealed_train_cache(arguments.package_root, authority)
    print("FORMAL_TRAIN_CACHE_VERIFY_PASS")
    print(result["cache_manifest_sha256"])


if __name__ == "__main__":
    main()
