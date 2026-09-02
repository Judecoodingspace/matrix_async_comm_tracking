#!/usr/bin/env python3
"""Validation-only Step 4 runner for frozen author XML-initialized MIA."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


CONDITIONS = {
    "Z0": {"local": 0, "homography": 0, "id_state": 0, "supplement": 0},
    "L1": {"local": 1, "homography": 0, "id_state": 0, "supplement": 0},
    "H1": {"local": 0, "homography": 1, "id_state": 0, "supplement": 0},
    "I1": {"local": 0, "homography": 0, "id_state": 1, "supplement": 0},
    "S1": {"local": 0, "homography": 0, "id_state": 0, "supplement": 1},
}
RUNS = (("off_a", False), ("off_b", False), ("on", True))


def _link(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        if destination.resolve() != source.resolve():
            raise RuntimeError(f"existing link mismatch: {destination}")
        return
    destination.symlink_to(source)


def _prepare_input(dataset_root: Path, input_root: Path, pair: str) -> tuple[Path, Path]:
    v1, v2 = f"{pair}-1", f"{pair}-2"
    for view, sequence in (("1", v1), ("2", v2)):
        source = dataset_root / "train" / view / sequence
        if not source.is_dir():
            raise FileNotFoundError(source)
        destination = input_root / view / sequence
        destination.parent.mkdir(parents=True, exist_ok=True)
        _link(source, destination)
    xml_dir = input_root / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    for view, sequence in (("1", v1), ("2", v2)):
        source = dataset_root / "new_xml" / view / f"{sequence}.xml"
        if not source.is_file():
            raise FileNotFoundError(source)
        _link(source, xml_dir / source.name)
    return input_root / "1", xml_dir


def _run(args: argparse.Namespace, condition: str, name: str, census: bool) -> None:
    delays = CONDITIONS[condition]
    root = args.output_root / condition / name
    if root.exists():
        raise RuntimeError(f"refusing to reuse run output: {root}")
    root.mkdir(parents=True)
    input_dir, xml_dir = _prepare_input(args.dataset_root, args.input_root / condition / name, args.pair)
    result_dir = root / "results"
    source = args.variant_root
    entry = source / "demo" / "supplement_MIA.py"
    environment = os.environ.copy()
    environment.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": str(args.seed),
        "PYTHONPATH": f"{source}:{source / 'demo'}:{source / 'demo/utils'}",
        "MIA_ASYNC_CHANNEL_DELAYS": json.dumps(delays, sort_keys=True),
        "MIA_ACTIVE_PACKET_STAGES": "all",
    })
    if census:
        environment["MIA_PACKET_CENSUS_RUN_ID"] = f"step4-{condition}"
    else:
        environment.pop("MIA_PACKET_CENSUS_RUN_ID", None)
    command = [str(args.python), str(args.wrapper), "--rng-report", str(root / "torch_rng.json"),
               "--entry", str(entry), "--seed", str(args.seed), "--", "--config", str(args.config),
               "--input", str(input_dir) + "/", "--xml_dir", str(xml_dir) + "/", "--result_dir", str(result_dir),
               "--method", f"mia_train_{args.pair}", "--output", str(root / "view1"),
               "--output2", str(root / "view2"), "--device", args.device]
    with (root / "command.json").open("w", encoding="utf-8") as handle:
        json.dump({"command": command, "delays": delays, "census": census, "pair": args.pair}, handle, indent=2)
    with (root / "author.log").open("w", encoding="utf-8") as handle:
        result = subprocess.run(command, cwd=root, env=environment, stdout=handle, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError({"condition": condition, "run": name, "returncode": result.returncode, "log": str(root / "author.log")})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--wrapper", type=Path, required=True)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--pair", default="23")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--condition", choices=tuple(CONDITIONS), required=True)
    parser.add_argument("--run", choices=("off_a", "off_b", "on"), required=True)
    args = parser.parse_args()
    _run(args, args.condition, args.run, dict(RUNS)[args.run])


if __name__ == "__main__":
    main()
