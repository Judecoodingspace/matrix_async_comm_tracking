#!/usr/bin/env python3
"""Read-only C6 baseline derivation helpers; CLI execution remains separately unauthorized."""
from __future__ import annotations
import json


class BaselineError(RuntimeError):
    pass


def packet_key(packet_id):
    required = {"census_run_id", "sequence_name", "runtime_instance_id", "emission_ordinal"}
    if not isinstance(packet_id, dict) or set(packet_id) != required:
        raise BaselineError("invalid packet identity")
    return json.dumps(packet_id, sort_keys=True, separators=(",", ":"))


def derive_serviceable_bytes(shadow_rows, ledger_rows):
    """Pure synthetic-fixture logic; callers must authorize real evidence access."""
    classes = {}
    for row in shadow_rows:
        key = packet_key(row["packet_id"])
        if key in classes or row.get("channel") != "id_state":
            raise BaselineError("duplicate or invalid classification")
        classes[key] = not bool(row["whole_packet_currently_non_applicable"])
    total = 0
    for row in ledger_rows:
        if row.get("event_type") != "service_slice" or row.get("channel") != "id_state":
            continue
        served = row.get("bytes_served")
        if not isinstance(served, int) or served <= 0:
            raise BaselineError("invalid service slice")
        key = packet_key(row["packet_id"])
        if key not in classes:
            raise BaselineError("service slice has no classification")
        if classes[key]:
            total += served
    return total
