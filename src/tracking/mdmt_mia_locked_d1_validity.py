"""Outcome-blind validity auditor.  It must never import evaluation code."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tracking.mdmt_mia_locked_d1_package import (LockedD1Error, LOGICAL_CONDITIONS, atomic_json,
    canonical_json, condition_record_sha256, load_sealed_package, population_pairs,
    sha256_bytes, sha256_file, require_same_authority)

FORBIDDEN_SCIENTIFIC_FIELDS = frozenset(("mda", "D_ID", "R_edge", "C_comp", "bootstrap_ci", "direction",
                                         "mechanism_positive", "gate_a", "gate_b", "gate_c", "gate_d", "gate_e", "gate_f"))
REQUIRED_TRACE_FIELDS = frozenset(("capture_frame", "view_id", "pre_branch_row_index", "delay_membership",
                                   "cf_membership", "high_score_triggered", "high_score_bbox_written"))


def assert_outcome_blind(value: Any) -> None:
    if isinstance(value, Mapping):
        overlap = FORBIDDEN_SCIENTIFIC_FIELDS & set(value)
        if overlap:
            raise LockedD1Error("VALIDITY_FORBIDDEN_SCIENTIFIC_FIELD: " + ",".join(sorted(overlap)))
        for child in value.values():
            assert_outcome_blind(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_outcome_blind(child)


def validate_json_prediction(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        raise LockedD1Error("prediction artifact missing")
    value = json.loads(path.read_text())
    if not isinstance(value, (dict, list)):
        raise LockedD1Error("prediction JSON schema invalid")
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def verify_y00_byte_parity(reference: Sequence[Path], packetized: Sequence[Path]) -> dict[str, object]:
    if len(reference) != 2 or len(packetized) != 2:
        raise LockedD1Error("Y00 parity requires exactly two views")
    checks = []
    for left, right in zip(reference, packetized):
        if not left.is_file() or not right.is_file() or left.read_bytes() != right.read_bytes():
            raise LockedD1Error("Y00_REFERENCE_BYTE_PARITY_MISMATCH")
        checks.append({"reference": str(left), "packetized": str(right), "sha256": sha256_file(left)})
    return {"y00_byte_identical": True, "views": checks}


def project_minimal_trace(candidate_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    projected = []
    for row in candidate_rows:
        if not REQUIRED_TRACE_FIELDS <= set(row):
            raise LockedD1Error("minimal mechanism trace field missing")
        projected.append({key: row[key] for key in sorted(REQUIRED_TRACE_FIELDS)})
    return projected


def validate_attempt(attempt: Mapping[str, Any], expected_authority: Mapping[str, Any]) -> dict[str, object]:
    assert_outcome_blind(attempt)
    require_same_authority(expected_authority, attempt.get("authority", {}))
    if attempt.get("state") != "ACCEPTED":
        raise LockedD1Error("attempt not accepted")
    artifacts = attempt.get("prediction_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 2:
        raise LockedD1Error("attempt prediction artifact cardinality invalid")
    return {"attempt_id": attempt.get("attempt_id"), "accepted": True, "prediction_artifact_count": 2}


def _contained(path: Path, root: Path) -> Path:
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise LockedD1Error("attempt artifact escapes accepted attempt root") from exc
    if path.is_symlink():
        raise LockedD1Error("accepted attempt artifact symlink forbidden")
    return resolved


def _source_mda_entries(condition_record: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    source = condition_record.get("source_mda", {})
    rows = source.get("artifacts", []) if isinstance(source, Mapping) else []
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or row.get("artifact_role") not in ("source_mda_gt_v1", "source_mda_gt_v2"):
            continue
        role = str(row["artifact_role"])
        if role in result:
            raise LockedD1Error("duplicate Source-MDA authority artifact")
        result[role] = row
    return result


def _inventory_entry(role: str, path: Path, *, identifier: str) -> dict[str, object]:
    return {"artifact_role": role, "identifier": identifier, "sha256": sha256_file(path),
            "bytes": path.stat().st_size}


def seal_attempt_acceptance(*, batch_root: Path, population: str, batch_id: str, pair: str,
                            logical_condition: str, attempt_root: Path,
                            prediction_artifacts: Sequence[Path], source_mda_gt: Sequence[Path],
                            minimal_mechanism_trace: Path | None = None,
                            packet_trace: Path | None = None,
                            runtime_manifests: Sequence[Path] = (),
                            artifact_validated: bool, runtime_gates_checked: bool,
                            y00_reference_parity_checked: bool | None = None) -> Path:
    """Create the immutable, outcome-blind terminal acceptance seal."""
    if logical_condition not in LOGICAL_CONDITIONS or pair not in population_pairs(population):
        raise LockedD1Error("attempt acceptance identity invalid")
    expected_root = batch_root / "attempts" / pair / logical_condition / attempt_root.name
    if attempt_root.resolve() != expected_root.resolve() or not attempt_root.name.startswith("attempt_"):
        raise LockedD1Error("attempt root identity mismatch")
    try:
        attempt_index = int(attempt_root.name.split("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise LockedD1Error("attempt index invalid") from exc
    package, authority, conditions = load_sealed_package(batch_root, population, batch_id)
    record = conditions["records"][(pair, logical_condition)]
    record_sha = condition_record_sha256(record)
    manifest_path = attempt_root / "attempt_manifest.json"
    terminal_path = attempt_root / "attempt_terminal_state.json"
    if not manifest_path.is_file() or not terminal_path.is_file():
        raise LockedD1Error("attempt validity lifecycle incomplete")
    manifest = json.loads(manifest_path.read_text())
    terminal = json.loads(terminal_path.read_text())
    assert_outcome_blind(manifest); assert_outcome_blind(terminal)
    expected_authority = authority["authority_bundle_sha256"]
    manifest_authority = manifest.get("authority", {})
    if (manifest.get("attempt_id") != attempt_root.name or manifest.get("pair") != pair
            or manifest.get("condition") != logical_condition
            or manifest_authority.get("batch_id") != batch_id
            or manifest_authority.get("population") != population
            or manifest_authority.get("authority_bundle_sha256") != expected_authority
            or manifest_authority.get("condition_record_sha256") != record_sha
            or manifest.get("state") != "PLANNED" or manifest.get("outcome_embargo") is not True):
        raise LockedD1Error("attempt manifest authority mismatch")
    if terminal.get("state") != "PROCESS_COMPLETE_PENDING_VALIDITY":
        raise LockedD1Error("attempt process not complete")
    if not artifact_validated or not runtime_gates_checked:
        raise LockedD1Error("outcome-blind validity gates incomplete")
    if logical_condition == "Y00" and y00_reference_parity_checked is not True:
        raise LockedD1Error("Y00 reference parity incomplete")
    if len(prediction_artifacts) != 2 or len(source_mda_gt) != 2:
        raise LockedD1Error("accepted evaluator artifact cardinality invalid")
    entries = []
    for index, path in enumerate(prediction_artifacts, 1):
        resolved = _contained(path, attempt_root)
        validate_json_prediction(resolved)
        entries.append(_inventory_entry("prediction_v%d" % index, resolved,
                                        identifier=str(resolved.relative_to(attempt_root.resolve()))))
    allowed_gt = _source_mda_entries(record)
    for index, path in enumerate(source_mda_gt, 1):
        role = "source_mda_gt_v%d" % index
        resolved = path.resolve(strict=True); declaration = allowed_gt.get(role)
        if (declaration is None or Path(str(declaration.get("path", ""))).resolve() != resolved
                or declaration.get("sha256") != sha256_file(resolved)):
            raise LockedD1Error("Source-MDA artifact outside sealed authority")
        entries.append(_inventory_entry(role, resolved, identifier=str(resolved)))
    if logical_condition == "Y10_d1" and (minimal_mechanism_trace is None or packet_trace is None):
        raise LockedD1Error("Y10_d1 primary mechanism traces required")
    if not runtime_manifests:
        raise LockedD1Error("runtime provenance manifest required")
    for role, path in (("minimal_mechanism_trace", minimal_mechanism_trace),
                       ("packet_trace", packet_trace)):
        if path is not None:
            resolved = _contained(path, attempt_root)
            trace_rows = []
            for line in resolved.read_text().splitlines():
                if line.strip():
                    row = json.loads(line)
                    if not isinstance(row, Mapping): raise LockedD1Error("trace row schema invalid")
                    trace_rows.append(row)
            assert_outcome_blind(trace_rows)
            if role == "minimal_mechanism_trace":
                project_minimal_trace(trace_rows)
            elif any(not {"capture_frame", "kind", "packet_action"} <= set(row) for row in trace_rows):
                raise LockedD1Error("packet trace field missing")
            entries.append(_inventory_entry(role, resolved,
                                            identifier=str(resolved.relative_to(attempt_root.resolve()))))
    for index, path in enumerate(runtime_manifests, 1):
        resolved = _contained(path, attempt_root)
        runtime_value = json.loads(resolved.read_text()); assert_outcome_blind(runtime_value)
        if not isinstance(runtime_value, Mapping): raise LockedD1Error("runtime manifest schema invalid")
        entries.append(_inventory_entry("runtime_manifest_%d" % index, resolved,
                                        identifier=str(resolved.relative_to(attempt_root.resolve()))))
    roles = [entry["artifact_role"] for entry in entries]
    if len(roles) != len(set(roles)):
        raise LockedD1Error("artifact inventory role duplicated")
    staging = attempt_root / ".acceptance.incomplete"; final = attempt_root / "acceptance"
    if staging.exists() or final.exists(): raise LockedD1Error("acceptance transaction collision")
    staging.mkdir()
    try:
        inventory_path = staging / "artifact_inventory.json"
        inventory_sha = atomic_json(inventory_path, {"artifacts": entries})
        seal_path = staging / "ACCEPTANCE_SEAL.json"
        atomic_json(seal_path, {"state": "ACCEPTED_VALIDITY", "attempt_id": attempt_root.name,
            "attempt_index": attempt_index, "batch_id": batch_id, "population_name": population,
            "split": population, "pair": pair, "logical_condition": logical_condition,
            "authority_bundle_sha256": expected_authority, "condition_record_sha256": record_sha,
            "attempt_manifest_sha256": sha256_file(manifest_path),
            "artifact_inventory_sha256": inventory_sha, "scientific_outcome_accessed": False})
        staging.replace(final)
    except Exception:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return final / "ACCEPTANCE_SEAL.json"


def verify_acceptance_seal(*, batch_root: Path, population: str, batch_id: str, pair: str,
                           logical_condition: str, attempt_root: Path,
                           condition_record: Mapping[str, Any], authority_bundle_sha256: str) -> dict[str, Any]:
    seal_path = attempt_root / "acceptance" / "ACCEPTANCE_SEAL.json"
    inventory_path = attempt_root / "acceptance" / "artifact_inventory.json"
    manifest_path = attempt_root / "attempt_manifest.json"
    if not all(path.is_file() for path in (seal_path, inventory_path, manifest_path)):
        raise LockedD1Error("acceptance seal provenance missing")
    seal = json.loads(seal_path.read_text()); inventory = json.loads(inventory_path.read_text())
    expected = {"state": "ACCEPTED_VALIDITY", "batch_id": batch_id, "population_name": population,
                "pair": pair, "logical_condition": logical_condition,
                "authority_bundle_sha256": authority_bundle_sha256,
                "condition_record_sha256": condition_record_sha256(condition_record),
                "attempt_manifest_sha256": sha256_file(manifest_path),
                "artifact_inventory_sha256": sha256_file(inventory_path),
                "scientific_outcome_accessed": False}
    if any(seal.get(key) != value for key, value in expected.items()):
        raise LockedD1Error("acceptance seal binding mismatch")
    try:
        attempt_index = int(attempt_root.name.split("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise LockedD1Error("accepted attempt index invalid") from exc
    if seal.get("attempt_id") != attempt_root.name or seal.get("attempt_index") != attempt_index:
        raise LockedD1Error("acceptance identity mismatch")
    artifacts = inventory.get("artifacts")
    if not isinstance(artifacts, list):
        raise LockedD1Error("artifact inventory invalid")
    role_map = {}
    allowed_gt = _source_mda_entries(condition_record)
    for entry in artifacts:
        role = entry.get("artifact_role"); identifier = entry.get("identifier")
        if not role or role in role_map or not isinstance(identifier, str):
            raise LockedD1Error("artifact inventory entry invalid")
        if role.startswith("source_mda_gt_v"):
            path = Path(identifier).resolve(strict=True); declaration = allowed_gt.get(role)
            if declaration is None or Path(str(declaration.get("path", ""))).resolve() != path:
                raise LockedD1Error("Source-MDA inventory authority mismatch")
        else:
            path = _contained(attempt_root / identifier, attempt_root)
        if entry.get("sha256") != sha256_file(path) or entry.get("bytes") != path.stat().st_size:
            raise LockedD1Error("accepted artifact digest mismatch")
        role_map[role] = {**entry, "path": path}
    required = {"prediction_v1", "prediction_v2", "source_mda_gt_v1", "source_mda_gt_v2"}
    if logical_condition == "Y10_d1":
        required |= {"minimal_mechanism_trace", "packet_trace"}
    if not required <= set(role_map):
        raise LockedD1Error("accepted artifact inventory incomplete")
    if not any(role.startswith("runtime_manifest_") for role in role_map):
        raise LockedD1Error("runtime provenance inventory incomplete")
    return {"seal": seal, "seal_sha256": sha256_file(seal_path), "inventory": inventory,
            "inventory_sha256": sha256_file(inventory_path), "artifacts": role_map,
            "attempt_manifest_sha256": sha256_file(manifest_path)}


def seal_measurement_validity(*, batch_root: Path, population: str, batch_id: str) -> Path:
    """Select the first accepted attempt for every cell and seal population provenance."""
    _, authority, conditions = load_sealed_package(batch_root, population, batch_id)
    authority_sha = authority["authority_bundle_sha256"]; selected = []
    for pair in population_pairs(population):
        for condition in LOGICAL_CONDITIONS:
            accepted = []
            cell_root = batch_root / "attempts" / pair / condition
            for attempt_root in cell_root.glob("attempt_*"):
                if (attempt_root / "acceptance" / "ACCEPTANCE_SEAL.json").is_file():
                    verified = verify_acceptance_seal(batch_root=batch_root, population=population,
                        batch_id=batch_id, pair=pair, logical_condition=condition,
                        attempt_root=attempt_root, condition_record=conditions["records"][(pair, condition)],
                        authority_bundle_sha256=authority_sha)
                    accepted.append((verified["seal"]["attempt_index"], attempt_root, verified))
            if not accepted:
                raise LockedD1Error("whole-population accepted attempt missing")
            accepted.sort(key=lambda item: item[0]); _, attempt_root, verified = accepted[0]
            selected.append({"pair": pair, "logical_condition": condition,
                "selected_attempt_id": attempt_root.name,
                "selected_attempt_index": verified["seal"]["attempt_index"],
                "selected_attempt_manifest_sha256": verified["attempt_manifest_sha256"],
                "acceptance_seal_sha256": verified["seal_sha256"],
                "condition_record_sha256": verified["seal"]["condition_record_sha256"],
                "artifact_inventory_sha256": verified["inventory_sha256"],
                "authority_bundle_sha256": authority_sha})
    path = batch_root / "measurement_validity_manifest.json"
    atomic_json(path, {"state": "MEASUREMENT_VALIDITY_PASS", "population": population,
        "batch_id": batch_id, "authority_bundle_sha256": authority_sha,
        "scientific_outcome_accessed": False, "selected_attempts": selected})
    return path
