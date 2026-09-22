"""Independent fail-closed validator for C7 Batch B artifacts.

This module does not import the Batch B producer.  It independently rebuilds
window-domain counts, the four gates, the qualified subset, and selection.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .mdmt_mia_c7_batch_b_schema import (
    BATCH_A_SEMANTICS_SCHEMA,
    BATCH_A_VALIDATION_SCHEMA,
    BATCH_A_FREEZE_AUTHORITY,
    BATCH_B_SCHEMA_VERSION,
    CAPACITY_DOMAIN,
    CELL_AGGREGATE_SCHEMA,
    CELL_ARTIFACTS_BEFORE_COMMIT,
    CELL_AUTHORITATIVE_FILES,
    CELL_COMMIT_SCHEMA,
    CELL_INVENTORY_SCHEMA,
    CELL_MANIFEST_SCHEMA,
    CELL_QUALIFICATION_SCHEMA,
    CELL_SEAL_SCHEMA,
    CELL_VALIDATION_SCHEMA,
    CONDITIONAL_MULTIPLIER,
    FORBIDDEN_OUTCOME_FAMILIES,
    FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY,
    GLOBAL_MULTIPLIER,
    MANIFEST_SCHEMA,
    NO_STALE_VALIDATION_SCHEMA,
    NO_STALE_RAW_OBSERVATION_SCHEMA,
    PACKAGE_ARTIFACTS_BEFORE_COMMIT,
    PACKAGE_AUTHORITATIVE_FILES,
    PACKAGE_COMMIT_SCHEMA,
    PACKAGE_INVENTORY_SCHEMA,
    PACKAGE_SEAL_SCHEMA,
    PACKAGE_VALIDATION_SCHEMA,
    PAIR_DOMAIN,
    ALLOWED_PARENT_ENV_KEYS,
    REGISTERED_CELL_IDS,
    REGISTERED_SOURCE_RELATIVE_PATHS,
    SELECTION_SCHEMA,
    SOURCE_HASH_KEYS,
    T_COUNT,
    T_DENOMINATOR,
    VALIDATED_WINDOW_SCHEMA,
    VERIFIED_CELL_INVENTORY_SCHEMA,
    authority_bindings,
    authorized_frame_domains,
    canonical_sha256,
    registered_cells,
    sha256_file,
)
from .mdmt_mia_c7_validator import C7ValidationError, validate_core_evidence
from .mdmt_mia_c7_census import (
    ReceiverStateEvidence,
    SUPPRESSIBLE_STALE,
    evaluate_id_state_applicability,
)


class C7BatchBValidationError(ValueError):
    """Raised when persisted Batch B evidence cannot be independently proven."""


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
_SELECTION_KEYS = frozenset({
    "schema_version", "run_id", "manifest_sha256",
    "all_21_complete_attestation", "qualified_subset", "comparison_trace",
    "selection_outcome", "selected_cell_id",
})
_MANIFEST_KEYS = frozenset({
    "schema_version", "batch_b_schema_version", "run_id",
    "synthetic_non_scientific", "authorities", "batch_b_implementation_sha",
    "source_hashes", "schema_identities", "registered_pair_domain",
    "registered_capacity_domain", "cells", "input_identity", "config_identity",
    "output_root", "expected_cell_artifacts", "expected_package_artifacts",
    "outcome_firewall_forbidden_families", "transaction_domain_kind",
    "authorized_frame_domains", "source_paths", "repository_identity",
    "execution_paths", "environment_allowlist",
})
_CELL_MANIFEST_KEYS = frozenset({
    "schema_version", "run_id", "cell", "expected_frame_domain",
    "batch_b_manifest_sha256", "authorities", "source_hashes",
    "schema_identities", "input_identity", "config_identity",
    "synthetic_non_scientific", "transaction_domain_kind", "expected_artifacts",
})
_CELL_SPEC_KEYS = frozenset({
    "cell_id", "pair_id", "frame_count", "capacity_id", "capacity_bytes",
    "stable_pair_order", "stable_capacity_order",
})


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise C7BatchBValidationError("{} must be an integer".format(label))
    if value < minimum:
        raise C7BatchBValidationError("{} must be >= {}".format(label, minimum))
    return value


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise C7BatchBValidationError("{} must be an object".format(label))
    keys = frozenset(value)
    if keys != expected:
        raise C7BatchBValidationError(
            "{} keys mismatch: missing={} extra={}".format(
                label, sorted(expected - keys), sorted(keys - expected)))


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise C7BatchBValidationError("{} must be a lowercase SHA-256".format(label))
    return value


def read_json(path: Path | str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise C7BatchBValidationError("invalid JSON: {}".format(path)) from exc
    if not isinstance(value, dict):
        raise C7BatchBValidationError("JSON object required: {}".format(path))
    return value


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise C7BatchBValidationError("invalid JSONL: {}".format(path)) from exc
    records = []
    for index, line in enumerate(lines, 1):
        if not line:
            raise C7BatchBValidationError("blank JSONL line {}".format(index))
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise C7BatchBValidationError("invalid JSONL line {}".format(index)) from exc
        if not isinstance(value, dict):
            raise C7BatchBValidationError("JSONL object required on line {}".format(index))
        records.append(value)
    return records


def reject_forbidden_outcome_content(value: Any, *, policy_context: bool = False) -> None:
    """Reject outcome-bearing keys/values while allowing firewall declarations."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "outcome_firewall_forbidden_families":
                continue
            reject_forbidden_outcome_content(str(key), policy_context=policy_context)
            reject_forbidden_outcome_content(item, policy_context=policy_context)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            reject_forbidden_outcome_content(item, policy_context=policy_context)
        return
    if isinstance(value, str) and not policy_context:
        normalized = value.casefold().replace("\\", "/")
        if any(token in normalized for token in FORBIDDEN_OUTCOME_FAMILIES):
            raise C7BatchBValidationError("forbidden outcome content")


