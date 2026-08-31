from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from src.tracking.mdmt_mia_work1_eligibility_observer import Work1EligibilityObserver
from src.tracking.mdmt_mia_work1_preexecution import (
    FROZEN_FRAME_SPEC,
    PreexecutionClosureError,
    build_g_xml1_expected,
    build_input_manifest,
    produce_g_xml1_observed,
    render_structured_launch,
    validate_input_manifest,
    validate_launch_provenance,
)
from src.tracking.mdmt_mia_work1_xml_governance import (
    G_XML1_FAIL,
    G_XML3_FAIL,
    G_XML4_FAIL,
    GovernanceGateError,
    Work1AccessAudit,
    make_author_initialization_marker,
    validate_initialization_boundary,
    validate_initialization_provenance,
    validate_runtime_oracle_firewall,
)


ROOT = Path(__file__).resolve().parents[1]
PARENT = Path("/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v8")


def test_g_xml1_observed_producer_passes_and_detects_all_material_drift(tmp_path):
    entrypoint = PARENT / "demo/supplement_MIA.py"
    reader = PARENT / "demo/utils/common.py"
    xml1, xml2 = tmp_path / "one.xml", tmp_path / "two.xml"
    xml1.write_bytes(b"opaque-one")
    xml2.write_bytes(b"opaque-two")
    observed = produce_g_xml1_observed(entrypoint, reader, xml1, xml2)
    expected = {key: observed[key] for key in (
        "author_entrypoint_sha256", "xml_reader_source_sha256", "initialization_code_sha256",
        "xml_view1_sha256", "xml_view2_sha256", "initialization_frame",
    )}
    assert validate_initialization_provenance(expected, observed)["status"] == "PASS"
    xml2.write_bytes(b"drift")
    with pytest.raises(GovernanceGateError) as error:
        validate_initialization_provenance(expected, produce_g_xml1_observed(entrypoint, reader, xml1, xml2))
    assert error.value.label == G_XML1_FAIL
    changed_entrypoint = tmp_path / "supplement_MIA.py"
    changed_entrypoint.write_bytes(entrypoint.read_bytes() + b"\n# drift\n")
    with pytest.raises(GovernanceGateError):
        validate_initialization_provenance(expected, produce_g_xml1_observed(changed_entrypoint, reader, xml1, xml1))
    region_drift = entrypoint.read_bytes().splitlines(keepends=True)
    region_drift[170] = region_drift[170] + b"# region drift\n"
    changed_entrypoint.write_bytes(b"".join(region_drift))
    with pytest.raises(GovernanceGateError):
        validate_initialization_provenance(expected, produce_g_xml1_observed(changed_entrypoint, reader, xml1, xml1))
    with pytest.raises(PreexecutionClosureError):
        produce_g_xml1_observed(entrypoint, reader, tmp_path / "missing.xml", xml1)


def _make_frozen_image_fixture(root: Path) -> None:
    for pair_id, (count, first_name, _, _) in FROZEN_FRAME_SPEC.items():
        first_index = int(first_name.split(".")[0])
        for view_id in (1, 2):
            image_root = root / "train" / str(view_id) / f"{pair_id}-{view_id}"
            image_root.mkdir(parents=True)
            for frame_id in range(first_index, first_index + count):
                (image_root / f"{frame_id:08d}.jpg").write_bytes(f"{pair_id}:{frame_id}".encode())


def test_exact_ten_unit_manifest_and_file_drift_fail_closed(tmp_path):
    dataset = tmp_path / "dataset"
    _make_frozen_image_fixture(dataset)
    manifest = build_input_manifest(dataset)
    assert validate_input_manifest(manifest)["unit_count"] == 10
    missing = copy.deepcopy(manifest)
    missing["units"].pop()
    missing["unit_count"] = 9
    with pytest.raises(PreexecutionClosureError):
        validate_input_manifest(missing, verify_files=False)
    wrong_count = copy.deepcopy(manifest)
    wrong_count["units"][0]["frame_count"] -= 1
    with pytest.raises(PreexecutionClosureError):
        validate_input_manifest(wrong_count, verify_files=False)
    wrong_name = copy.deepcopy(manifest)
    wrong_name["units"][0]["first_filename"] = "wrong.jpg"
    with pytest.raises(PreexecutionClosureError):
        validate_input_manifest(wrong_name, verify_files=False)
    (dataset / "train/1/23-1/00000001.jpg").write_bytes(b"content drift")
    with pytest.raises(PreexecutionClosureError, match="bytes/filenames drift"):
        validate_input_manifest(manifest)


