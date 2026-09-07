import json
from pathlib import Path
import pytest

from evaluation.mdmt_mia_locked_d1_analysis import guarded_evaluator_import, verdict_filename, write_verdict
from tracking.mdmt_mia_locked_d1_package import LockedD1Error


def test_analyzer_cannot_import_before_authorization(tmp_path: Path, monkeypatch):
    called = []
    import evaluation.mdmt_mia_locked_d1_analysis as module
    monkeypatch.setattr(module.importlib, "import_module", lambda name: called.append(name))
    with pytest.raises(LockedD1Error, match="AUTHORIZATION"):
        guarded_evaluator_import(tmp_path / "missing.json", "abc", "train")
    assert called == []


def test_canonical_verdict_names_only(tmp_path: Path):
    assert verdict_filename("train") == "primary_verdict.json"
    assert verdict_filename("val") == "external_verdict.json"
    digest = write_verdict(tmp_path, "train", {"state": "FROZEN"})
    assert len(digest) == 64 and (tmp_path / "primary_verdict.json").is_file()
    assert not (tmp_path / "primary_or_external_verdict.json").exists()
