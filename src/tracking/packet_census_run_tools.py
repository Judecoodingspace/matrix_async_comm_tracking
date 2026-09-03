"""Pure, fail-closed tooling for the frozen Z0 passive packet census.

This module intentionally does not import an XML parser, launch author code,
or mutate the packet runtime.  It consumes only sidecar files already written
by the frozen runtime and produces descriptive, software-level aggregates.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import numpy as np

from tracking.mdmt_mia_async_deadline_runtime import validate_packet_census_records


SCHEMA_VERSION = "packet-census-z0-tools-v1"
CENSUS_RUN_ID = "mdmt-mia-packet-census-z0-train-all-3a071174"
FROZEN_CHECKPOINT = "3a071174331805b8eb55eeb3cc33951541711f5a"
FROZEN_BRANCH = "exp/20260902-001-mdmt-mia-semantic-freshness-mve"
POPULATION_ID = "ALL_PREAUDITED_RUNNABLE_TRAIN_PAIRS"
Z0_DELAYS = {"homography": 0, "id_state": 0, "local": 0, "supplement": 0}
CHANNELS = ("local", "homography", "id_state", "supplement")
FORBIDDEN_WIRE_FIELDS = (
    "packet_id", "packet_census", "census_run_id", "runtime_instance_id",
    "emission_ordinal", "JSON_WIRE_BYTES", "SEMANTIC_ARRAY_RAW_BYTES",
    "terminal_class", "completion_state", "CENSUS_FINALIZATION",
)


class PacketCensusToolError(RuntimeError):
    """Raised when a contract-level tool gate fails."""


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def filename_list_digest(names):
    ordered = list(names)
    if ordered != sorted(ordered):
        raise PacketCensusToolError("filename list is not lexicographically sorted")
    return sha256_bytes("".join("{}\n".format(name) for name in ordered).encode("utf-8"))


def _atomic_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".packet_census_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, str(path))
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def atomic_write_json(path, value):
    _atomic_write(path, (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))


def atomic_write_jsonl(path, records):
    _atomic_write(path, "".join(canonical_json(record) + "\n" for record in records).encode("utf-8"))


def read_json(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PacketCensusToolError("invalid JSON: {}".format(path)) from exc
    if not isinstance(value, dict):
        raise PacketCensusToolError("JSON object required: {}".format(path))
    return value


def load_jsonl(path, expected_record_type=None):
    """Read append-only JSONL without repairing or reordering records."""
    path = Path(path)
    records = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise PacketCensusToolError("cannot read JSONL: {}".format(path)) from exc
    for index, line in enumerate(lines, 1):
        if not line:
            raise PacketCensusToolError("blank JSONL line {} in {}".format(index, path))
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PacketCensusToolError("invalid JSONL line {} in {}".format(index, path)) from exc
        if not isinstance(record, dict):
            raise PacketCensusToolError("non-object JSONL line {} in {}".format(index, path))
        if expected_record_type is not None and record.get("record_type") != expected_record_type:
            raise PacketCensusToolError("unexpected record type on line {} in {}".format(index, path))
        records.append(record)
    return records


def artifact_digest(path):
    path = Path(path)
    if not path.is_file():
        raise PacketCensusToolError("missing artifact: {}".format(path))
    return {"path": str(path), "sha256": sha256_file(path), "byte_count": path.stat().st_size}


def _jpg_basenames(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise PacketCensusToolError("missing image directory: {}".format(directory))
    names = sorted(item.name for item in directory.glob("*.jpg") if item.is_file())
    if not names:
        raise PacketCensusToolError("no jpg images: {}".format(directory))
    if any(not item.rsplit(".", 1)[0].isdigit() for item in names):
        raise PacketCensusToolError("non-numeric jpg basename: {}".format(directory))
    return names


def inspect_pair(pair_id, frame_count, dataset_root, expected_xml_hashes):
    """Inspect path/filename/XML identity only; never parse XML contents."""
    dataset_root = Path(dataset_root)
    pair_id = str(pair_id)
    view1_sequence, view2_sequence = "{}-1".format(pair_id), "{}-2".format(pair_id)
    view1_dir = dataset_root / "train" / "1" / view1_sequence
    view2_dir = dataset_root / "train" / "2" / view2_sequence
    xml1 = dataset_root / "new_xml" / "1" / (view1_sequence + ".xml")
    xml2 = dataset_root / "new_xml" / "2" / (view2_sequence + ".xml")
    names1, names2 = _jpg_basenames(view1_dir), _jpg_basenames(view2_dir)
    reasons = []
    if names1 != names2:
        reasons.append("same_basename_mapping_failed")
    if len(names1) != int(frame_count) or len(names2) != int(frame_count):
        reasons.append("frozen_frame_count_mismatch")
    if not xml1.is_file() or not xml2.is_file():
        reasons.append("missing_xml_initialization_input")
    hash1 = sha256_file(xml1) if xml1.is_file() else ""
    hash2 = sha256_file(xml2) if xml2.is_file() else ""
    if expected_xml_hashes and (hash1, hash2) != tuple(expected_xml_hashes):
        reasons.append("frozen_xml_hash_mismatch")
    return {
        "pair_id": pair_id,
        "view1_sequence": view1_sequence,
        "view2_sequence": view2_sequence,
        "frame_count": int(frame_count),
        "view1_image_dir": str(view1_dir),
        "view2_image_dir": str(view2_dir),
        "view1_image_count": len(names1),
        "view2_image_count": len(names2),
        "view1_ordered_filename_sha256": filename_list_digest(names1),
        "view2_ordered_filename_sha256": filename_list_digest(names2),
        "same_basename_mapping": names1 == names2,
        "view1_xml_path": str(xml1),
        "view2_xml_path": str(xml2),
        "view1_xml_sha256": hash1,
        "view2_xml_sha256": hash2,
        "xml_initialization_available": xml1.is_file() and xml2.is_file(),
        "pre_run_eligible": not reasons,
        "pre_run_ineligibility_reasons": reasons,
    }


def build_manifest(contract_path, runtime_inputs, tooling_paths, pair_records, created_at_utc):
    pair_records = list(pair_records)
    pair_order = [str(record["pair_id"]) for record in pair_records]
    expected_frames = sum(int(record["frame_count"]) for record in pair_records)
    if len(pair_order) != 25 or len(set(pair_order)) != 25:
        raise PacketCensusToolError("exactly 25 unique frozen pairs required")
    if expected_frames != 12026:
        raise PacketCensusToolError("frozen frame total mismatch: {}".format(expected_frames))
    if not all(record.get("pre_run_eligible") for record in pair_records):
        raise PacketCensusToolError("manifest includes ineligible pair")
    tooling_sha256 = {str(Path(path)): sha256_file(path) for path in tooling_paths}
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_path": str(contract_path),
        "contract_sha256": sha256_file(contract_path),
        "frozen_git_checkpoint": FROZEN_CHECKPOINT,
        "frozen_branch": FROZEN_BRANCH,
        "population_id": POPULATION_ID,
        "census_run_id": CENSUS_RUN_ID,
        "condition": "Z0",
        "delay_frames": dict(Z0_DELAYS),
        "seed": 7,
        "device": "cuda:0",
        "expected_pair_count": 25,
        "expected_census_frame_unit_count": 12026,
        "runtime_inputs": runtime_inputs,
        "tooling_sha256": tooling_sha256,
        "pair_order": pair_order,
        "pairs": pair_records,
        "created_at_utc": str(created_at_utc),
    }


def freeze_manifest(output_root, manifest):
    output_root = Path(output_root)
    manifest_path = output_root / "CENSUS_PAIR_MANIFEST.json"
    digest_path = output_root / "CENSUS_PAIR_MANIFEST.sha256"
    if manifest_path.exists() or digest_path.exists():
        raise PacketCensusToolError("refusing to reuse frozen manifest")
    output_root.mkdir(parents=True, exist_ok=False)
    atomic_write_json(manifest_path, manifest)
    _atomic_write(digest_path, (sha256_file(manifest_path) + "  " + manifest_path.name + "\n").encode("ascii"))
    return manifest_path


def verify_frozen_manifest(output_root):
    output_root = Path(output_root)
    manifest_path = output_root / "CENSUS_PAIR_MANIFEST.json"
    digest_path = output_root / "CENSUS_PAIR_MANIFEST.sha256"
    if not manifest_path.is_file() or not digest_path.is_file():
        raise PacketCensusToolError("missing frozen manifest or detached digest")
    expected = digest_path.read_text(encoding="ascii").strip().split()
    if len(expected) != 2 or expected[1] != manifest_path.name or expected[0] != sha256_file(manifest_path):
        raise PacketCensusToolError("frozen manifest digest mismatch")
    manifest = read_json(manifest_path)
    required = {
        "schema_version", "frozen_git_checkpoint", "frozen_branch", "population_id", "census_run_id",
        "condition", "delay_frames", "expected_pair_count", "expected_census_frame_unit_count", "pair_order", "pairs",
    }
    if not required.issubset(manifest):
        raise PacketCensusToolError("manifest schema missing fields")
    if (manifest["schema_version"] != SCHEMA_VERSION or manifest["frozen_git_checkpoint"] != FROZEN_CHECKPOINT
            or manifest["frozen_branch"] != FROZEN_BRANCH or manifest["population_id"] != POPULATION_ID
            or manifest["census_run_id"] != CENSUS_RUN_ID or manifest["condition"] != "Z0"
            or manifest["delay_frames"] != Z0_DELAYS or manifest["expected_pair_count"] != 25
            or manifest["expected_census_frame_unit_count"] != 12026):
        raise PacketCensusToolError("frozen manifest contract mismatch")
    if manifest["pair_order"] != [record.get("pair_id") for record in manifest["pairs"]]:
        raise PacketCensusToolError("pair order does not match pair records")
    return manifest


def expected_pair_paths(attempt_root, pair_id):
    pair_id = str(pair_id)
    sequence = "{}-1".format(pair_id)
    runtime_root = Path(attempt_root) / "results" / "mia_train_{}".format(pair_id)
    return {
        "emissions": runtime_root / "packet_census_emissions_{}.jsonl".format(sequence),
        "terminals": runtime_root / "packet_census_terminals_{}.jsonl".format(sequence),
        "finalizations": runtime_root / "packet_census_finalization_{}.jsonl".format(sequence),
        "runtime_validation": runtime_root / "packet_census_validation_{}.json".format(sequence),
        "author_manifest": runtime_root / "async_packet_manifest_{}.json".format(sequence),
        "trace": runtime_root / "async_packet_trace_{}.jsonl".format(sequence),
        "prediction_view1": Path(attempt_root) / "view1" / "{}.json".format(sequence),
        "prediction_view2": Path(attempt_root) / "view2" / "{}-2.json".format(pair_id),
        "rng_report": Path(attempt_root) / "torch_rng.json",
        "author_log": Path(attempt_root) / "author.log",
    }


def _consistent_namespace(emissions, sequence_name):
    if not emissions:
        raise PacketCensusToolError("empty emission ledger")
    namespaces = {
        (item["packet_id"].get("census_run_id"), item["packet_id"].get("sequence_name"),
         item["packet_id"].get("runtime_instance_id"))
        for item in emissions if isinstance(item.get("packet_id"), dict)
    }
    if namespaces != {(CENSUS_RUN_ID, sequence_name, next(iter(namespaces))[2])}:
        raise PacketCensusToolError("inconsistent census namespace")
    return next(iter(namespaces))[2]


def _gate(condition, name, failures):
    if not condition:
        failures.append(name)


def _contains_forbidden_payload(path):
    raw = Path(path).read_bytes()
    return [field for field in FORBIDDEN_WIRE_FIELDS if field.encode("utf-8") in raw]


def validate_pair_attempt(attempt_root, pair_record):
    """Revalidate a completed Z0 pair directly from immutable disk artifacts."""
    pair_id = str(pair_record["pair_id"])
    sequence = str(pair_record["view1_sequence"])
    paths = expected_pair_paths(attempt_root, pair_id)
    for path in paths.values():
        if not path.is_file():
            raise PacketCensusToolError("missing required pair artifact: {}".format(path))
    emissions = load_jsonl(paths["emissions"], "PACKET_EMISSION")
    terminals = load_jsonl(paths["terminals"], "PACKET_TERMINAL")
    finalizations = load_jsonl(paths["finalizations"], "CENSUS_FINALIZATION")
    runtime_validation = read_json(paths["runtime_validation"])
    author_manifest = read_json(paths["author_manifest"])
    rng_report = read_json(paths["rng_report"])
    independent = validate_packet_census_records(emissions, terminals, finalizations)
    failures = []
    _gate(independent.get("passed") is True, "independent_c1_c8_failed", failures)
    _gate(independent.get("census_status") == "CENSUS_COMPLETE", "independent_census_incomplete", failures)
    runtime_core = {key: runtime_validation.get(key) for key in independent}
    _gate(runtime_core == independent and runtime_validation.get("io_failure", "") == "",
          "runtime_validation_disagrees", failures)
    _gate(len(finalizations) == 1, "finalization_evidence_not_unique", failures)
    try:
        runtime_instance_id = _consistent_namespace(emissions, sequence)
    except PacketCensusToolError as exc:
        runtime_instance_id = ""
        failures.append(str(exc))
    ordinals = [item.get("packet_id", {}).get("emission_ordinal") for item in emissions]
    _gate(ordinals == list(range(1, len(emissions) + 1)), "emission_ordinal_gap", failures)
    frame_count = int(pair_record["frame_count"])
    _gate(all(isinstance(item.get("capture_frame"), int) and 0 <= item["capture_frame"] < frame_count
              for item in emissions), "capture_frame_out_of_domain", failures)
    _gate(all(item.get("capture_frame") == item.get("emitted_frame") == item.get("arrival_frame")
              for item in emissions), "non_z0_arrival", failures)
    _gate(all(item.get("terminal_class") == "TIMELY_DELIVERED" and item.get("terminal_reason") == "timely"
              for item in terminals), "non_timely_z0_terminal", failures)
    _gate(author_manifest.get("delay_frames") == Z0_DELAYS, "author_manifest_delay_mismatch", failures)
    _gate(author_manifest.get("packet_census_status") == "CENSUS_COMPLETE", "author_manifest_census_incomplete", failures)
    integrity_fields = (
        "future_read_violations", "source_bypass_read_count", "wire_roundtrip_digest_mismatches",
        "numpy_alias_violations", "feedback_chain_mismatches",
    )
    _gate(all(author_manifest.get(field) == 0 for field in integrity_fields), "author_runtime_integrity_failure", failures)
    _gate(rng_report.get("completed") is True, "rng_wrapper_not_completed", failures)
    pollution = {}
    for key in ("prediction_view1", "prediction_view2", "trace"):
        found = _contains_forbidden_payload(paths[key])
        if found:
            pollution[key] = found
    _gate(not pollution, "census_field_pollution", failures)
    artifacts = {key: artifact_digest(path) for key, path in paths.items()}
    report = {
        "schema_version": SCHEMA_VERSION,
        "pair_id": pair_id,
        "sequence_name": sequence,
        "runtime_instance_id": runtime_instance_id,
        "passed": not failures,
        "failures": failures,
        "validator": independent,
        "emission_record_count": len(emissions),
        "terminal_record_count": len(terminals),
        "finalization_record_count": len(finalizations),
        "artifact_hashes": artifacts,
        "pollution": pollution,
    }
    return report, emissions, terminals, finalizations


def write_pair_validation(attempt_root, report):
    path = Path(attempt_root) / "validation.json"
    if path.exists():
        raise PacketCensusToolError("refusing to overwrite validation report")
    atomic_write_json(path, report)
    return path


def _number(value):
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool)


def _stats(values):
    values = list(values)
    if not values:
        return {"count": 0, "mean": "NOT_OBSERVED", "p50": "NOT_OBSERVED", "p95": "NOT_OBSERVED",
                "max": "NOT_OBSERVED", "min": "NOT_OBSERVED", "p25": "NOT_OBSERVED", "p75": "NOT_OBSERVED",
                "iqr": "NOT_OBSERVED", "range": "NOT_OBSERVED"}
    array = np.asarray(values, dtype=np.float64)
    if not np.isfinite(array).all():
        raise PacketCensusToolError("non-finite aggregate value")
    p25, p50, p75, p95 = [float(np.quantile(array, q, method="linear")) for q in (0.25, 0.5, 0.75, 0.95)]
    minimum, maximum = float(np.min(array)), float(np.max(array))
    return {"count": int(array.size), "mean": float(np.mean(array)), "p50": p50, "p95": p95,
            "max": maximum, "min": minimum, "p25": p25, "p75": p75,
            "iqr": float(p75 - p25), "range": {"min": minimum, "max": maximum,
                                                    "max_minus_min": float(maximum - minimum)}}


def _routing_key(value):
    return canonical_json(value)


def packet_audit_rows(pair_to_emissions, pair_order):
    rows = []
    for pair_id in pair_order:
        emissions = list(pair_to_emissions[str(pair_id)])
        for expected, emission in enumerate(emissions, 1):
            if emission.get("packet_id", {}).get("emission_ordinal") != expected:
                raise PacketCensusToolError("audit emission ordinal order failure for pair {}".format(pair_id))
            row = dict(emission)
            row["pair_id"] = str(pair_id)
            rows.append(row)
    return rows


def _frame_grid(pair_records, audit_rows):
    grids = {}
    for pair in pair_records:
        pair_id = str(pair["pair_id"])
        for frame in range(int(pair["frame_count"])):
            grids[(pair_id, frame)] = {"packet_count": 0, "JSON_WIRE_BYTES_sum": 0,
                                       "SEMANTIC_ARRAY_RAW_BYTES_sum": 0}
            for channel in CHANNELS:
                grids[(pair_id, frame, channel)] = {"packet_count": 0, "JSON_WIRE_BYTES_sum": 0,
                                                     "SEMANTIC_ARRAY_RAW_BYTES_sum": 0}
    for row in audit_rows:
        pair_id, frame, channel = str(row["pair_id"]), row["capture_frame"], row["channel"]
        if (pair_id, frame) not in grids or (pair_id, frame, channel) not in grids:
            raise PacketCensusToolError("PACKET_CENSUS_OBSERVABILITY_GAP")
        stage_key = (pair_id, frame, channel, row["stage"])
        grids.setdefault(stage_key, {"packet_count": 0, "JSON_WIRE_BYTES_sum": 0,
                                     "SEMANTIC_ARRAY_RAW_BYTES_sum": 0})
        for key in ((pair_id, frame), (pair_id, frame, channel), stage_key):
            grids[key]["packet_count"] += 1
            grids[key]["JSON_WIRE_BYTES_sum"] += row["JSON_WIRE_BYTES"]
            grids[key]["SEMANTIC_ARRAY_RAW_BYTES_sum"] += row["SEMANTIC_ARRAY_RAW_BYTES"]
    return grids


def _share(numerator, denominator):
    if denominator == 0:
        return "UNDEFINED_ZERO_DENOMINATOR"
    return float(numerator) / float(denominator)


def _group_records(rows, key_fn):
    grouped = {}
    for row in rows:
        key = key_fn(row)
        grouped.setdefault(key, []).append(row)
    return grouped


def _content_summary(rows):
    result = {}
    for field in sorted({name for row in rows for name in row["content_counts"]}):
        values = [row["content_counts"].get(field) for row in rows if field in row["content_counts"]]
        if values and all(isinstance(value, bool) for value in values):
            result[field] = {"true_count": sum(values), "false_count": len(values) - sum(values),
                             "statistics": _stats([int(value) for value in values])}
        elif values and all(_number(value) for value in values):
            result[field] = _stats(values)
        else:
            categories = {}
            for value in values:
                categories[str(value)] = categories.get(str(value), 0) + 1
            result[field] = {"category_counts": dict(sorted(categories.items()))}
    return result


def _per_packet_summary(rows):
    return {
        "packet_count": len(rows),
        "JSON_WIRE_BYTES": _stats([row["JSON_WIRE_BYTES"] for row in rows]),
        "SEMANTIC_ARRAY_RAW_BYTES": _stats([row["SEMANTIC_ARRAY_RAW_BYTES"] for row in rows]),
        "content_counts": _content_summary(rows),
    }


def _frame_stats(grids, keys):
    zero = {"packet_count": 0, "JSON_WIRE_BYTES_sum": 0, "SEMANTIC_ARRAY_RAW_BYTES_sum": 0}
    values = [grids.get(key, zero) for key in keys]
    packets = [value["packet_count"] for value in values]
    json_bytes = [value["JSON_WIRE_BYTES_sum"] for value in values]
    raw_bytes = [value["SEMANTIC_ARRAY_RAW_BYTES_sum"] for value in values]
    return {
        "packet_count": _stats(packets),
        "zero_emission_frame_fraction": float(sum(value == 0 for value in packets)) / len(packets) if packets else "NOT_OBSERVED",
        "JSON_WIRE_BYTES_sum": _stats(json_bytes),
        "SEMANTIC_ARRAY_RAW_BYTES_sum": _stats(raw_bytes),
    }


def summarize_census(pair_records, pair_to_emissions):
    """Create contract-defined descriptive aggregates from already-valid records."""
    pair_records = list(pair_records)
    pair_order = [str(item["pair_id"]) for item in pair_records]
    if set(pair_to_emissions) != set(pair_order):
        raise PacketCensusToolError("partial cohort cannot aggregate")
    audit_rows = packet_audit_rows(pair_to_emissions, pair_order)
    grids = _frame_grid(pair_records, audit_rows)
    all_frame_keys = [(str(pair["pair_id"]), frame) for pair in pair_records for frame in range(int(pair["frame_count"]))]
    if len(all_frame_keys) != 12026:
        raise PacketCensusToolError("frozen frame grid total mismatch")
    by_channel = _group_records(audit_rows, lambda row: row["channel"])
    by_channel_stage = _group_records(audit_rows, lambda row: (row["channel"], row["stage"]))
    by_routing = _group_records(audit_rows, lambda row: (row["channel"], row["stage"], _routing_key(row["routing_attribution"])))
    pooled = {
        "all_channels_per_packet": _per_packet_summary(audit_rows),
        "all_channels_per_frame": _frame_stats(grids, all_frame_keys),
        "by_channel": {},
        "by_channel_stage": {},
        "by_routing_attribution": {},
    }
    total_json = sum(row["JSON_WIRE_BYTES"] for row in audit_rows)
    total_raw = sum(row["SEMANTIC_ARRAY_RAW_BYTES"] for row in audit_rows)
    for channel in CHANNELS:
        rows = by_channel.get(channel, [])
        keys = [(str(pair["pair_id"]), frame, channel) for pair in pair_records
                for frame in range(int(pair["frame_count"]))]
        pooled["by_channel"][channel] = {
            "per_packet": _per_packet_summary(rows),
            "per_frame": _frame_stats(grids, keys),
            "logical_software_representation_workload_share": {
                "JSON_WIRE_BYTES": _share(sum(row["JSON_WIRE_BYTES"] for row in rows), total_json),
                "SEMANTIC_ARRAY_RAW_BYTES": _share(sum(row["SEMANTIC_ARRAY_RAW_BYTES"] for row in rows), total_raw),
            },
        }
    for key, rows in sorted(by_channel_stage.items()):
        channel, stage = key
        keys = [(str(pair["pair_id"]), frame, channel, stage) for pair in pair_records
                for frame in range(int(pair["frame_count"]))]
        pooled["by_channel_stage"]["{}|{}".format(*key)] = {
            "packet_total": len(rows),
            "packets_per_frame": float(len(rows)) / len(all_frame_keys),
            "per_packet": _per_packet_summary(rows),
            "per_frame": _frame_stats(grids, keys),
        }
    for key, rows in sorted(by_routing.items()):
        channel, stage, routing = key
        pooled["by_routing_attribution"]["{}|{}|{}".format(channel, stage, routing)] = {"packet_count": len(rows)}

    pair_results = {}
    core = {"total_packets_per_frame": [], "total_JSON_WIRE_BYTES_per_frame": [],
            "total_SEMANTIC_ARRAY_RAW_BYTES_per_frame": []}
    for pair in pair_records:
        pair_id, frames = str(pair["pair_id"]), int(pair["frame_count"])
        rows = list(pair_to_emissions[pair_id])
        payload = {
            "frame_count": frames,
            "packet_total": len(rows),
            "packets_per_frame": float(len(rows)) / frames,
            "JSON_WIRE_BYTES_per_frame": float(sum(row["JSON_WIRE_BYTES"] for row in rows)) / frames,
            "SEMANTIC_ARRAY_RAW_BYTES_per_frame": float(sum(row["SEMANTIC_ARRAY_RAW_BYTES"] for row in rows)) / frames,
            "by_channel": {},
        }
        core["total_packets_per_frame"].append(payload["packets_per_frame"])
        core["total_JSON_WIRE_BYTES_per_frame"].append(payload["JSON_WIRE_BYTES_per_frame"])
        core["total_SEMANTIC_ARRAY_RAW_BYTES_per_frame"].append(payload["SEMANTIC_ARRAY_RAW_BYTES_per_frame"])
        for channel in CHANNELS:
            values = [row for row in rows if row["channel"] == channel]
            channel_payload = {
                "packet_total": len(values),
                "packets_per_frame": float(len(values)) / frames,
                "JSON_WIRE_BYTES_per_frame": float(sum(row["JSON_WIRE_BYTES"] for row in values)) / frames,
                "SEMANTIC_ARRAY_RAW_BYTES_per_frame": float(sum(row["SEMANTIC_ARRAY_RAW_BYTES"] for row in values)) / frames,
                "JSON_WIRE_BYTES_workload_share": _share(sum(row["JSON_WIRE_BYTES"] for row in values),
                                                          sum(row["JSON_WIRE_BYTES"] for row in rows)),
                "SEMANTIC_ARRAY_RAW_BYTES_workload_share": _share(sum(row["SEMANTIC_ARRAY_RAW_BYTES"] for row in values),
                                                                     sum(row["SEMANTIC_ARRAY_RAW_BYTES"] for row in rows)),
            }
            payload["by_channel"][channel] = channel_payload
            for name, value in channel_payload.items():
                if name.endswith("_share") and isinstance(value, str):
                    continue
                if name != "packet_total":
                    core.setdefault("{}_{}".format(channel, name), []).append(value)
        pair_results[pair_id] = payload
    return {
        "schema_version": SCHEMA_VERSION,
        "quantile_estimator": "numpy.quantile(method=linear)",
        "pair_count": len(pair_records),
        "census_frame_unit_count": len(all_frame_keys),
        "emission_count": len(audit_rows),
        "pair_results": pair_results,
        "pooled_frame_or_packet_view": pooled,
        "equal_pair_view": {key: _stats(values) for key, values in core.items()},
        "packet_audit_rows": audit_rows,
    }


def write_summary(output_root, summary):
    output_root = Path(output_root)
    audit_rows = summary.pop("packet_audit_rows")
    audit_path = output_root / "PACKET_CENSUS_PACKET_AUDIT.jsonl"
    summary_path = output_root / "PACKET_CENSUS_DESCRIPTIVE_SUMMARY.json"
    if audit_path.exists() or summary_path.exists():
        raise PacketCensusToolError("refusing to overwrite aggregate artifacts")
    atomic_write_jsonl(audit_path, audit_rows)
    summary["packet_audit_sha256"] = sha256_file(audit_path)
    atomic_write_json(summary_path, summary)
    return audit_path, summary_path
