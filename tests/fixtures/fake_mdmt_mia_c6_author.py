#!/usr/bin/env python3
"""Non-scientific author stand-in for the C6 real-subprocess path rehearsal."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import numpy as np

from utils.async_deadline_runtime import PacketRuntime


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _run_runtime(result_dir, method, pair):
    runtime = PacketRuntime(result_dir, method, "{}-1".format(pair))
    rows = np.empty((0, 6), dtype=np.float32)
    runtime.begin_frame(0, rows, rows, [], [])

    def deliver_serviceable(confirmed):
        provider = runtime._c5_context_provider
        runtime._c5_context_provider = lambda *_args: provider(rows, rows, ())
        try:
            runtime.deliver_id_state(
                0, "fixture", rows, rows, rows, rows, [], [], [], confirmed, 0, 0
            )
        finally:
            runtime._c5_context_provider = provider

    for index in range(3):
        runtime.deliver_id_state(
            0, "fixture", rows, rows, rows, rows, [], [], [], [], 0, 0
        )
        deliver_serviceable([10000 + index])
    runtime.deliver_supplement(
        0, "fixture", rows, rows, rows, rows, [], [], [], [], rows, rows
    )
    runtime.deliver_supplement(
        0, "fixture", rows, rows, rows, rows, [], [], [], [], rows, rows
    )
    for frame in range(1, 13):
        runtime.begin_frame(frame, rows, rows, [], [])
    runtime.finalize()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--xml_dir", required=True)
    parser.add_argument("--result_dir", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output2", required=True)
    parser.add_argument("--device", required=True)
    args = parser.parse_args(argv)
    c6_config = json.loads(os.environ["MIA_C6_SUPPRESSION_CONFIG"])
    record = {
        "schema_version": "C6_FAKE_AUTHOR_PATH_RECORD_V1",
        "cwd": os.getcwd(),
        "argv": list(argv) if argv is not None else __import__("sys").argv[1:],
        "MIA_OUTPUT_ROOT": os.environ["MIA_OUTPUT_ROOT"],
        "MIA_RUN_INPUT_ROOT": os.environ["MIA_RUN_INPUT_ROOT"],
        "MPLCONFIGDIR": os.environ["MPLCONFIGDIR"],
        "MIA_C6_SUPPRESSION_CONFIG": c6_config,
        "result_dir": args.result_dir,
        "output": args.output,
        "output2": args.output2,
        "tracking_outcome_read": False,
        "scientific_nontrivial_workload_executed": False,
    }
    record_path = Path(os.environ["FAKE_C6_AUTHOR_RECORD"])
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(_canonical(record) + "\n", encoding="utf-8")
    pair = args.method.rsplit("_", 1)[-1]
    _run_runtime(args.result_dir, args.method, pair)
    print("[=> ] 1/1")
    print("fake C6 author completed without tracking or scientific outcome reads")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
