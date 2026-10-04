"""Keep historical V2-3 registration tests pinned to their accepted map era."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from tracking.governance_v2 import validate_mapping

V23_REGISTRATION_SHA = "f0687193ed720c3732e1c656dcda8d284b34ae80"


@pytest.fixture(autouse=True)
def _pin_historical_v23_registration(request, monkeypatch):
    if Path(request.module.__file__).name != "test_governance_v2_v23_registration.py":
        return
    module = request.module

    def accepted_v23_inputs():
        def pinned(relative: str) -> dict:
            raw = subprocess.check_output([
                "git", "-C", str(module.ROOT), "show",
                V23_REGISTRATION_SHA + ":summary_md/governance/v2_1/" + relative,
            ])
            return json.loads(raw)
        return validate_mapping(pinned("DEPENDENCY_MAP.json")), pinned("MAP_APPLICABILITY.json")

    monkeypatch.setattr(module, "_current", accepted_v23_inputs)
