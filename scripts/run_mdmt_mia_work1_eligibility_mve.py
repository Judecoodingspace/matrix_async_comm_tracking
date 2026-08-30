#!/usr/bin/env python3
"""Fail-closed Work 1 orchestration and ledger summarization.

This is intentionally not an experiment launcher.  A future separately
authorized executor may consume its manifest; this implementation cannot make
an accidental MVE/formal run possible.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FROZEN_PAIRS = (23, 25, 27, 28, 29)
FROZEN_DELAY = 5


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(output: Path, image_roots: dict[int, Path]) -> None:
    records = []
    for pair_id in FROZEN_PAIRS:
        root = image_roots[pair_id]
        images = sorted(path for path in root.iterdir() if path.is_file())
        records.append({"pair_id": pair_id, "full_frame_count": len(images), "image_hashes": {path.name: _sha256(path) for path in images}})
    output.write_text(json.dumps({"pair_ids": FROZEN_PAIRS, "delay_frames": FROZEN_DELAY, "records": records}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def summarize(ledger: Path, output: Path) -> None:
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line]
    by_source = {source: sum(row.get("eligibility_source") == source for row in rows) for source in ("PRE_ID_FROZEN", "POST_ID_MUTABLE")}
    created = sum(bool(row.get("writein_opportunity")) for row in rows)
    payload = {"rows": len(rows), "by_eligibility_source": by_source, "writein_opportunities": created,
               "decision": "MECHANISM_SIGNAL_OBSERVED" if created else "NO_OBSERVED_WRITEIN_OPPORTUNITY"}
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    summary = sub.add_parser("summarize")
    summary.add_argument("--ledger", type=Path, required=True)
    summary.add_argument("--output", type=Path, required=True)
    manifest = sub.add_parser("manifest-preflight")
    manifest.add_argument("--image-roots-json", type=Path, required=True)
    manifest.add_argument("--output", type=Path, required=True)
    compare = sub.add_parser("non-interference-preflight")
    compare.add_argument("--parent-artifact", type=Path, required=True)
    compare.add_argument("--derivative-off-artifact", type=Path, required=True)
    compare.add_argument("--derivative-on-artifact", type=Path, required=True)
    compare.add_argument("--output", type=Path, required=True)
    blocked = sub.add_parser("mve")
    blocked.add_argument("--authorize-mve-execution", action="store_true")
    args = parser.parse_args()
    if args.command == "summarize":
        summarize(args.ledger, args.output)
        return
    if args.command == "manifest-preflight":
        roots = {int(key): Path(value) for key, value in json.loads(args.image_roots_json.read_text(encoding="utf-8")).items()}
        if set(roots) != set(FROZEN_PAIRS):
            raise SystemExit("FROZEN_PAIR_MANIFEST_MISMATCH")
        write_manifest(args.output, roots)
        return
    if args.command == "non-interference-preflight":
        digests = {"parent": _sha256(args.parent_artifact), "derivative_off": _sha256(args.derivative_off_artifact), "derivative_on": _sha256(args.derivative_on_artifact)}
        digests["core_output_diff"] = int(not (digests["parent"] == digests["derivative_off"] == digests["derivative_on"]))
        args.output.write_text(json.dumps(digests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if digests["core_output_diff"]:
            raise SystemExit("NON_INTERFERENCE_FAILURE")
        return
    raise SystemExit("MVE_EXECUTION_NOT_IMPLEMENTED: requires a separately frozen execution authorization")


if __name__ == "__main__":
    main()