def test_launch_provenance_and_structured_pair_injection(tmp_path):
    provenance = json.loads((ROOT / "summary_md/WORK1_DYNAMIC_M2_LAUNCH_PROVENANCE_MANIFEST.json").read_text())
    assert validate_launch_provenance(provenance)["status"] == "PASS"
    drift = copy.deepcopy(provenance)
    drift["config"]["sha256"] = "0" * 64
    with pytest.raises(PreexecutionClosureError, match="config"):
        validate_launch_provenance(drift)
    structured = json.loads((ROOT / "summary_md/WORK1_DYNAMIC_M2_STRUCTURED_LAUNCH_MANIFEST.json").read_text())
    rendered = render_structured_launch(
        structured, 23, tmp_path / "artifacts", tmp_path / "A", tmp_path / "BC",
        Path(provenance["wrapper"]["realpath"]),
    )
    assert set(rendered["records"]) == {"A", "B", "B_REPEAT", "C"}
    assert all(record["env"]["MIA_WORK1_PAIR_ID"] == "23" for record in rendered["records"].values())
    assert rendered["records"]["B"]["env"]["MIA_SOURCE_ROOT"] == rendered["records"]["C"]["env"]["MIA_SOURCE_ROOT"]


def _boundary_payload(order):
    sequence = {event: index + 1 for index, event in enumerate(order)}
    marker = make_author_initialization_marker(0, (np.zeros((1, 2)),), sequence.get("AUTHOR_GT_INITIALIZATION_COMPLETE", 1))
    return {
        "last_author_gt_read_sequence_number": sequence.get("AUTHOR_LAST_GT_INITIALIZATION_READ", 0),
        "marker": marker.as_dict(),
        "first_work1_e_pre_sequence_number": sequence.get("FIRST_WORK1_E_PRE_RECORD", 0),
        "event_log": [{"event": event, "sequence_number": index + 1} for index, event in enumerate(order)],
    }


def test_real_event_g_xml4_all_order_and_missing_cases():
    valid = ["AUTHOR_LAST_GT_INITIALIZATION_READ", "AUTHOR_GT_INITIALIZATION_COMPLETE", "FIRST_WORK1_E_PRE_RECORD"]
    assert validate_initialization_boundary(_boundary_payload(valid))["status"] == "PASS"
    invalid_orders = [
        ["AUTHOR_GT_INITIALIZATION_COMPLETE", "AUTHOR_LAST_GT_INITIALIZATION_READ", "FIRST_WORK1_E_PRE_RECORD"],
        ["AUTHOR_LAST_GT_INITIALIZATION_READ", "FIRST_WORK1_E_PRE_RECORD", "AUTHOR_GT_INITIALIZATION_COMPLETE"],
        valid[1:], valid[::2], valid[:2],
    ]
    for order in invalid_orders:
        with pytest.raises(GovernanceGateError) as error:
            validate_initialization_boundary(_boundary_payload(order))
        assert error.value.label == G_XML4_FAIL


def test_actual_access_evidence_detects_path_and_serialized_field():
    legal = Work1AccessAudit()
    legal.observe_runtime_interfaces(("frame_id", "pair_id", "run_role"))
    legal.observe_serialized_payload({"pair_id": 23, "frame_id": 1})
    assert validate_runtime_oracle_firewall(legal.as_dict())["status"] == "PASS"
    path_access = Work1AccessAudit()
    path_access.observe_file_access("/tmp/frozen.xml", owner="WORK1_SCIENTIFIC", purpose="RUNTIME_READ")
    with pytest.raises(GovernanceGateError) as error:
        validate_runtime_oracle_firewall(path_access.as_dict())
    assert error.value.label == G_XML3_FAIL
    serialized = Work1AccessAudit()
    serialized.observe_serialized_payload({"gt_identity": 9})
    with pytest.raises(GovernanceGateError):
        validate_runtime_oracle_firewall(serialized.as_dict())


def test_observer_artifacts_bind_pair_role_and_views(monkeypatch, tmp_path):
    monkeypatch.setenv("MIA_WORK1_PAIR_ID", "23")
    monkeypatch.setenv("MIA_WORK1_RUN_ROLE", "C")
    observer = Work1EligibilityObserver.from_environment(tmp_path)
    rows = np.asarray([[1, 10, 10, 20, 20, 0.9]], dtype=np.float32)
    observer.record_author_last_gt_initialization_read(0)
    observer.record_author_initialization_complete(0, (rows, rows))
    observer.capture_pre_id(1, rows, rows, [1], [[15, 15]], [[10, 10], [20, 20]], [], [], [])
    observer.end_frame(1)
    observer.finalize()
    lifecycle = json.loads((tmp_path / "TOKEN_LIFECYCLE_AUDIT.json").read_text())
    ledger = [json.loads(line) for line in (tmp_path / "ELIGIBILITY_LEDGER.jsonl").read_text().splitlines()]
    assert lifecycle["pair_id"] == 23 and lifecycle["run_role"] == "C"
    assert all(row["pair_id"] == 23 and row["run_role"] == "C" for row in ledger)


def test_expected_g_xml1_record_is_derived_only_from_frozen_manifest():
    manifest = json.loads((ROOT / "summary_md/WORK1_DYNAMIC_M2_XML_INPUT_MANIFEST.json").read_text())
    expected = build_g_xml1_expected(manifest, 23)
    assert expected["xml_view1_sha256"] == manifest["records"][0]["view1_xml_sha256"]
    with pytest.raises(PreexecutionClosureError):
        build_g_xml1_expected(manifest, 999)
