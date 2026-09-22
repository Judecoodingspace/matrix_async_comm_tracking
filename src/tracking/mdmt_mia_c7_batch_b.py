"""C7 Batch B producer logic for M5 aggregation and M6 selection.

All inputs are communication-side evidence.  No tracking evaluator or result
reader is imported here.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Iterable, Mapping, Sequence

from .mdmt_mia_c7_batch_b_schema import (
    BATCH_A_FREEZE_AUTHORITY,
    BATCH_A_SEMANTICS_SCHEMA,
    BATCH_A_VALIDATION_SCHEMA,
    CELL_AGGREGATE_SCHEMA,
    CELL_QUALIFICATION_SCHEMA,
    CONDITIONAL_MULTIPLIER,
    GLOBAL_MULTIPLIER,
    FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY,
    MANIFEST_SCHEMA,
    NO_STALE_VALIDATION_SCHEMA,
    NO_STALE_RAW_OBSERVATION_SCHEMA,
    REGISTERED_CELL_IDS,
    SELECTION_SCHEMA,
    T_COUNT,
    T_DENOMINATOR,
    VALIDATED_WINDOW_SCHEMA,
    authority_bindings,
    canonical_sha256,
    registered_cells,
)
from .mdmt_mia_c7_validator import C7ValidationError, validate_core_evidence
from .mdmt_mia_c7_census import (
    ReceiverStateEvidence,
    SUPPRESSIBLE_STALE,
    evaluate_id_state_applicability,
)


class C7BatchBError(ValueError):
    """Raised when Batch B producer inputs are incomplete or inconsistent."""


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_WINDOW_KEYS = frozenset({
    "schema_version", "run_id", "cell_id", "pair_id", "capacity_id",
    "capacity_bytes", "frame_index", "evidence_kind", "evidence",
    "validation", "evidence_sha256", "validation_sha256",
})
_NO_STALE_EVIDENCE_KEYS = frozenset({
    "schema_version", "frame_index", "observations", "observer_failures",
})
_RAW_OBSERVATION_KEYS = frozenset({
    "schema_version", "observation_kind", "event", "item",
    "fifo_snapshot", "receiver_state", "stale_classification",
})
_AGGREGATE_KEYS = frozenset({
    "schema_version", "run_id", "cell_id", "pair_id", "capacity_id",
    "capacity_bytes", "expected_frame_domain", "observed_frame_domain",
    "cell_validity", "invalid_reasons", "N_all", "N_stale", "N_eligible",
    "nesting_attestation", "overall_rate", "conditional_rate",
    "input_window_evidence_digests", "schema_identity",
    "producer_source_authority", "validator_source_authority",
})
_QUALIFICATION_KEYS = frozenset({
    "schema_version", "run_id", "cell_id", "pair_id", "capacity_id",
    "capacity_bytes", "aggregate_sha256", "N_all", "N_stale", "N_eligible",
    "count_threshold", "denominator_threshold", "count_pass",
    "denominator_pass", "global_lhs", "global_rhs", "global_pass",
    "conditional_lhs", "conditional_rhs", "conditional_pass", "CELL_QUALIFIED",
    "cell_validity", "cell_validation_status", "qualification_complete",
    "frozen_batch_a_implementation_authority", "batch_a_freeze_authority",
})


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise C7BatchBError("{} must be an integer".format(label))
    if value < minimum:
        raise C7BatchBError("{} must be >= {}".format(label, minimum))
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise C7BatchBError("{} must be an object".format(label))
    keys = frozenset(value)
    if keys != expected:
        raise C7BatchBError(
            "{} keys mismatch: missing={} extra={}".format(
                label, sorted(expected - keys), sorted(keys - expected)))


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise C7BatchBError("{} must be a lowercase SHA-256".format(label))
    return value


def make_validated_window_record(
    *, run_id: str, cell: Mapping[str, Any], frame_index: int,
    batch_a_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist one Batch A record after independent core validation."""
    try:
        validation = validate_core_evidence(batch_a_evidence)
    except C7ValidationError as exc:
        raise C7BatchBError("Batch A window validation failed") from exc
    if batch_a_evidence.get("schema_version") != BATCH_A_SEMANTICS_SCHEMA:
        raise C7BatchBError("unexpected Batch A semantics schema")
    if validation.get("schema_version") != BATCH_A_VALIDATION_SCHEMA:
        raise C7BatchBError("unexpected Batch A validation schema")
    if batch_a_evidence.get("raw_baseline_evidence", {}).get("frame_index") != frame_index:
        raise C7BatchBError("Batch A frame identity mismatch")
    record = {
        "schema_version": VALIDATED_WINDOW_SCHEMA,
        "run_id": str(run_id),
        "cell_id": str(cell["cell_id"]),
        "pair_id": str(cell["pair_id"]),
        "capacity_id": str(cell["capacity_id"]),
        "capacity_bytes": _integer(cell["capacity_bytes"], "capacity bytes", 1),
        "frame_index": _integer(frame_index, "frame index"),
        "evidence_kind": "BATCH_A_CORE",
        "evidence": copy.deepcopy(dict(batch_a_evidence)),
        "validation": copy.deepcopy(validation),
        "evidence_sha256": canonical_sha256(batch_a_evidence),
        "validation_sha256": canonical_sha256(validation),
    }
    return record


