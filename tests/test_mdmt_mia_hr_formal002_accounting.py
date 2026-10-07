"""Accounting failures must invalidate measurement even for excluded packets."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import analyze_mdmt_mia_hr_formal002 as analysis

MODE = analysis.TREATMENT_PACKET_IDENTITY
RUN = "fixture"


def event(packet, ordinal, frame, kind, amount=0, remaining=None, channel="id_state", wire_bytes=15):
    return {"packet_id": {"census_run_id": "fixture", "sequence_name": "66-1",
                "runtime_instance_id": "fixture_runtime", "emission_ordinal": packet},
            "runtime_instance_id": "fixture_runtime",
            "wire_digest": str(packet) * 64, "channel": channel,
            "event_ordinal": ordinal, "frame": frame, "event_type": kind,
            "bytes_served": amount, "JSON_WIRE_BYTES": wire_bytes,
            "remaining_service_bytes": wire_bytes if remaining is None else remaining}


@pytest.fixture
def evidence():
    ledger = [event(1, 1, 0, "service_start"), event(1, 2, 0, "service_slice", 10, 5),
              event(1, 3, 1, "service_slice", 5, 0),
              event(2, 4, 1, "service_start", wire_bytes=5),
              event(2, 5, 1, "service_slice", 5, 0, wire_bytes=5)]
    classes = {
        analysis.key(ledger[0], MODE, RUN): {"frame": 0, "ordinal": 1, "wire_bytes": 15,
                                  "classification": "SERVICEABLE"},
        analysis.key(ledger[3], MODE, RUN): {"frame": 1, "ordinal": 4, "wire_bytes": 5,
                                  "classification": "SUPPRESSIBLE_STALE"},
    }
    observed = {analysis.event_id(row): analysis.slice_signature(row, MODE, RUN)
                for row in ledger if row["event_type"] == "service_slice"}
    return classes, observed, ledger, [10, 10]


def test_partial_service_across_frames_counts_all_serviceable_packet_bytes(evidence):
    classes, observed, ledger, totals = evidence
    assert analysis.account_slices(classes, observed, ledger, 2, totals, MODE, RUN) == 15


def test_excluded_stale_bytes_still_require_complete_accounting(evidence):
    classes, observed, ledger, totals = evidence
    for cls in classes.values():
        cls["classification"] = "SUPPRESSIBLE_STALE"
    assert analysis.account_slices(classes, observed, ledger, 2, totals, MODE, RUN) == 0
    ledger.pop()
    with pytest.raises(analysis.AccountingError):
        analysis.account_slices(classes, observed, ledger, 2, totals, MODE, RUN)


def test_valid_no_id_service_is_zero():
    ledger = [event(1, 1, 0, "service_start", channel="supplement", wire_bytes=3),
              event(1, 2, 0, "service_slice", 3, 0, channel="supplement", wire_bytes=3)]
    observed = {analysis.event_id(ledger[1]): analysis.slice_signature(ledger[1], MODE, RUN)}
    assert analysis.account_slices({}, observed, ledger, 1, [3], MODE, RUN) == 0


@pytest.mark.parametrize("change", ["duplicate", "missing_slice", "missing_class", "wire_mismatch",
    "over_service", "bad_start", "outside_horizon", "float_bytes", "frame_total", "unknown_class"])
def test_corrupt_or_unreconciled_required_record_fails_closed(evidence, change):
    classes, observed, ledger, totals = copy.deepcopy(evidence)
    if change == "duplicate":
        ledger.append(dict(ledger[-1]))
    elif change == "missing_slice":
        ledger.pop(2)
    elif change == "missing_class":
        del classes[analysis.key(ledger[0], MODE, RUN)]
    elif change == "wire_mismatch":
        ledger[2]["wire_digest"] = "f" * 64
    elif change == "over_service":
        ledger[2]["bytes_served"] = 6
        observed[analysis.event_id(ledger[2])] = analysis.slice_signature(ledger[2], MODE, RUN)
    elif change == "bad_start":
        classes[analysis.key(ledger[0], MODE, RUN)]["ordinal"] = 2
    elif change == "outside_horizon":
        ledger[2]["frame"] = 2
    elif change == "float_bytes":
        ledger[2]["bytes_served"] = 5.0
    elif change == "frame_total":
        totals[1] = 9
    elif change == "unknown_class":
        classes[analysis.key(ledger[0], MODE, RUN)]["classification"] = "UNKNOWN"
    with pytest.raises(analysis.AccountingError):
        analysis.account_slices(classes, observed, ledger, 2, totals, MODE, RUN)


def test_duplicate_json_key_is_invalid():
    with pytest.raises(analysis.AccountingError):
        analysis.strict_json('{"bytes_served":5,"bytes_served":6}')


def baseline_event():
    row = event(1, 1, 0, "service_start")
    row["packet_id"] = {"sequence_name": "66-1", "packet_sequence": 101}
    row["packet_sequence"] = 101
    row["runtime_instance_id"] = ""
    return row


def test_baseline_exact_two_field_packet_identity_passes():
    row = baseline_event()
    assert analysis.key(row, analysis.BASELINE_PACKET_IDENTITY, analysis.C7_RUN)[0] == (
        analysis.canonical(row["packet_id"]))


@pytest.mark.parametrize("change", ["missing_name", "missing_sequence", "extra_census",
    "negative", "zero", "text", "boolean", "wrong_name", "event_sequence_mismatch"])
def test_baseline_packet_identity_rejects_wrong_schema_or_sequence(change):
    row = baseline_event()
    packet = row["packet_id"]
    if change == "missing_name":
        del packet["sequence_name"]
    elif change == "missing_sequence":
        del packet["packet_sequence"]
    elif change == "extra_census":
        packet["census_run_id"] = analysis.C7_RUN
    elif change == "negative":
        packet["packet_sequence"] = -1
    elif change == "zero":
        packet["packet_sequence"] = 0
    elif change == "text":
        packet["packet_sequence"] = "101"
    elif change == "boolean":
        packet["packet_sequence"] = True
    elif change == "wrong_name":
        packet["sequence_name"] = "other"
    elif change == "event_sequence_mismatch":
        row["packet_sequence"] = 102
    with pytest.raises(analysis.AccountingError):
        analysis.key(row, analysis.BASELINE_PACKET_IDENTITY, analysis.C7_RUN)


def test_treatment_exact_census_packet_identity_passes():
    row = event(1, 1, 0, "service_start")
    assert analysis.key(row, MODE, RUN)[0] == analysis.canonical(row["packet_id"])


def test_unknown_packet_identity_mode_fails_even_without_packets():
    with pytest.raises(analysis.AccountingError, match="UNKNOWN_PACKET_IDENTITY_MODE"):
        analysis.account_slices({}, {}, [], 0, [], "AUTO", RUN)


@pytest.mark.parametrize("change", ["two_field", "wrong_run", "wrong_runtime",
    "wrong_name", "missing_ordinal", "negative_ordinal", "zero_ordinal",
    "text_ordinal", "boolean_ordinal"])
def test_treatment_packet_identity_rejects_wrong_schema_or_provenance(change):
    row = event(1, 1, 0, "service_start")
    packet = row["packet_id"]
    if change == "two_field":
        row["packet_id"] = {"sequence_name": "66-1", "packet_sequence": 1}
    elif change == "wrong_run":
        packet["census_run_id"] = "other"
    elif change == "wrong_runtime":
        row["runtime_instance_id"] = "other"
    elif change == "wrong_name":
        packet["sequence_name"] = "other"
    elif change == "missing_ordinal":
        del packet["emission_ordinal"]
    elif change == "negative_ordinal":
        packet["emission_ordinal"] = -1
    elif change == "zero_ordinal":
        packet["emission_ordinal"] = 0
    elif change == "text_ordinal":
        packet["emission_ordinal"] = "1"
    elif change == "boolean_ordinal":
        packet["emission_ordinal"] = True
    with pytest.raises(analysis.AccountingError):
        analysis.key(row, MODE, RUN)


def test_same_service_history_has_same_byte_accounting_under_explicit_source_schemas(evidence):
    treatment_classes, treatment_observed, treatment_ledger, totals = copy.deepcopy(evidence)
    treatment = analysis.account_slices(treatment_classes, treatment_observed,
                                        treatment_ledger, 2, totals, MODE, RUN)
    baseline_ledger = copy.deepcopy(treatment_ledger)
    for row in baseline_ledger:
        row["packet_id"] = {"sequence_name": "66-1",
                            "packet_sequence": row["packet_id"]["emission_ordinal"] + 100}
        row["packet_sequence"] = row["packet_id"]["packet_sequence"]
        row["runtime_instance_id"] = ""
    baseline_mode = analysis.BASELINE_PACKET_IDENTITY
    baseline_classes = {
        analysis.key(baseline_ledger[0], baseline_mode, analysis.C7_RUN):
            copy.deepcopy(treatment_classes[analysis.key(treatment_ledger[0], MODE, RUN)]),
        analysis.key(baseline_ledger[3], baseline_mode, analysis.C7_RUN):
            copy.deepcopy(treatment_classes[analysis.key(treatment_ledger[3], MODE, RUN)]),
    }
    baseline_observed = {analysis.event_id(row):
        analysis.slice_signature(row, baseline_mode, analysis.C7_RUN)
        for row in baseline_ledger if row["event_type"] == "service_slice"}
    baseline = analysis.account_slices(baseline_classes, baseline_observed,
                                       baseline_ledger, 2, totals, baseline_mode, analysis.C7_RUN)
    assert treatment == baseline == 15


def test_corrected_c7_inventory_digest_and_required_fail_closed_negatives():
    cell = analysis.C7 / "cells/P66__P20"
    inventory = json.loads((cell / "cell_inventory.json").read_bytes())
    seal = json.loads((cell / "cell_seal.json").read_bytes())
    terminal = json.loads((cell / "CELL_COMMITTED.json").read_bytes())
    observed = {relative: analysis.sha(analysis.C7 / relative) for relative in analysis.EXPECTED}
    rebuilt = analysis.rebuild_c7_cell_inventory(cell)
    # This positive case uses the actual sealed C7 inventory and seal metadata.
    analysis.validate_c7_inventory_binding(inventory, seal, terminal, observed, rebuilt)
    malformed = "205aafad0d21237207cd46c6e07998d9459b436849e7660b1a6f14031a7cdb85ef4"
    with pytest.raises(analysis.AccountingError, match="C7_RECORDED_DIGEST_MALFORMED"):
        analysis.validate_c7_inventory_binding(inventory, seal, terminal, observed,
                                               rebuilt, malformed)
    changed_file = dict(observed)
    changed_file["cells/P66__P20/windows.jsonl"] = "0" * 64
    with pytest.raises(analysis.AccountingError, match="C7_SOURCE_IDENTITY_CHANGED"):
        analysis.validate_c7_inventory_binding(inventory, seal, terminal, changed_file,
                                               rebuilt)
    changed_inventory = copy.deepcopy(inventory)
    changed_inventory["files"][0]["byte_count"] += 1
    with pytest.raises(analysis.AccountingError, match="C7_INVENTORY_BYTES_CHANGED"):
        analysis.validate_c7_inventory_binding(changed_inventory, seal, terminal, observed,
                                               rebuilt)
    changed_seal = copy.deepcopy(seal)
    changed_seal["sealed_payload"]["inventory_sha256"] = "0" * 64
    with pytest.raises(analysis.AccountingError, match="C7_SEAL_IDENTITY_CHANGED"):
        analysis.validate_c7_inventory_binding(inventory, changed_seal, terminal, observed,
                                               rebuilt)
