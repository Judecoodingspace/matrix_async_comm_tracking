"""Passive, exact full-core tracing for Work 1 Dynamic M2.

This module is execution-validity instrumentation.  It never imports or reads
GT/XML, calls author algorithms, or returns a replacement for author state.
All supplied values are defensively canonicalized without mutation.
"""
from __future__ import annotations

import ast
import base64
import copy
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


TRACE_SCHEMA_VERSION = "work1-full-core-comparison-v1"

CHECKPOINTS = (
    "FRAME_INPUT",
    "DETECTOR_OUTPUT",
    "TRACKER_RAW_OUTPUT",
    "TRACKER_OUTPUT",
    "INITIALIZATION_STATE",
    "PRE_ID_STATE",
    "ID_STAGE_1",
    "ID_STAGE_2",
    "ID_STAGE_3",
    "POST_ID_RECOMPUTE",
    "HIGH_SCORE_INPUT",
    "HIGH_SCORE_OUTPUT",
    "LOW_SCORE_INPUT",
    "LOW_SCORE_OUTPUT",
    "NMS_INPUT",
    "NMS_OUTPUT",
    "FEEDBACK_INPUT",
    "FEEDBACK_OUTPUT",
    "NEXT_FRAME_STATE",
    "FINAL_PREDICTION",
    "PACKET_ACCOUNTING",
    "FRAME_TERMINAL",
    "OBSERVER_GUARD_INITIALIZATION_PRE",
    "OBSERVER_GUARD_INITIALIZATION_POST",
    "OBSERVER_GUARD_PRE_ID_PRE",
    "OBSERVER_GUARD_PRE_ID_POST",
    "OBSERVER_GUARD_POST_ID_PRE",
    "OBSERVER_GUARD_POST_ID_POST",
    "OBSERVER_GUARD_HIGH_OUTPUT_PRE",
    "OBSERVER_GUARD_HIGH_OUTPUT_POST",
    "OBSERVER_GUARD_TERMINAL_PRE",
    "OBSERVER_GUARD_TERMINAL_POST",
    "PACKET_ACCOUNTING_FINAL",
)

FRAME0_CHECKPOINT_PROFILE = (
    "FRAME_INPUT", "DETECTOR_OUTPUT", "TRACKER_RAW_OUTPUT", "TRACKER_OUTPUT",
    "INITIALIZATION_STATE", "OBSERVER_GUARD_INITIALIZATION_PRE",
    "OBSERVER_GUARD_INITIALIZATION_POST", "NEXT_FRAME_STATE",
    "FINAL_PREDICTION", "PACKET_ACCOUNTING", "FRAME_TERMINAL",
)

STANDARD_FRAME_CHECKPOINT_PROFILE = (
    "FRAME_INPUT", "DETECTOR_OUTPUT", "TRACKER_RAW_OUTPUT", "TRACKER_OUTPUT",
    "PRE_ID_STATE", "OBSERVER_GUARD_PRE_ID_PRE", "OBSERVER_GUARD_PRE_ID_POST",
    "ID_STAGE_1", "ID_STAGE_2", "ID_STAGE_3", "POST_ID_RECOMPUTE",
    "OBSERVER_GUARD_POST_ID_PRE", "OBSERVER_GUARD_POST_ID_POST",
    "HIGH_SCORE_INPUT", "OBSERVER_GUARD_HIGH_OUTPUT_PRE",
    "OBSERVER_GUARD_HIGH_OUTPUT_POST", "HIGH_SCORE_OUTPUT", "LOW_SCORE_INPUT",
    "LOW_SCORE_OUTPUT", "NMS_INPUT", "NMS_OUTPUT", "FEEDBACK_INPUT",
    "FEEDBACK_OUTPUT", "NEXT_FRAME_STATE", "FINAL_PREDICTION",
    "OBSERVER_GUARD_TERMINAL_PRE", "OBSERVER_GUARD_TERMINAL_POST",
    "PACKET_ACCOUNTING", "FRAME_TERMINAL",
)

FINAL_CHECKPOINT_PROFILE = ("PACKET_ACCOUNTING_FINAL",)

TRACE_RECORD_FIELDS = frozenset({
    "run_role", "pair_id", "frame_id", "view_id", "checkpoint",
    "checkpoint_sequence", "payload_type", "payload_shape", "payload_dtype",
    "canonical_digest", "optional_event_count", "source_file",
    "source_region_id", "observer_enabled", "trace_schema_version",
})

