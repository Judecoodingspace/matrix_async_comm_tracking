"""Fail-closed governance gates for the Work 1 author XML initialization.

This module is validity infrastructure, not Work 1 mechanism logic.  It never
opens XML/GT data and never creates an expected hash baseline.  Future runtime
instrumentation may pass hashes, digests, counters, and ordering metadata to
these validators; raw initialization values are not retained.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


AUTHOR_ENTRYPOINT_SHA256 = "4c8674425462dc8e14dc1f53eaaa62a83d93879e45b4cb46a05b38ea78008616"
XML_READER_SOURCE_SHA256 = "c87dfcf6d6a785e0042b4bf348fa87733b61de78e92d6c32c60c8c1cc31d3b93"
INITIALIZATION_CODE_SHA256 = "53773a70cf69e8ae434c04ecaa013818968d1b20549116477a85d81e2113d395"
INITIALIZATION_FRAME = 0

G_XML1_FAIL = "G_XML1_INITIALIZATION_PROVENANCE_FAIL"
G_XML2_FAIL = "G_XML2_ABC_INITIALIZATION_MISMATCH"
G_XML3_FAIL = "G_XML3_WORK1_ORACLE_FIREWALL_FAIL"
G_XML4_FAIL = "G_XML4_INITIALIZATION_BOUNDARY_FAIL"
G_XML5_FAIL = "G_XML5_CLAIM_BOUNDARY_FAIL"

PROVENANCE_FIELDS = (
    "author_entrypoint_sha256",
    "xml_reader_source_sha256",
    "initialization_code_sha256",
    "xml_view1_sha256",
    "xml_view2_sha256",
    "initialization_frame",
)

ABC_EQUALITY_FIELDS = (
    "xml_view1_sha256",
    "xml_view2_sha256",
    "initialization_code_sha256",
    "initialization_frame",
    "initial_bbox_view1_digest",
    "initial_id_view1_digest",
    "initial_label_view1_digest",
    "initial_bbox_view2_digest",
    "initial_id_view2_digest",
    "initial_label_view2_digest",
    "post_initialization_tracker_state_digest",
)

RUNTIME_ORACLE_COUNTERS = (
    "xml_open_count_by_work1",
    "gt_file_open_count_by_work1",
    "gt_field_access_count_by_work1",
    "gt_serialized_field_count",
)

INITIALIZATION_STATE_FIELDS = (
    "initialization_frame",
    "initial_bbox_view1_digest",
    "initial_id_view1_digest",
    "initial_label_view1_digest",
    "initial_bbox_view2_digest",
    "initial_id_view2_digest",
    "initial_label_view2_digest",
    "post_initialization_tracker_state_digest",
)

_FORBIDDEN_IMPORT_PARTS = (
    "xml.etree",
    "lxml",
    "ground_truth",
    "mda_gt",
    "evaluation.mdmt",
)

_FORBIDDEN_INTERFACE_PARTS = (
    "xml_path",
    "xml_file",
    "xml_dir",
    "gt_path",
    "gt_file",
    "gt_bbox",
    "gt_identity",
    "gt_id",
    "gt_label",
    "gt_visibility",
    "ground_truth",
    "candidate_truth",
    "association_truth",
    "correctness",
    "mda_gt",
)

_FORBIDDEN_OUTPUT_FIELDS = {
    "gt_correctness",
    "candidate_truth",
    "candidate_correctness",
    "association_truth",
    "association_label",
    "true_association",
    "false_association",
    "false_writein",
    "safe_writein",
    "mda",
    "idf1",
    "mota",
    "idsw",
    "deployment_ready",
    "gt_free_runtime",
    "tracking_performance",
}

_FORBIDDEN_POSITIVE_CLAIMS = (
    "fully gt-free tracker",
    "gt-free runtime",
    "xml-free mia",
    "gt-free initialization",
    "autonomous tracker",
    "deployment-ready tracking",
    "gt-free deployment",
)


class GovernanceGateError(RuntimeError):
    """A machine-checkable governance gate failed closed."""

    def __init__(self, label: str, detail: str):
        super().__init__(f"{label}: {detail}")
        self.label = label
        self.detail = detail


@dataclass
class PassiveAuditSequence:
    """Monotonic metadata sequence advanced only by real hook events."""

    value: int = 0
    events: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = []

    def record(self, event: str) -> int:
        if event not in {
            "AUTHOR_LAST_GT_INITIALIZATION_READ",
            "AUTHOR_GT_INITIALIZATION_COMPLETE",
            "FIRST_WORK1_E_PRE_RECORD",
        }:
            raise GovernanceGateError(G_XML4_FAIL, f"unknown audit event: {event}")
        self.value += 1
        assert self.events is not None
        self.events.append({"event": event, "sequence_number": self.value})
        return self.value


@dataclass
class Work1AccessAudit:
    """Actual calls observed at frozen Work 1-owned I/O/schema interfaces.

    This deliberately does not claim to intercept arbitrary Python reflection.
    Static source auditing forbids unregistered scientific file-read interfaces;
    this object records every call crossing the registered runtime boundary.
    """

    counters: dict[str, int] | None = None
    observations: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.counters is None:
            self.counters = {field: 0 for field in RUNTIME_ORACLE_COUNTERS}
        if self.observations is None:
            self.observations = []

    def observe_file_access(self, path: str | Path, *, owner: str, purpose: str) -> None:
        resolved = str(path).lower()
        assert self.counters is not None and self.observations is not None
        forbidden_scientific = owner == "WORK1_SCIENTIFIC" and purpose != "PROVENANCE_HASH_ONLY"
        if forbidden_scientific and resolved.endswith(".xml"):
            self.counters["xml_open_count_by_work1"] += 1
        if forbidden_scientific and any(part in resolved for part in ("/gt/", "mda_gt", "ground_truth")):
            self.counters["gt_file_open_count_by_work1"] += 1
        self.observations.append({"kind": "FILE_ACCESS", "owner": owner, "purpose": purpose,
                                  "forbidden": forbidden_scientific and (resolved.endswith(".xml") or "/gt/" in resolved or "mda_gt" in resolved)})

    def observe_runtime_interfaces(self, names: Iterable[str]) -> None:
        assert self.counters is not None and self.observations is not None
        materialized = tuple(names)
        count = sum(any(part in str(name).lower() for part in _FORBIDDEN_INTERFACE_PARTS) for name in materialized)
        self.counters["gt_field_access_count_by_work1"] += count
        self.observations.append({"kind": "RUNTIME_INTERFACE", "field_count": len(materialized), "forbidden_count": count})

    def observe_serialized_payload(self, payload: Any) -> None:
        assert self.counters is not None and self.observations is not None
        count = 0

        def visit(value: Any) -> None:
            nonlocal count
            if isinstance(value, Mapping):
                for key, item in value.items():
                    if any(part in str(key).lower() for part in _FORBIDDEN_INTERFACE_PARTS):
                        count += 1
                    visit(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    visit(item)

        visit(payload)
        self.counters["gt_serialized_field_count"] += count
        self.observations.append({"kind": "SERIALIZATION", "forbidden_count": count})

    def as_dict(self) -> dict[str, Any]:
        assert self.counters is not None and self.observations is not None
        return {
            **self.counters,
            "counter_source": "ACTUAL_WORK1_ACCESS_OBSERVATION",
            "observability_boundary": [
                "registered Work1-owned file/path interfaces",
                "observer constructor/runtime interface names",
                "token/ledger serialization keys",
                "static rejection of unregistered forbidden interfaces",
            ],
            "observation_count": len(self.observations),
            "observations": list(self.observations),
            "arbitrary_hidden_python_reflection_covered": False,
        }


def _require_fields(payload: Mapping[str, Any], fields: Iterable[str], label: str) -> None:
    missing = [field for field in fields if field not in payload]
    if missing:
        raise GovernanceGateError(label, f"missing fields: {missing}")


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _array_digest(*values: Any) -> str:
    digest = hashlib.sha256()
    for value in values:
        array = np.ascontiguousarray(np.asarray(value))
        digest.update(array.dtype.str.encode("ascii"))
        digest.update(str(tuple(array.shape)).encode("ascii"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


@dataclass(frozen=True)
class AuthorInitializationMarker:
    frame_id: int
    author_initialization_complete: bool
    initialization_state_digest: str
    marker_sequence_number: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "author_initialization_complete": self.author_initialization_complete,
            "initialization_state_digest": self.initialization_state_digest,
            "marker_sequence_number": self.marker_sequence_number,
        }


def make_author_initialization_marker(
    frame_id: int,
    state_values: Sequence[Any],
    marker_sequence_number: int = 1,
) -> AuthorInitializationMarker:
    """Digest author state and return passive boundary metadata only."""
    if int(frame_id) != INITIALIZATION_FRAME:
        raise GovernanceGateError(G_XML4_FAIL, "marker is not on frozen initialization frame")
    if int(marker_sequence_number) <= 0:
        raise GovernanceGateError(G_XML4_FAIL, "marker sequence must be positive")
    return AuthorInitializationMarker(
        frame_id=int(frame_id),
        author_initialization_complete=True,
        initialization_state_digest=_array_digest(*state_values),
        marker_sequence_number=int(marker_sequence_number),
    )


def validate_initialization_provenance(
    expected: Mapping[str, Any], observed: Mapping[str, Any]
) -> dict[str, Any]:
    """G-XML1: compare against an already-frozen baseline; never create one."""
    _require_fields(expected, PROVENANCE_FIELDS, G_XML1_FAIL)
    _require_fields(observed, PROVENANCE_FIELDS, G_XML1_FAIL)
    frozen = {
        "author_entrypoint_sha256": AUTHOR_ENTRYPOINT_SHA256,
        "xml_reader_source_sha256": XML_READER_SOURCE_SHA256,
        "initialization_code_sha256": INITIALIZATION_CODE_SHA256,
        "initialization_frame": INITIALIZATION_FRAME,
    }
    for field, value in frozen.items():
        if expected[field] != value:
            raise GovernanceGateError(G_XML1_FAIL, f"expected baseline is not frozen authority: {field}")
    for field in PROVENANCE_FIELDS:
        if field.endswith("sha256") and not _is_sha256(expected[field]):
            raise GovernanceGateError(G_XML1_FAIL, f"invalid expected SHA-256: {field}")
        if expected[field] != observed[field]:
            raise GovernanceGateError(G_XML1_FAIL, f"provenance drift: {field}")
    return {"gate": "G-XML1", "status": "PASS", "checked_fields": list(PROVENANCE_FIELDS)}


def validate_abc_initialization_equality(payload: Mapping[str, Any]) -> dict[str, Any]:
    """G-XML2: require exact A/B/C initialization equality."""
    conditions = payload.get("conditions")
    if not isinstance(conditions, Mapping) or set(conditions) != {"A", "B", "C"}:
        raise GovernanceGateError(G_XML2_FAIL, "conditions must be exactly A, B, C")
    reference = conditions["A"]
    if not isinstance(reference, Mapping):
        raise GovernanceGateError(G_XML2_FAIL, "A record is not an object")
    _require_fields(reference, ABC_EQUALITY_FIELDS, G_XML2_FAIL)
    for condition in ("B", "C"):
        record = conditions[condition]
        if not isinstance(record, Mapping):
            raise GovernanceGateError(G_XML2_FAIL, f"{condition} record is not an object")
        _require_fields(record, ABC_EQUALITY_FIELDS, G_XML2_FAIL)
        for field in ABC_EQUALITY_FIELDS:
            if record[field] != reference[field]:
                raise GovernanceGateError(G_XML2_FAIL, f"{condition} differs from A: {field}")
    return {"gate": "G-XML2", "status": "PASS", "equality": "A == B == C"}


def build_abc_initialization_equality(
    condition_records: Mapping[str, Mapping[str, Any]],
    xml_manifest: Mapping[str, Any],
    pair_id: int,
) -> dict[str, Any]:
    """Build G-XML2 evidence from passive state digests and frozen XML identity."""
    if set(condition_records) != {"A", "B", "C"}:
        raise GovernanceGateError(G_XML2_FAIL, "condition records must be exactly A, B, C")
    records = xml_manifest.get("records")
    if not isinstance(records, list):
        raise GovernanceGateError(G_XML2_FAIL, "XML manifest records are unavailable")
    matches = [record for record in records if record.get("pair_id") == int(pair_id)]
    if len(matches) != 1:
        raise GovernanceGateError(G_XML2_FAIL, "pair does not resolve uniquely in frozen XML manifest")
    provenance = matches[0]
    conditions: dict[str, dict[str, Any]] = {}
    for role in ("A", "B", "C"):
        record = condition_records[role]
        _require_fields(record, ("run_role", "pair_id", *INITIALIZATION_STATE_FIELDS), G_XML2_FAIL)
        if record["run_role"] != role or int(record["pair_id"]) != int(pair_id):
            raise GovernanceGateError(G_XML2_FAIL, f"condition identity mismatch for {role}")
        for field in INITIALIZATION_STATE_FIELDS[1:]:
            if not _is_sha256(record[field]):
                raise GovernanceGateError(G_XML2_FAIL, f"invalid state digest for {role}: {field}")
        conditions[role] = {
            "xml_view1_sha256": provenance["view1_xml_sha256"],
            "xml_view2_sha256": provenance["view2_xml_sha256"],
            "initialization_code_sha256": INITIALIZATION_CODE_SHA256,
            **{field: record[field] for field in INITIALIZATION_STATE_FIELDS},
        }
    payload = {"conditions": conditions}
    validate_abc_initialization_equality(payload)
    return payload


def validate_runtime_oracle_firewall(payload: Mapping[str, Any]) -> dict[str, Any]:
    """G-XML3 dynamic layer: every Work 1 oracle counter must be zero."""
    _require_fields(payload, RUNTIME_ORACLE_COUNTERS, G_XML3_FAIL)
    _require_fields(payload, ("counter_source", "observability_boundary", "observation_count", "observations",
                              "arbitrary_hidden_python_reflection_covered"), G_XML3_FAIL)
    if payload["counter_source"] != "ACTUAL_WORK1_ACCESS_OBSERVATION":
        raise GovernanceGateError(G_XML3_FAIL, "runtime counters are not actual-access observations")
    if not isinstance(payload["observability_boundary"], list) or not payload["observability_boundary"]:
        raise GovernanceGateError(G_XML3_FAIL, "observability boundary is absent")
    if not isinstance(payload["observations"], list) or payload["observation_count"] != len(payload["observations"]):
        raise GovernanceGateError(G_XML3_FAIL, "runtime access observation ledger is inconsistent")
    nonzero = {field: payload[field] for field in RUNTIME_ORACLE_COUNTERS if payload[field] != 0}
    if nonzero:
        raise GovernanceGateError(G_XML3_FAIL, f"nonzero runtime oracle counters: {nonzero}")
    return {"gate": "G-XML3-DYNAMIC", "status": "PASS", "counters": dict(payload)}


def validate_initialization_boundary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """G-XML4: enforce GT-read < marker < first Work 1 E_pre record."""
    _require_fields(
        payload,
        ("last_author_gt_read_sequence_number", "marker", "first_work1_e_pre_sequence_number", "event_log"),
        G_XML4_FAIL,
    )
    marker = payload["marker"]
    if not isinstance(marker, Mapping):
        raise GovernanceGateError(G_XML4_FAIL, "marker is not an object")
    _require_fields(
        marker,
        ("frame_id", "author_initialization_complete", "initialization_state_digest", "marker_sequence_number"),
        G_XML4_FAIL,
    )
    if marker["frame_id"] != INITIALIZATION_FRAME or marker["author_initialization_complete"] is not True:
        raise GovernanceGateError(G_XML4_FAIL, "invalid initialization marker")
    if not _is_sha256(marker["initialization_state_digest"]):
        raise GovernanceGateError(G_XML4_FAIL, "invalid initialization-state digest")
    last_gt = int(payload["last_author_gt_read_sequence_number"])
    marker_sequence = int(marker["marker_sequence_number"])
    first_work1 = int(payload["first_work1_e_pre_sequence_number"])
    if not last_gt < marker_sequence < first_work1:
        raise GovernanceGateError(G_XML4_FAIL, "required event ordering is not satisfied")
    event_log = payload["event_log"]
    expected_events = [
        ("AUTHOR_LAST_GT_INITIALIZATION_READ", last_gt),
        ("AUTHOR_GT_INITIALIZATION_COMPLETE", marker_sequence),
        ("FIRST_WORK1_E_PRE_RECORD", first_work1),
    ]
    if not isinstance(event_log, list) or [
        (item.get("event"), item.get("sequence_number")) for item in event_log if isinstance(item, Mapping)
    ] != expected_events:
        raise GovernanceGateError(G_XML4_FAIL, "event log is absent, incomplete, or not real-event ordered")
    return {"gate": "G-XML4", "status": "PASS", "ordering": "last_GT_read < marker < first_E_pre"}


def audit_static_oracle_firewall(
    source_paths: Sequence[Path], declared_schema_fields: Iterable[str] = ()
) -> dict[str, Any]:
    """G-XML3 static layer over imports, interfaces, env keys, and schemas."""
    violations: list[str] = []
    for path in source_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name.lower() for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [(node.module or "").lower()]
            else:
                modules = []
            for module in modules:
                if any(part in module for part in _FORBIDDEN_IMPORT_PARTS):
                    violations.append(f"{path}:forbidden import:{module}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                arguments = [argument.arg.lower() for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)]
                for argument in arguments:
                    if any(part in argument for part in _FORBIDDEN_INTERFACE_PARTS):
                        violations.append(f"{path}:{node.name}:forbidden argument:{argument}")
                if node.args.kwarg is not None:
                    violations.append(f"{path}:{node.name}:unbounded kwargs")
            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        lowered = key.value.lower()
                        if key.value in RUNTIME_ORACLE_COUNTERS:
                            # These four zero-valued execution-validity counters are
                            # the frozen G-XML3 evidence schema, not serialized oracle data.
                            continue
                        if any(part in lowered for part in _FORBIDDEN_INTERFACE_PARTS):
                            violations.append(f"{path}:forbidden serialized key:{key.value}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args:
                if node.func.attr == "get" and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    environment_key = node.args[0].value.lower()
                    if any(part in environment_key for part in _FORBIDDEN_INTERFACE_PARTS):
                        violations.append(f"{path}:forbidden environment key:{node.args[0].value}")
    for field in declared_schema_fields:
        lowered = str(field).lower()
        if any(part in lowered for part in _FORBIDDEN_INTERFACE_PARTS):
            violations.append(f"schema:forbidden field:{field}")
    if violations:
        raise GovernanceGateError(G_XML3_FAIL, "; ".join(violations))
    return {"gate": "G-XML3-STATIC", "status": "PASS", "source_count": len(source_paths)}


def validate_claim_output(payload: Any) -> dict[str, Any]:
    """G-XML5: reject correctness/performance fields and forbidden claims."""
    violations: list[str] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                lowered = str(key).lower()
                if lowered in _FORBIDDEN_OUTPUT_FIELDS:
                    violations.append(f"{path}.{key}: forbidden field")
                if lowered == "gt_safety" and item not in ("UNGRADED", "GT_SAFETY_UNGRADED"):
                    violations.append(f"{path}.{key}: GT safety must remain ungraded")
                visit(item, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")
        elif isinstance(value, str):
            lowered = value.lower()
            if value != "GT_SAFETY_UNGRADED" and any(claim in lowered for claim in _FORBIDDEN_POSITIVE_CLAIMS):
                violations.append(f"{path}: forbidden claim")

    visit(payload, "$")
    if violations:
        raise GovernanceGateError(G_XML5_FAIL, "; ".join(violations))
    return {"gate": "G-XML5", "status": "PASS"}


def write_gate_result(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
