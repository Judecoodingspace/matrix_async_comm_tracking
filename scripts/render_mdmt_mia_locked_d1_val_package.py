#!/usr/bin/env python3
"""Render a sealed, outcome-blind Formal Val package from its Val cache binding."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from tracking.mdmt_mia_locked_d1_package import LockedD1Error, load_formal_val_authorization, render_manifests


def _head() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=False)
    if result.returncode or status.returncode or status.stdout.strip():
        raise LockedD1Error("formal Val package rendering requires a clean worktree")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--formal-authorization", type=Path, required=True)
    parser.add_argument("--cache-binding", type=Path, required=True)
    arguments = parser.parse_args()
    authorization, auth_sha = load_formal_val_authorization(
        arguments.formal_authorization, implementation_sha=_head())
    if (authorization.get("batch_id") != arguments.batch_id
            or authorization.get("package_root") != str(arguments.package_root.resolve())):
        raise LockedD1Error("Val authorization/package identity mismatch")
    binding = json.loads(arguments.cache_binding.read_text())
    required = {"source_mda", "authority_static", "execution_static", "cache_static"}
    if not isinstance(binding, dict) or set(binding) != required:
        raise LockedD1Error("Val cache binding schema mismatch")
    bound = authorization["bound_inputs"]
    if (binding["source_mda"] != bound.get("source_mda")
            or binding["execution_static"] != bound.get("execution_static")
            or {key: value for key, value in binding["authority_static"].items()
                if key != "cache_manifest_sha256"} != bound.get("authority_static")):
        raise LockedD1Error("Val cache binding does not match authorization inputs")
    result = render_manifests(arguments.package_root.resolve(), "val", arguments.batch_id,
        source_mda=binding["source_mda"], authority_static=binding["authority_static"],
        cache_static=binding["cache_static"], execution_static=binding["execution_static"],
        formal_authorization=authorization, formal_authorization_sha256=auth_sha)
    print("OUTCOME_EMBARGO_ACTIVE")
    print("VAL_PACKAGE_SEALED")
    print(result["execution_package_sha256"])


if __name__ == "__main__":
    main()
