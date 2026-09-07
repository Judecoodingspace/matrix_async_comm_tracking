import json
from pathlib import Path
import pytest

from evaluation.mdmt_mia_locked_d1_analysis import guarded_evaluator_import, verdict_filename, write_verdict, classify_three_state, analyze_whole_population
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

def test_analysis_whole_population_and_atomic_transaction(tmp_path: Path):
    auth=tmp_path/"auth.json"; auth.write_text(json.dumps({"state":"AUTHORIZED","population":"val","execution_package_sha256":"p","batch_id":"b","authority_bundle_sha256":"a","measurement_validity_manifest_sha256":"v"}))
    from tracking.mdmt_mia_locked_d1_package import VAL_PAIRS
    attempts={p:{"Y00":1.,"Y01":1.,"Y10_d1":.8,"Y11_d1":.85,"Yec_d1":.79} for p in VAL_PAIRS}
    traces={p:[{"capture_frame":1,"view_id":1,"pre_branch_row_index":1,"delay_membership":True,"cf_membership":False,"high_score_triggered":True,"high_score_bbox_written":True}] for p in VAL_PAIRS}
    output=analyze_whole_population(authorization=auth,batch_root=tmp_path,population="val",batch_id="b",package_manifest_sha256="p",authority_bundle_sha256="a",validity_manifest_sha256="v",attempts=attempts,traces=traces,evaluator=object())
    assert output.endswith("external_verdict.json") and not (tmp_path/"analysis.staging").exists()
    assert classify_three_state(traces[VAL_PAIRS[0]]) == "complete_path"
