from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tracking.mdmt_mia_async_deadline_runtime import validate_packet_census_records
from tracking.packet_census_run_tools import (
    CENSUS_RUN_ID,
    FROZEN_CHECKPOINT,
    PacketCensusToolError,
    Z0_DELAYS,
    atomic_write_json,
    atomic_write_jsonl,
    build_manifest,
    expected_pair_paths,
    filename_list_digest,
    freeze_manifest,
    inspect_pair,
    load_jsonl,
    summarize_census,
    validate_pair_attempt,
    verify_frozen_manifest,
    write_pair_validation,
)


PAIR_COUNTS = (700, 500, 340, 700, 700, 700, 300, 400, 450, 360, 400, 460, 430,
               500, 220, 390, 700, 490, 370, 300, 700, 348, 700, 520, 348)


def _pair_records(tmp_path: Path):
    records = []
    for index, count in enumerate(PAIR_COUNTS, 1):
        pair_id = str(index)
        records.append({
            "pair_id": pair_id,
            "view1_sequence": "{}-1".format(pair_id),
            "view2_sequence": "{}-2".format(pair_id),
            "frame_count": count,
            "view1_image_dir": str(tmp_path / "images" / pair_id / "1"),
            "view2_image_dir": str(tmp_path / "images" / pair_id / "2"),
            "view1_image_count": count,
            "view2_image_count": count,
            "view1_ordered_filename_sha256": "a",
            "view2_ordered_filename_sha256": "a",
            "same_basename_mapping": True,
            "view1_xml_path": str(tmp_path / "xml" / (pair_id + "-1.xml")),
            "view2_xml_path": str(tmp_path / "xml" / (pair_id + "-2.xml")),
            "view1_xml_sha256": "x",
            "view2_xml_sha256": "y",
            "xml_initialization_available": True,
            "pre_run_eligible": True,
            "pre_run_ineligibility_reasons": [],
        })
    assert sum(PAIR_COUNTS) == 12026
    return records


def _local_records(pair_id="1", ordinal=1, frame=0, raw_bytes=0):
    sequence = "{}-1".format(pair_id)
    packet_id = {
        "census_run_id": CENSUS_RUN_ID,
        "sequence_name": sequence,
        "runtime_instance_id": "runtime-{}".format(pair_id),
        "emission_ordinal": ordinal,
    }
    routing = {"type": "VIEW_NATIVE", "view_id": 1, "source": "NOT_EXPLICIT",
               "target": "NOT_EXPLICIT", "direction": "NOT_EXPLICIT"}
    emission = {
        "record_type": "PACKET_EMISSION", "packet_id": packet_id, "channel": "local",
        "stage": "NOT_EXPLICIT", "runtime_instance_id": packet_id["runtime_instance_id"],
        "source_state_version": ordinal, "capture_frame": frame, "emitted_frame": frame,
        "arrival_frame": frame, "valid_until_frame": frame, "wire_digest": "digest-{}-{}".format(pair_id, ordinal),
        "JSON_WIRE_BYTES": 10 + ordinal, "SEMANTIC_ARRAY_RAW_BYTES": raw_bytes,
        "routing_attribution": routing,
        "content_counts": {"tracker_row_count": 0, "detector_candidate_count": 0},
    }
    terminal = {
        "record_type": "PACKET_TERMINAL", "packet_id": copy.deepcopy(packet_id), "channel": "local",
        "stage": "NOT_EXPLICIT", "routing_attribution": copy.deepcopy(routing),
        "terminal_class": "TIMELY_DELIVERED", "terminal_reason": "timely", "terminal_frame": frame,
        "wire_digest": emission["wire_digest"],
    }
    finalization = {
        "record_type": "CENSUS_FINALIZATION", "census_run_id": CENSUS_RUN_ID, "sequence_name": sequence,
        "runtime_instance_id": packet_id["runtime_instance_id"], "finalization_frame": frame,
        "completion_state": "SUCCESSFUL_FINALIZE", "emission_record_count": 1, "terminal_record_count": 1,
    }
    return emission, terminal, finalization


def _write_valid_attempt(root: Path, pair_record: dict):
    paths = expected_pair_paths(root, pair_record["pair_id"])
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    emission, terminal, finalization = _local_records(pair_record["pair_id"])
    atomic_write_jsonl(paths["emissions"], [emission])
    atomic_write_jsonl(paths["terminals"], [terminal])
    atomic_write_jsonl(paths["finalizations"], [finalization])
    validation = validate_packet_census_records([emission], [terminal], [finalization])
    validation["io_failure"] = ""
    atomic_write_json(paths["runtime_validation"], validation)
    atomic_write_json(paths["author_manifest"], {
        "delay_frames": dict(Z0_DELAYS), "packet_census_status": "CENSUS_COMPLETE",
        "future_read_violations": 0, "source_bypass_read_count": 0,
        "wire_roundtrip_digest_mismatches": 0, "numpy_alias_violations": 0,
        "feedback_chain_mismatches": 0,
    })
    atomic_write_json(paths["prediction_view1"], {})
    atomic_write_json(paths["prediction_view2"], {})
    atomic_write_jsonl(paths["trace"], [{"packet_action": "timely"}])
    atomic_write_json(paths["rng_report"], {"completed": True})
    paths["author_log"].write_text("complete\n", encoding="utf-8")
    return paths


def test_expected_pair_paths_place_prediction_json_in_author_result_root(tmp_path):
    paths = expected_pair_paths(tmp_path, "23")

    assert paths["prediction_view1"] == tmp_path / "results" / "mia_train_23" / "23-1.json"
    assert paths["prediction_view2"] == tmp_path / "results" / "mia_train_23" / "23-2.json"


