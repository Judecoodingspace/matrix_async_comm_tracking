"""Accounting failures must invalidate measurement even for excluded packets."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import analyze_mdmt_mia_hr_formal002 as analysis


def event(packet, ordinal, frame, kind, amount=0, remaining=None, channel="id_state", wire_bytes=15):
    return {"packet_id": {"census_run_id": "fixture", "sequence_name": "66-1",
                "runtime_instance_id": "fixture_runtime", "emission_ordinal": packet},
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
        analysis.key(ledger[0]): {"frame": 0, "ordinal": 1, "wire_bytes": 15,
                                  "classification": "SERVICEABLE"},
        analysis.key(ledger[3]): {"frame": 1, "ordinal": 4, "wire_bytes": 5,
                                  "classification": "SUPPRESSIBLE_STALE"},
    }
    observed = {analysis.event_id(row): analysis.slice_signature(row)
                for row in ledger if row["event_type"] == "service_slice"}
    return classes, observed, ledger, [10, 10]


def test_partial_service_across_frames_counts_all_serviceable_packet_bytes(evidence):
    classes, observed, ledger, totals = evidence
    assert analysis.account_slices(classes, observed, ledger, 2, totals) == 15


def test_excluded_stale_bytes_still_require_complete_accounting(evidence):
    classes, observed, ledger, totals = evidence
    for cls in classes.values():
        cls["classification"] = "SUPPRESSIBLE_STALE"
    assert analysis.account_slices(classes, observed, ledger, 2, totals) == 0
    ledger.pop()
    with pytest.raises(analysis.AccountingError):
        analysis.account_slices(classes, observed, ledger, 2, totals)


def test_valid_no_id_service_is_zero():
    ledger = [event(1, 1, 0, "service_start", channel="supplement", wire_bytes=3),
              event(1, 2, 0, "service_slice", 3, 0, channel="supplement", wire_bytes=3)]
    observed = {analysis.event_id(ledger[1]): analysis.slice_signature(ledger[1])}
    assert analysis.account_slices({}, observed, ledger, 1, [3]) == 0


@pytest.mark.parametrize("change", ["duplicate", "missing_slice", "missing_class", "wire_mismatch",
    "over_service", "bad_start", "outside_horizon", "float_bytes", "frame_total", "unknown_class"])
def test_corrupt_or_unreconciled_required_record_fails_closed(evidence, change):
    classes, observed, ledger, totals = copy.deepcopy(evidence)
    if change == "duplicate":
        ledger.append(dict(ledger[-1]))
    elif change == "missing_slice":
        ledger.pop(2)
    elif change == "missing_class":
        del classes[analysis.key(ledger[0])]
    elif change == "wire_mismatch":
        ledger[2]["wire_digest"] = "f" * 64
    elif change == "over_service":
        ledger[2]["bytes_served"] = 6
        observed[analysis.event_id(ledger[2])] = analysis.slice_signature(ledger[2])
    elif change == "bad_start":
        classes[analysis.key(ledger[0])]["ordinal"] = 2
    elif change == "outside_horizon":
        ledger[2]["frame"] = 2
    elif change == "float_bytes":
        ledger[2]["bytes_served"] = 5.0
    elif change == "frame_total":
        totals[1] = 9
    elif change == "unknown_class":
        classes[analysis.key(ledger[0])]["classification"] = "UNKNOWN"
    with pytest.raises(analysis.AccountingError):
        analysis.account_slices(classes, observed, ledger, 2, totals)


def test_duplicate_json_key_is_invalid():
    with pytest.raises(analysis.AccountingError):
        analysis.strict_json('{"bytes_served":5,"bytes_served":6}')
