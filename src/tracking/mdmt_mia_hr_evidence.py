"""Outcome-blind, self-contained H_R communication evidence."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .mdmt_mia_c7_batch_b_schema import registered_cells
from .mdmt_mia_async_deadline_runtime import validate_packet_census_records


class HREvidenceError(ValueError):
    pass


SELECTION_SHA256 = "15264520fe185b5fa34000f978e502ef350dca2a8332c28a4685a7fd7c59a522"
VALIDATION_SHA256 = "0a521db4f52d5963796f4708e89fa16344ccb8c7fb03830c29549af1e09ea364"
SELECTED_CELL_ID = "P66__P20"
FORMAL_SUPPORT_CONSUMER_SHA256 = "45cb1631497311fa416840ec84fd55b90b13b42c3a8cb7386e8f52ad94e71fc9"
FORMAL_SUPPORT_CIM_SHA256 = "3315dea2dc7a5f9bcbd69af5a9b7296e1b60efcef273dace8fca54281a68411e"
FORMAL_SUPPORT_ATTESTATION_SHA256 = "2c5cb35129fcdc8d897986c665850cdbfc16a197a2c99587ab96d502c66b442e"
C7_FULL_AUTH_SHA256 = "046f8803df9a2f218cbe0fe00686806e0631f27456ab27e97adca9fa10e67afe"
GENERATED_MANIFEST_ID = "871956be0adb5b42aaadd8abd2c41416de32c9dd87398ed5d6f3736b9724be3e"
RAW_NAME = "H_R_RAW_EVIDENCE.jsonl"
NORMALIZED_NAME = "H_R_NORMALIZED_EVIDENCE.json"
EFFECTIVE_NAME = "H_R_EFFECTIVE_CONFIG.json"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_digest(path: Path) -> str:
    return digest(path.read_bytes())


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise HREvidenceError("INVALID_JSON:" + path.name) from exc
    if not isinstance(value, dict):
        raise HREvidenceError("OBJECT_REQUIRED:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict]:
    try:
        values = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as exc:
        raise HREvidenceError("INVALID_JSONL:" + path.name) from exc
    if not all(isinstance(value, dict) for value in values):
        raise HREvidenceError("JSONL_OBJECT_REQUIRED:" + path.name)
    return values


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical(value))


def selection(selection_path: Path, validation_path: Path) -> dict:
    if file_digest(selection_path) != SELECTION_SHA256 or file_digest(validation_path) != VALIDATION_SHA256:
        raise HREvidenceError("C7_AUTHORITY_HASH_MISMATCH")
    choice, validation = read_json(selection_path), read_json(validation_path)
    if (choice.get("schema_version") != "C7_SELECTION_V1"
            or choice.get("selection_outcome") != "SELECTED_CELL"
            or choice.get("selected_cell_id") != SELECTED_CELL_ID
            or choice.get("all_21_complete_attestation") is not True
            or validation.get("status") != "PASS"
            or validation.get("selection_validation", {}).get("status") != "PASS"
            or validation.get("selection_validation", {}).get("selected_cell_id") != SELECTED_CELL_ID
            or validation.get("manifest_sha256") != choice.get("manifest_sha256")):
        raise HREvidenceError("C7_SELECTION_VALIDATION_MISMATCH")
    cell = next((row for row in registered_cells() if row["cell_id"] == SELECTED_CELL_ID), None)
    if cell is None or (cell["pair_id"], cell["capacity_id"], cell["capacity_bytes"]) != ("P66", "P20", 16649):
        raise HREvidenceError("C7_REGISTERED_CELL_MISMATCH")
    return cell


def node_ref(attempt_root: Path, path: Path) -> dict:
    path, root = path.resolve(), attempt_root.resolve()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise HREvidenceError("NODE_FILE_OUTSIDE_ATTEMPT") from exc
    if not path.is_file():
        raise HREvidenceError("NODE_FILE_MISSING")
    raw = path.read_bytes()
    return {"kind": "NODE_FILE", "path": str(relative), "size_bytes": len(raw), "sha256": digest(raw)}


def source_paths(attempt_root: Path) -> dict[str, Path]:
    source = attempt_root / "output/hr/source_runtime"
    seq = "66-1"
    results = source / "author_outputs/mia/train_66/results/mia_train_66"
    suppression = source / "suppression"
    return {
        "c7_observer": source / "raw_c7/raw_observer.json",
        "packet_manifest": results / ("async_packet_manifest_" + seq + ".json"),
        "service_ledger": results / ("c4_service_ledger_" + seq + ".jsonl"),
        "service_summary": results / ("c4_service_summary_" + seq + ".json"),
        "census_emissions": results / ("packet_census_emissions_" + seq + ".jsonl"),
        "census_terminals": results / ("packet_census_terminals_" + seq + ".jsonl"),
        "census_finalization": results / ("packet_census_finalization_" + seq + ".jsonl"),
        "census_validation": results / ("packet_census_validation_" + seq + ".json"),
        "suppression_decisions": suppression / ("c6_first_service_decisions_" + seq + ".jsonl"),
        "suppression_seal": suppression / ("c6_suppression_seal_" + seq + ".json"),
    }


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def read_raw(path: Path) -> list[dict]:
    records = read_jsonl(path)
    if len(records) != len(source_paths(Path("/"))) + 1:
        raise HREvidenceError("RAW_FAMILY_COUNT_MISMATCH")
    if len({row.get("family") for row in records}) != len(records):
        raise HREvidenceError("RAW_FAMILY_DUPLICATE")
    return records


def validate_raw(records: list[dict], auth: Mapping[str, Any]) -> dict:
    by = {row.get("family"): row.get("value") for row in records}
    if set(by) != {"header", *source_paths(Path("/"))}:
        raise HREvidenceError("RAW_FAMILY_MISMATCH")
    header, cell = by["header"], auth["cell"]
    if header.get("schema_version") != "H_R_RAW_COMMUNICATION_EVIDENCE_V1":
        raise HREvidenceError("RAW_HEADER_SCHEMA_MISMATCH")
    for key, expected in (("run_id", auth["run_id"]), ("attempt_id", auth["attempt_id"]),
                          ("authorization_hash", auth["authorization_hash"]),
                          ("selected_cell", cell), ("source_sha", auth["source_sha"]),
                          ("selection_sha256", SELECTION_SHA256),
                          ("validation_sha256", VALIDATION_SHA256),
                          ("tracking_outcome_read", False)):
        if header.get(key) != expected:
            raise HREvidenceError("RAW_HEADER_MISMATCH:" + key)
    observer = by["c7_observer"]
    config = observer.get("service_config", {})
    if (observer.get("schema_version") != "C7_REAL_RAW_OBSERVER_RUN_V1"
            or observer.get("sequence_name") != "66-1"
            or not isinstance(observer.get("frames"), list) or not observer["frames"]
            or config.get("schema_version") != "C7_REGISTERED_FIFO_SERVICE_V1"
            or config.get("run_id") != auth["run_id"] or config.get("pair_id") != cell["pair_id"]
            or config.get("capacity_id") != cell["capacity_id"]
            or config.get("rate_logical_bytes_per_frame") != cell["capacity_bytes"]
            or config.get("mode") != "fifo" or config.get("ledger_enabled") is not True):
        raise HREvidenceError("EFFECTIVE_C7_CONFIG_MISMATCH")
    if any(frame.get("frame_index") != index or frame.get("observer_failures")
           for index, frame in enumerate(observer["frames"])):
        raise HREvidenceError("C7_OBSERVER_FRAME_INVALID")
    ledger = by["service_ledger"]
    event_by_ordinal = {}
    for event in ledger:
        ordinal = event.get("event_ordinal")
        if type(ordinal) is not int or ordinal in event_by_ordinal:
            raise HREvidenceError("SERVICE_LEDGER_ORDINAL_INVALID")
        event_by_ordinal[ordinal] = event
    seen_observer_ordinals = set()
    for index, frame in enumerate(observer["frames"]):
        observations = frame.get("observations")
        if not isinstance(observations, list) or not observations:
            raise HREvidenceError("C7_OBSERVER_EMPTY_FRAME")
        types = []
        for row in observations:
            event = row.get("event") if isinstance(row, dict) else None
            ordinal = event.get("event_ordinal") if isinstance(event, dict) else None
            if (event != event_by_ordinal.get(ordinal)
                    or event.get("frame") != index
                    or ordinal in seen_observer_ordinals):
                raise HREvidenceError("C7_OBSERVER_LEDGER_MISMATCH")
            seen_observer_ordinals.add(ordinal)
            types.append(event["event_type"])
        if types[0] != "frame_open" or types[-1] != "frame_summary":
            raise HREvidenceError("C7_OBSERVER_FRAME_BOUNDARY_INVALID")
        opening = observations[0]["event"]
        closing = observations[-1]["event"]
        budget = cell["capacity_bytes"]
        slices = [row["event"] for row in observations
                  if row["event"]["event_type"] == "service_slice"]
        if (opening.get("frame_service_budget") != budget
                or closing.get("frame_service_budget") != budget
                or opening.get("frame_unused_budget") != budget
                or type(closing.get("frame_unused_budget")) is not int
                or closing["frame_unused_budget"] < 0
                or closing["frame_unused_budget"] > budget
                or sum(row.get("bytes_served", 0) for row in slices)
                   != budget - closing["frame_unused_budget"]):
            raise HREvidenceError("OBSERVED_FIFO_FRAME_BUDGET_MISMATCH")
    expected_observer_ordinals = {
        row["event_ordinal"] for row in ledger
        if row.get("event_type") not in {
            "suppression", "terminal", "packet_summary", "service_finalization"}}
    if seen_observer_ordinals != expected_observer_ordinals:
        raise HREvidenceError("C7_OBSERVER_EVENT_COVERAGE_MISMATCH")
    if any(event.get("record_type") != "C4_SERVICE_EVENT" for event in ledger):
        raise HREvidenceError("SERVICE_LEDGER_RECORD_INVALID")
    summary = by["service_summary"]
    manifest = by["packet_manifest"]
    if (summary.get("run_id") != auth["run_id"]
            or summary.get("pair_id") != cell["pair_id"]
            or summary.get("R") != cell["capacity_bytes"]
            or summary.get("mode") != "fifo"
            or manifest.get("c4_service_config") != config):
        raise HREvidenceError("SERVICE_CONFIG_RECONCILIATION_FAILED")
    finalization_flags = (
        "passed", "byte_conservation", "frame_budget_conservation",
        "work_conserving", "terminal_conservation", "packet_identity_authoritative",
    )
    if (any(type(summary.get(flag)) is not int or summary[flag] != 1
            for flag in finalization_flags)
            or summary.get("ledger_io_failure") != ""):
        raise HREvidenceError("SERVICE_FINALIZATION_GATE_FAILED")
    if any(row.get("run_id") != auth["run_id"] or row.get("pair_id") != cell["pair_id"]
           for row in by["service_ledger"]):
        raise HREvidenceError("SERVICE_LEDGER_IDENTITY_MISMATCH")
    census = validate_packet_census_records(
        by["census_emissions"], by["census_terminals"], by["census_finalization"])
    if not census.get("passed") or by["census_validation"].get("census_status") != "CENSUS_COMPLETE":
        raise HREvidenceError("PACKET_CENSUS_INVALID")
    seal = by["suppression_seal"]
    payload = seal.get("sealed_payload", {})
    decisions = by["suppression_decisions"]
    keys = [json.dumps(row.get("packet_id"), sort_keys=True, separators=(",", ":")) for row in decisions]
    decision_bytes = "\n".join(canonical(row).decode("utf-8").rstrip("\n") for row in decisions).encode("utf-8")
    if (seal.get("schema_version") != "C6_SUPPRESSION_DECISION_SEAL_V1"
            or seal.get("seal_sha256") != digest(canonical(payload).rstrip(b"\n"))
            or payload.get("run_id") != auth["run_id"] or payload.get("status") != "PASS"
            or payload.get("decision_record_count") != len(decisions)
            or payload.get("unique_packet_id_count") != len(set(keys))
            or payload.get("ordered_decision_records_sha256") != digest(decision_bytes)
            or payload.get("suppressed_packet_count") != sum(
                row.get("whole_packet_currently_non_applicable") is True for row in decisions)
            or payload.get("serviceable_packet_count") != sum(
                row.get("whole_packet_currently_non_applicable") is False for row in decisions)
            or payload.get("suppressed_wire_bytes") != sum(
                row["JSON_WIRE_BYTES"] for row in decisions
                if row.get("whole_packet_currently_non_applicable") is True)
            or payload.get("serviceable_wire_bytes") != sum(
                row["JSON_WIRE_BYTES"] for row in decisions
                if row.get("whole_packet_currently_non_applicable") is False)):
        raise HREvidenceError("C6_SUPPRESSION_SEAL_INVALID")
    ledger_by_packet = {}
    for event in ledger:
        packet_id = event.get("packet_id")
        if packet_id is not None:
            ledger_by_packet.setdefault(json.dumps(packet_id, sort_keys=True), []).append(event)
    terminal_by_packet = {
        json.dumps(row["packet_id"], sort_keys=True): row for row in by["census_terminals"]
    }
    for decision in decisions:
        if (decision.get("schema_version") != "C6_TRUE_FIRST_SERVICE_SUPPRESSION_V1"
                or decision.get("channel") != "id_state"
                or type(decision.get("whole_packet_currently_non_applicable")) is not bool):
            raise HREvidenceError("C6_DECISION_INVALID")
        key = json.dumps(decision["packet_id"], sort_keys=True)
        events = ledger_by_packet.get(key, [])
        suppressed = decision["whole_packet_currently_non_applicable"]
        expected_type = "suppression" if suppressed else "service_start"
        if not any(row.get("event_type") == expected_type
                   and row.get("frame") == decision["frame"] for row in events):
            raise HREvidenceError("C6_DECISION_SERVICE_MISMATCH")
        terminal = terminal_by_packet.get(key)
        if suppressed and (terminal is None or terminal.get("terminal_class") != "SUPPRESSED"
                           or terminal.get("terminal_reason") != "c6_whole_packet_non_applicable"
                           or any(row.get("event_type") == "service_slice" for row in events)):
            raise HREvidenceError("C6_SUPPRESSION_TERMINAL_MISMATCH")
    if (not isinstance(by["service_ledger"], list) or not isinstance(by["service_summary"], dict)
            or not isinstance(by["packet_manifest"], dict)):
        raise HREvidenceError("SERVICE_EVIDENCE_INVALID")
    return config


def collect_raw(attempt_root: Path, auth: Mapping[str, Any], inventory: Mapping[str, Any]) -> Path:
    """Capture exact communication sidecars; never search a result directory."""
    paths = source_paths(attempt_root)
    records = [{"family": "header", "value": {
        "schema_version": "H_R_RAW_COMMUNICATION_EVIDENCE_V1",
        "run_id": auth["run_id"], "attempt_id": auth["attempt_id"],
        "authorization_hash": auth["authorization_hash"], "selected_cell": auth["cell"],
        "selection_sha256": SELECTION_SHA256, "validation_sha256": VALIDATION_SHA256,
        "source_sha": auth["source_sha"], "generated_source_inventory": dict(inventory),
        "tracking_outcome_read": False,
    }}]
    for family, path in paths.items():
        if not _inside(path, attempt_root / "output") or not path.is_file() or path.is_symlink():
            raise HREvidenceError("MISSING_OR_UNSAFE_SOURCE:" + family)
        value = read_jsonl(path) if path.suffix == ".jsonl" else read_json(path)
        records.append({"family": family, "value": value})
    validate_raw(records, auth)
    target = attempt_root / "output/hr" / RAW_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        for record in records:
            handle.write(canonical(record))
    return target


def normalized_from_raw(raw_path: Path, auth: Mapping[str, Any]) -> tuple[dict, dict]:
    """Derive and validate without opening any source-runtime file."""
    records = read_raw(raw_path)
    config = validate_raw(records, auth)
    by = {row["family"]: row["value"] for row in records}
    normalized = {
        "schema_version": "H_R_NORMALIZED_COMMUNICATION_EVIDENCE_V1",
        "raw_sha256": file_digest(raw_path), "run_id": auth["run_id"],
        "cell_id": auth["cell"]["cell_id"],
        "observed_frame_count": len(by["c7_observer"]["frames"]),
        "service_event_count": len(by["service_ledger"]),
        "packet_emission_count": len(by["census_emissions"]),
        "packet_terminal_count": len(by["census_terminals"]),
        "suppression_decision_count": len(by["suppression_decisions"]),
        "suppressed_packet_count": by["suppression_seal"]["sealed_payload"]["suppressed_packet_count"],
        "observed_service_config": config, "tracking_outcome_read": False,
    }
    effective = {
        "schema_version": "H_R_EFFECTIVE_CONFIG_V1", "run_id": auth["run_id"],
        "cell_id": auth["cell"]["cell_id"], "pair_id": config["pair_id"],
        "capacity_id": config["capacity_id"], "capacity_bytes": auth["cell"]["capacity_bytes"],
        "observed_effective_rate": config["rate_logical_bytes_per_frame"],
        "observed_fifo": config["mode"] == "fifo",
        "observed_ledger_enabled": config["ledger_enabled"],
        "observed_suppression_enabled": by["suppression_seal"]["sealed_payload"]["status"] == "PASS",
        "generated_source_inventory": by["header"]["generated_source_inventory"],
    }
    return normalized, effective


def _source_identity_digests(repo_root: Path, source_sha: str, mode: str) -> tuple[str, str, str]:
    paths = (
        "scripts/run_mdmt_mia_hr_formal.py",
        "scripts/run_mdmt_mia_hr_real_child.py",
        "src/tracking/mdmt_mia_async_deadline_runtime.py",
    )
    if mode == "CURRENT_WORKTREE":
        return tuple(file_digest(repo_root / path) for path in paths)
    if mode != "HISTORICAL_GIT":
        raise HREvidenceError("AUTHORIZATION_SOURCE_IDENTITY_MODE_INVALID")
    if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise HREvidenceError("AUTHORIZATION_SOURCE_COMMIT_INVALID")
    commit = subprocess.run(
        ["git", "rev-parse", "--verify", source_sha + "^{commit}"],
        cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if commit.returncode or commit.stdout.decode("ascii", errors="replace").strip() != source_sha:
        raise HREvidenceError("AUTHORIZATION_SOURCE_COMMIT_INVALID")
    hashes = []
    for path in paths:
        blob = subprocess.run(
            ["git", "cat-file", "blob", source_sha + ":" + path],
            cwd=repo_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if blob.returncode:
            raise HREvidenceError("AUTHORIZATION_SOURCE_BLOB_MISSING:" + path)
        hashes.append(digest(blob.stdout))
    return tuple(hashes)


def validate_formal_support_consumer(path: Path) -> str:
    """Bind Formal issuance and admission to the one accepted content-verified reuse."""
    raw = path.read_bytes()
    observed_sha = digest(raw)
    if observed_sha != FORMAL_SUPPORT_CONSUMER_SHA256:
        raise HREvidenceError("FORMAL_SUPPORT_CONSUMER_SHA_MISMATCH")
    try:
        record = json.loads(raw)
    except ValueError as exc:
        raise HREvidenceError("FORMAL_SUPPORT_CONSUMER_INVALID") from exc
    if not isinstance(record, dict):
        raise HREvidenceError("FORMAL_SUPPORT_CONSUMER_INVALID")
    expected = {
        "schema_version": "GOVERNANCE_V2_ARTIFACT_NODE_V1",
        "purpose": "H_R_FORMAL_PREISSUANCE",
        "consumption_class": "FORMAL_AUTHORIZATION_SUPPORT",
        "attempt_id": "v2_4_hr_qual_002", "node_id": "validator_cr1",
        "decision": "REUSE_ADMISSIBLE", "verification_depth": "CONTENT",
    }
    if any(record.get(key) != value for key, value in expected.items()):
        raise HREvidenceError("FORMAL_SUPPORT_CONSUMER_DECISION_INVALID")
    checks = record.get("C1_C6", {})
    if not isinstance(checks, dict) or any(
            not isinstance(checks.get("C" + str(i)), dict)
            or checks["C" + str(i)].get("status") != "PASS" for i in range(1, 7)):
        raise HREvidenceError("FORMAL_SUPPORT_CONSUMER_CHECK_INVALID")
    c4 = checks["C4"]
    if (c4.get("cim_sha256") != FORMAL_SUPPORT_CIM_SHA256
            or c4.get("independent_review_sha256") != FORMAL_SUPPORT_ATTESTATION_SHA256
            or c4.get("relied_evidence_ids") != ["V2_4_H_R_PREISSUE_CONSUMER"]):
        raise HREvidenceError("FORMAL_SUPPORT_CONSUMER_V21_INVALID")
    anchor = record.get("anchor", {})
    if not isinstance(anchor, dict) or any(
            anchor.get(key) != expected[key] for key in ("attempt_id", "node_id")):
        raise HREvidenceError("FORMAL_SUPPORT_CONSUMER_ANCHOR_INVALID")
    for gate in ("C5", "C6"):
        layers = checks[gate].get("layers", {})
        if (not isinstance(layers, dict)
                or layers.get("RAW_EVIDENCE", {}).get("heads") != ["initial"]
                or layers.get("RAW_EVIDENCE", {}).get("owner_node_id") != "initial"
                or layers.get("NORMALIZED_EVIDENCE", {}).get("heads") != ["validator_cr1"]
                or layers.get("NORMALIZED_EVIDENCE", {}).get("owner_node_id") != "validator_cr1"):
            raise HREvidenceError("FORMAL_SUPPORT_CONSUMER_LINEAGE_INVALID")
    return observed_sha


def formal_config_expectation(auth: Mapping[str, Any]) -> dict:
    cell = auth["cell"]
    return {
        "run_id": auth["run_id"], "cell_id": cell["cell_id"],
        "pair_id": cell["pair_id"], "capacity_id": cell["capacity_id"],
        "capacity_bytes": cell["capacity_bytes"], "mode": "fifo",
        "rate_logical_bytes_per_frame": cell["capacity_bytes"],
        "ledger_enabled": True, "suppression_enabled": True,
    }


def load_authorization(path: Path | Mapping[str, Any], attempt_root: Path, repo_root: Path, *,
                       source_identity_mode: str = "CURRENT_WORKTREE") -> dict:
    auth = read_json(path) if isinstance(path, Path) else dict(path)
    signed = dict(auth)
    supplied_hash = signed.pop("authorization_hash", None)
    if supplied_hash != digest(canonical(signed)):
        raise HREvidenceError("AUTHORIZATION_HASH_MISMATCH")
    required = {
        "schema_version", "authorization_hash", "source_sha", "selection_path",
        "selection_sha256", "validation_path", "validation_sha256", "cell",
        "run_id", "attempt_id", "attempt_root", "qualification_only",
        "qualification_frame_count", "operator_sha256", "child_sha256",
        "wrapper_path", "wrapper_sha256", "preparer_path", "preparer_sha256",
        "runtime_sha256", "generated_source_manifest_sha256",
        "service_config_schema", "suppression_config_schema",
        "evidence_layout", "v2_3_purpose", "v2_3_policy",
        "mdmt_root", "mia_root", "mia_config_path", "device",
    }
    formal = auth.get("schema_version") == "H_R_FORMAL_AUTHORIZATION_V1"
    formal_fields = {
        "authorization_purpose", "formal_output_root", "formal_support_consumer_record_path",
        "formal_support_consumer_record_sha256", "formal_service_config",
        "formal_suppression_config", "formal_effective_config_expectation",
    }
    if set(auth) != (required | formal_fields if formal else required) or (
            auth.get("schema_version") != ("H_R_FORMAL_AUTHORIZATION_V1" if formal
                                            else "H_R_PRODUCTION_AUTHORIZATION_V1")):
        raise HREvidenceError("AUTHORIZATION_SCHEMA_MISMATCH")
    if formal:
        if (auth["authorization_purpose"] != "H_R_FORMAL"
                or auth["qualification_only"] is not False
                or auth["qualification_frame_count"] != 0
                or auth["formal_output_root"] != str((attempt_root.resolve() / "output"))
                or auth["run_id"] != auth["attempt_id"]
                or not isinstance(auth["attempt_id"], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", auth["attempt_id"])):
            raise HREvidenceError("FORMAL_AUTHORIZATION_SCOPE_MISMATCH")
        service = {
            "schema_version": "C7_REGISTERED_FIFO_SERVICE_V1", "mode": "fifo",
            "capacity_id": auth["cell"]["capacity_id"],
            "rate_logical_bytes_per_frame": auth["cell"]["capacity_bytes"],
            "ledger_enabled": True, "run_id": auth["run_id"],
            "pair_id": auth["cell"]["pair_id"],
        }
        suppression = {"enabled": True, "run_id": auth["run_id"]}
        if (auth["formal_service_config"] != service
                or auth["formal_suppression_config"] != suppression
                or auth["formal_effective_config_expectation"] != formal_config_expectation(auth)
                or auth["formal_support_consumer_record_sha256"] !=
                   validate_formal_support_consumer(Path(auth["formal_support_consumer_record_path"]))):
            raise HREvidenceError("FORMAL_AUTHORIZATION_BINDING_MISMATCH")
    if (auth["attempt_root"] != str(attempt_root.resolve())
            or auth["attempt_id"] != attempt_root.name
            or auth["cell"] != selection(Path(auth["selection_path"]), Path(auth["validation_path"]))
            or auth["selection_sha256"] != SELECTION_SHA256
            or auth["validation_sha256"] != VALIDATION_SHA256
            or auth["service_config_schema"] != "C7_REGISTERED_FIFO_SERVICE_V1"
            or auth["suppression_config_schema"] != "C6_TRUE_FIRST_SERVICE_SUPPRESSION_V1"
            or auth["evidence_layout"] != "H_R_ATTEMPT_LOCAL_V1"
            or auth["v2_3_purpose"] != "H_R_PRODUCTION_PROOF"
            or auth["v2_3_policy"] != "DIRECT_NODE_FILE_V1"
            or type(auth["qualification_only"]) is not bool
            or type(auth["qualification_frame_count"]) is not int
            or auth["qualification_frame_count"] < 0
            or (not auth["qualification_only"] and auth["qualification_frame_count"] != 0)):
        raise HREvidenceError("AUTHORIZATION_SCOPE_MISMATCH")
    outer = Path(auth["selection_path"]).resolve().parents[3]
    frozen_path = outer / "authorizations/c7/C7_FULL_CENSUS_AUTHORIZATION_exp_20260925_001.json"
    if file_digest(frozen_path) != C7_FULL_AUTH_SHA256:
        raise HREvidenceError("C7_FULL_AUTHORITY_MISMATCH")
    frozen = read_json(frozen_path)
    wrapper, preparer = frozen["wrapper_identity"], frozen["generated_source_preparer_identity"]
    resources = frozen["execution_resources"]
    if (auth["wrapper_path"] != wrapper["canonical_path"]
            or auth["wrapper_sha256"] != wrapper["sha256"]
            or auth["preparer_path"] != preparer["canonical_path"]
            or auth["preparer_sha256"] != preparer["sha256"]
            or auth["generated_source_manifest_sha256"] != GENERATED_MANIFEST_ID
            or auth["mdmt_root"] != resources["mdmt_root"]
            or auth["mia_root"] != resources["mia_root"]
            or auth["mia_config_path"] != resources["mia_config_path"]
            or auth["device"] != resources["device"]):
        raise HREvidenceError("C7_FROZEN_EXECUTION_IDENTITY_MISMATCH")
    operator_sha, child_sha, runtime_sha = _source_identity_digests(
        repo_root, auth["source_sha"], source_identity_mode)
    if (operator_sha != auth["operator_sha256"]
            or child_sha != auth["child_sha256"]
            or runtime_sha != auth["runtime_sha256"]
            or file_digest(Path(auth["wrapper_path"])) != auth["wrapper_sha256"]
            or file_digest(Path(auth["preparer_path"])) != auth["preparer_sha256"]):
        raise HREvidenceError("AUTHORIZATION_SOURCE_IDENTITY_MISMATCH")
    return auth
