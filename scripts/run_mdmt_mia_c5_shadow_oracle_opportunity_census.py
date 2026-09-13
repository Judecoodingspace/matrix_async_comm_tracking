#!/usr/bin/env python3
"""Render the frozen C5 Shadow matrix; scientific execution is intentionally disabled."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


IMPLEMENTATION_BASE_SHA = "0e18e0871d2e37207f54a1bf90c5129ef9896901"
FOUR_CELL_SCIENTIFIC_EXECUTION_AUTHORIZED = False
FIFO_RATES = {"FIFO_mild": 31987, "FIFO_moderate": 26148, "FIFO_strong": 16649}
FROZEN_CELLS = (
    ("CONTROL", "23", "FIFO_mild"),
    ("FRONTIER", "23", "FIFO_strong"),
    ("FRONTIER", "44", "FIFO_moderate"),
    ("FRONTIER", "66", "FIFO_mild"),
)


def render_matrix(run_id: str, output_root: Path):
    """Return precisely the approved C5 future-execution configuration."""
    root = Path(output_root) / str(run_id)
    return [{
        "role": role,
        "pair_id": pair_id,
        "condition": condition,
        "cell_id": "pair_{}__{}".format(pair_id, condition),
        "runtime_output_dir": str(root / "runtime" / ("pair_{}__{}".format(pair_id, condition))),
        "shadow_output_dir": str(root / "shadow" / ("pair_{}__{}".format(pair_id, condition))),
        "service_config": {"mode": "fifo", "condition": condition,
                           "rate_logical_bytes_per_frame": FIFO_RATES[condition],
                           "ledger_enabled": True, "run_id": str(run_id), "pair_id": pair_id},
        "shadow_config": {"enabled": True, "run_id": str(run_id),
                          "output_dir": str(root / "shadow" / ("pair_{}__{}".format(pair_id, condition)))},
        "execution_authorized": False,
    } for role, pair_id, condition in FROZEN_CELLS]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="c5-shadow-oracle-opportunity-census")
    parser.add_argument("--output-root", type=Path, default=Path("outputs/c5_shadow_oracle_opportunity_census"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run:
        raise SystemExit("C5 scientific execution is not authorized; use --dry-run only")
    print(json.dumps({"implementation_base_sha": IMPLEMENTATION_BASE_SHA,
                      "FOUR_CELL_SCIENTIFIC_EXECUTION_AUTHORIZED": False,
                      "cells": render_matrix(args.run_id, args.output_root)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