_GLOBAL_CHECKPOINTS = {"PACKET_ACCOUNTING", "FRAME_TERMINAL", "PACKET_ACCOUNTING_FINAL"}
_GUARD_PHASES = {
    "OBSERVER_GUARD_INITIALIZATION_PRE": "INITIALIZATION",
    "OBSERVER_GUARD_INITIALIZATION_POST": "INITIALIZATION",
    "OBSERVER_GUARD_PRE_ID_PRE": "PRE_ID",
    "OBSERVER_GUARD_PRE_ID_POST": "PRE_ID",
    "OBSERVER_GUARD_POST_ID_PRE": "POST_ID",
    "OBSERVER_GUARD_POST_ID_POST": "POST_ID",
    "OBSERVER_GUARD_HIGH_OUTPUT_PRE": "HIGH_OUTPUT",
    "OBSERVER_GUARD_HIGH_OUTPUT_POST": "HIGH_OUTPUT",
    "OBSERVER_GUARD_TERMINAL_PRE": "TERMINAL",
    "OBSERVER_GUARD_TERMINAL_POST": "TERMINAL",
}

_FORBIDDEN_FIELD_FRAGMENTS = (
    "xml_path", "xml_file", "xml_dir", "gt_bbox", "gt_id", "gt_label",
    "gt_identity", "ground_truth", "correctness", "candidate_truth",
)

_AUTHOR_METHOD_NAMES = {
    "inference_mot", "get_matched_ids", "get_matched_ids_lineage",
    "not_matched_supplement", "low_confidence_target_refresh_same_ID",
    "all_nms", "deliver_id_state", "deliver_supplement",
    "commit_fused_state_to_tracker",
}


class CoreComparisonError(RuntimeError):
    """A fail-closed trace, comparison, or passivity violation."""


def _float_token(value: float) -> Mapping[str, str]:
    if math.isnan(value):
        return {"special": "nan"}
    if math.isinf(value):
        return {"special": "+inf" if value > 0 else "-inf"}
    return {"hex": float(value).hex()}


def _array_values(array: np.ndarray) -> list[Any]:
    flat = array.reshape(-1)
    if array.dtype.kind in "fc":
        if array.dtype.kind == "c":
            return [{"real": _float_token(float(v.real)), "imag": _float_token(float(v.imag))} for v in flat]
        return [_float_token(float(v)) for v in flat]
    if array.dtype.kind in "iu":
        return [str(int(v)) for v in flat]
    if array.dtype.kind == "b":
        return [bool(v) for v in flat]
    if array.dtype.kind in "SU":
        return [str(v) for v in flat]
    raise CoreComparisonError(f"unsupported numpy dtype for exact trace: {array.dtype}")


def canonical_tree(value: Any, _active: set[int] | None = None) -> Any:
    """Return a deterministic, type-tagged tree without mutating ``value``."""
    active = set() if _active is None else _active
    if value is None:
        return {"type": "none"}
    if isinstance(value, (bool, np.bool_)):
        return {"type": "bool", "value": bool(value)}
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return {"type": "int", "value": str(int(value))}
    if isinstance(value, (float, np.floating)):
        return {"type": "float", "value": _float_token(float(value))}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "bytes", "base64": base64.b64encode(bytes(value)).decode("ascii")}

    # Torch is optional in the research environment.  Runtime tensors expose
    # these methods; conversion operates on a detached CPU copy.
    if all(hasattr(value, name) for name in ("detach", "cpu", "numpy")):
        tensor_array = value.detach().cpu().numpy().copy()
        return {"type": "tensor", "array": canonical_tree(tensor_array, active)}
    if isinstance(value, np.ndarray):
        array = np.ascontiguousarray(np.array(value, copy=True))
        if array.dtype.hasobject:
            raise CoreComparisonError("object-dtype arrays are forbidden")
        return {
            "type": "ndarray",
            "dtype": array.dtype.str,
            "shape": [int(v) for v in array.shape],
            "values": _array_values(array),
        }
    if isinstance(value, np.generic):
        return canonical_tree(value.item(), active)

    object_id = id(value)
    if object_id in active:
        raise CoreComparisonError("cyclic object graph is forbidden")
    active.add(object_id)
    try:
        if isinstance(value, Mapping):
            entries = []
            for key, item in value.items():
                key_tree = canonical_tree(key, active)
                item_tree = canonical_tree(item, active)
                key_bytes = _tree_bytes(key_tree)
                entries.append((key_bytes, {"key": key_tree, "value": item_tree}))
            return {"type": "mapping", "entries": [entry for _, entry in sorted(entries, key=lambda pair: pair[0])]}
        if isinstance(value, list):
            return {"type": "list", "items": [canonical_tree(item, active) for item in value]}
        if isinstance(value, tuple):
            return {"type": "tuple", "items": [canonical_tree(item, active) for item in value]}
        if isinstance(value, (set, frozenset)):
            items = [canonical_tree(item, active) for item in value]
            return {"type": "set", "items": sorted(items, key=_tree_bytes)}
    finally:
        active.remove(object_id)
    raise CoreComparisonError(f"unsupported trace payload type: {type(value).__name__}")


