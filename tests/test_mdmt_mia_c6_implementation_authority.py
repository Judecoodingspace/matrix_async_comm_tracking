import importlib.util
import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "c6_production_runner",
    ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py",
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

e2e_spec = importlib.util.spec_from_file_location(
    "c6_e2e_qualification",
    ROOT / "scripts/run_mdmt_mia_c6_e2e_qualification.py",
)
e2e = importlib.util.module_from_spec(e2e_spec)
e2e_spec.loader.exec_module(e2e)

INTENDED = "1e440166554e04d219291b1c3c6a8a1f5f6b88ff"
MALFORMED = "1e440166554e04d219291b1c3c6a8f5f6b88ff"
DIFFERENT = "0" + INTENDED[1:]


def test_canonical_40_hex_implementation_authority_is_accepted():
    assert runner.validate_implementation_authority(INTENDED, INTENDED) == INTENDED


def test_malformed_38_hex_implementation_authority_fails_closed():
    with pytest.raises(runner.GateError) as exc_info:
        runner.validate_implementation_authority(MALFORMED, INTENDED)
    assert MALFORMED in str(exc_info.value)
    assert "canonical 40-hex" in str(exc_info.value)


def test_e2e_preflight_rejects_malformed_manifest_before_qualification(tmp_path, monkeypatch):
    source = e2e.MANIFEST.read_text(encoding="utf-8")
    malformed = source.replace(
        '"implementation_sha":"' + INTENDED + '"',
        '"implementation_sha":"' + MALFORMED + '"',
    )
    manifest = tmp_path / "malformed_manifest.json"
    manifest.write_text(malformed, encoding="utf-8")
    monkeypatch.setattr(e2e, "MANIFEST", manifest)
    monkeypatch.setattr(e2e, "MANIFEST_SHA", e2e.sha(manifest))
    with pytest.raises(RuntimeError, match="canonical 40-hex"):
        e2e.preflight(manifest_sha=e2e.sha(manifest))


def test_different_canonical_40_hex_authority_fails_with_actual_operands():
    with pytest.raises(runner.GateError) as exc_info:
        runner.validate_implementation_authority(DIFFERENT, INTENDED)
    message = str(exc_info.value)
    assert "requested={!r}".format(DIFFERENT) in message
    assert "accepted={!r}".format(INTENDED) in message


def test_corrected_manifest_binds_exact_intended_git_authority():
    manifest_path = ROOT / (
        "summary_md/communication/"
        "c6_generated_author_source_qualification_corrective/"
        "C6_GENERATED_AUTHOR_SOURCE_MANIFEST.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert re.fullmatch(r"[0-9a-f]{40}", manifest["implementation_sha"])
    assert manifest["implementation_sha"] == INTENDED