def test_filename_digest_and_strict_jsonl(tmp_path: Path):
    assert filename_list_digest(["00000001.jpg", "00000002.jpg"]) == filename_list_digest([
        "00000001.jpg", "00000002.jpg"
    ])
    with pytest.raises(PacketCensusToolError):
        filename_list_digest(["00000002.jpg", "00000001.jpg"])
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text('{"record_type":"PACKET_EMISSION"}\n\n', encoding="utf-8")
    with pytest.raises(PacketCensusToolError):
        load_jsonl(ledger, "PACKET_EMISSION")


def test_inspect_pair_never_parses_xml_and_freezes_filename_mapping(tmp_path: Path):
    dataset = tmp_path / "dataset"
    for view in ("1", "2"):
        directory = dataset / "train" / view / "23-{}".format(view)
        directory.mkdir(parents=True)
        for name in ("00000001.jpg", "00000002.jpg"):
            (directory / name).write_bytes(b"image")
        xml = dataset / "new_xml" / view / "23-{}.xml".format(view)
        xml.parent.mkdir(parents=True, exist_ok=True)
        xml.write_bytes(b"<not-well-formed")
    from tracking.packet_census_run_tools import sha256_file
    hashes = (sha256_file(dataset / "new_xml" / "1" / "23-1.xml"),
              sha256_file(dataset / "new_xml" / "2" / "23-2.xml"))
    record = inspect_pair("23", 2, dataset, hashes)
    assert record["pre_run_eligible"]
    assert record["same_basename_mapping"]


def test_manifest_is_immutable_and_digest_checked(tmp_path: Path):
    contract, tool = tmp_path / "contract.md", tmp_path / "tool.py"
    contract.write_text("contract\n", encoding="utf-8")
    tool.write_text("tool\n", encoding="utf-8")
    manifest = build_manifest(contract, {"runtime": "hash"}, [tool], _pair_records(tmp_path), "2026-09-02T00:00:00+00:00")
    root = tmp_path / "output"
    freeze_manifest(root, manifest)
    assert verify_frozen_manifest(root)["frozen_git_checkpoint"] == FROZEN_CHECKPOINT
    with pytest.raises(PacketCensusToolError):
        freeze_manifest(root, manifest)
    (root / "CENSUS_PAIR_MANIFEST.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(PacketCensusToolError):
        verify_frozen_manifest(root)


def test_outer_z0_validation_reloads_disk_artifacts_and_rejects_pollution(tmp_path: Path):
    pair = _pair_records(tmp_path)[0]
    attempt = tmp_path / "attempt_001"
    paths = _write_valid_attempt(attempt, pair)
    report, emissions, terminals, finalizations = validate_pair_attempt(attempt, pair)
    assert report["passed"]
    assert len(emissions) == len(terminals) == len(finalizations) == 1
    validation_path = write_pair_validation(attempt, report)
    assert validation_path.is_file()
    with pytest.raises(PacketCensusToolError):
        write_pair_validation(attempt, report)
    paths["trace"].write_text('{"packet_id":"forbidden"}\n', encoding="utf-8")
    report, _, _, _ = validate_pair_attempt(attempt, pair)
    assert not report["passed"]
    assert "census_field_pollution" in report["failures"]


def test_outer_validation_rejects_non_z0_terminal(tmp_path: Path):
    pair = _pair_records(tmp_path)[0]
    attempt = tmp_path / "attempt_001"
    paths = _write_valid_attempt(attempt, pair)
    terminal = load_jsonl(paths["terminals"])[0]
    terminal["terminal_class"] = "EXPIRED"
    terminal["terminal_reason"] = "expired"
    atomic_write_jsonl(paths["terminals"], [terminal])
    report, _, _, _ = validate_pair_attempt(attempt, pair)
    assert not report["passed"]
    assert "non_timely_z0_terminal" in report["failures"]


def test_zero_frame_grid_and_equal_pair_view_are_separate(tmp_path: Path):
    pairs = _pair_records(tmp_path)
    emissions = {}
    for index, pair in enumerate(pairs, 1):
        emission, _, _ = _local_records(pair["pair_id"], raw_bytes=0 if index == 1 else index)
        emissions[pair["pair_id"]] = [emission]
    result = summarize_census(pairs, emissions)
    assert result["census_frame_unit_count"] == 12026
    assert result["emission_count"] == 25
    local = result["pooled_frame_or_packet_view"]["by_channel"]["local"]
    assert local["per_frame"]["zero_emission_frame_fraction"] > 0.99
    assert local["per_packet"]["packet_count"] == 25
    assert result["equal_pair_view"]["total_packets_per_frame"]["count"] == 25
    assert result["pair_results"]["1"]["by_channel"]["local"]["SEMANTIC_ARRAY_RAW_BYTES_workload_share"] == "UNDEFINED_ZERO_DENOMINATOR"


def test_partial_cohort_and_observability_gap_fail_closed(tmp_path: Path):
    pairs = _pair_records(tmp_path)
    emission, _, _ = _local_records("1")
    with pytest.raises(PacketCensusToolError, match="partial cohort"):
        summarize_census(pairs, {"1": [emission]})
    emissions = {}
    for pair in pairs:
        row, _, _ = _local_records(pair["pair_id"])
        emissions[pair["pair_id"]] = [row]
    emissions["1"][0]["capture_frame"] = 99999
    with pytest.raises(PacketCensusToolError, match="OBSERVABILITY_GAP"):
        summarize_census(pairs, emissions)
