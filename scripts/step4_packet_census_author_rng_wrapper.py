#!/usr/bin/env python3
"""Run a frozen author entry while recording non-mutating RNG snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import runpy
import sys
from pathlib import Path

import numpy as np


def _digest(value) -> str:
    return hashlib.sha256(value.cpu().numpy().tobytes()).hexdigest()


def _snapshot(torch) -> dict[str, object]:
    cuda_available = bool(torch.cuda.is_available())
    return {
        "torch_cpu_rng_sha256": _digest(torch.get_rng_state()),
        "cuda_available": cuda_available,
        "torch_cuda_rng_sha256": [_digest(item) for item in torch.cuda.get_rng_state_all()] if cuda_available else [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rng-report", type=Path, required=True)
    parser.add_argument("--entry", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("author_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.entry.is_file():
        raise FileNotFoundError(args.entry)
    author_args = list(args.author_args)
    if author_args[:1] == ["--"]:
        author_args = author_args[1:]

    import torch

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    report: dict[str, object] = {"seed": int(args.seed), "before": _snapshot(torch), "completed": False}
    args.rng_report.parent.mkdir(parents=True, exist_ok=True)
    prior_argv = sys.argv
    try:
        sys.argv = [str(args.entry), *author_args]
        runpy.run_path(str(args.entry), run_name="__main__")
        report["completed"] = True
    finally:
        sys.argv = prior_argv
        report["after"] = _snapshot(torch)
        args.rng_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