def raw_no_stale_evidence_from_observer(
    frame_index: int, observer: Any,
) -> dict[str, Any]:
    """Persist raw frozen-observer facts needed to prove stale absence."""
    frame = _integer(frame_index, "frame index")
    observations = []
    for source in getattr(observer, "events", ()):
        event = source.get("event", {}) if isinstance(source, Mapping) else {}
        if not isinstance(event, Mapping) or event.get("frame") != frame:
            continue
        item = source.get("item")
        normalized_item = None
        if isinstance(item, Mapping):
            normalized_item = {
                key: copy.deepcopy(item.get(key)) for key in (
                    "packet_id", "wire_digest", "channel", "wire",
                    "JSON_WIRE_BYTES", "remaining_service_bytes",
                    "bytes_served_total", "service_start_frame", "packet_sequence")
            }
        snapshot = source.get("receiver_state")
        normalized_state = None
        if snapshot is not None:
            normalized_state = ReceiverStateEvidence.from_runtime_snapshot(
                event.get("event_ordinal"), snapshot).to_dict()
        classification = source.get("stale_classification")
        observations.append({
            "schema_version": source.get("schema_version"),
            "observation_kind": source.get("observation_kind"),
            "event": copy.deepcopy(dict(event)),
            "item": normalized_item,
            "fifo_snapshot": copy.deepcopy(list(source.get("fifo_snapshot", ()))),
            "receiver_state": normalized_state,
            "stale_classification": (
                copy.deepcopy(dict(classification))
                if isinstance(classification, Mapping) else None),
        })
    failures = [
        copy.deepcopy(dict(row)) for row in getattr(observer, "failures", ())
        if isinstance(row, Mapping) and row.get("frame") in {None, frame}
    ]
    return {
        "schema_version": NO_STALE_RAW_OBSERVATION_SCHEMA,
        "frame_index": frame,
        "observations": observations,
        "observer_failures": failures,
    }


def _packet_identity(value: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        canonical_sha256(value.get("packet_id")),
        str(value.get("wire_digest", "")),
        str(value.get("channel", "")),
    )


