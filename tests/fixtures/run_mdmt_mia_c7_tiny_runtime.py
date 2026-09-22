#!/usr/bin/env python3
"""Generate explicitly synthetic C7 validated-window fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tracking.mdmt_mia_c7_batch_b import (
    make_validated_no_stale_window_record,
    make_validated_window_record,
)
from tracking.mdmt_mia_c7_batch_b_package import atomic_write_jsonl


def _load(path: Path | str):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("synthetic fixture spec must be an object")
    return value


def generate(spec):
    if spec.get("synthetic_non_scientific") is not True:
        raise ValueError("SYNTHETIC_NON_SCIENTIFIC marker is required")
    records = []
    for window in spec.get("windows", ()):
        if window.get("kind") == "BATCH_A_CORE":
            records.append(make_validated_window_record(
                run_id=spec["run_id"],
                cell=spec["cell"],
                frame_index=window["frame_index"],
                batch_a_evidence=_load(window["evidence_path"]),
            ))
        elif window.get("kind") == "VALIDATED_NO_STALE":
            records.append(make_validated_no_stale_window_record(
                run_id=spec["run_id"],
                cell=spec["cell"],
                frame_index=window["frame_index"],
                raw_observation_evidence=_load(window["raw_observation_evidence_path"]),
            ))
        else:
            raise ValueError("unknown synthetic window kind")
    atomic_write_jsonl(spec["output_path"], records)
    return records


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    args = parser.parse_args(argv)
    generate(_load(args.spec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
