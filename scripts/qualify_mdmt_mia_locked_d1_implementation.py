#!/usr/bin/env python3
"""P9 harness descriptor only. It cannot launch qualification or formal runs."""
from __future__ import annotations
import json


def main() -> None:
    print(json.dumps({"classification": "QUALIFICATION_HARNESS_ONLY", "launch": "PROHIBITED",
                      "checks": ["authority", "cache", "parity", "validity_blindness", "analyzer_guard",
                                 "attempt_immutability", "storage", "trace", "type_i", "type_ii"]}, sort_keys=True))


if __name__ == "__main__":
    main()
