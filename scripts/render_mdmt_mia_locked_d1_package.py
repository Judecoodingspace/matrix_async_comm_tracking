#!/usr/bin/env python3
"""Render a bound, outcome-blind Formal Train package from governance-supplied JSON bindings."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from tracking.mdmt_mia_locked_d1_package import (LockedD1Error, load_formal_train_authorization,
    render_manifests)


def _json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict): raise LockedD1Error("binding JSON must be an object")
    return value


def _head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    if result.returncode: raise LockedD1Error("cannot resolve implementation SHA")
    if subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=False).stdout.strip():
        raise LockedD1Error("formal package rendering requires a clean worktree")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--formal-authorization", type=Path, required=True)
    parser.add_argument("--cache-binding", type=Path, required=True)
    arguments = parser.parse_args()
    authorization, auth_sha = load_formal_train_authorization(arguments.formal_authorization, implementation_sha=_head())
    if authorization.get("batch_id") != arguments.batch_id or authorization.get("package_root") != str(arguments.package_root.resolve()):
        raise LockedD1Error("authorization/package identity mismatch")
    binding = _json(arguments.cache_binding)
    required = {"source_mda", "authority_static", "execution_static", "cache_static"}
    if set(binding) != required: raise LockedD1Error("cache binding schema mismatch")
    result = render_manifests(arguments.package_root, "train", arguments.batch_id,
        source_mda=binding["source_mda"], authority_static=binding["authority_static"],
        cache_static=binding["cache_static"], execution_static=binding["execution_static"],
        formal_authorization=authorization, formal_authorization_sha256=auth_sha)
    print("OUTCOME_EMBARGO_ACTIVE")
    print("TRAIN_PACKAGE_SEALED")
    print(result["execution_package_sha256"])


if __name__ == "__main__":
    main()