def _derive_no_stale_facts(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute completeness and stale absence from raw observer events."""
    _exact_keys(evidence, _NO_STALE_EVIDENCE_KEYS, "no-stale raw evidence")
    if evidence.get("schema_version") != NO_STALE_RAW_OBSERVATION_SCHEMA:
        raise C7BatchBError("no-stale raw evidence schema mismatch")
    frame = _integer(evidence.get("frame_index"), "no-stale frame")
    failures = evidence.get("observer_failures")
    if not isinstance(failures, list) or failures:
        raise C7BatchBError("no-stale evidence has observer failure or invalid failure ledger")
    observations = evidence.get("observations")
    if not isinstance(observations, list) or not observations:
        raise C7BatchBError("no-stale raw observations are missing")
    ordinals = []
    frame_open = 0
    frame_close = 0
    frame_open_event = None
    frame_close_event = None
    observed_service_slice_bytes = 0
    true_first: dict[tuple[str, str, str], int] = {}
    stale_count = 0
    id_state_true_first_count = 0
    served_id_state = set()
    for row in observations:
        _exact_keys(row, _RAW_OBSERVATION_KEYS, "raw observation")
        if row.get("schema_version") != BATCH_A_SEMANTICS_SCHEMA:
            raise C7BatchBError("raw observation schema mismatch")
        event = row.get("event")
        if not isinstance(event, Mapping) or event.get("frame") != frame:
            raise C7BatchBError("raw observation frame mismatch")
        ordinal = _integer(event.get("event_ordinal"), "raw event ordinal", 1)
        ordinals.append(ordinal)
        kind = row.get("observation_kind")
        event_type = event.get("event_type")
        if kind == "frame_open" and event_type == "frame_open":
            frame_open += 1
            frame_open_event = event
        if kind == "frame_close" and event_type == "frame_summary":
            frame_close += 1
            frame_close_event = event
        if kind == "service_slice":
            if event_type != "service_slice":
                raise C7BatchBError("service-slice observation has wrong event type")
            observed_service_slice_bytes += _integer(
                event.get("bytes_served"), "observed service-slice bytes", 1)
        if event_type == "service_slice" and event.get("channel") == "id_state":
            served_id_state.add(_packet_identity(event))
        if kind != "true_first_service":
            continue
        if event_type != "service_start":
            raise C7BatchBError("true-first-service observation has wrong event type")
        item = row.get("item")
        if not isinstance(item, Mapping) or _packet_identity(item) != _packet_identity(event):
            raise C7BatchBError("true-first-service item identity mismatch")
        identity = _packet_identity(item)
        if identity in true_first:
            raise C7BatchBError("duplicate true-first-service observation")
        true_first[identity] = ordinal
        if item.get("channel") != "id_state":
            continue
        id_state_true_first_count += 1
        size = _integer(item.get("JSON_WIRE_BYTES"), "no-stale wire bytes", 1)
        if (_integer(item.get("bytes_served_total"), "no-stale bytes served") != 0
                or _integer(item.get("remaining_service_bytes"), "no-stale residual", 1) != size
                or item.get("service_start_frame") != frame):
            raise C7BatchBError("true-first-service item is not pristine")
        wire = item.get("wire")
        if not isinstance(wire, Mapping) or canonical_sha256(wire) != item.get("wire_digest"):
            raise C7BatchBError("true-first-service wire provenance mismatch")
        state_raw = row.get("receiver_state")
        if not isinstance(state_raw, Mapping):
            raise C7BatchBError("true-first-service receiver state missing")
        state = ReceiverStateEvidence.from_dict(state_raw)
        if state.frame_index != frame or state.event_ordinal != ordinal:
            raise C7BatchBError("true-first-service receiver state identity mismatch")
        applicability = evaluate_id_state_applicability(wire, state)
        expected_classification = (
            SUPPRESSIBLE_STALE if applicability.whole_packet_currently_non_applicable
            else "SERVICEABLE")
        classification = row.get("stale_classification")
        if (not isinstance(classification, Mapping)
                or classification.get("classification") != expected_classification
                or classification.get("event_ordinal") != ordinal
                or classification.get("frame_index") != frame
                or classification.get("source_wire") != wire
                or not isinstance(classification.get("source"), Mapping)
                or _packet_identity(classification["source"]) != identity
                or classification.get("raw_receiver_state") != state.to_dict()
                or classification.get("raw_applicability") != applicability.to_dict()
                or classification.get("hook_event_type") != "service_start"
                or classification.get("json_wire_bytes") != size
                or classification.get("bytes_served_before_hook") != 0
                or classification.get("remaining_service_bytes_before_hook") != size):
            raise C7BatchBError("raw stale classification record is missing or inconsistent")
        stale_count += int(applicability.whole_packet_currently_non_applicable)
    if len(ordinals) != len(set(ordinals)) or ordinals != sorted(ordinals):
        raise C7BatchBError("raw observation ordinals are not unique and ordered")
    if frame_open != 1 or frame_close != 1:
        raise C7BatchBError("complete frame open/close evidence is required")
    if frame_open_event.get("frame_service_budget") != frame_close_event.get(
            "frame_service_budget"):
        raise C7BatchBError("frame service budget changed within raw observation stream")
    close_served = _integer(
        frame_close_event.get("bytes_served"), "frame-close bytes served")
    if observed_service_slice_bytes != close_served:
        raise C7BatchBError("raw service-slice byte ledger is incomplete")
    frame_budget = frame_open_event.get("frame_service_budget")
    open_unused = frame_open_event.get("frame_unused_budget")
    close_unused = frame_close_event.get("frame_unused_budget")
    if frame_budget is None:
        if open_unused is not None or close_unused is not None:
            raise C7BatchBError("unlimited frame budget ledger is inconsistent")
    else:
        budget = _integer(frame_budget, "frame service budget", 1)
        if (_integer(open_unused, "frame-open unused budget") != budget
                or close_served + _integer(
                    close_unused, "frame-close unused budget") != budget):
            raise C7BatchBError("finite frame service budget ledger is inconsistent")
    if not served_id_state.issubset(true_first):
        raise C7BatchBError("served ID-State packet lacks true-first-service evidence")
    return {
        "frame_index": frame,
        "evidence_complete": True,
        "observer_failure_count": 0,
        "true_first_service_count": len(true_first),
        "id_state_true_first_service_count": id_state_true_first_count,
        "stale_classification_count": stale_count,
        "stale_present": stale_count > 0,
        "window_eligible": False,
        "raw_evidence_sha256": canonical_sha256(evidence),
    }


def make_validated_no_stale_window_record(
    *, run_id: str, cell: Mapping[str, Any], frame_index: int,
    raw_observation_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Create no-stale evidence only after raw observer reconstruction."""
    frame = _integer(frame_index, "frame index")
    evidence = copy.deepcopy(dict(raw_observation_evidence))
    facts = _derive_no_stale_facts(evidence)
    if facts["frame_index"] != frame:
        raise C7BatchBError("no-stale raw frame identity mismatch")
    if facts["stale_present"]:
        raise C7BatchBError("raw window contains suppressible stale classification")
    validation = {
        "schema_version": NO_STALE_VALIDATION_SCHEMA,
        "status": "PASS",
        **facts,
    }
    return {
        "schema_version": VALIDATED_WINDOW_SCHEMA,
        "run_id": str(run_id),
        "cell_id": str(cell["cell_id"]),
        "pair_id": str(cell["pair_id"]),
        "capacity_id": str(cell["capacity_id"]),
        "capacity_bytes": _integer(cell["capacity_bytes"], "capacity bytes", 1),
        "frame_index": frame,
        "evidence_kind": "VALIDATED_NO_STALE",
        "evidence": evidence,
        "validation": validation,
        "evidence_sha256": canonical_sha256(evidence),
        "validation_sha256": canonical_sha256(validation),
    }


def _validated_window_facts(
    record: Mapping[str, Any], *, run_id: str, cell: Mapping[str, Any],
) -> tuple[int, bool, bool]:
    _exact_keys(record, _WINDOW_KEYS, "validated window")
    if record.get("schema_version") != VALIDATED_WINDOW_SCHEMA:
        raise C7BatchBError("validated window schema mismatch")
    for key in ("run_id", "cell_id", "pair_id", "capacity_id", "capacity_bytes"):
        expected = run_id if key == "run_id" else cell[key]
        if record.get(key) != expected:
            raise C7BatchBError("validated window {} mismatch".format(key))
    frame = _integer(record.get("frame_index"), "frame index")
    evidence = record.get("evidence")
    validation = record.get("validation")
    if not isinstance(evidence, Mapping) or not isinstance(validation, Mapping):
        raise C7BatchBError("validated window evidence/validation must be objects")
    if _digest(record.get("evidence_sha256"), "evidence digest") != canonical_sha256(evidence):
        raise C7BatchBError("window evidence digest mismatch")
    if _digest(record.get("validation_sha256"), "validation digest") != canonical_sha256(validation):
        raise C7BatchBError("window validation digest mismatch")

    if record.get("evidence_kind") == "BATCH_A_CORE":
        try:
            reconstructed = validate_core_evidence(evidence)
        except C7ValidationError as exc:
            raise C7BatchBError("persisted Batch A evidence is invalid") from exc
        if reconstructed != validation:
            raise C7BatchBError("persisted Batch A validation is not reproducible")
        if evidence.get("raw_baseline_evidence", {}).get("frame_index") != frame:
            raise C7BatchBError("persisted Batch A frame mismatch")
        return frame, True, bool(reconstructed["window_eligible"])

    if record.get("evidence_kind") != "VALIDATED_NO_STALE":
        raise C7BatchBError("unknown validated window evidence kind")
    facts = _derive_no_stale_facts(evidence)
    expected_validation = {
        "schema_version": NO_STALE_VALIDATION_SCHEMA,
        "status": "PASS",
        **facts,
    }
    if facts["frame_index"] != frame or facts["stale_present"] or validation != expected_validation:
        raise C7BatchBError("no-stale raw reconstruction mismatch")
    return frame, False, False


def aggregate_cell(
    *, run_id: str, cell: Mapping[str, Any], expected_frame_domain: Sequence[int],
    validated_windows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """M5: reconstruct counts from validated windows and exact frame bijection."""
    expected = tuple(_integer(frame, "expected frame") for frame in expected_frame_domain)
    if not expected or len(set(expected)) != len(expected):
        raise C7BatchBError("expected frame domain must be nonempty and unique")
    if tuple(sorted(expected)) != expected:
        raise C7BatchBError("expected frame domain must be sorted")

    parsed = []
    for record in validated_windows:
        frame, stale, eligible = _validated_window_facts(record, run_id=run_id, cell=cell)
        parsed.append((frame, stale, eligible, canonical_sha256(record)))
    frames = [row[0] for row in parsed]
    if len(set(frames)) != len(frames):
        raise C7BatchBError("duplicate window")
    if set(frames) != set(expected):
        missing = sorted(set(expected) - set(frames))
        extra = sorted(set(frames) - set(expected))
        raise C7BatchBError("window domain mismatch: missing={} extra={}".format(missing, extra))
    parsed.sort(key=lambda row: row[0])
    n_all = len(parsed)
    n_stale = sum(1 for _, stale, _, _ in parsed if stale)
    n_eligible = sum(1 for _, _, eligible, _ in parsed if eligible)
    if not 0 <= n_eligible <= n_stale <= n_all:
        raise C7BatchBError("aggregate count nesting failed")
    validity = "VALID_ZERO" if n_stale == 0 else "VALID"
    conditional_rate = (
        {"status": "N/A", "numerator": n_eligible, "denominator": 0}
        if n_stale == 0 else
        {"status": "DEFINED", "numerator": n_eligible, "denominator": n_stale}
    )
    return {
        "schema_version": CELL_AGGREGATE_SCHEMA,
        "run_id": str(run_id),
        "cell_id": str(cell["cell_id"]),
        "pair_id": str(cell["pair_id"]),
        "capacity_id": str(cell["capacity_id"]),
        "capacity_bytes": _integer(cell["capacity_bytes"], "capacity bytes", 1),
        "expected_frame_domain": list(expected),
        "observed_frame_domain": [row[0] for row in parsed],
        "cell_validity": validity,
        "invalid_reasons": [],
        "N_all": n_all,
        "N_stale": n_stale,
        "N_eligible": n_eligible,
        "nesting_attestation": True,
        "overall_rate": {
            "status": "DEFINED", "numerator": n_eligible, "denominator": n_all},
        "conditional_rate": conditional_rate,
        "input_window_evidence_digests": [
            {"frame_index": row[0], "record_sha256": row[3]} for row in parsed],
        "schema_identity": VALIDATED_WINDOW_SCHEMA,
        "producer_source_authority": BATCH_A_SEMANTICS_SCHEMA,
        "validator_source_authority": BATCH_A_VALIDATION_SCHEMA,
    }


def _qualification_from_counts(n_all: int, n_stale: int, n_eligible: int) -> dict[str, Any]:
    n_all = _integer(n_all, "N_all", 1)
    n_stale = _integer(n_stale, "N_stale")
    n_eligible = _integer(n_eligible, "N_eligible")
    if not 0 <= n_eligible <= n_stale <= n_all:
        raise C7BatchBError("qualification count nesting failed")
    count_pass = n_eligible >= T_COUNT
    denominator_pass = n_stale >= T_DENOMINATOR
    global_lhs = GLOBAL_MULTIPLIER * n_eligible
    global_rhs = n_all
    conditional_lhs = CONDITIONAL_MULTIPLIER * n_eligible
    conditional_rhs = n_stale
    global_pass = global_lhs >= global_rhs
    conditional_pass = n_stale > 0 and conditional_lhs >= conditional_rhs
    return {
        "N_all": n_all,
        "N_stale": n_stale,
        "N_eligible": n_eligible,
        "count_threshold": T_COUNT,
        "denominator_threshold": T_DENOMINATOR,
        "count_pass": count_pass,
        "denominator_pass": denominator_pass,
        "global_lhs": global_lhs,
        "global_rhs": global_rhs,
        "global_pass": global_pass,
        "conditional_lhs": conditional_lhs,
        "conditional_rhs": conditional_rhs,
        "conditional_pass": conditional_pass,
        "CELL_QUALIFIED": bool(
            count_pass and denominator_pass and global_pass and conditional_pass),
    }


def qualify_cell(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    """M5: evaluate all four frozen gates with integer arithmetic only."""
    _exact_keys(aggregate, _AGGREGATE_KEYS, "cell aggregate")
    if aggregate.get("schema_version") != CELL_AGGREGATE_SCHEMA:
        raise C7BatchBError("aggregate schema mismatch")
    if aggregate.get("cell_validity") not in {"VALID", "VALID_ZERO"}:
        raise C7BatchBError("only valid cells may be qualified")
    if aggregate.get("invalid_reasons") != [] or aggregate.get("nesting_attestation") is not True:
        raise C7BatchBError("aggregate validity attestation failed")
    gates = _qualification_from_counts(
        aggregate.get("N_all"), aggregate.get("N_stale"), aggregate.get("N_eligible"))
    return {
        "schema_version": CELL_QUALIFICATION_SCHEMA,
        "run_id": aggregate.get("run_id"),
        "cell_id": aggregate.get("cell_id"),
        "pair_id": aggregate.get("pair_id"),
        "capacity_id": aggregate.get("capacity_id"),
        "capacity_bytes": aggregate.get("capacity_bytes"),
        "aggregate_sha256": canonical_sha256(aggregate),
        "cell_validity": aggregate.get("cell_validity"),
        "cell_validation_status": "PASS",
        "qualification_complete": True,
        "frozen_batch_a_implementation_authority": (
            FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY),
        "batch_a_freeze_authority": BATCH_A_FREEZE_AUTHORITY,
        **gates,
    }


def _registered_manifest_cells(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise C7BatchBError("selection manifest schema mismatch")
    if manifest.get("authorities") != authority_bindings():
        raise C7BatchBError("selection manifest authority mismatch")
    cells = manifest.get("cells")
    if not isinstance(cells, list) or len(cells) != 21:
        raise C7BatchBError("selection requires all 21 registered cells")
    if cells != list(registered_cells()):
        raise C7BatchBError("selection manifest differs from frozen registered domain")
    return cells


def _reconstructed_qualification(
    record: Mapping[str, Any], cell: Mapping[str, Any], expected_frame_count: int,
) -> dict[str, Any]:
    _exact_keys(record, _QUALIFICATION_KEYS, "selection qualification")
    if record.get("schema_version") != CELL_QUALIFICATION_SCHEMA:
        raise C7BatchBError("qualification schema mismatch")
    if record.get("cell_id") != cell["cell_id"]:
        raise C7BatchBError("qualification cell mismatch")
    if record.get("N_all") != expected_frame_count:
        raise C7BatchBError("qualification frame count mismatch")
    if (record.get("cell_validity") not in {"VALID", "VALID_ZERO"}
            or record.get("cell_validation_status") != "PASS"
            or record.get("qualification_complete") is not True
            or record.get("frozen_batch_a_implementation_authority")
            != FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY
            or record.get("batch_a_freeze_authority") != BATCH_A_FREEZE_AUTHORITY):
        raise C7BatchBError("qualification validity/authority mismatch")
    gates = _qualification_from_counts(
        record.get("N_all"), record.get("N_stale"), record.get("N_eligible"))
    for key, expected in gates.items():
        if record.get(key) != expected:
            raise C7BatchBError("qualification {} mismatch".format(key))
    return {**record, **gates}


def _rate_compare(a: Mapping[str, Any], b: Mapping[str, Any], numerator: str) -> int:
    if numerator == "overall":
        lhs = a["N_eligible"] * b["N_all"]
        rhs = b["N_eligible"] * a["N_all"]
    else:
        lhs = a["N_eligible"] * b["N_stale"]
        rhs = b["N_eligible"] * a["N_stale"]
    return (lhs > rhs) - (lhs < rhs)


def _dominates(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    overall = _rate_compare(a, b, "overall")
    conditional = _rate_compare(a, b, "conditional")
    return overall >= 0 and conditional >= 0 and (overall > 0 or conditional > 0)


def select_qualified_cell(
    manifest: Mapping[str, Any], qualifications: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """M6: select only after exact all-21 validation and reconstruction."""
    cells = _registered_manifest_cells(manifest)
    if len(qualifications) != 21:
        raise C7BatchBError("selection requires 21 qualification records")
    by_id: dict[str, Mapping[str, Any]] = {}
    for record in qualifications:
        cell_id = record.get("cell_id")
        if cell_id in by_id:
            raise C7BatchBError("duplicate qualification cell")
        by_id[cell_id] = record
    if set(by_id) != set(REGISTERED_CELL_IDS):
        raise C7BatchBError("qualification domain differs from registered cells")

    reconstructed = []
    for cell in cells:
        domain = manifest.get("authorized_frame_domains", {}).get(cell["cell_id"])
        if not isinstance(domain, list) or not domain:
            raise C7BatchBError("selection manifest frame domain missing")
        record = _reconstructed_qualification(
            by_id[cell["cell_id"]], cell, len(domain))
        reconstructed.append((cell, record))
    qualified = [(cell, record) for cell, record in reconstructed if record["CELL_QUALIFIED"]]
    trace: dict[str, Any] = {
        "qualified_subset_reconstructed": [cell["cell_id"] for cell, _ in qualified],
        "maximum_N_eligible": None,
        "count_tied_candidates": [],
        "pareto_comparisons": [],
        "pareto_survivors": [],
        "stable_tiebreak": [],
    }
    if not qualified:
        return {
            "schema_version": SELECTION_SCHEMA,
            "run_id": manifest.get("run_id"),
            "manifest_sha256": canonical_sha256(manifest),
            "all_21_complete_attestation": True,
            "qualified_subset": [],
            "comparison_trace": trace,
            "selection_outcome": "NO_CELL_SELECTED",
            "selected_cell_id": None,
        }

    maximum = max(record["N_eligible"] for _, record in qualified)
    tied = [(cell, record) for cell, record in qualified if record["N_eligible"] == maximum]
    trace["maximum_N_eligible"] = maximum
    trace["count_tied_candidates"] = [cell["cell_id"] for cell, _ in tied]
    survivors = []
    for candidate_cell, candidate in tied:
        dominated_by = []
        for other_cell, other in tied:
            if other_cell["cell_id"] == candidate_cell["cell_id"]:
                continue
            dominates = _dominates(other, candidate)
            trace["pareto_comparisons"].append({
                "candidate": candidate_cell["cell_id"],
                "other": other_cell["cell_id"],
                "other_dominates": dominates,
                "overall_cross_product": [
                    other["N_eligible"] * candidate["N_all"],
                    candidate["N_eligible"] * other["N_all"],
                ],
                "conditional_cross_product": [
                    other["N_eligible"] * candidate["N_stale"],
                    candidate["N_eligible"] * other["N_stale"],
                ],
            })
            if dominates:
                dominated_by.append(other_cell["cell_id"])
        if not dominated_by:
            survivors.append((candidate_cell, candidate))
    trace["pareto_survivors"] = [cell["cell_id"] for cell, _ in survivors]
    survivors.sort(key=lambda item: (
        item[0]["stable_pair_order"], item[0]["stable_capacity_order"],
        item[0]["cell_id"]))
    trace["stable_tiebreak"] = [cell["cell_id"] for cell, _ in survivors]
    selected_cell = survivors[0][0]
    return {
        "schema_version": SELECTION_SCHEMA,
        "run_id": manifest.get("run_id"),
        "manifest_sha256": canonical_sha256(manifest),
        "all_21_complete_attestation": True,
        "qualified_subset": [cell["cell_id"] for cell, _ in qualified],
        "comparison_trace": trace,
        "selection_outcome": "SELECTED_CELL",
        "selected_cell_id": selected_cell["cell_id"],
    }
