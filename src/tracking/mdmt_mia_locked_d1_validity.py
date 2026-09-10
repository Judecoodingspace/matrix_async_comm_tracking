"""Outcome-blind validity producers and acceptance sealing for locked-d1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tracking.mdmt_mia_locked_d1_package import (LockedD1Error, LOGICAL_CONDITIONS, atomic_json,
    canonical_json, condition_record_sha256, load_sealed_package, population_pairs,
    sha256_bytes, sha256_file, require_same_authority)

FORBIDDEN_SCIENTIFIC_FIELDS = frozenset(("mda", "D_ID", "R_edge", "C_comp", "bootstrap_ci", "direction", "mechanism_positive", "gate_a", "gate_b", "gate_c", "gate_d", "gate_e", "gate_f"))
REQUIRED_TRACE_FIELDS = frozenset(("capture_frame", "view_id", "pre_branch_row_index", "delay_membership", "cf_membership", "high_score_triggered", "high_score_bbox_written"))
ZERO_RUNTIME_GATES = ("future_read_violations", "source_bypass_read_count", "wire_roundtrip_digest_mismatches", "feedback_chain_mismatches", "published_history_rewrites", "numpy_alias_violations", "prebranch_missing_count", "prebranch_double_capture_count", "prebranch_stale_count", "prebranch_wrong_frame_count", "snapshot_alias_violations", "actual_input_mutation_violations", "shadow_quarantine_violations", "runtime_gt_read_count")
ARTIFACT_EVIDENCE = "ARTIFACT_VALIDATION.json"
RUNTIME_EVIDENCE = "RUNTIME_GATES_CHECKED.json"
Y00_EVIDENCE = "Y00_REFERENCE_PARITY_CHECKED.json"


def assert_outcome_blind(value: Any) -> None:
    if isinstance(value, Mapping):
        overlap = FORBIDDEN_SCIENTIFIC_FIELDS & set(value)
        if overlap: raise LockedD1Error("VALIDITY_FORBIDDEN_SCIENTIFIC_FIELD: " + ",".join(sorted(overlap)))
        for child in value.values(): assert_outcome_blind(child)
    elif isinstance(value, (list, tuple)):
        for child in value: assert_outcome_blind(child)


def validate_json_prediction(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0: raise LockedD1Error("prediction artifact missing")
    try: value = json.loads(path.read_text())
    except json.JSONDecodeError as exc: raise LockedD1Error("prediction JSON schema invalid") from exc
    if not isinstance(value, (dict, list)): raise LockedD1Error("prediction JSON schema invalid")
    assert_outcome_blind(value)
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def verify_y00_byte_parity(reference: Sequence[Path], packetized: Sequence[Path]) -> dict[str, object]:
    if len(reference) != 2 or len(packetized) != 2: raise LockedD1Error("Y00 parity requires exactly two views")
    checks = []
    for left, right in zip(reference, packetized):
        if not left.is_file() or not right.is_file() or left.read_bytes() != right.read_bytes(): raise LockedD1Error("Y00_REFERENCE_BYTE_PARITY_MISMATCH")
        checks.append({"reference": str(left), "packetized": str(right), "sha256": sha256_file(left)})
    return {"y00_byte_identical": True, "views": checks}


def project_minimal_trace(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    projected = []
    for row in rows:
        if not REQUIRED_TRACE_FIELDS <= set(row): raise LockedD1Error("minimal mechanism trace field missing")
        projected.append({key: row[key] for key in sorted(REQUIRED_TRACE_FIELDS)})
    return projected


def validate_attempt(attempt: Mapping[str, Any], expected_authority: Mapping[str, Any]) -> dict[str, object]:
    assert_outcome_blind(attempt); require_same_authority(expected_authority, attempt.get("authority", {}))
    if attempt.get("state") != "ACCEPTED": raise LockedD1Error("attempt not accepted")
    if not isinstance(attempt.get("prediction_artifacts"), list) or len(attempt["prediction_artifacts"]) != 2: raise LockedD1Error("attempt prediction artifact cardinality invalid")
    return {"attempt_id": attempt.get("attempt_id"), "accepted": True, "prediction_artifact_count": 2}


def _contained(path: Path, root: Path) -> Path:
    try: resolved = path.resolve(strict=True)
    except FileNotFoundError as exc: raise LockedD1Error("attempt artifact provenance missing") from exc
    try: resolved.relative_to(root.resolve(strict=True))
    except ValueError as exc: raise LockedD1Error("attempt artifact escapes accepted attempt root") from exc
    if path.is_symlink(): raise LockedD1Error("accepted attempt artifact symlink forbidden")
    return resolved


def _read_json(path: Path, error: str) -> Any:
    try: value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc: raise LockedD1Error(error) from exc
    assert_outcome_blind(value)
    return value


def _source_mda_entries(record: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    source = record.get("source_mda", {}); rows = source.get("artifacts", []) if isinstance(source, Mapping) else []
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("artifact_role") in ("source_mda_gt_v1", "source_mda_gt_v2"):
            role = str(row["artifact_role"])
            if role in result: raise LockedD1Error("duplicate Source-MDA authority artifact")
            result[role] = row
    return result


def _entry(role: str, path: Path, identifier: str) -> dict[str, object]:
    return {"artifact_role": role, "identifier": identifier, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _context(*, batch_root: Path, population: str, batch_id: str, pair: str, logical_condition: str, attempt_root: Path) -> dict[str, Any]:
    if logical_condition not in LOGICAL_CONDITIONS or pair not in population_pairs(population): raise LockedD1Error("attempt acceptance identity invalid")
    if attempt_root.resolve() != (batch_root / "attempts" / pair / logical_condition / attempt_root.name).resolve() or not attempt_root.name.startswith("attempt_"): raise LockedD1Error("attempt root identity mismatch")
    try: index = int(attempt_root.name.split("_", 1)[1])
    except (IndexError, ValueError) as exc: raise LockedD1Error("attempt index invalid") from exc
    _, authority, conditions = load_sealed_package(batch_root, population, batch_id)
    record = conditions["records"][(pair, logical_condition)]; record_sha = condition_record_sha256(record)
    manifest_path, terminal_path = attempt_root / "attempt_manifest.json", attempt_root / "attempt_terminal_state.json"
    if not manifest_path.is_file() or not terminal_path.is_file(): raise LockedD1Error("attempt validity lifecycle incomplete")
    manifest, terminal = _read_json(manifest_path, "attempt manifest invalid"), _read_json(terminal_path, "attempt terminal invalid")
    bundle = authority["authority_bundle_sha256"]; ma = manifest.get("authority", {}) if isinstance(manifest, Mapping) else {}
    if not isinstance(manifest, Mapping) or manifest.get("attempt_id") != attempt_root.name or manifest.get("pair") != pair or manifest.get("condition") != logical_condition or ma.get("batch_id") != batch_id or ma.get("population") != population or ma.get("authority_bundle_sha256") != bundle or ma.get("condition_record_sha256") != record_sha or manifest.get("state") != "PLANNED" or manifest.get("outcome_embargo") is not True: raise LockedD1Error("attempt manifest authority mismatch")
    if not isinstance(terminal, Mapping) or terminal.get("state") != "PROCESS_COMPLETE_PENDING_VALIDITY": raise LockedD1Error("attempt process not complete")
    return {"batch_root": batch_root, "population": population, "batch_id": batch_id, "pair": pair, "logical_condition": logical_condition, "attempt_root": attempt_root, "attempt_id": attempt_root.name, "attempt_index": index, "authority_bundle_sha256": bundle, "condition_record": record, "condition_record_sha256": record_sha, "attempt_manifest_sha256": sha256_file(manifest_path)}


def _trace(path: Path, role: str) -> None:
    if role == "packet_trace":
        _runtime_packet_trace(path, path.parent)
        return
    rows = []
    try:
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, Mapping): raise LockedD1Error("trace row schema invalid")
                rows.append(row)
    except json.JSONDecodeError as exc: raise LockedD1Error("trace schema invalid") from exc
    assert_outcome_blind(rows)
    if role == "minimal_mechanism_trace": project_minimal_trace(rows)


def _runtime_packet_trace(path: Path, root: Path) -> tuple[Path, int]:
    """Derive the non-scientific terminal packet count from current trace bytes."""
    resolved = _contained(path, root); pending = 0

    def assert_trace_outcome_blind(value: Any) -> None:
        if isinstance(value, Mapping):
            forbidden = (FORBIDDEN_SCIENTIFIC_FIELDS - {"direction"}) & set(value)
            if forbidden:
                raise LockedD1Error("VALIDITY_FORBIDDEN_SCIENTIFIC_FIELD: " + ",".join(sorted(forbidden)))
            for child in value.values(): assert_trace_outcome_blind(child)
        elif isinstance(value, (list, tuple)):
            for child in value: assert_trace_outcome_blind(child)

    try:
        for line in resolved.read_text().splitlines():
            if not line.strip(): continue
            row = json.loads(line)
            if not isinstance(row, Mapping) or not {"capture_frame", "kind"} <= set(row):
                raise LockedD1Error("runtime packet trace schema invalid")
            assert_trace_outcome_blind(row)
            action = row.get("packet_action")
            if action is not None and not isinstance(action, str):
                raise LockedD1Error("runtime packet action schema invalid")
            pending += int(action == "pending_at_end")
    except json.JSONDecodeError as exc:
        raise LockedD1Error("runtime packet trace schema invalid") from exc
    return resolved, pending


def _identity_evidence(value: Mapping[str, Any], c: Mapping[str, Any], state: str) -> None:
    expected = {"state": state, "attempt_id": c["attempt_id"], "pair": c["pair"], "logical_condition": c["logical_condition"], "batch_id": c["batch_id"], "population": c["population"], "authority_bundle_sha256": c["authority_bundle_sha256"], "condition_record_sha256": c["condition_record_sha256"], "scientific_outcome_accessed": False}
    if any(value.get(k) != v for k, v in expected.items()): raise LockedD1Error("evidence authority mismatch")


def produce_artifact_validation(*, batch_root: Path, population: str, batch_id: str, pair: str, logical_condition: str, attempt_root: Path, prediction_artifacts: Sequence[Path], source_mda_gt: Sequence[Path], minimal_mechanism_trace: Path | None = None, packet_trace: Path | None = None, runtime_packet_trace: Path | None = None, runtime_manifests: Sequence[Path] = ()) -> Path:
    """Mechanically validate permitted artifacts, then emit immutable evidence."""
    c = _context(batch_root=batch_root, population=population, batch_id=batch_id, pair=pair, logical_condition=logical_condition, attempt_root=attempt_root)
    if len(prediction_artifacts) != 2 or len(source_mda_gt) != 2: raise LockedD1Error("accepted evaluator artifact cardinality invalid")
    if logical_condition == "Y10_d1" and (minimal_mechanism_trace is None or packet_trace is None): raise LockedD1Error("Y10_d1 primary mechanism traces required")
    if not runtime_manifests: raise LockedD1Error("runtime provenance manifest required")
    entries: list[dict[str, object]] = []
    for i, path in enumerate(prediction_artifacts, 1):
        resolved = _contained(path, attempt_root); validate_json_prediction(resolved); entries.append(_entry("prediction_v%d" % i, resolved, str(resolved.relative_to(attempt_root.resolve()))))
    allowed = _source_mda_entries(c["condition_record"])
    for i, path in enumerate(source_mda_gt, 1):
        role = "source_mda_gt_v%d" % i; resolved = path.resolve(strict=True); declared = allowed.get(role)
        if declared is None or Path(str(declared.get("path", ""))).resolve() != resolved or declared.get("sha256") != sha256_file(resolved): raise LockedD1Error("Source-MDA artifact outside sealed authority")
        entries.append(_entry(role, resolved, str(resolved)))
    for role, path in (("minimal_mechanism_trace", minimal_mechanism_trace), ("packet_trace", packet_trace)):
        if path is not None:
            resolved = _contained(path, attempt_root); _trace(resolved, role); entries.append(_entry(role, resolved, str(resolved.relative_to(attempt_root.resolve()))))
    if runtime_packet_trace is not None:
        resolved, _ = _runtime_packet_trace(runtime_packet_trace, attempt_root)
        entries.append(_entry("runtime_packet_trace", resolved, str(resolved.relative_to(attempt_root.resolve()))))
    for i, path in enumerate(runtime_manifests, 1):
        resolved = _contained(path, attempt_root); value = _read_json(resolved, "runtime manifest schema invalid")
        if not isinstance(value, Mapping): raise LockedD1Error("runtime manifest schema invalid")
        entries.append(_entry("runtime_manifest_%d" % i, resolved, str(resolved.relative_to(attempt_root.resolve()))))
    if len({x["artifact_role"] for x in entries}) != len(entries): raise LockedD1Error("artifact inventory role duplicated")
    inventory = {"artifacts": entries}
    evidence = {"state": "ARTIFACT_VALIDATED", **{k: c[k] for k in ("attempt_id", "pair", "logical_condition", "batch_id", "population", "authority_bundle_sha256", "condition_record_sha256")}, "validated_artifact_entries": entries, "validated_artifact_sha256s": {str(x["artifact_role"]): str(x["sha256"]) for x in entries}, "artifact_inventory_candidate_sha256": sha256_bytes(canonical_json(inventory)), "scientific_outcome_accessed": False}
    path = attempt_root / ARTIFACT_EVIDENCE; atomic_json(path, evidence); return path


def _runtime_values(paths: Sequence[Path], root: Path) -> tuple[list[dict[str, object]], dict[str, Any]]:
    entries, values = [], {}
    gate_keys = set(ZERO_RUNTIME_GATES) | {"logger_read_only", "shadow_export_fields", "prebranch_capture_count", "prebranch_consume_count", "packet_emission_count", "packet_consumption_count", "pending_at_end_count"}
    for i, path in enumerate(paths, 1):
        resolved = _contained(path, root); value = _read_json(resolved, "runtime manifest schema invalid")
        if not isinstance(value, Mapping): raise LockedD1Error("runtime manifest schema invalid")
        for key, item in value.items():
            if key in gate_keys:
                if key in values and values[key] != item: raise LockedD1Error("runtime gate duplicate conflict")
                values[key] = item
        entries.append(_entry("runtime_manifest_%d" % i, resolved, str(resolved.relative_to(root.resolve()))))
    return entries, values


def derive_runtime_gate_results(runtime_manifests: Sequence[Path], attempt_root: Path,
                                runtime_packet_trace: Path | None = None) -> dict[str, Any]:
    """Re-derive the complete frozen gate mapping from current manifest bytes."""
    _, results = _runtime_values(runtime_manifests, attempt_root)
    if runtime_packet_trace is not None:
        _, pending = _runtime_packet_trace(runtime_packet_trace, attempt_root)
        declared = results.get("pending_at_end_count")
        if declared is not None and declared != pending:
            raise LockedD1Error("RUNTIME_PENDING_AT_END_CONFLICT")
        results["pending_at_end_count"] = pending
    return results


def _check_gates(gates: Mapping[str, Any]) -> None:
    required = set(ZERO_RUNTIME_GATES) | {"logger_read_only", "shadow_export_fields", "prebranch_capture_count", "prebranch_consume_count", "packet_emission_count", "packet_consumption_count", "pending_at_end_count"}
    if not required <= set(gates): raise LockedD1Error("runtime hard gate missing")
    for key in ZERO_RUNTIME_GATES:
        if gates.get(key) != 0: raise LockedD1Error("runtime hard gate failed: " + key)
    if gates.get("logger_read_only") != 1: raise LockedD1Error("runtime hard gate failed: logger_read_only")
    if gates.get("shadow_export_fields") != ["membership"]: raise LockedD1Error("runtime hard gate failed: shadow_export_fields")
    if gates.get("prebranch_capture_count") != gates.get("prebranch_consume_count"): raise LockedD1Error("runtime hard gate failed: prebranch conservation")
    if gates.get("packet_emission_count") != gates.get("packet_consumption_count", -1) + gates.get("pending_at_end_count", -1): raise LockedD1Error("runtime hard gate failed: packet conservation")


def produce_runtime_gates_checked(*, batch_root: Path, population: str, batch_id: str, pair: str, logical_condition: str, attempt_root: Path, runtime_manifests: Sequence[Path], runtime_packet_trace: Path | None = None) -> Path:
    c = _context(batch_root=batch_root, population=population, batch_id=batch_id, pair=pair, logical_condition=logical_condition, attempt_root=attempt_root)
    if not runtime_manifests: raise LockedD1Error("runtime provenance manifest required")
    entries, _ = _runtime_values(runtime_manifests, attempt_root)
    gates = derive_runtime_gate_results(runtime_manifests, attempt_root, runtime_packet_trace); _check_gates(gates)
    pending_evidence: dict[str, object] = {"source": "RUNTIME_MANIFEST", "pending_at_end_count": gates["pending_at_end_count"]}
    if runtime_packet_trace is not None:
        trace, pending = _runtime_packet_trace(runtime_packet_trace, attempt_root)
        pending_evidence = {"source": "PACKET_TRACE_DERIVED", "identifier": str(trace.relative_to(attempt_root.resolve())), "sha256": sha256_file(trace), "bytes": trace.stat().st_size, "pending_at_end_count": pending}
    evidence = {"state": "RUNTIME_GATES_CHECKED", **{k: c[k] for k in ("attempt_id", "pair", "logical_condition", "batch_id", "population", "authority_bundle_sha256", "condition_record_sha256")}, "checked_runtime_manifest_sha256s": {str(x["identifier"]): str(x["sha256"]) for x in entries}, "pending_at_end_evidence": pending_evidence, "gate_results": gates, "all_mandatory_gates_pass": True, "scientific_outcome_accessed": False}
    path = attempt_root / RUNTIME_EVIDENCE; atomic_json(path, evidence); return path


def produce_y00_reference_parity(*, batch_root: Path, population: str, batch_id: str, pair: str, attempt_root: Path, reference_attempt_root: Path, reference_artifacts: Sequence[Path], packetized_artifacts: Sequence[Path]) -> Path:
    c = _context(batch_root=batch_root, population=population, batch_id=batch_id, pair=pair, logical_condition="Y00", attempt_root=attempt_root)
    expected = batch_root / "references" / pair / "Y00" / reference_attempt_root.name
    if reference_attempt_root.resolve() != expected.resolve() or reference_attempt_root.resolve() == attempt_root.resolve(): raise LockedD1Error("Y00 reference attempt identity mismatch")
    refs, packets = [_contained(p, reference_attempt_root) for p in reference_artifacts], [_contained(p, attempt_root) for p in packetized_artifacts]
    verify_y00_byte_parity(refs, packets)
    evidence = {"state": "Y00_REFERENCE_PARITY_CHECKED", **{k: c[k] for k in ("attempt_id", "pair", "logical_condition", "batch_id", "population", "authority_bundle_sha256", "condition_record_sha256")}, "reference_attempt_identity": reference_attempt_root.name, "reference_artifact_identifiers": [str(p.relative_to(reference_attempt_root.resolve())) for p in refs], "packetized_artifact_identifiers": [str(p.relative_to(attempt_root.resolve())) for p in packets], "reference_view1_sha256": sha256_file(refs[0]), "reference_view2_sha256": sha256_file(refs[1]), "packetized_view1_sha256": sha256_file(packets[0]), "packetized_view2_sha256": sha256_file(packets[1]), "y00_reference_parity_checked": True, "y00_reference_parity_pass": True, "scientific_outcome_accessed": False}
    path = attempt_root / Y00_EVIDENCE; atomic_json(path, evidence); return path


def _verified_evidence(path: Path, c: Mapping[str, Any], state: str) -> tuple[dict[str, Any], str]:
    value = _read_json(_contained(path, c["attempt_root"]), "evidence schema invalid")
    if not isinstance(value, Mapping): raise LockedD1Error("evidence schema invalid")
    expected = {"state": state, "attempt_id": c["attempt_id"], "pair": c["pair"], "logical_condition": c["logical_condition"], "batch_id": c["batch_id"], "population": c["population"], "authority_bundle_sha256": c["authority_bundle_sha256"], "condition_record_sha256": c["condition_record_sha256"], "scientific_outcome_accessed": False}
    if any(value.get(k) != v for k, v in expected.items()): raise LockedD1Error("evidence authority mismatch")
    return dict(value), sha256_file(path)


def _verify_inventory(entries: Sequence[Mapping[str, Any]], c: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    roles: dict[str, dict[str, Any]] = {}; allowed = _source_mda_entries(c["condition_record"])
    for entry in entries:
        role, identifier = entry.get("artifact_role"), entry.get("identifier")
        if not isinstance(role, str) or role in roles or not isinstance(identifier, str): raise LockedD1Error("artifact inventory entry invalid")
        if role.startswith("source_mda_gt_v"):
            path = Path(identifier).resolve(strict=True); declared = allowed.get(role)
            if declared is None or Path(str(declared.get("path", ""))).resolve() != path: raise LockedD1Error("Source-MDA inventory authority mismatch")
        else: path = _contained(c["attempt_root"] / identifier, c["attempt_root"])
        if entry.get("sha256") != sha256_file(path) or entry.get("bytes") != path.stat().st_size: raise LockedD1Error("accepted artifact digest mismatch")
        roles[role] = {**dict(entry), "path": path}
    required = {"prediction_v1", "prediction_v2", "source_mda_gt_v1", "source_mda_gt_v2"}
    if c["logical_condition"] == "Y10_d1": required |= {"minimal_mechanism_trace", "packet_trace"}
    if not required <= set(roles) or not any(key.startswith("runtime_manifest_") for key in roles): raise LockedD1Error("accepted artifact inventory incomplete")
    return roles


def _verify_artifact(value: Mapping[str, Any], c: Mapping[str, Any]) -> list[dict[str, Any]]:
    entries = value.get("validated_artifact_entries")
    if not isinstance(entries, list) or value.get("artifact_inventory_candidate_sha256") != sha256_bytes(canonical_json({"artifacts": entries})): raise LockedD1Error("artifact validation evidence closure mismatch")
    if value.get("validated_artifact_sha256s") != {str(x.get("artifact_role")): str(x.get("sha256")) for x in entries if isinstance(x, Mapping)}: raise LockedD1Error("artifact validation evidence digest mismatch")
    _verify_inventory(entries, c); return [dict(x) for x in entries]


def _verify_runtime(value: Mapping[str, Any], runtime_artifacts: Sequence[Mapping[str, Any]], artifact_roles: Mapping[str, Mapping[str, Any]], c: Mapping[str, Any]) -> None:
    if value.get("all_mandatory_gates_pass") is not True or not isinstance(value.get("checked_runtime_manifest_sha256s"), Mapping) or not isinstance(value.get("gate_results"), Mapping) or not isinstance(value.get("pending_at_end_evidence"), Mapping): raise LockedD1Error("runtime gate evidence invalid")
    expected_hashes: dict[str, str] = {}
    paths = []
    for artifact in runtime_artifacts:
        identifier = artifact.get("identifier")
        if not isinstance(identifier, str) or identifier in expected_hashes:
            raise LockedD1Error("RUNTIME_MANIFEST_SET_MISMATCH")
        path = _contained(c["attempt_root"] / identifier, c["attempt_root"])
        expected_hashes[identifier] = sha256_file(path)
        paths.append(path)
    evidence_hashes = value["checked_runtime_manifest_sha256s"]
    if not expected_hashes or set(evidence_hashes) != set(expected_hashes):
        raise LockedD1Error("RUNTIME_MANIFEST_SET_MISMATCH")
    if dict(evidence_hashes) != expected_hashes:
        raise LockedD1Error("RUNTIME_MANIFEST_SHA_MISMATCH")
    pending = value["pending_at_end_evidence"]; source = pending.get("source")
    trace_path = None
    if source == "PACKET_TRACE_DERIVED":
        artifact = artifact_roles.get("runtime_packet_trace")
        if artifact is None or pending.get("identifier") != artifact.get("identifier"):
            raise LockedD1Error("RUNTIME_PACKET_TRACE_BINDING_MISMATCH")
        trace_path = _contained(c["attempt_root"] / str(pending["identifier"]), c["attempt_root"])
        if pending.get("sha256") != sha256_file(trace_path) or pending.get("bytes") != trace_path.stat().st_size:
            raise LockedD1Error("RUNTIME_PACKET_TRACE_SHA_MISMATCH")
    elif source != "RUNTIME_MANIFEST" or "runtime_packet_trace" in artifact_roles:
        raise LockedD1Error("RUNTIME_PENDING_AT_END_SOURCE_MISMATCH")
    rederived = derive_runtime_gate_results(paths, c["attempt_root"], trace_path)
    if pending.get("pending_at_end_count") != rederived.get("pending_at_end_count"):
        raise LockedD1Error("RUNTIME_PENDING_AT_END_RESULT_MISMATCH")
    if dict(value["gate_results"]) != rederived:
        raise LockedD1Error("RUNTIME_GATE_RESULT_MISMATCH")
    _check_gates(rederived)


def _verify_y00_parity(value: Mapping[str, Any], c: Mapping[str, Any], entries: Sequence[Mapping[str, Any]]) -> None:
    reference = c["batch_root"] / "references" / c["pair"] / "Y00" / str(value.get("reference_attempt_identity", ""))
    if not reference.is_dir() or reference.resolve() == c["attempt_root"].resolve(): raise LockedD1Error("Y00 reference parity invalid")
    refs = [_contained(reference / str(item), reference) for item in value.get("reference_artifact_identifiers", [])]
    packets = [_contained(c["attempt_root"] / str(item), c["attempt_root"]) for item in value.get("packetized_artifact_identifiers", [])]
    if len(refs) != 2 or len(packets) != 2: raise LockedD1Error("Y00 reference parity invalid")
    verify_y00_byte_parity(refs, packets)
    expected_packets = [next((x for x in entries if x.get("artifact_role") == "prediction_v%d" % view), None) for view in (1, 2)]
    if any(item is None for item in expected_packets) or [str(x["identifier"]) for x in expected_packets] != [str(x) for x in value["packetized_artifact_identifiers"]]: raise LockedD1Error("Y00 packetized artifact binding invalid")
    if [sha256_file(x) for x in refs] != [value.get("reference_view1_sha256"), value.get("reference_view2_sha256")] or [sha256_file(x) for x in packets] != [value.get("packetized_view1_sha256"), value.get("packetized_view2_sha256")]: raise LockedD1Error("Y00 parity evidence digest mismatch")


def seal_attempt_acceptance(*, batch_root: Path, population: str, batch_id: str, pair: str, logical_condition: str, attempt_root: Path, artifact_validation_evidence: Path, runtime_gate_evidence: Path, y00_parity_evidence: Path | None = None) -> Path:
    """Bind mechanical evidence; callers cannot provide a validity verdict."""
    c = _context(batch_root=batch_root, population=population, batch_id=batch_id, pair=pair, logical_condition=logical_condition, attempt_root=attempt_root)
    artifact, artifact_sha = _verified_evidence(artifact_validation_evidence, c, "ARTIFACT_VALIDATED")
    runtime, runtime_sha = _verified_evidence(runtime_gate_evidence, c, "RUNTIME_GATES_CHECKED")
    entries = _verify_artifact(artifact, c); roles = _verify_inventory(entries, c)
    runtime_artifacts = [entry for entry in entries if str(entry.get("artifact_role", "")).startswith("runtime_manifest_")]
    _verify_runtime(runtime, runtime_artifacts, roles, c); parity_sha = None
    if logical_condition == "Y00":
        if y00_parity_evidence is None: raise LockedD1Error("Y00 reference parity incomplete")
        parity, parity_sha = _verified_evidence(y00_parity_evidence, c, "Y00_REFERENCE_PARITY_CHECKED")
        if parity.get("y00_reference_parity_checked") is not True or parity.get("y00_reference_parity_pass") is not True: raise LockedD1Error("Y00 reference parity invalid")
        _verify_y00_parity(parity, c, entries)
    elif y00_parity_evidence is not None: raise LockedD1Error("Y00 parity evidence is not applicable")
    staging, final = attempt_root / ".acceptance.incomplete", attempt_root / "acceptance"
    if staging.exists() or final.exists(): raise LockedD1Error("acceptance transaction collision")
    staging.mkdir()
    try:
        inventory_sha = atomic_json(staging / "artifact_inventory.json", {"artifacts": entries})
        if inventory_sha != artifact["artifact_inventory_candidate_sha256"]: raise LockedD1Error("artifact inventory closure changed")
        seal = {"state": "ACCEPTED_VALIDITY", **{k: c[k] for k in ("attempt_id", "attempt_index", "batch_id", "pair", "logical_condition", "authority_bundle_sha256", "condition_record_sha256", "attempt_manifest_sha256")}, "population_name": population, "split": population, "artifact_inventory_sha256": inventory_sha, "artifact_validation_evidence_sha256": artifact_sha, "runtime_gate_evidence_sha256": runtime_sha, "scientific_outcome_accessed": False}
        if parity_sha: seal["y00_parity_evidence_sha256"] = parity_sha
        else: seal["y00_parity_evidence_state"] = "Y00_PARITY_NOT_APPLICABLE"
        atomic_json(staging / "ACCEPTANCE_SEAL.json", seal); staging.replace(final)
    except Exception:
        import shutil; shutil.rmtree(staging, ignore_errors=True); raise
    return final / "ACCEPTANCE_SEAL.json"


def verify_acceptance_seal(*, batch_root: Path, population: str, batch_id: str, pair: str, logical_condition: str, attempt_root: Path, condition_record: Mapping[str, Any], authority_bundle_sha256: str) -> dict[str, Any]:
    c = _context(batch_root=batch_root, population=population, batch_id=batch_id, pair=pair, logical_condition=logical_condition, attempt_root=attempt_root)
    if c["condition_record"] != condition_record or c["authority_bundle_sha256"] != authority_bundle_sha256: raise LockedD1Error("acceptance verification authority mismatch")
    seal_path, inventory_path = attempt_root / "acceptance" / "ACCEPTANCE_SEAL.json", attempt_root / "acceptance" / "artifact_inventory.json"
    if not seal_path.is_file() or not inventory_path.is_file(): raise LockedD1Error("acceptance seal provenance missing")
    seal = _read_json(seal_path, "acceptance seal invalid")
    if not isinstance(seal, Mapping): raise LockedD1Error("acceptance seal invalid")
    expected = {"state": "ACCEPTED_VALIDITY", **{k: c[k] for k in ("attempt_id", "attempt_index", "batch_id", "pair", "logical_condition", "authority_bundle_sha256", "condition_record_sha256", "attempt_manifest_sha256")}, "population_name": population, "split": population, "artifact_inventory_sha256": sha256_file(inventory_path), "scientific_outcome_accessed": False}
    if any(seal.get(k) != v for k, v in expected.items()): raise LockedD1Error("acceptance seal binding mismatch")
    artifact, artifact_sha = _verified_evidence(attempt_root / ARTIFACT_EVIDENCE, c, "ARTIFACT_VALIDATED")
    runtime, runtime_sha = _verified_evidence(attempt_root / RUNTIME_EVIDENCE, c, "RUNTIME_GATES_CHECKED")
    if seal.get("artifact_validation_evidence_sha256") != artifact_sha or seal.get("runtime_gate_evidence_sha256") != runtime_sha: raise LockedD1Error("acceptance evidence digest mismatch")
    entries = _verify_artifact(artifact, c); roles = _verify_inventory(entries, c)
    runtime_artifacts = [entry for entry in entries if str(entry.get("artifact_role", "")).startswith("runtime_manifest_")]
    _verify_runtime(runtime, runtime_artifacts, roles, c)
    inventory = _read_json(inventory_path, "artifact inventory invalid")
    if not isinstance(inventory, Mapping) or inventory.get("artifacts") != entries: raise LockedD1Error("artifact inventory invalid")
    if logical_condition == "Y00":
        parity, parity_sha = _verified_evidence(attempt_root / Y00_EVIDENCE, c, "Y00_REFERENCE_PARITY_CHECKED")
        if seal.get("y00_parity_evidence_sha256") != parity_sha or parity.get("y00_reference_parity_pass") is not True: raise LockedD1Error("Y00 reference parity invalid")
        _verify_y00_parity(parity, c, entries)
    elif seal.get("y00_parity_evidence_state") != "Y00_PARITY_NOT_APPLICABLE": raise LockedD1Error("non-Y00 parity state invalid")
    return {"seal": dict(seal), "seal_sha256": sha256_file(seal_path), "inventory": dict(inventory), "inventory_sha256": sha256_file(inventory_path), "artifacts": roles, "attempt_manifest_sha256": c["attempt_manifest_sha256"]}


def seal_measurement_validity(*, batch_root: Path, population: str, batch_id: str) -> Path:
    _, authority, conditions = load_sealed_package(batch_root, population, batch_id); bundle = authority["authority_bundle_sha256"]; selected = []
    for pair in population_pairs(population):
        for condition in LOGICAL_CONDITIONS:
            accepted = []
            for root in (batch_root / "attempts" / pair / condition).glob("attempt_*"):
                if (root / "acceptance" / "ACCEPTANCE_SEAL.json").is_file():
                    checked = verify_acceptance_seal(batch_root=batch_root, population=population, batch_id=batch_id, pair=pair, logical_condition=condition, attempt_root=root, condition_record=conditions["records"][(pair, condition)], authority_bundle_sha256=bundle)
                    accepted.append((checked["seal"]["attempt_index"], root, checked))
            if not accepted: raise LockedD1Error("whole-population accepted attempt missing")
            accepted.sort(key=lambda x: x[0]); _, root, checked = accepted[0]
            selected.append({"pair": pair, "logical_condition": condition, "selected_attempt_id": root.name, "selected_attempt_index": checked["seal"]["attempt_index"], "selected_attempt_manifest_sha256": checked["attempt_manifest_sha256"], "acceptance_seal_sha256": checked["seal_sha256"], "condition_record_sha256": checked["seal"]["condition_record_sha256"], "artifact_inventory_sha256": checked["inventory_sha256"], "authority_bundle_sha256": bundle})
    path = batch_root / "measurement_validity_manifest.json"; atomic_json(path, {"state": "MEASUREMENT_VALIDITY_PASS", "population": population, "batch_id": batch_id, "authority_bundle_sha256": bundle, "scientific_outcome_accessed": False, "selected_attempts": selected}); return path
