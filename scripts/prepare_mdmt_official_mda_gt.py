#!/usr/bin/env python3
"""Download the small official MDMT MDA ground-truth files from GitHub."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen

from datasets.mdmt import OFFICIAL_MDA_TEST_SEQUENCE_IDS, load_official_mda_gt


BASE_URL = (
    "https://raw.githubusercontent.com/VisDrone/"
    "Multi-Drone-Multi-Object-Detection-and-Tracking/main/demo/eval/test"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    total = len(OFFICIAL_MDA_TEST_SEQUENCE_IDS) * 2
    completed = 0
    for sequence_id in OFFICIAL_MDA_TEST_SEQUENCE_IDS:
        for view_id in (1, 2):
            completed += 1
            destination = args.output_dir / f"{sequence_id}-{view_id}.txt"
            if args.resume and destination.is_file():
                print(f"[download] {completed}/{total} resume: skip {destination.name}", flush=True)
                continue
            url = f"{BASE_URL}/{sequence_id}-{view_id}.txt"
            print(f"[download] {completed}/{total} {url}", flush=True)
            with urlopen(url, timeout=60) as response:
                payload = response.read()
            destination.write_bytes(payload)
            rows = load_official_mda_gt(
                destination,
                sequence_id=sequence_id,
                view_id=view_id,
            )
            if not rows:
                raise RuntimeError(f"downloaded empty GT: {destination}")
            print(f"[verify] {destination.name} rows={len(rows)}", flush=True)
    print(f"[complete] official MDA GT ready at {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