def _tree_bytes(tree: Any) -> bytes:
    return json.dumps(tree, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_bytes(value: Any) -> bytes:
    return _tree_bytes(canonical_tree(value))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def payload_metadata(value: Any) -> tuple[str, Any, Any]:
    if all(hasattr(value, name) for name in ("detach", "cpu", "numpy")):
        array = value.detach().cpu().numpy()
        return "tensor", [int(v) for v in array.shape], array.dtype.str
    if isinstance(value, np.ndarray):
        return "ndarray", [int(v) for v in value.shape], value.dtype.str
    return type(value).__name__, None, None


def packet_accounting_snapshot(runtime: Any) -> dict[str, Any]:
    """Copy every packet-accounting field required by the frozen scope."""
    queue_records: dict[str, list[Any]] = {}
    for channel, queue in getattr(runtime, "_queues", {}).items():
        queue_records[str(channel)] = copy.deepcopy(list(queue))
    return {
        "events": copy.deepcopy(list(getattr(runtime, "events", []))),
        "queues": queue_records,
        "packet_version": int(getattr(runtime, "_packet_version", 0)),
        "queue_sequence": int(getattr(runtime, "_queue_sequence", 0)),
        "state_version": int(getattr(runtime, "state_version", 0)),
        "last_id_packet_version": int(getattr(runtime, "_last_id_packet_version", -1)),
        "latest_h": copy.deepcopy(getattr(runtime, "_latest_h", {})),
        "applied_id_map": copy.deepcopy(getattr(runtime, "_applied_id_map", {})),
        "current_frame": int(getattr(runtime, "_current_frame", -1)),
        "current_local_ready": copy.deepcopy(getattr(runtime, "_current_local_ready", {})),
        "emitted": int(getattr(runtime, "emitted_count", 0)),
        "consumed": int(getattr(runtime, "consumed_count", 0)),
        "expired": int(getattr(runtime, "expired_count", 0)),
        "obsolete": int(getattr(runtime, "obsolete_count", 0)),
        "conflict": int(getattr(runtime, "conflict_count", 0)),
        "applied": int(getattr(runtime, "applied_count", 0)),
        "future_read_violations": int(getattr(runtime, "future_read_violations", 0)),
        "source_bypass_read_count": int(getattr(runtime, "source_bypass_read_count", 0)),
        "wire_roundtrip_digest_mismatches": int(getattr(runtime, "wire_roundtrip_digest_mismatches", 0)),
        "alias_violations": int(getattr(runtime, "alias_violations", 0)),
        "feedback_chain_mismatches": int(getattr(runtime, "feedback_chain_mismatches", 0)),
        "published_history_rewrites": int(getattr(runtime, "published_history_rewrites", 0)),
        "last_feedback_digest": copy.deepcopy(getattr(runtime, "last_feedback_digest", None)),
    }


@dataclass
class Work1CoreComparisonRecorder:
    output_path: Path
    run_role: str
    pair_id: int
    observer_enabled: bool
    records: list[dict[str, Any]] = field(default_factory=list)
    author_input_mutation_count: int = 0
    alias_violation_count: int = 0
    _sequence: int = 0
    _initialization_components: dict[int, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_environment(cls) -> "Work1CoreComparisonRecorder":
        role = os.environ["MIA_WORK1_RUN_ROLE"]
        if role not in {"A", "B", "C"}:
            raise CoreComparisonError("MIA_WORK1_RUN_ROLE must be A, B, or C")
        enabled = os.environ.get("MIA_WORK1_OBSERVER", "0") == "1"
        if enabled != (role == "C"):
            raise CoreComparisonError("observer treatment disagrees with A/B/C run role")
        return cls(Path(os.environ["MIA_WORK1_CORE_TRACE"]), role,
                   int(os.environ["MIA_WORK1_PAIR_ID"]), enabled)

    def record(self, checkpoint: str, frame_id: int, view_id: int, payload: Any,
               source_file: str, source_region_id: str, optional_event_count: int | None = None) -> None:
        if checkpoint not in CHECKPOINTS:
            raise CoreComparisonError(f"unknown checkpoint: {checkpoint}")
        before = canonical_bytes(payload)
        payload_type, payload_shape, payload_dtype = payload_metadata(payload)
        # A second traversal is an explicit synthetic/runtime passivity check.
        after = canonical_bytes(payload)
        if before != after:
            self.author_input_mutation_count += 1
            raise CoreComparisonError("trace hook changed its supplied author payload")
        self._sequence += 1
        self.records.append({
            "run_role": self.run_role,
            "pair_id": int(self.pair_id),
            "frame_id": int(frame_id),
            "view_id": int(view_id),
            "checkpoint": checkpoint,
            "checkpoint_sequence": self._sequence,
            "payload_type": payload_type,
            "payload_shape": payload_shape,
            "payload_dtype": payload_dtype,
            "canonical_digest": hashlib.sha256(before).hexdigest(),
            "optional_event_count": optional_event_count,
            "source_file": source_file,
            "source_region_id": source_region_id,
            "observer_enabled": self.observer_enabled,
            "trace_schema_version": TRACE_SCHEMA_VERSION,
        })
        if checkpoint == "INITIALIZATION_STATE":
            if frame_id != 0 or view_id not in {1, 2} or not isinstance(payload, Mapping):
                raise CoreComparisonError("invalid initialization-state checkpoint")
            required = {"bboxes", "ids", "labels", "tracker_rows"}
            if set(payload) != required or view_id in self._initialization_components:
                raise CoreComparisonError("invalid or duplicate initialization-state payload")
            self._initialization_components[view_id] = {
                "bbox_digest": canonical_digest(payload["bboxes"]),
                "id_digest": canonical_digest(payload["ids"]),
                "label_digest": canonical_digest(payload["labels"]),
                "tracker_digest": canonical_digest(payload["tracker_rows"]),
            }

    def record_pair(self, checkpoint: str, frame_id: int, view1_payload: Any,
                    view2_payload: Any, source_region_id: str) -> None:
        self.record(checkpoint, frame_id, 1, view1_payload, "demo/supplement_MIA.py", source_region_id)
        self.record(checkpoint, frame_id, 2, view2_payload, "demo/supplement_MIA.py", source_region_id)

    def finalize(self) -> None:
        validate_trace_records(
            self.records,
            expected_role=self.run_role,
            expected_pair_id=self.pair_id,
            expected_frame_ids=sorted({row["frame_id"] for row in self.records if row["frame_id"] >= 0}),
        )
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("w", encoding="utf-8") as handle:
            for record in self.records:
                handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        initialization_path = os.environ.get("MIA_WORK1_INITIALIZATION_STATE_RECORD")
        if initialization_path:
            record = self.initialization_state_record()
            path = Path(initialization_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def initialization_state_record(self) -> dict[str, Any]:
        if set(self._initialization_components) != {1, 2}:
            raise CoreComparisonError("missing initialization components for view 1 or 2")
        view1 = self._initialization_components[1]
        view2 = self._initialization_components[2]
        return {
            "run_role": self.run_role,
            "pair_id": int(self.pair_id),
            "initialization_frame": 0,
            "initial_bbox_view1_digest": view1["bbox_digest"],
            "initial_id_view1_digest": view1["id_digest"],
            "initial_label_view1_digest": view1["label_digest"],
            "initial_bbox_view2_digest": view2["bbox_digest"],
            "initial_id_view2_digest": view2["id_digest"],
            "initial_label_view2_digest": view2["label_digest"],
            "post_initialization_tracker_state_digest": canonical_digest({
                "view1": view1["tracker_digest"], "view2": view2["tracker_digest"],
            }),
        }


def load_trace(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


_COMPARE_FIELDS = (
    "pair_id", "frame_id", "view_id", "checkpoint", "checkpoint_sequence",
    "payload_type", "payload_shape", "payload_dtype", "canonical_digest",
    "optional_event_count", "source_file", "source_region_id", "trace_schema_version",
)


def _expanded_profile(profile: Sequence[str]) -> list[tuple[str, int]]:
    expanded: list[tuple[str, int]] = []
    for checkpoint in profile:
        views = (0,) if checkpoint in _GLOBAL_CHECKPOINTS else (1, 2)
        expanded.extend((checkpoint, view_id) for view_id in views)
    return expanded


def _require_integer(value: Any, label: str, minimum: int | None = None) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CoreComparisonError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise CoreComparisonError(f"{label} must be >= {minimum}")


def validate_trace_records(
    records: Sequence[Mapping[str, Any]], *, expected_role: str,
    expected_pair_id: int, expected_frame_ids: Sequence[int],
) -> dict[str, Any]:
    """Validate one run independently before any cross-run equality check."""
    if expected_role not in {"A", "B", "C"}:
        raise CoreComparisonError("expected role must be A, B, or C")
    frames = list(expected_frame_ids)
    if not frames or frames != list(range(len(frames))):
        raise CoreComparisonError("expected frame ids must be contiguous from zero and non-empty")
    expected_observer = expected_role == "C"
    for index, row in enumerate(records, start=1):
        if set(row) != TRACE_RECORD_FIELDS:
            raise CoreComparisonError(f"trace schema fields mismatch at record {index}")
        _require_integer(row["pair_id"], "pair_id")
        _require_integer(row["frame_id"], "frame_id")
        _require_integer(row["view_id"], "view_id")
        _require_integer(row["checkpoint_sequence"], "checkpoint_sequence", 1)
        if row["run_role"] != expected_role or row["observer_enabled"] is not expected_observer:
            raise CoreComparisonError(f"role/observer mismatch at record {index}")
        if row["pair_id"] != expected_pair_id:
            raise CoreComparisonError(f"pair mismatch at record {index}")
        if row["checkpoint_sequence"] != index:
            raise CoreComparisonError(f"non-contiguous checkpoint sequence at record {index}")
        if row["checkpoint"] not in CHECKPOINTS or row["trace_schema_version"] != TRACE_SCHEMA_VERSION:
            raise CoreComparisonError(f"unknown checkpoint/schema version at record {index}")
        if row["source_file"] != "demo/supplement_MIA.py" or not isinstance(row["source_region_id"], str):
            raise CoreComparisonError(f"invalid source metadata at record {index}")
        if not isinstance(row["payload_type"], str):
            raise CoreComparisonError(f"invalid payload type at record {index}")
        if row["payload_shape"] is not None and (
            not isinstance(row["payload_shape"], list)
            or any(isinstance(value, bool) or not isinstance(value, int) for value in row["payload_shape"])
        ):
            raise CoreComparisonError(f"invalid payload shape at record {index}")
        if row["payload_dtype"] is not None and not isinstance(row["payload_dtype"], str):
            raise CoreComparisonError(f"invalid payload dtype at record {index}")
        if not isinstance(row["canonical_digest"], str) or re.fullmatch(r"[0-9a-f]{64}", row["canonical_digest"]) is None:
            raise CoreComparisonError(f"invalid canonical digest at record {index}")
        if row["optional_event_count"] is not None:
            _require_integer(row["optional_event_count"], "optional_event_count", 0)

    expected_layout: list[tuple[int, str, int]] = []
    for frame_id in frames:
        profile = FRAME0_CHECKPOINT_PROFILE if frame_id == 0 else STANDARD_FRAME_CHECKPOINT_PROFILE
        expected_layout.extend((frame_id, checkpoint, view_id) for checkpoint, view_id in _expanded_profile(profile))
    expected_layout.extend((-1, checkpoint, view_id) for checkpoint, view_id in _expanded_profile(FINAL_CHECKPOINT_PROFILE))
    observed_layout = [(row["frame_id"], row["checkpoint"], row["view_id"]) for row in records]
    if observed_layout != expected_layout:
        mismatch = next((index for index, pair in enumerate(zip(observed_layout, expected_layout)) if pair[0] != pair[1]), min(len(observed_layout), len(expected_layout)))
        raise CoreComparisonError(
            f"trace checkpoint profile mismatch at position {mismatch + 1}: "
            f"observed={observed_layout[mismatch:mismatch + 1]} expected={expected_layout[mismatch:mismatch + 1]}"
        )
    return {
        "status": "PASS", "run_role": expected_role, "pair_id": expected_pair_id,
        "frame_count": len(frames), "record_count": len(records),
        "schema": "PASS", "checkpoint_profiles": "PASS", "full_frame_coverage": "PASS",
    }


def compare_trace_records(a: Sequence[Mapping[str, Any]], b: Sequence[Mapping[str, Any]],
                          c: Sequence[Mapping[str, Any]], *, expected_pair_id: int,
                          expected_frame_ids: Sequence[int]) -> dict[str, Any]:
    validation = {
        role: validate_trace_records(records, expected_role=role, expected_pair_id=expected_pair_id,
                                     expected_frame_ids=expected_frame_ids)
        for role, records in zip("ABC", (a, b, c))
    }
    lengths = {"A": len(a), "B": len(b), "C": len(c)}
    diff_count = 0
    bc_diff_count = 0
    first: dict[str, Any] | None = None
    bc_non_guard_mismatch_keys: set[tuple[int, int, str, int]] = set()
    bc_guard_phase_keys: set[tuple[int, int, str]] = set()
    maximum = max(lengths.values(), default=0)
    for index in range(maximum):
        triplet = {"A": a[index] if index < len(a) else None,
                   "B": b[index] if index < len(b) else None,
                   "C": c[index] if index < len(c) else None}
        mismatch_fields = []
        for field_name in _COMPARE_FIELDS:
            values = [None if triplet[role] is None else triplet[role].get(field_name) for role in "ABC"]
            if not (values[0] == values[1] == values[2]):
                mismatch_fields.append(field_name)
        if mismatch_fields:
            diff_count += 1
            if triplet["B"] is None or triplet["C"] is None or any(
                triplet["B"].get(field_name) != triplet["C"].get(field_name)
                for field_name in _COMPARE_FIELDS
            ):
                bc_diff_count += 1
                exemplar = triplet["B"] or triplet["C"] or {}
                checkpoint = exemplar.get("checkpoint")
                if checkpoint in _GUARD_PHASES:
                    bc_guard_phase_keys.add((exemplar.get("frame_id"), exemplar.get("view_id"), _GUARD_PHASES[checkpoint]))
                else:
                    bc_non_guard_mismatch_keys.add((exemplar.get("frame_id"), exemplar.get("view_id"), checkpoint, index))
            if first is None:
                exemplar = next((record for record in triplet.values() if record is not None), {})
                first = {
                    "record_index": index,
                    "first_mismatch_pair": exemplar.get("pair_id"),
                    "first_mismatch_frame": exemplar.get("frame_id"),
                    "first_mismatch_view": exemplar.get("view_id"),
                    "first_mismatch_checkpoint": exemplar.get("checkpoint"),
                    "mismatch_fields": mismatch_fields,
                    "A_digest": None if triplet["A"] is None else triplet["A"].get("canonical_digest"),
                    "B_digest": None if triplet["B"] is None else triplet["B"].get("canonical_digest"),
                    "C_digest": None if triplet["C"] is None else triplet["C"].get("canonical_digest"),
                    "structural_metadata": {role: None if record is None else {
                        key: record.get(key) for key in ("payload_type", "payload_shape", "payload_dtype")
                    } for role, record in triplet.items()},
                }
    guard_changes = 0
    c_by_checkpoint = {(row["frame_id"], row["view_id"], row["checkpoint"]): row for row in c}
    guard_pairs = (
        ("OBSERVER_GUARD_INITIALIZATION_PRE", "OBSERVER_GUARD_INITIALIZATION_POST"),
        ("OBSERVER_GUARD_PRE_ID_PRE", "OBSERVER_GUARD_PRE_ID_POST"),
        ("OBSERVER_GUARD_POST_ID_PRE", "OBSERVER_GUARD_POST_ID_POST"),
        ("OBSERVER_GUARD_HIGH_OUTPUT_PRE", "OBSERVER_GUARD_HIGH_OUTPUT_POST"),
        ("OBSERVER_GUARD_TERMINAL_PRE", "OBSERVER_GUARD_TERMINAL_POST"),
    )
    for (frame_id, view_id, checkpoint), row in c_by_checkpoint.items():
        for before_name, after_name in guard_pairs:
            if checkpoint == before_name:
                after_row = c_by_checkpoint.get((frame_id, view_id, after_name))
                if after_row is None or row["canonical_digest"] != after_row["canonical_digest"]:
                    guard_changes += 1
                    bc_guard_phase_keys.add((frame_id, view_id, _GUARD_PHASES[before_name]))
    return {
        "trace_schema_version": TRACE_SCHEMA_VERSION,
        "record_counts": lengths,
        "CORE_OUTPUT_DIFF": diff_count,
        "B_VS_C_CORE_DIFF_COUNT": bc_diff_count,
        "OBSERVER_GUARD_CHANGE_COUNT": guard_changes,
        "TRACKER_MUTATION_GATE_PASS": bc_diff_count == 0 and guard_changes == 0,
        "observer_mutation_boundary_semantics": "TWO_INDEPENDENT_ZERO_GATES; NONZERO_VALUES_ARE_NOT_SUMMED_AS_EVENTS",
        "first_mismatch": first,
        "trace_validation": validation,
        "exact_canonical_equality": diff_count == 0,
    }


def compare_trace_files(a: Path, b: Path, c: Path, output: Path, *, expected_pair_id: int,
                        expected_frame_ids: Sequence[int]) -> dict[str, Any]:
    result = compare_trace_records(load_trace(a), load_trace(b), load_trace(c),
                                   expected_pair_id=expected_pair_id,
                                   expected_frame_ids=expected_frame_ids)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def compare_repeat_records(first: Sequence[Mapping[str, Any]], second: Sequence[Mapping[str, Any]], *,
                           expected_role: str, expected_pair_id: int,
                           expected_frame_ids: Sequence[int]) -> dict[str, Any]:
    validations = [
        validate_trace_records(records, expected_role=expected_role, expected_pair_id=expected_pair_id,
                               expected_frame_ids=expected_frame_ids)
        for records in (first, second)
    ]
    maximum = max(len(first), len(second))
    mismatch_count = 0
    first_mismatch = None
    fields = ("run_role", "observer_enabled", *_COMPARE_FIELDS)
    for index in range(maximum):
        left = first[index] if index < len(first) else None
        right = second[index] if index < len(second) else None
        mismatch_fields = [field for field in fields if (None if left is None else left.get(field)) != (None if right is None else right.get(field))]
        if mismatch_fields:
            mismatch_count += 1
            if first_mismatch is None:
                first_mismatch = {"record_index": index, "mismatch_fields": mismatch_fields}
    return {
        "status": "PASS" if mismatch_count == 0 else "FAIL",
        "EXACT_REPEAT_DIFF": mismatch_count,
        "first_mismatch": first_mismatch,
        "trace_validation": validations,
    }


def compare_artifact_pairs(parent_paths: Sequence[Path], traced_paths: Sequence[Path]) -> dict[str, Any]:
    if not parent_paths or len(parent_paths) != len(traced_paths):
        raise CoreComparisonError("parent/A-traced artifact lists must be non-empty and equal length")
    records = []
    for parent, traced in zip(parent_paths, traced_paths):
        parent_digest = hashlib.sha256(parent.read_bytes()).hexdigest()
        traced_digest = hashlib.sha256(traced.read_bytes()).hexdigest()
        records.append({"parent": str(parent), "a_traced": str(traced),
                        "parent_sha256": parent_digest, "a_traced_sha256": traced_digest,
                        "equal": parent_digest == traced_digest})
    diff = sum(not row["equal"] for row in records)
    return {"status": "PASS" if diff == 0 else "FAIL", "PARENT_VS_A_TRACED_OUTPUT_DIFF": diff,
            "comparison": "EXACT_FILE_BYTES_SHA256", "records": records}


def _split_env_command(command: str) -> tuple[dict[str, str], list[str]]:
    tokens = shlex.split(command)
    if not tokens or tokens[0] != "env":
        raise CoreComparisonError("launch command must begin with env")
    environment: dict[str, str] = {}
    index = 1
    while index < len(tokens) and "=" in tokens[index] and not tokens[index].startswith("="):
        name, value = tokens[index].split("=", 1)
        if not name or name in environment:
            raise CoreComparisonError("invalid or duplicate launch environment key")
        environment[name] = value
        index += 1
    return environment, tokens[index:]


def audit_launch_command_diff(command_templates: Mapping[str, str]) -> dict[str, Any]:
    required = {"A_traced", "B_derivative_off", "B_repeat", "C_derivative_on"}
    if set(command_templates) != required:
        raise CoreComparisonError(f"launch commands must be exactly {sorted(required)}")
    parsed = {name: _split_env_command(command) for name, command in command_templates.items()}
    allowed = {
        ("A_traced", "B_derivative_off"): {"MIA_SOURCE_ROOT", "MIA_RUN_INPUT_ROOT", "MIA_OUTPUT_ROOT", "MIA_WORK1_RUN_ROLE", "MIA_WORK1_CORE_TRACE", "MIA_WORK1_INITIALIZATION_STATE_RECORD"},
        ("B_derivative_off", "B_repeat"): {"MIA_RUN_INPUT_ROOT", "MIA_OUTPUT_ROOT", "MIA_WORK1_CORE_TRACE", "MIA_WORK1_INITIALIZATION_STATE_RECORD"},
        ("B_derivative_off", "C_derivative_on"): {"MIA_RUN_INPUT_ROOT", "MIA_OUTPUT_ROOT", "MIA_WORK1_RUN_ROLE", "MIA_WORK1_CORE_TRACE", "MIA_WORK1_INITIALIZATION_STATE_RECORD", "MIA_WORK1_OBSERVER", "MIA_WORK1_OUTPUT_DIR"},
    }
    audits = []
    for pair, permitted in allowed.items():
        left_env, left_argv = parsed[pair[0]]
        right_env, right_argv = parsed[pair[1]]
        keys = set(left_env) | set(right_env)
        differences = {key for key in keys if left_env.get(key) != right_env.get(key)}
        unauthorized = differences - permitted
        unused_authorizations = permitted - differences
        argv_equal = left_argv == right_argv
        if unauthorized or unused_authorizations or not argv_equal:
            raise CoreComparisonError(
                f"launch diff violation {pair}: unauthorized={sorted(unauthorized)} "
                f"unused={sorted(unused_authorizations)} argv_equal={argv_equal}"
            )
        audits.append({"left": pair[0], "right": pair[1], "differences": sorted(differences),
                       "argv_equal": True, "status": "PASS"})
    for name, (environment, _) in parsed.items():
        if environment.get("MIA_CASCADE_EDGE_CUT") != "0" or environment.get("MIA_CASCADE_SHADOW") != "0":
            raise CoreComparisonError(f"forbidden cascade environment in {name}")
        if environment.get("MIA_WORK1_OBSERVER") != ("1" if name == "C_derivative_on" else "0"):
            raise CoreComparisonError(f"observer treatment mismatch in {name}")
    return {"status": "PASS", "comparison": "EXACT_NORMALIZED_ENV_AND_ARGV", "audits": audits}


def audit_source(source_paths: Iterable[Path], protected_hashes: Mapping[Path, str] | None = None) -> dict[str, Any]:
    violations: list[str] = []
    recorder_hashes = set()
    for path in source_paths:
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if path.name not in {"mdmt_mia_work1_core_comparison.py", "work1_core_comparison.py"}:
            for fragment in _FORBIDDEN_FIELD_FRAGMENTS:
                if fragment in lowered:
                    violations.append(f"forbidden oracle fragment {fragment}: {path}")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                value = getattr(node, "value", None)
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr in {"record", "record_pair"}:
                    violations.append(f"trace-hook return assigned: {path}:{node.lineno}")
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                if path.name.endswith("core_comparison.py") and name in _AUTHOR_METHOD_NAMES:
                    violations.append(f"forbidden author-method call {name}: {path}:{node.lineno}")
                if name in {"sort", "resize", "fill", "put", "itemset", "__setitem__"}:
                    violations.append(f"forbidden inplace mutation call {name}: {path}:{node.lineno}")
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [alias.name for alias in node.names]
                if any("xml" in name.lower() or "ground_truth" in name.lower() for name in names):
                    violations.append(f"forbidden GT/XML import: {path}:{node.lineno}")
        if path.name == "work1_core_comparison.py" or path.name == "mdmt_mia_work1_core_comparison.py":
            recorder_hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
    protected_modified = False
    for path, expected in (protected_hashes or {}).items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            protected_modified = True
            violations.append(f"protected source modified: {path}")
    return {
        "status": "PASS" if not violations else "FAIL",
        "violations": violations,
        "hook_return_assigned": any("return assigned" in item for item in violations),
        "forbidden_GT_access_count": sum("oracle" in item or "GT/XML" in item for item in violations),
        "protected_source_modified": protected_modified,
        "recorder_source_divergence": max(len(recorder_hashes) - 1, 0),
        "forbidden_inplace_mutation_count": sum("inplace mutation" in item for item in violations),
    }