def _raw_packet_identity(value: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        canonical_sha256(value.get("packet_id")),
        str(value.get("wire_digest", "")),
        str(value.get("channel", "")),
    )


def _reconstruct_no_stale_facts(evidence: Mapping[str, Any]) -> dict[str, Any]:
    """Independently prove completeness and stale absence from persisted raw events."""
    _exact_keys(evidence, _NO_STALE_EVIDENCE_KEYS, "no-stale raw evidence")
    if evidence.get("schema_version") != NO_STALE_RAW_OBSERVATION_SCHEMA:
        raise C7BatchBValidationError("no-stale raw schema mismatch")
    frame = _integer(evidence.get("frame_index"), "no-stale frame")
    failures = evidence.get("observer_failures")
    if not isinstance(failures, list) or failures:
        raise C7BatchBValidationError("no-stale observer failure/incomplete ledger")
    observations = evidence.get("observations")
    if not isinstance(observations, list) or not observations:
        raise C7BatchBValidationError("no-stale raw observations missing")
    ordinals = []
    frame_open = 0
    frame_close = 0
    frame_open_event = None
    frame_close_event = None
    observed_service_slice_bytes = 0
    true_first: dict[tuple[str, str, str], int] = {}
    served_id_state = set()
    stale_count = 0
    id_state_true_first_count = 0
    for row in observations:
        _exact_keys(row, _RAW_OBSERVATION_KEYS, "raw observation")
        if row.get("schema_version") != BATCH_A_SEMANTICS_SCHEMA:
            raise C7BatchBValidationError("raw observation schema mismatch")
        event = row.get("event")
        if not isinstance(event, Mapping) or event.get("frame") != frame:
            raise C7BatchBValidationError("raw observation frame mismatch")
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
                raise C7BatchBValidationError(
                    "service-slice observation event type mismatch")
            observed_service_slice_bytes += _integer(
                event.get("bytes_served"), "observed service-slice bytes", 1)
        if event_type == "service_slice" and event.get("channel") == "id_state":
            served_id_state.add(_raw_packet_identity(event))
        if kind != "true_first_service":
            continue
        if event_type != "service_start":
            raise C7BatchBValidationError("true-first-service event type mismatch")
        item = row.get("item")
        if not isinstance(item, Mapping) or _raw_packet_identity(item) != _raw_packet_identity(event):
            raise C7BatchBValidationError("true-first-service item identity mismatch")
        identity = _raw_packet_identity(item)
        if identity in true_first:
            raise C7BatchBValidationError("duplicate true-first-service observation")
        true_first[identity] = ordinal
        if item.get("channel") != "id_state":
            continue
        id_state_true_first_count += 1
        size = _integer(item.get("JSON_WIRE_BYTES"), "no-stale wire bytes", 1)
        if (_integer(item.get("bytes_served_total"), "no-stale bytes served") != 0
                or _integer(item.get("remaining_service_bytes"), "no-stale residual", 1) != size
                or item.get("service_start_frame") != frame):
            raise C7BatchBValidationError("true-first-service item is not pristine")
        wire = item.get("wire")
        if not isinstance(wire, Mapping) or canonical_sha256(wire) != item.get("wire_digest"):
            raise C7BatchBValidationError("true-first-service wire mismatch")
        state_raw = row.get("receiver_state")
        if not isinstance(state_raw, Mapping):
            raise C7BatchBValidationError("true-first-service receiver state missing")
        state = ReceiverStateEvidence.from_dict(state_raw)
        if state.frame_index != frame or state.event_ordinal != ordinal:
            raise C7BatchBValidationError("true-first-service state identity mismatch")
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
                or _raw_packet_identity(classification["source"]) != identity
                or classification.get("raw_receiver_state") != state.to_dict()
                or classification.get("raw_applicability") != applicability.to_dict()
                or classification.get("hook_event_type") != "service_start"
                or classification.get("json_wire_bytes") != size
                or classification.get("bytes_served_before_hook") != 0
                or classification.get("remaining_service_bytes_before_hook") != size):
            raise C7BatchBValidationError("classification record missing/inconsistent")
        stale_count += int(applicability.whole_packet_currently_non_applicable)
    if len(ordinals) != len(set(ordinals)) or ordinals != sorted(ordinals):
        raise C7BatchBValidationError("raw observation ordinals invalid")
    if frame_open != 1 or frame_close != 1:
        raise C7BatchBValidationError("complete frame boundary evidence required")
    if frame_open_event.get("frame_service_budget") != frame_close_event.get(
            "frame_service_budget"):
        raise C7BatchBValidationError("raw frame service budget identity mismatch")
    close_served = _integer(
        frame_close_event.get("bytes_served"), "frame-close bytes served")
    if observed_service_slice_bytes != close_served:
        raise C7BatchBValidationError("raw service-slice byte ledger is incomplete")
    frame_budget = frame_open_event.get("frame_service_budget")
    open_unused = frame_open_event.get("frame_unused_budget")
    close_unused = frame_close_event.get("frame_unused_budget")
    if frame_budget is None:
        if open_unused is not None or close_unused is not None:
            raise C7BatchBValidationError(
                "unlimited raw frame budget ledger is inconsistent")
    else:
        budget = _integer(frame_budget, "frame service budget", 1)
        if (_integer(open_unused, "frame-open unused budget") != budget
                or close_served + _integer(
                    close_unused, "frame-close unused budget") != budget):
            raise C7BatchBValidationError(
                "finite raw frame service budget ledger is inconsistent")
    if not served_id_state.issubset(true_first):
        raise C7BatchBValidationError("served ID-State packet lacks classification opportunity")
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


