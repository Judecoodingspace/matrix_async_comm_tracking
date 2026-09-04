#!/usr/bin/env python3
"""Build/audit the isolated onset variant without changing E023 v8.

The command is intentionally not a tracking launcher.  It composes only the
accepted Homography fallback module into a copy of the frozen E023 variant and
records content hashes so a later, separately authorized execution preflight
can materialize and inspect the variant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


class VariantCompositionError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compose_variant(e023_root: Path, fallback_module: Path, destination: Path) -> dict[str, str]:
    if destination.exists():
        raise VariantCompositionError("variant destination already exists")
    target = destination / "demo" / "utils" / "trans_matrix.py"
    source_target = e023_root / "demo" / "utils" / "trans_matrix.py"
    if not source_target.is_file() or not fallback_module.is_file():
        raise VariantCompositionError("required frozen composition input missing")
    shutil.copytree(e023_root, destination, symlinks=True)
    shutil.copy2(fallback_module, target)
    return audit_composition(e023_root, fallback_module, destination)


def audit_composition(e023_root: Path, fallback_module: Path, variant_root: Path) -> dict[str, str]:
    target = variant_root / "demo" / "utils" / "trans_matrix.py"
    retained_entry = variant_root / "demo" / "supplement_MIA.py"
    source_entry = e023_root / "demo" / "supplement_MIA.py"
    if not target.is_file() or not retained_entry.is_file() or not source_entry.is_file():
        raise VariantCompositionError("composition audit input missing")
    result = {
        "e023_entry_sha256": sha256(source_entry),
        "variant_entry_sha256": sha256(retained_entry),
        "fallback_source_sha256": sha256(fallback_module),
        "variant_trans_matrix_sha256": sha256(target),
    }
    if result["e023_entry_sha256"] != result["variant_entry_sha256"]:
        raise VariantCompositionError("E023 author entry drift during composition")
    if result["fallback_source_sha256"] != result["variant_trans_matrix_sha256"]:
        raise VariantCompositionError("accepted fallback not installed exactly")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--e023-root", type=Path, required=True)
    parser.add_argument("--fallback-module", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--audit-existing", action="store_true")
    args = parser.parse_args()
    result = (audit_composition(args.e023_root, args.fallback_module, args.destination)
              if args.audit_existing else compose_variant(args.e023_root, args.fallback_module, args.destination))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
