#!/usr/bin/env python3
"""Aggregate a fully validated frozen Z0 packet-census cohort.

This program never launches author code.  It refuses partial cohorts and
revalidates every accepted attempt from its raw append-only ledgers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tracking.packet_census_run_tools import (
    PacketCensusToolError,
    atomic_write_json,
    read_json,
    sha256_file,
    summarize_census,
    validate_pair_attempt,
    verify_frozen_manifest,
    write_summary,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        manifest = verify_frozen_manifest(args.output_root)
        state_path = Path(args.output_root) / "RUN_STATE.json"
        state = read_json(state_path)
        if state.get("state") != "COHORT_VALIDATED":
            raise PacketCensusToolError("aggregation requires COHORT_VALIDATED")
        accepted = state.get("accepted_attempts", {})
        if set(accepted) != set(manifest["pair_order"]):
            raise PacketCensusToolError("partial cohort cannot aggregate")
        pair_to_emissions = {}
        validation_hashes = {}
        for pair_id in manifest["pair_order"]:
            selected = accepted[pair_id]
            attempt_root = Path(selected["path"])
            report, emissions, _, _ = validate_pair_attempt(attempt_root, next(
                item for item in manifest["pairs"] if item["pair_id"] == pair_id
            ))
            persisted = read_json(attempt_root / "validation.json")
            if not report["passed"] or persisted != report:
                raise PacketCensusToolError("accepted attempt no longer validates: {}".format(pair_id))
            if selected.get("validation_sha256") != sha256_file(attempt_root / "validation.json"):
                raise PacketCensusToolError("accepted validation hash drift: {}".format(pair_id))
            pair_to_emissions[pair_id] = emissions
            validation_hashes[pair_id] = selected["validation_sha256"]
        summary = summarize_census(manifest["pairs"], pair_to_emissions)
        summary["manifest_sha256"] = sha256_file(Path(args.output_root) / "CENSUS_PAIR_MANIFEST.json")
        summary["accepted_validation_sha256"] = validation_hashes
        audit_path, summary_path = write_summary(args.output_root, summary)
        state["state"] = "AGGREGATION_COMPLETE"
        state["packet_audit_path"] = str(audit_path)
        state["summary_path"] = str(summary_path)
        atomic_write_json(state_path, state)
        print(json.dumps({"state": state["state"], "packet_audit_path": str(audit_path),
                          "summary_path": str(summary_path)}, sort_keys=True))
    except PacketCensusToolError as exc:
        print("PACKET_CENSUS_RUN_INCOMPLETE: {}".format(exc), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
