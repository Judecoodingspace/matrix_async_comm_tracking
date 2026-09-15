#!/usr/bin/env python3
"""Deterministic synthetic input for a later, separately authorized C6 E2E test.

It constructs data only; it does not instantiate a runtime or launch work.
"""
from __future__ import annotations

import json


def tiny_sequence():
    """One suppressible ID-State, one mixed/serviceable ID-State, one Supplement.

    The budget is intentionally the sum of the suppressible and Supplement
    wire lengths so a future test can demonstrate capacity reuse in one frame.
    """
    suppressible = {"kind": "id_state", "source_state_version": 1,
                    "payload": {"stage": "fixture", "remap_events": [], "confirmed_ids": []}}
    serviceable = {"kind": "id_state", "source_state_version": 2,
                   "payload": {"stage": "fixture", "remap_events": [], "confirmed_ids": [42]}}
    supplement = {"kind": "supplement", "source_state_version": 3,
                  "payload": {"stage": "fixture", "note": "unaffected-by-c6"}}
    wire = lambda value: len(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return {"schema_version": "C6_TINY_RUNTIME_FIXTURE_V1", "sequence_name": "tiny",
            "packets": [suppressible, serviceable, supplement],
            "same_frame_reuse_budget_bytes": wire(suppressible) + wire(supplement)}


def main():
    print(json.dumps(tiny_sequence(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
