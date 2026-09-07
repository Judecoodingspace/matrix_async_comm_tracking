#!/usr/bin/env python3
"""Render an outcome-blind locked-d1 package; execution is intentionally absent."""
from __future__ import annotations
import argparse
from pathlib import Path

from tracking.mdmt_mia_locked_d1_package import render_manifests


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--population", choices=("train", "val"), required=True)
    parser.add_argument("--batch-id", required=True)
    arguments = parser.parse_args()
    # These placeholders are replaced by qualification-authorized authority binding,
    # never inferred from a result or silently regenerated.
    result = render_manifests(arguments.package_root, arguments.population, arguments.batch_id,
                              source_mda={"state": "UNBOUND"}, authority_static={"state": "UNBOUND"},
                              cache_static={"state": "UNBOUND"})
    print("OUTCOME_EMBARGO_ACTIVE")
    print("EXECUTION_DISABLED")
    print(result["execution_package_sha256"])


if __name__ == "__main__":
    main()
