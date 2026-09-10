#!/usr/bin/env python3
"""Render the frozen C4 baseline matrix; dataset execution is still blocked."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CONTRACT_AUTHORITY = "24778f49ec9c913aadf95199343b12a75fd4078d"
IMPLEMENTATION_PLAN_AUTHORITY = "cd8c1f94c88faaf63e106827bfcb095a518de49d"
PAIRS = ("23", "44", "66")
CONDITIONS = (
    "Unlimited", "FIFO_mild", "FIFO_moderate", "FIFO_strong", "Y10_d1", "Y11_d1",
)
FIFO_RATES = {"FIFO_mild": 31987, "FIFO_moderate": 26148, "FIFO_strong": 16649}
ZERO_DELAYS = {"local": 0, "homography": 0, "id_state": 0, "supplement": 0}
BRIDGE_DELAYS = {
    "Y10_d1": {"local": 0, "homography": 0, "id_state": 1, "supplement": 0},
    "Y11_d1": {"local": 0, "homography": 0, "id_state": 1, "supplement": 1},
}


def render_condition(condition: str, run_id: str, pair_id: str) -> dict[str, object]:
    if pair_id not in PAIRS:
        raise ValueError("C4 runner accepts only frozen pairs 23/44/66")
    if condition not in CONDITIONS:
        raise ValueError("unknown or unauthorized C4 condition")
    if condition == "Unlimited":
        service = {"mode": "unlimited", "condition": condition,
                   "rate_logical_bytes_per_frame": None, "ledger_enabled": True,
                   "run_id": run_id, "pair_id": pair_id}
        delays = dict(ZERO_DELAYS)
    elif condition in FIFO_RATES:
        service = {"mode": "fifo", "condition": condition,
                   "rate_logical_bytes_per_frame": FIFO_RATES[condition], "ledger_enabled": True,
                   "run_id": run_id, "pair_id": pair_id}
        delays = dict(ZERO_DELAYS)
    else:
        service = {"mode": "disabled", "condition": condition,
                   "rate_logical_bytes_per_frame": None, "ledger_enabled": False,
                   "run_id": run_id, "pair_id": pair_id}
        delays = dict(BRIDGE_DELAYS[condition])
    return {
        "pair_id": pair_id,
        "condition": condition,
        "service_config": service,
        "delay_map": delays,
    }


def render_matrix(run_id: str, pairs=PAIRS, conditions=CONDITIONS) -> list[dict[str, object]]:
    selected_pairs = tuple(str(value) for value in pairs)
    selected_conditions = tuple(str(value) for value in conditions)
    if len(set(selected_pairs)) != len(selected_pairs) or any(value not in PAIRS for value in selected_pairs):
        raise ValueError("matrix contains a duplicate or unauthorized pair")
    if len(set(selected_conditions)) != len(selected_conditions) \
            or any(value not in CONDITIONS for value in selected_conditions):
        raise ValueError("matrix contains a duplicate or unauthorized condition")
    return [render_condition(condition, run_id, pair_id)
            for pair_id in selected_pairs for condition in selected_conditions]


def render_commands(cells: list[dict[str, object]], output_root: Path) -> list[dict[str, object]]:
    rendered = []
    for cell in cells:
        pair_id, condition = str(cell["pair_id"]), str(cell["condition"])
        cell_root = output_root / condition / ("train_" + pair_id)
        rendered.append({
            **cell,
            "environment": {
                "MIA_C4_SERVICE_CONFIG": json.dumps(
                    cell["service_config"], sort_keys=True, separators=(",", ":")),
                "MIA_ASYNC_CHANNEL_DELAYS": json.dumps(
                    cell["delay_map"], sort_keys=True, separators=(",", ":")),
                "MIA_PACKET_CENSUS_RUN_ID": "c4-baseline-qualification",
                "MIA_OUTPUT_ROOT": str(cell_root),
                "PYTHONNOUSERSITE": "1",
            },
            "author_command": ["bash", "scripts/run_mdmt_mia_author_sync.sh", "mia", "train", pair_id],
            "execution_authorized": False,
        })
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pair", action="append", choices=PAIRS)
    parser.add_argument("--condition", action="append", choices=CONDITIONS)
    parser.add_argument("--run-id", default="c4-baseline-qualification-candidate")
    parser.add_argument("--output-root", type=Path, default=Path("outputs/c4_baseline_qualification_BLOCKED"))
    parser.add_argument("--dry-run", action="store_true",
                        help="render only; this implementation does not authorize dataset execution")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.dry_run:
        raise SystemExit("DATASET_LEVEL_C4_MVE_NOT_AUTHORIZED: use --dry-run")
    cells = render_matrix(args.run_id, args.pair or PAIRS, args.condition or CONDITIONS)
    payload = {
        "document_role": "C4_IMPLEMENTATION_ONLY_RENDERING",
        "contract_authority": CONTRACT_AUTHORITY,
        "implementation_plan_authority": IMPLEMENTATION_PLAN_AUTHORITY,
        "scientific_cell_count": len(cells),
        "dataset_execution_authorized": False,
        "gpu_execution_authorized": False,
        "unlimited_comparator_rendering": "DEFERRED_TO_MVE_EXECUTION_MATERIAL",
        "cells": render_commands(cells, args.output_root),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
