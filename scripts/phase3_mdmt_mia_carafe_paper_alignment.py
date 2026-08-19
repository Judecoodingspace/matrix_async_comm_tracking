#!/usr/bin/env python3
"""Run the bounded CARAFE+ByteTrack paper-alignment reproduction.

The tracker itself remains the author implementation.  This CLI only chooses
the isolated source variant, gives each condition an independent output root,
and persists completion checkpoints.  It intentionally has no delay, ReID or
custom fusion arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


OFFICIAL_PAIRS = ("26", "31", "34", "48", "52", "55", "56", "57", "59", "61", "62", "68", "71", "73")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("pilot", "formal"), required=True)
    parser.add_argument("--mia-root", type=Path, default=Path("/mnt/data/yzm/experiments/mdmt_mia_official"))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--official-mda-gt-root", type=Path, required=True)
    parser.add_argument("--released-source", type=Path, default=None)
    parser.add_argument("--threshold-source", type=Path, default=None)
    parser.add_argument("--low-score-source", type=Path, default=None)
    parser.add_argument("--aligned-source", type=Path, default=None)
    parser.add_argument("--pair-ids", nargs="+", default=None)
    parser.add_argument("--variant", action="append", default=[], help="restrict to a named condition")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument(
        "--run-id",
        default="exp_20260804_003",
        help="isolated raw-output and input namespace below --mia-root/outputs and run_inputs",
    )
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def conditions(args: argparse.Namespace) -> list[tuple[str, Path, str]]:
    released = args.released_source or args.mia_root / "upstream"
    threshold = args.threshold_source or args.mia_root / "variants/paper_thresholds_only"
    low_score = args.low_score_source or args.mia_root / "variants/paper_low_score_only"
    aligned = args.aligned_source or args.mia_root / "variants/paper_aligned_mia"
    if args.mode == "pilot":
        values = [
            ("released_mia", released, "mia"),
            ("paper_thresholds_only", threshold, "mia"),
            ("paper_low_score_only", low_score, "mia"),
            ("paper_aligned_mia", aligned, "mia"),
            ("local_matching", aligned, "local"),
            ("id_allocation_no_supplement", aligned, "global"),
        ]
    else:
        values = [
            ("paper_aligned_local", aligned, "local"),
            ("paper_aligned_id_allocation", aligned, "global"),
            ("paper_aligned_mia", aligned, "mia"),
        ]
    return [value for value in values if not args.variant or value[0] in args.variant]


def complete(run_root: Path, stage: str, pair_id: str) -> bool:
    result_dir = run_root / stage / f"test_{pair_id}" / "results" / f"{stage}_test_{pair_id}"
    return all((result_dir / f"{pair_id}-{view_id}.json").is_file() for view_id in (1, 2))


def write_checkpoint(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    selected_pairs = tuple(args.pair_ids or (("26",) if args.mode == "pilot" else OFFICIAL_PAIRS))
    selected_conditions = conditions(args)
    if not selected_conditions:
        raise SystemExit("no conditions selected")
    run_base = args.mia_root / "outputs" / args.run_id
    start = time.monotonic()
    tasks = [(name, source, stage, pair_id) for name, source, stage in selected_conditions for pair_id in selected_pairs]
    for index, (name, source, stage, pair_id) in enumerate(tasks, start=1):
        run_root = run_base / name
        checkpoint = args.output_dir / "checkpoints" / f"{name}_{stage}_test_{pair_id}.json"
        if args.resume and complete(run_root, stage, pair_id):
            print(f"[resume] skip completed condition={name} stage={stage} pair={pair_id} checkpoint={checkpoint}", flush=True)
            continue
        if not source.is_dir():
            raise FileNotFoundError(f"source variant missing for {name}: {source}")
        elapsed = time.monotonic() - start
        eta = elapsed / max(index - 1, 1) * (len(tasks) - index)
        print(f"[run] condition={index}/{len(tasks)} variant={name} stage={stage} pair={pair_id} elapsed={elapsed:.1f}s eta={eta:.1f}s", flush=True)
        env = os.environ.copy()
        env.update({
            "MIA_ROOT": str(args.mia_root), "MIA_SOURCE_ROOT": str(source), "MDMT_ROOT": str(args.dataset_root),
            "MIA_OUTPUT_ROOT": str(run_root),
            "MIA_RUN_INPUT_ROOT": str(args.mia_root / f"run_inputs_{args.run_id}" / name),
            "DEVICE": args.device, "PYTHONNOUSERSITE": "1",
        })
        command = ["bash", "scripts/run_mdmt_mia_author_sync.sh", stage, "test", pair_id]
        if args.dry_run:
            print("[dry-run] " + " ".join(command), flush=True)
            continue
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env=env)
        payload = {"condition": name, "stage": stage, "pair_id": pair_id, "returncode": result.returncode,
                   "source": str(source), "run_root": str(run_root), "completed": int(result.returncode == 0 and complete(run_root, stage, pair_id))}
        write_checkpoint(checkpoint, payload)
        if result.returncode != 0 or not complete(run_root, stage, pair_id):
            raise SystemExit(f"author run failed or produced incomplete JSON: {payload}")
        print(f"[checkpoint] completed={name}/{stage}/pair-{pair_id} path={checkpoint}", flush=True)

    evaluator = Path(__file__).with_name("evaluate_mdmt_mia_paper_alignment.py")
    command = [str(args.mia_root / ".conda-env/bin/python"), str(evaluator), "--official-mda-gt-root", str(args.official_mda_gt_root),
               "--mot-gt-root", str(args.mia_root / "upstream/demo/txt/gt_true"),
               "--pair-ids", *selected_pairs, "--output-dir", str(args.output_dir)]
    for name, _, stage in selected_conditions:
        command.extend(["--condition", f"{name}={run_base / name}={stage}"])
    print("[evaluate] " + " ".join(command), flush=True)
    if not args.dry_run:
        result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], env={**os.environ, "PYTHONPATH": "src"})
        if result.returncode != 0:
            raise SystemExit(result.returncode)
    print(f"[finalize] mode={args.mode} outputs={args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
