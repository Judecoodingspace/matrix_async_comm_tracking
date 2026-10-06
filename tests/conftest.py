"""Keep historical registration tests pinned to their accepted map eras."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from tracking.governance_v2 import validate_mapping

V23_REGISTRATION_SHA = "f0687193ed720c3732e1c656dcda8d284b34ae80"
V24_REGISTRATION_SHA = "92c05753d869318bff246b1d32e28be8f4703236"


@pytest.fixture(autouse=True)
def _pin_historical_registration(request, monkeypatch):
    name = Path(request.module.__file__).name
    authority = {
        "test_governance_v2_v23_registration.py": V23_REGISTRATION_SHA,
        "test_governance_v2_v24_registration.py": V24_REGISTRATION_SHA,
    }.get(name)
    if authority is None:
        return
    module = request.module

    def accepted_inputs():
        def pinned(relative: str) -> dict:
            raw = subprocess.check_output([
                "git", "-C", str(module.ROOT), "show",
                authority + ":summary_md/governance/v2_1/" + relative,
            ])
            return json.loads(raw)
        return validate_mapping(pinned("DEPENDENCY_MAP.json")), pinned("MAP_APPLICABILITY.json")

    monkeypatch.setattr(module, "_current", accepted_inputs)