def _git_observed(repo_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise C7BatchBValidationError(
            "registered manifest Git provenance is not observable") from exc
    return completed.stdout.strip()


def _observed_file(path: Any, label: str) -> Path:
    if not isinstance(path, str):
        raise C7BatchBValidationError("{} path must be canonical string".format(label))
    try:
        observed = Path(path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise C7BatchBValidationError("{} path cannot be resolved".format(label)) from exc
    if not observed.is_file() or str(observed) != path:
        raise C7BatchBValidationError("{} path is not a canonical file".format(label))
    return observed


def _validate_registered_identity(
    identity: Any, *, label: str, expected_kind: str,
) -> None:
    if not isinstance(identity, Mapping) or frozenset(identity) != {"kind", "files", "digest"}:
        raise C7BatchBValidationError("registered {} identity schema mismatch".format(label))
    if identity.get("kind") != expected_kind:
        raise C7BatchBValidationError("registered {} identity kind mismatch".format(label))
    files = identity.get("files")
    if not isinstance(files, list) or not files:
        raise C7BatchBValidationError("registered {} identity files missing".format(label))
    observed = []
    for row in files:
        if not isinstance(row, Mapping) or frozenset(row) != {"path", "sha256"}:
            raise C7BatchBValidationError("registered {} file schema mismatch".format(label))
        path = _observed_file(row.get("path"), "registered {}".format(label))
        actual = sha256_file(path)
        if row.get("sha256") != actual:
            raise C7BatchBValidationError("registered {} file digest mismatch".format(label))
        observed.append({"path": str(path), "sha256": actual})
    if observed != sorted(observed, key=lambda row: row["path"]):
        raise C7BatchBValidationError("registered {} files are not canonical ordered".format(label))
    if len({row["path"] for row in observed}) != len(observed):
        raise C7BatchBValidationError("registered {} identity has duplicate file".format(label))
    if identity.get("digest") != canonical_sha256(observed):
        raise C7BatchBValidationError("registered {} aggregate digest mismatch".format(label))


def _validate_registered_provenance(manifest: Mapping[str, Any]) -> None:
    repository = manifest.get("repository_identity")
    if not isinstance(repository, Mapping) or frozenset(repository) != {
            "mode", "repo_root", "git_head", "worktree_clean"}:
        raise C7BatchBValidationError("registered repository identity schema mismatch")
    if repository.get("mode") != "REGISTERED_C7" or repository.get("worktree_clean") is not True:
        raise C7BatchBValidationError("registered repository identity marker mismatch")
    root_text = repository.get("repo_root")
    if not isinstance(root_text, str):
        raise C7BatchBValidationError("registered repository root missing")
    try:
        root = Path(root_text).resolve(strict=True)
        observed_root = Path(
            _git_observed(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise C7BatchBValidationError("registered repository root invalid") from exc
    if str(root) != root_text or observed_root != root:
        raise C7BatchBValidationError("registered repository root is not canonical")
    observed_head = _git_observed(root, "rev-parse", "HEAD")
    if (repository.get("git_head") != observed_head
            or manifest.get("batch_b_implementation_sha") != observed_head):
        raise C7BatchBValidationError("registered implementation SHA differs from actual Git HEAD")

    source_paths = manifest.get("source_paths")
    source_hashes = manifest.get("source_hashes")
    if not isinstance(source_paths, Mapping) or frozenset(source_paths) != SOURCE_HASH_KEYS:
        raise C7BatchBValidationError("registered source path inventory mismatch")
    expected_paths = {}
    for key, relative in sorted(REGISTERED_SOURCE_RELATIVE_PATHS.items()):
        expected = (root / relative).resolve(strict=True)
        try:
            expected.relative_to(root)
        except ValueError as exc:
            raise C7BatchBValidationError(
                "registered source escapes repository root") from exc
        observed = _observed_file(source_paths.get(key), "registered source {}".format(key))
        if observed != expected:
            raise C7BatchBValidationError("registered source path mismatch")
        expected_paths[key] = str(expected)
        if source_hashes.get(key) != sha256_file(expected):
            raise C7BatchBValidationError("registered source file digest mismatch")
    if dict(source_paths) != expected_paths:
        raise C7BatchBValidationError("registered source paths are not canonical")

    execution = manifest.get("execution_paths")
    if not isinstance(execution, Mapping) or frozenset(execution) != {
            "wrapper_path", "wrapper_sha256", "generated_source_root",
            "generated_source_lifecycle", "generated_source_sha256"}:
        raise C7BatchBValidationError("registered execution path schema mismatch")
    if (execution.get("wrapper_path") != expected_paths["wrapper"]
            or execution.get("wrapper_sha256") != source_hashes["wrapper"]):
        raise C7BatchBValidationError("registered wrapper provenance mismatch")
    generated_root = execution.get("generated_source_root")
    if (not isinstance(generated_root, str)
            or str(Path(generated_root).resolve()) != generated_root
            or execution.get("generated_source_lifecycle") != "MATERIALIZED_DURING_REAL_CHILD"
            or execution.get("generated_source_sha256") is not None):
        raise C7BatchBValidationError("registered generated-source lifecycle mismatch")

    _validate_registered_identity(
        manifest.get("input_identity"), label="input",
        expected_kind="REGISTERED_C7_INPUT_FILES_V1")
    _validate_registered_identity(
        manifest.get("config_identity"), label="config",
        expected_kind="REGISTERED_C7_CONFIG_FILES_V1")
    if _git_observed(root, "status", "--porcelain", "--untracked-files=all"):
        raise C7BatchBValidationError("registered worktree is dirty")


def validate_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(manifest, _MANIFEST_KEYS, "Batch B manifest")
    if (manifest.get("schema_version") != MANIFEST_SCHEMA
            or manifest.get("batch_b_schema_version") != BATCH_B_SCHEMA_VERSION):
        raise C7BatchBValidationError("manifest schema mismatch")
    if manifest.get("authorities") != authority_bindings():
        raise C7BatchBValidationError("manifest authority mismatch")
    implementation_sha = manifest.get("batch_b_implementation_sha")
    if not isinstance(implementation_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", implementation_sha):
        raise C7BatchBValidationError("Batch B implementation SHA mismatch")
    source_hashes = manifest.get("source_hashes")
    if not isinstance(source_hashes, Mapping) or frozenset(source_hashes) != SOURCE_HASH_KEYS:
        raise C7BatchBValidationError("manifest source hash inventory mismatch")
    for key, value in source_hashes.items():
        _digest(value, "{} source hash".format(key))
    if manifest.get("schema_identities") != {
        "batch_a_semantics": BATCH_A_SEMANTICS_SCHEMA,
        "batch_a_validation": BATCH_A_VALIDATION_SCHEMA,
        "validated_window": VALIDATED_WINDOW_SCHEMA,
        "selection": SELECTION_SCHEMA,
    }:
        raise C7BatchBValidationError("manifest schema identities mismatch")
    if manifest.get("registered_pair_domain") != [
        {"pair_id": pair_id, "frame_count": frame_count}
        for pair_id, frame_count in PAIR_DOMAIN
    ]:
        raise C7BatchBValidationError("manifest pair domain mismatch")
    if manifest.get("registered_capacity_domain") != [
        {"capacity_id": capacity_id, "capacity_bytes": capacity_bytes}
        for capacity_id, capacity_bytes in CAPACITY_DOMAIN
    ]:
        raise C7BatchBValidationError("manifest capacity domain mismatch")
    if manifest.get("cells") != list(registered_cells()):
        raise C7BatchBValidationError("manifest cell domain mismatch")
    if manifest.get("synthetic_non_scientific") not in {True, False}:
        raise C7BatchBValidationError("manifest synthetic marker mismatch")
    synthetic = manifest["synthetic_non_scientific"]
    expected_kind = "SYNTHETIC_NON_SCIENTIFIC" if synthetic else "REGISTERED_C7"
    if manifest.get("transaction_domain_kind") != expected_kind:
        raise C7BatchBValidationError("manifest transaction domain kind mismatch")
    if manifest.get("environment_allowlist") != list(ALLOWED_PARENT_ENV_KEYS):
        raise C7BatchBValidationError("manifest environment allowlist mismatch")
    if manifest.get("authorized_frame_domains") != authorized_frame_domains(synthetic):
        raise C7BatchBValidationError("manifest authorized frame domain mismatch")
    if not isinstance(manifest.get("input_identity"), Mapping):
        raise C7BatchBValidationError("manifest input identity missing")
    if not isinstance(manifest.get("config_identity"), Mapping):
        raise C7BatchBValidationError("manifest config identity missing")
    output_root = manifest.get("output_root")
    if not isinstance(output_root, str) or str(Path(output_root).resolve()) != output_root:
        raise C7BatchBValidationError("manifest output root is not canonical")
    if synthetic:
        if manifest.get("source_paths") != {}:
            raise C7BatchBValidationError("synthetic source paths must not claim authority")
        if manifest.get("repository_identity") != {
                "mode": "SYNTHETIC_NON_SCIENTIFIC",
                "repo_root": None,
                "git_head": implementation_sha,
                "worktree_clean": None}:
            raise C7BatchBValidationError("synthetic repository identity mismatch")
        if manifest.get("execution_paths") != {
                "wrapper_path": None,
                "wrapper_sha256": None,
                "generated_source_root": None,
                "generated_source_lifecycle": "SYNTHETIC_NON_SCIENTIFIC",
                "generated_source_sha256": None}:
            raise C7BatchBValidationError("synthetic execution provenance mismatch")
    else:
        _validate_registered_provenance(manifest)
    if manifest.get("expected_cell_artifacts") != [
        "windows.jsonl", "cell_aggregate.json", "cell_qualification.json",
        "cell_manifest.json", "cell_validation.json", "cell_inventory.json",
        "cell_seal.json", "CELL_COMMITTED.json",
    ]:
        raise C7BatchBValidationError("manifest cell inventory contract mismatch")
    if manifest.get("expected_package_artifacts") != [
        "package_manifest.json", "cell_qualifications.jsonl", "C7_SELECTION.json",
        "verified_cell_inventory.json", "package_validation.json",
        "package_inventory.json", "package_seal.json", "PACKAGE_COMMITTED.json",
    ]:
        raise C7BatchBValidationError("manifest package inventory contract mismatch")
    if manifest.get("outcome_firewall_forbidden_families") != list(FORBIDDEN_OUTCOME_FAMILIES):
        raise C7BatchBValidationError("manifest outcome firewall policy mismatch")
    reject_forbidden_outcome_content(manifest)
    return {
        "status": "PASS",
        "manifest_sha256": canonical_sha256(manifest),
        "cell_count": 21,
        "outcome_firewall": "PASS",
    }


def _window_facts(
    record: Mapping[str, Any], *, run_id: str, cell: Mapping[str, Any],
) -> tuple[int, bool, bool, str]:
    _exact_keys(record, _WINDOW_KEYS, "validated window")
    if record.get("schema_version") != VALIDATED_WINDOW_SCHEMA:
        raise C7BatchBValidationError("validated window schema mismatch")
    identities = {
        "run_id": run_id,
        "cell_id": cell["cell_id"],
        "pair_id": cell["pair_id"],
        "capacity_id": cell["capacity_id"],
        "capacity_bytes": cell["capacity_bytes"],
    }
    for key, expected in identities.items():
        if record.get(key) != expected:
            raise C7BatchBValidationError("validated window {} mismatch".format(key))
    frame = _integer(record.get("frame_index"), "frame index")
    evidence = record.get("evidence")
    validation = record.get("validation")
    if not isinstance(evidence, Mapping) or not isinstance(validation, Mapping):
        raise C7BatchBValidationError("window evidence/validation must be objects")
    if _digest(record.get("evidence_sha256"), "evidence digest") != canonical_sha256(evidence):
        raise C7BatchBValidationError("window evidence digest mismatch")
    if _digest(record.get("validation_sha256"), "validation digest") != canonical_sha256(validation):
        raise C7BatchBValidationError("window validation digest mismatch")
    reject_forbidden_outcome_content(record)

    if record.get("evidence_kind") == "BATCH_A_CORE":
        try:
            reconstructed = validate_core_evidence(evidence)
        except C7ValidationError as exc:
            raise C7BatchBValidationError("Batch A evidence validation failed") from exc
        if reconstructed != validation:
            raise C7BatchBValidationError("Batch A validation reconstruction mismatch")
        if evidence.get("raw_baseline_evidence", {}).get("frame_index") != frame:
            raise C7BatchBValidationError("Batch A frame mismatch")
        return frame, True, bool(reconstructed["window_eligible"]), canonical_sha256(record)

    if record.get("evidence_kind") != "VALIDATED_NO_STALE":
        raise C7BatchBValidationError("unknown window evidence kind")
    facts = _reconstruct_no_stale_facts(evidence)
    expected = {"schema_version": NO_STALE_VALIDATION_SCHEMA, "status": "PASS", **facts}
    if facts["frame_index"] != frame or facts["stale_present"] or validation != expected:
        raise C7BatchBValidationError("no-stale raw reconstruction mismatch")
    return frame, False, False, canonical_sha256(record)


def reconstruct_aggregate(
    *, run_id: str, cell: Mapping[str, Any], expected_frame_domain: Sequence[int],
    windows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected = tuple(_integer(frame, "expected frame") for frame in expected_frame_domain)
    if not expected or tuple(sorted(expected)) != expected or len(set(expected)) != len(expected):
        raise C7BatchBValidationError("invalid expected frame domain")
    parsed = [_window_facts(record, run_id=run_id, cell=cell) for record in windows]
    frames = [row[0] for row in parsed]
    if len(frames) != len(set(frames)):
        raise C7BatchBValidationError("duplicate window")
    if set(frames) != set(expected):
        raise C7BatchBValidationError("window-domain bijection failed")
    parsed.sort(key=lambda row: row[0])
    n_all = len(parsed)
    n_stale = sum(1 for _, stale, _, _ in parsed if stale)
    n_eligible = sum(1 for _, _, eligible, _ in parsed if eligible)
    if not 0 <= n_eligible <= n_stale <= n_all:
        raise C7BatchBValidationError("count nesting failed")
    return {
        "schema_version": CELL_AGGREGATE_SCHEMA,
        "run_id": run_id,
        "cell_id": cell["cell_id"],
        "pair_id": cell["pair_id"],
        "capacity_id": cell["capacity_id"],
        "capacity_bytes": cell["capacity_bytes"],
        "expected_frame_domain": list(expected),
        "observed_frame_domain": [row[0] for row in parsed],
        "cell_validity": "VALID_ZERO" if n_stale == 0 else "VALID",
        "invalid_reasons": [],
        "N_all": n_all,
        "N_stale": n_stale,
        "N_eligible": n_eligible,
        "nesting_attestation": True,
        "overall_rate": {
            "status": "DEFINED", "numerator": n_eligible, "denominator": n_all},
        "conditional_rate": (
            {"status": "N/A", "numerator": n_eligible, "denominator": 0}
            if n_stale == 0 else
            {"status": "DEFINED", "numerator": n_eligible, "denominator": n_stale}),
        "input_window_evidence_digests": [
            {"frame_index": row[0], "record_sha256": row[3]} for row in parsed],
        "schema_identity": VALIDATED_WINDOW_SCHEMA,
        "producer_source_authority": BATCH_A_SEMANTICS_SCHEMA,
        "validator_source_authority": BATCH_A_VALIDATION_SCHEMA,
    }


def _gates(n_all: int, n_stale: int, n_eligible: int) -> dict[str, Any]:
    n_all = _integer(n_all, "N_all", 1)
    n_stale = _integer(n_stale, "N_stale")
    n_eligible = _integer(n_eligible, "N_eligible")
    if not 0 <= n_eligible <= n_stale <= n_all:
        raise C7BatchBValidationError("qualification nesting failed")
    count_pass = n_eligible >= T_COUNT
    denominator_pass = n_stale >= T_DENOMINATOR
    global_lhs = GLOBAL_MULTIPLIER * n_eligible
    conditional_lhs = CONDITIONAL_MULTIPLIER * n_eligible
    global_pass = global_lhs >= n_all
    conditional_pass = n_stale > 0 and conditional_lhs >= n_stale
    return {
        "N_all": n_all,
        "N_stale": n_stale,
        "N_eligible": n_eligible,
        "count_threshold": T_COUNT,
        "denominator_threshold": T_DENOMINATOR,
        "count_pass": count_pass,
        "denominator_pass": denominator_pass,
        "global_lhs": global_lhs,
        "global_rhs": n_all,
        "global_pass": global_pass,
        "conditional_lhs": conditional_lhs,
        "conditional_rhs": n_stale,
        "conditional_pass": conditional_pass,
        "CELL_QUALIFIED": bool(
            count_pass and denominator_pass and global_pass and conditional_pass),
    }


def reconstruct_qualification(aggregate: Mapping[str, Any]) -> dict[str, Any]:
    _exact_keys(aggregate, _AGGREGATE_KEYS, "cell aggregate")
    if aggregate.get("schema_version") != CELL_AGGREGATE_SCHEMA:
        raise C7BatchBValidationError("aggregate schema mismatch")
    if aggregate.get("cell_validity") not in {"VALID", "VALID_ZERO"}:
        raise C7BatchBValidationError("aggregate is invalid")
    if aggregate.get("invalid_reasons") != [] or aggregate.get("nesting_attestation") is not True:
        raise C7BatchBValidationError("aggregate validity mismatch")
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
        **_gates(aggregate.get("N_all"), aggregate.get("N_stale"), aggregate.get("N_eligible")),
    }


def validate_cell_documents(
    *, windows: Sequence[Mapping[str, Any]], aggregate: Mapping[str, Any],
    qualification: Mapping[str, Any], cell_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    _exact_keys(cell_manifest, _CELL_MANIFEST_KEYS, "cell manifest")
    if cell_manifest.get("schema_version") != CELL_MANIFEST_SCHEMA:
        raise C7BatchBValidationError("cell manifest schema mismatch")
    if cell_manifest.get("synthetic_non_scientific") not in {True, False}:
        raise C7BatchBValidationError("synthetic marker must be boolean")
    reject_forbidden_outcome_content(cell_manifest)
    cell = cell_manifest.get("cell")
    if not isinstance(cell, Mapping):
        raise C7BatchBValidationError("cell manifest cell missing")
    _exact_keys(cell, _CELL_SPEC_KEYS, "cell specification")
    if cell_manifest.get("authorities") != authority_bindings():
        raise C7BatchBValidationError("cell manifest authority mismatch")
    source_hashes = cell_manifest.get("source_hashes")
    if not isinstance(source_hashes, Mapping) or frozenset(source_hashes) != SOURCE_HASH_KEYS:
        raise C7BatchBValidationError("cell source hash inventory mismatch")
    for key, value in source_hashes.items():
        _digest(value, "{} source hash".format(key))
    if cell_manifest.get("schema_identities") != {
        "batch_a_semantics": BATCH_A_SEMANTICS_SCHEMA,
        "batch_a_validation": BATCH_A_VALIDATION_SCHEMA,
        "validated_window": VALIDATED_WINDOW_SCHEMA,
        "selection": SELECTION_SCHEMA,
    }:
        raise C7BatchBValidationError("cell schema identities mismatch")
    if cell_manifest.get("expected_artifacts") != [
        "windows.jsonl", "cell_aggregate.json", "cell_qualification.json",
        "cell_manifest.json", "cell_validation.json", "cell_inventory.json",
        "cell_seal.json", "CELL_COMMITTED.json",
    ]:
        raise C7BatchBValidationError("cell artifact contract mismatch")
    expected_kind = (
        "SYNTHETIC_NON_SCIENTIFIC"
        if cell_manifest["synthetic_non_scientific"] else "REGISTERED_C7")
    if cell_manifest.get("transaction_domain_kind") != expected_kind:
        raise C7BatchBValidationError("cell transaction domain kind mismatch")
    _digest(cell_manifest.get("batch_b_manifest_sha256"), "Batch B manifest digest")
    expected_aggregate = reconstruct_aggregate(
        run_id=cell_manifest.get("run_id"), cell=cell,
        expected_frame_domain=cell_manifest.get("expected_frame_domain", ()),
        windows=windows)
    _exact_keys(aggregate, _AGGREGATE_KEYS, "cell aggregate")
    if aggregate != expected_aggregate:
        raise C7BatchBValidationError("producer aggregate differs from disk reconstruction")
    expected_qualification = reconstruct_qualification(expected_aggregate)
    _exact_keys(qualification, _QUALIFICATION_KEYS, "cell qualification")
    if qualification != expected_qualification:
        raise C7BatchBValidationError("producer qualification differs from reconstruction")
    reject_forbidden_outcome_content(aggregate)
    reject_forbidden_outcome_content(qualification)
    return {
        "schema_version": CELL_VALIDATION_SCHEMA,
        "status": "PASS",
        "run_id": cell_manifest.get("run_id"),
        "cell_id": cell.get("cell_id"),
        "window_count": len(windows),
        "aggregate_sha256": canonical_sha256(aggregate),
        "qualification_sha256": canonical_sha256(qualification),
        "frame_domain_bijection": True,
        "nesting_verified": True,
        "four_gates_reconstructed": True,
        "outcome_firewall": "PASS",
    }


def validate_cell_files(cell_root: Path | str) -> dict[str, Any]:
    root = Path(cell_root)
    return validate_cell_documents(
        windows=read_jsonl(root / "windows.jsonl"),
        aggregate=read_json(root / "cell_aggregate.json"),
        qualification=read_json(root / "cell_qualification.json"),
        cell_manifest=read_json(root / "cell_manifest.json"),
    )


def _qualification_for_selection(
    record: Mapping[str, Any], cell: Mapping[str, Any], expected_frame_count: int,
) -> dict[str, Any]:
    _exact_keys(record, _QUALIFICATION_KEYS, "selection qualification")
    if record.get("schema_version") != CELL_QUALIFICATION_SCHEMA:
        raise C7BatchBValidationError("qualification schema mismatch")
    if record.get("cell_id") != cell["cell_id"]:
        raise C7BatchBValidationError("qualification cell mismatch")
    if record.get("N_all") != expected_frame_count:
        raise C7BatchBValidationError("qualification frame count mismatch")
    if (record.get("cell_validity") not in {"VALID", "VALID_ZERO"}
            or record.get("cell_validation_status") != "PASS"
            or record.get("qualification_complete") is not True
            or record.get("frozen_batch_a_implementation_authority")
            != FROZEN_BATCH_A_IMPLEMENTATION_AUTHORITY
            or record.get("batch_a_freeze_authority") != BATCH_A_FREEZE_AUTHORITY):
        raise C7BatchBValidationError("qualification validity/authority mismatch")
    expected = _gates(record.get("N_all"), record.get("N_stale"), record.get("N_eligible"))
    for key, value in expected.items():
        if record.get(key) != value:
            raise C7BatchBValidationError("qualification {} mismatch".format(key))
    reject_forbidden_outcome_content(record)
    return {**record, **expected}


def _rate_compare(a: Mapping[str, Any], b: Mapping[str, Any], conditional: bool) -> int:
    a_den = a["N_stale"] if conditional else a["N_all"]
    b_den = b["N_stale"] if conditional else b["N_all"]
    lhs = a["N_eligible"] * b_den
    rhs = b["N_eligible"] * a_den
    return (lhs > rhs) - (lhs < rhs)


def _dominates(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    overall = _rate_compare(a, b, False)
    conditional = _rate_compare(a, b, True)
    return overall >= 0 and conditional >= 0 and (overall > 0 or conditional > 0)


def reconstruct_selection(
    manifest: Mapping[str, Any], qualifications: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    validate_manifest(manifest)
    cells = manifest.get("cells")
    if cells != list(registered_cells()):
        raise C7BatchBValidationError("manifest does not contain the exact 21 cells")
    if len(qualifications) != 21:
        raise C7BatchBValidationError("selection requires 21 qualifications")
    by_id: dict[str, Mapping[str, Any]] = {}
    for record in qualifications:
        cell_id = record.get("cell_id")
        if cell_id in by_id:
            raise C7BatchBValidationError("duplicate cell qualification")
        by_id[cell_id] = record
    if set(by_id) != set(REGISTERED_CELL_IDS):
        raise C7BatchBValidationError("qualification cell domain mismatch")
    reconstructed = []
    for cell in cells:
        domain = manifest["authorized_frame_domains"].get(cell["cell_id"])
        if not isinstance(domain, list) or not domain:
            raise C7BatchBValidationError("selection manifest frame domain missing")
        reconstructed.append((
            cell,
            _qualification_for_selection(
                by_id[cell["cell_id"]], cell, len(domain)),
        ))
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
        dominated = False
        for other_cell, other in tied:
            if candidate_cell["cell_id"] == other_cell["cell_id"]:
                continue
            other_dominates = _dominates(other, candidate)
            trace["pareto_comparisons"].append({
                "candidate": candidate_cell["cell_id"],
                "other": other_cell["cell_id"],
                "other_dominates": other_dominates,
                "overall_cross_product": [
                    other["N_eligible"] * candidate["N_all"],
                    candidate["N_eligible"] * other["N_all"],
                ],
                "conditional_cross_product": [
                    other["N_eligible"] * candidate["N_stale"],
                    candidate["N_eligible"] * other["N_stale"],
                ],
            })
            dominated = dominated or other_dominates
        if not dominated:
            survivors.append((candidate_cell, candidate))
    trace["pareto_survivors"] = [cell["cell_id"] for cell, _ in survivors]
    survivors.sort(key=lambda item: (
        item[0]["stable_pair_order"], item[0]["stable_capacity_order"], item[0]["cell_id"]))
    trace["stable_tiebreak"] = [cell["cell_id"] for cell, _ in survivors]
    return {
        "schema_version": SELECTION_SCHEMA,
        "run_id": manifest.get("run_id"),
        "manifest_sha256": canonical_sha256(manifest),
        "all_21_complete_attestation": True,
        "qualified_subset": [cell["cell_id"] for cell, _ in qualified],
        "comparison_trace": trace,
        "selection_outcome": "SELECTED_CELL",
        "selected_cell_id": survivors[0][0]["cell_id"],
    }


def validate_selection(
    manifest: Mapping[str, Any], qualifications: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
) -> dict[str, Any]:
    _exact_keys(selection, _SELECTION_KEYS, "selection")
    expected = reconstruct_selection(manifest, qualifications)
    if selection != expected:
        raise C7BatchBValidationError("selection differs from independent reconstruction")
    reject_forbidden_outcome_content(selection)
    return {
        "schema_version": "C7_SELECTION_VALIDATION_V1",
        "status": "PASS",
        "all_21_complete": True,
        "qualified_subset_reconstructed": True,
        "selection_outcome": selection["selection_outcome"],
        "selected_cell_id": selection["selected_cell_id"],
        "outcome_firewall": "PASS",
    }


def _inventory_for(root: Path, names: Sequence[str], schema_version: str) -> dict[str, Any]:
    files = []
    for name in sorted(names):
        path = root / name
        if not path.is_file():
            raise C7BatchBValidationError("missing authoritative artifact: {}".format(name))
        files.append({
            "path": name,
            "sha256": sha256_file(path),
            "byte_count": path.stat().st_size,
        })
    return {"schema_version": schema_version, "files": files}


def validate_committed_cell(
    cell_root: Path | str, *, expected_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reread and independently reproduce a completed cell transaction."""
    root = Path(cell_root)
    if not root.is_dir():
        raise C7BatchBValidationError("committed cell directory is missing")
    names = tuple(sorted(path.name for path in root.iterdir()))
    if names != CELL_AUTHORITATIVE_FILES:
        raise C7BatchBValidationError("unexpected authoritative cell inventory")
    validation = validate_cell_files(root)
    if read_json(root / "cell_validation.json") != validation:
        raise C7BatchBValidationError("persisted cell validation is not reproducible")
    inventory = _inventory_for(root, CELL_ARTIFACTS_BEFORE_COMMIT, CELL_INVENTORY_SCHEMA)
    if read_json(root / "cell_inventory.json") != inventory:
        raise C7BatchBValidationError("cell inventory digest mismatch")
    cell_manifest = read_json(root / "cell_manifest.json")
    manifest_sha = cell_manifest.get("batch_b_manifest_sha256")
    _digest(manifest_sha, "Batch B manifest digest")
    if expected_manifest is not None:
        validate_manifest(expected_manifest)
        if manifest_sha != canonical_sha256(expected_manifest):
            raise C7BatchBValidationError("cell manifest authority mismatch")
        cell = cell_manifest.get("cell")
        if cell not in expected_manifest.get("cells", ()):
            raise C7BatchBValidationError("cell is not in expected manifest domain")
        expected_domain = expected_manifest["authorized_frame_domains"][cell["cell_id"]]
        if cell_manifest.get("expected_frame_domain") != expected_domain:
            raise C7BatchBValidationError("cell frame domain differs from manifest")
        for key in (
            "authorities", "source_hashes", "schema_identities", "input_identity",
            "config_identity", "synthetic_non_scientific", "transaction_domain_kind",
        ):
            if cell_manifest.get(key) != expected_manifest.get(key):
                raise C7BatchBValidationError(
                    "cell manifest {} binding mismatch".format(key))
    payload = {
        "run_id": cell_manifest.get("run_id"),
        "cell_id": cell_manifest.get("cell", {}).get("cell_id"),
        "cell_manifest_sha256": sha256_file(root / "cell_manifest.json"),
        "inventory_sha256": canonical_sha256(inventory),
        "status": "VALIDATED",
    }
    seal = read_json(root / "cell_seal.json")
    expected_seal = {
        "schema_version": CELL_SEAL_SCHEMA,
        "sealed_payload": payload,
        "seal_sha256": canonical_sha256(payload),
    }
    if seal != expected_seal:
        raise C7BatchBValidationError("cell seal is not reproducible")
    terminal = read_json(root / "CELL_COMMITTED.json")
    expected_terminal = {
        "schema_version": CELL_COMMIT_SCHEMA,
        "status": "COMMITTED",
        "cell_id": payload["cell_id"],
        "inventory_sha256": payload["inventory_sha256"],
        "seal_sha256": expected_seal["seal_sha256"],
    }
    if terminal != expected_terminal:
        raise C7BatchBValidationError("cell terminal marker mismatch")
    return {
        **validation,
        "inventory_reproduced": True,
        "seal_reproduced": True,
        "terminal_marker_valid": True,
    }


def reconstruct_verified_cell_inventory(
    output_root: Path | str, manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Rebuild the exact qualification set from 21 verified sealed cells."""
    validate_manifest(manifest)
    root = Path(output_root)
    manifest_sha = canonical_sha256(manifest)
    inventory_rows = []
    qualifications = []
    for cell in manifest["cells"]:
        cell_root = root / "cells" / cell["cell_id"]
        validate_committed_cell(cell_root, expected_manifest=manifest)
        cell_manifest = read_json(cell_root / "cell_manifest.json")
        qualification = read_json(cell_root / "cell_qualification.json")
        if qualification.get("cell_id") != cell["cell_id"]:
            raise C7BatchBValidationError("sealed qualification cell identity mismatch")
        qualifications.append(qualification)
        terminal = read_json(cell_root / "CELL_COMMITTED.json")
        inventory_rows.append({
            "cell_id": cell["cell_id"],
            "cell_manifest_sha256": sha256_file(cell_root / "cell_manifest.json"),
            "cell_qualification_sha256": sha256_file(cell_root / "cell_qualification.json"),
            "cell_inventory_sha256": sha256_file(cell_root / "cell_inventory.json"),
            "cell_seal_sha256": sha256_file(cell_root / "cell_seal.json"),
            "terminal_marker_sha256": sha256_file(cell_root / "CELL_COMMITTED.json"),
            "terminal_status": terminal.get("status"),
            "terminal_seal_sha256": terminal.get("seal_sha256"),
            "cell_manifest_binding_sha256": cell_manifest.get("batch_b_manifest_sha256"),
        })
    if len(inventory_rows) != 21 or len({row["cell_id"] for row in inventory_rows}) != 21:
        raise C7BatchBValidationError("exact 21-cell sealed inventory required")
    return ({
        "schema_version": VERIFIED_CELL_INVENTORY_SCHEMA,
        "manifest_sha256": manifest_sha,
        "cell_count": 21,
        "all_cells_valid_sealed": True,
        "cells": inventory_rows,
    }, qualifications)


def validate_committed_package(package_root: Path | str) -> dict[str, Any]:
    """Reread and independently reproduce a completed selection package."""
    root = Path(package_root)
    if not root.is_dir():
        raise C7BatchBValidationError("committed package directory is missing")
    names = tuple(sorted(path.name for path in root.iterdir()))
    if names != PACKAGE_AUTHORITATIVE_FILES:
        raise C7BatchBValidationError("unexpected authoritative package inventory")
    manifest = read_json(root / "package_manifest.json")
    validate_manifest(manifest)
    verified_inventory, qualifications = reconstruct_verified_cell_inventory(
        root.parent, manifest)
    if read_json(root / "verified_cell_inventory.json") != verified_inventory:
        raise C7BatchBValidationError("verified cell inventory is not reproducible")
    if read_jsonl(root / "cell_qualifications.jsonl") != qualifications:
        raise C7BatchBValidationError("package qualifications are not sealed-cell-derived")
    selection = read_json(root / "C7_SELECTION.json")
    selection_validation = validate_selection(manifest, qualifications, selection)
    expected_validation = {
        "schema_version": PACKAGE_VALIDATION_SCHEMA,
        "status": "PASS",
        "run_id": manifest.get("run_id"),
        "manifest_sha256": canonical_sha256(manifest),
        "qualification_count": len(qualifications),
        "verified_cell_inventory_sha256": canonical_sha256(verified_inventory),
        "all_21_cell_seals_verified": True,
        "selection_validation": selection_validation,
        "outcome_firewall": "PASS",
    }
    if read_json(root / "package_validation.json") != expected_validation:
        raise C7BatchBValidationError("package validation is not reproducible")
    inventory = _inventory_for(root, PACKAGE_ARTIFACTS_BEFORE_COMMIT, PACKAGE_INVENTORY_SCHEMA)
    if read_json(root / "package_inventory.json") != inventory:
        raise C7BatchBValidationError("package inventory digest mismatch")
    payload = {
        "run_id": manifest.get("run_id"),
        "manifest_sha256": sha256_file(root / "package_manifest.json"),
        "selection_sha256": sha256_file(root / "C7_SELECTION.json"),
        "verified_cell_inventory_sha256": sha256_file(
            root / "verified_cell_inventory.json"),
        "inventory_sha256": canonical_sha256(inventory),
        "status": "VALIDATED",
    }
    expected_seal = {
        "schema_version": PACKAGE_SEAL_SCHEMA,
        "sealed_payload": payload,
        "seal_sha256": canonical_sha256(payload),
    }
    if read_json(root / "package_seal.json") != expected_seal:
        raise C7BatchBValidationError("package seal is not reproducible")
    expected_terminal = {
        "schema_version": PACKAGE_COMMIT_SCHEMA,
        "status": "COMMITTED",
        "inventory_sha256": payload["inventory_sha256"],
        "seal_sha256": expected_seal["seal_sha256"],
    }
    if read_json(root / "PACKAGE_COMMITTED.json") != expected_terminal:
        raise C7BatchBValidationError("package terminal marker mismatch")
    return {
        **expected_validation,
        "inventory_reproduced": True,
        "seal_reproduced": True,
        "terminal_marker_valid": True,
    }
