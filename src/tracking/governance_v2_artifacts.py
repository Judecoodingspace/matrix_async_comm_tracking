"""V2-3 local artifact lineage. Structural evidence only; no scientific verdicts."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Mapping

from tracking.governance_v2_execution import inspect as inspect_execution

SCHEMA = "GOVERNANCE_V2_ARTIFACT_NODE_V1"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
LAYERS = ("RAW_EVIDENCE", "NORMALIZED_EVIDENCE")
CLASSES = ("ORDINARY_COMPOSITION", "FORMAL_AUTHORIZATION_SUPPORT")


class ArtifactError(RuntimeError):
    def __init__(self, code: str, route: str = "BLOCK") -> None:
        super().__init__(code)
        self.code, self.route = code, route


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ArtifactError(code)


def _hex(value: Any, length: int = 64) -> str:
    _require(isinstance(value, str) and bool((HEX64 if length == 64 else HEX40).fullmatch(value)),
             "EXACT_SHA_REQUIRED")
    return value


def _id(value: Any) -> str:
    _require(isinstance(value, str) and bool(IDENTIFIER.fullmatch(value))
             and value not in {".", ".."}, "NODE_ID_INVALID")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read(path: Path) -> tuple[dict, bytes]:
    try:
        if path.is_symlink():
            raise ArtifactError("METADATA_SYMLINK_FORBIDDEN", "A1")
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ArtifactError("UNRESOLVED_METADATA", "A1") from exc
    if not isinstance(value, dict):
        raise ArtifactError("METADATA_SCHEMA_INVALID", "A2")
    return value, raw


def _write_new(path: Path, value: dict) -> None:
    """Same-directory durable, no-replace publication; marker is written last."""
    raw = _canonical(value)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".stage-", delete=False) as f:
            name = Path(f.name)
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.link(name, path)  # O_EXCL semantics, even if another writer races.
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)


def _safe_file(root: Path, relative: str) -> Path:
    _require(isinstance(relative, str) and relative and not relative.startswith("/")
             and "\\" not in relative, "RELATIVE_PATH_INVALID")
    parts = PurePosixPath(relative).parts
    _require(all(part not in {"", ".", ".."} for part in parts), "RELATIVE_PATH_ESCAPE")
    root = root.resolve(strict=True)
    path = root
    for part in parts:
        path = path / part
        try:
            mode = path.lstat().st_mode
        except OSError as exc:
            raise ArtifactError("UNRESOLVED_FILE", "A1") from exc
        _require(not stat.S_ISLNK(mode), "SYMLINK_FORBIDDEN")
    try:
        path.relative_to(root)
        metadata = path.stat()
    except (OSError, ValueError) as exc:
        raise ArtifactError("UNRESOLVED_FILE", "A1") from exc
    _require(stat.S_ISREG(metadata.st_mode), "REGULAR_FILE_REQUIRED")
    _require(metadata.st_nlink == 1, "UNSAFE_HARDLINK_ALIAS")
    return path


def _hash_file(path: Path) -> tuple[int, str]:
    """A failed/short read is unresolved, not a positively verified mismatch."""
    try:
        before = path.stat()
        h = hashlib.sha256()
        count = 0
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                count += len(block)
                h.update(block)
        after = path.stat()
    except OSError as exc:
        raise ArtifactError("CONTENT_READ_UNRESOLVED", "A1") from exc
    if count != before.st_size or before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise ArtifactError("CONTENT_READ_UNRESOLVED", "A1")
    return count, h.hexdigest()


def _git_blob(repo: Path, ref: Mapping[str, Any], deep: bool) -> tuple[int, str | None]:
    _require(set(ref) == {"kind", "commit", "repo_path", "size_bytes", "sha256"}, "REFERENCE_SCHEMA")
    commit = _hex(ref["commit"], 40)
    path = ref["repo_path"]
    _require(isinstance(path, str) and path and not path.startswith("/") and "\\" not in path
             and all(p not in {"", ".", ".."} for p in PurePosixPath(path).parts), "GIT_PATH_INVALID")
    def git(*args: str) -> bytes:
        try:
            result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ArtifactError("GIT_REFERENCE_UNRESOLVED", "A1") from exc
        return result.stdout
    _require(git("rev-parse", "--verify", commit + "^{commit}").decode().strip() == commit,
             "GIT_COMMIT_UNRESOLVED")
    object_name = commit + ":" + path
    _require(git("cat-file", "-t", object_name).strip() == b"blob", "GIT_BLOB_REQUIRED")
    size = int(git("cat-file", "-s", object_name).strip())
    if not deep:
        return size, None
    raw = git("show", object_name)
    if len(raw) != size:
        raise ArtifactError("GIT_BLOB_READ_UNRESOLVED", "A1")
    return len(raw), _digest(raw)


def _paths(attempts_root: Path, attempt_id: str, node_id: str) -> tuple[Path, Path]:
    attempts = Path(attempts_root).resolve()
    attempt_id, node_id = _id(attempt_id), _id(node_id)
    if node_id == "initial":
        node = attempts / attempt_id
    else:
        node = attempts / ".v2_3_corrections" / attempt_id / node_id
    return node, node / "v2_3"


def _published(attempts_root: Path, attempt_id: str, node_id: str) -> tuple[dict, dict, str, str]:
    node, meta = _paths(attempts_root, attempt_id, node_id)
    if not (meta / "finalization_receipt.json").is_file():
        raise ArtifactError("NODE_NOT_FINALIZED", "A1")
    final, final_raw = _read(meta / "finalization_receipt.json")
    manifest, manifest_raw = _read(meta / "manifest.json")
    _require(set(final) == {"schema_version", "attempt_id", "node_id", "manifest_sha256",
                                  "validation_receipt_sha256", "finalized_at"}, "FINAL_RECEIPT_SCHEMA")
    if (final["schema_version"] != SCHEMA or final["attempt_id"] != attempt_id
            or final["node_id"] != node_id):
        raise ArtifactError("FINAL_RECEIPT_IDENTITY_MISMATCH", "A2")
    if final["manifest_sha256"] != _digest(manifest_raw):
        raise ArtifactError("FINAL_MANIFEST_MISMATCH", "A2")
    _require(manifest.get("schema_version") == SCHEMA and manifest.get("attempt_id") == attempt_id
             and manifest.get("node_id") == node_id, "MANIFEST_IDENTITY_MISMATCH")
    validation, validation_raw = _read(meta / "validation_receipt.json")
    if (final["validation_receipt_sha256"] != _digest(validation_raw)
            or manifest.get("validation_receipt_sha256") != _digest(validation_raw)):
        raise ArtifactError("VALIDATION_RECEIPT_MISMATCH", "A2")
    _require(validation.get("STRUCTURAL_VERDICT") == "PASS", "STRUCTURAL_VERDICT_NOT_PASS")
    _require(validation.get("validated_evidence") == manifest.get("evidence")
             and validation.get("validation_provenance") == manifest.get("provenance", {}).get("validation")
             and validation.get("effective_scientific_config") == manifest.get("effective_scientific_config"),
             "FINALIZED_BINDING_INCONSISTENT")
    return manifest, final, _digest(manifest_raw), _digest(final_raw)


def inspect(attempts_root: Path, attempt_id: str, node_id: str = "initial") -> dict:
    node, meta = _paths(attempts_root, attempt_id, node_id)
    if not meta.exists():
        return {"state": "NOT_ADOPTED", "attempt_id": attempt_id, "node_id": node_id}
    if not (meta / "finalization_receipt.json").exists():
        return {"state": "NOT_FINALIZED", "attempt_id": attempt_id, "node_id": node_id}
    try:
        _, _, manifest_sha, final_sha = _published(attempts_root, attempt_id, node_id)
        return {"state": "FINALIZED", "attempt_id": attempt_id, "node_id": node_id,
                "manifest_sha256": manifest_sha, "finalization_sha256": final_sha}
    except ArtifactError as exc:
        return {"state": "INVALID_FINALIZED_CLAIM", "route": exc.route,
                "reason": exc.code, "attempt_id": attempt_id, "node_id": node_id}


def _resolve(attempts_root: Path, attempt_id: str, node_id: str, ref: Mapping[str, Any],
             repo_root: Path, deep: bool, seen: frozenset[str] = frozenset()) -> dict:
    _require(isinstance(ref, Mapping), "REFERENCE_SCHEMA")
    kind = ref.get("kind")
    if kind == "NODE_FILE":
        _require(set(ref) == {"kind", "path", "size_bytes", "sha256"}, "REFERENCE_SCHEMA")
        path = _safe_file(_paths(attempts_root, attempt_id, node_id)[0], ref["path"])
        try:
            size = path.stat().st_size
        except OSError as exc:
            raise ArtifactError("FILE_STAT_UNRESOLVED", "A1") from exc
        digest = None
        if deep:
            size, digest = _hash_file(path)
    elif kind == "GIT_BLOB":
        size, digest = _git_blob(Path(repo_root), ref, deep)
    elif kind == "INHERITED":
        _require(set(ref) == {"kind", "parent_node_id", "layer", "parent_manifest_sha256",
                              "parent_finalization_sha256", "size_bytes", "sha256"}, "REFERENCE_SCHEMA")
        parent = _id(ref["parent_node_id"])
        _require(parent not in seen and parent != node_id, "LINEAGE_CYCLE")
        _require(ref["layer"] in LAYERS, "INHERITED_LAYER_INVALID")
        manifest, _, msha, fsha = _published(attempts_root, attempt_id, parent)
        _require(msha == ref["parent_manifest_sha256"]
                 and fsha == ref["parent_finalization_sha256"], "INHERITED_PARENT_MISMATCH")
        parent_ref = manifest["evidence"][ref["layer"]]
        _require(ref["size_bytes"] == parent_ref["size_bytes"]
                 and ref["sha256"] == parent_ref["sha256"], "INHERITED_CONTENT_MISMATCH")
        return _resolve(attempts_root, attempt_id, parent,
                        parent_ref, repo_root, deep, seen | {node_id})
    else:
        raise ArtifactError("REFERENCE_KIND_INVALID")
    _hex(ref["sha256"])
    _require(type(ref["size_bytes"]) is int and ref["size_bytes"] >= 0, "REFERENCE_SIZE_INVALID")
    if size != ref["size_bytes"] or (deep and digest != ref["sha256"]):
        raise ArtifactError("CONTENT_BINDING_MISMATCH", "A2")
    return {"size_bytes": size, "sha256": ref["sha256"], "verification_depth": "CONTENT" if deep else "METADATA"}


def _validation_receipt(declaration: Mapping[str, Any]) -> dict:
    validation = declaration.get("validation")
    _require(isinstance(validation, Mapping) and set(validation) == {
        "STRUCTURAL_VERDICT", "validated_evidence", "validation_provenance", "description"},
        "VALIDATION_SCHEMA")
    _require(validation["STRUCTURAL_VERDICT"] in {"PASS", "FAIL"}, "STRUCTURAL_VERDICT_INVALID")
    _require(validation["validated_evidence"] == declaration["evidence"], "VALIDATED_EVIDENCE_MISMATCH")
    _require(validation["validation_provenance"] == declaration["provenance"]["validation"],
             "VALIDATION_PROVENANCE_MISMATCH")
    _require(isinstance(validation["description"], str) and validation["description"].strip(),
             "VALIDATION_DESCRIPTION_MISSING")
    return {"schema_version": SCHEMA, **validation,
            "effective_scientific_config": declaration["effective_scientific_config"]}


def _declaration(declaration: Mapping[str, Any], kind: str) -> None:
    _require(isinstance(declaration, Mapping) and set(declaration) == {
        "evidence", "provenance", "validation", "effective_scientific_config",
        "retention", "terminal_binding", "correction"}, "DECLARATION_SCHEMA")
    evidence = declaration["evidence"]
    _require(isinstance(evidence, Mapping) and set(evidence) == set(LAYERS), "EVIDENCE_LAYERS_INVALID")
    provenance = declaration["provenance"]
    _require(isinstance(provenance, Mapping) and set(provenance) == {"derivation", "validation"},
             "PROVENANCE_SCHEMA")
    _require(isinstance(provenance["derivation"], Mapping) and set(provenance["derivation"]) == {
        "raw_evidence", "extractor", "extraction_contract", "extraction_config", "normalized_evidence"},
        "DERIVATION_SCHEMA")
    _require(provenance["derivation"]["raw_evidence"] == evidence["RAW_EVIDENCE"]
             and provenance["derivation"]["normalized_evidence"] == evidence["NORMALIZED_EVIDENCE"],
             "DERIVATION_BINDING_MISMATCH")
    _require(isinstance(provenance["validation"], Mapping) and set(provenance["validation"]) == {
        "normalized_evidence", "validator", "validation_contract", "validation_config"},
        "VALIDATION_PROVENANCE_SCHEMA")
    _require(provenance["validation"]["normalized_evidence"] == evidence["NORMALIZED_EVIDENCE"],
             "VALIDATION_BINDING_MISMATCH")
    _require(isinstance(declaration["retention"], list), "RETENTION_SCHEMA")
    for row in declaration["retention"]:
        _require(isinstance(row, Mapping) and set(row) in ({"path", "tier"},
                 {"path", "tier", "regenerable_from"})
                 and isinstance(row.get("path"), str) and row["path"]
                 and not row["path"].startswith("/")
                 and row.get("tier") in {1, 2, 3}, "RETENTION_ITEM_INVALID")
        if row["tier"] == 3:
            _require(isinstance(row.get("regenerable_from"), list), "REGENERABILITY_DECLARATION_REQUIRED")
    _require((declaration["correction"] is None) == (kind == "initial"), "CORRECTION_SCHEMA")
    _validation_receipt(declaration)


def _eligible(attempts_root: Path, attempt_id: str, declaration: Mapping[str, Any]) -> dict:
    state = inspect_execution(attempts_root, attempt_id)
    _require(state["state"] != "RUNNING" and not state.get("session_live_pids"), "ATTEMPT_RUNNING")
    if state["state"] == "INCOMPLETE":
        binding = declaration["terminal_binding"]
        _require(isinstance(binding, Mapping) and binding.get("kind") == "ABSENT_DERIVED"
                 and isinstance(binding.get("reason"), str) and binding["reason"]
                 and ("launch_identity" in state or binding.get("launch_identity") == "EXPLICITLY_ABSENT"),
                 "INCOMPLETE_TERMINAL_BINDING_REQUIRED")
    else:
        _require(state["state"] in {"COMPLETED", "FAILED"}, "EXECUTION_STATE_INVALID")
    return state


def finalize(attempts_root: Path, attempt_id: str, declaration: Mapping[str, Any], *,
             repo_root: Path, node_id: str = "initial", adopt: bool = False,
             authority_boundary: bool = False, fail_before_marker: bool = False,
             _allow_correction: bool = False) -> dict:
    """Explicit adoption and authority-boundary content verification, then marker LAST."""
    node, meta = _paths(attempts_root, attempt_id, node_id)
    _require(node.is_dir() and not node.is_symlink(), "NODE_ROOT_MISSING")
    _require(adopt and authority_boundary, "EXPLICIT_ADOPTION_AND_AUTHORITY_BOUNDARY_REQUIRED")
    _require(node_id == "initial" or _allow_correction, "CORRECTION_CREATION_PATH_REQUIRED")
    meta.mkdir(exist_ok=True)
    lock_fd = os.open(meta / ".finalize.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ArtifactError("FINALIZATION_BUSY") from exc
        _require(not (meta / "finalization_receipt.json").exists(), "ALREADY_FINALIZED")
        _require(not (meta / "manifest.json").exists() and not (meta / "validation_receipt.json").exists(),
                 "PARTIAL_FINALIZATION_REQUIRES_RESOLUTION")
        state = _eligible(attempts_root, attempt_id, declaration)
        _declaration(declaration, "initial" if node_id == "initial" else "corrective")
        if node_id != "initial":
            _require(declaration["correction"]["parent_node_id"] != node_id, "LINEAGE_CYCLE")
            _published(attempts_root, attempt_id, declaration["correction"]["parent_node_id"])
        for ref in declaration["evidence"].values():
            _resolve(attempts_root, attempt_id, node_id, ref, repo_root, True)
        for ref in (declaration["provenance"]["derivation"][k]
                    for k in ("extractor", "extraction_contract", "extraction_config")):
            _resolve(attempts_root, attempt_id, node_id, ref, repo_root, True)
        for ref in (declaration["provenance"]["validation"][k]
                    for k in ("validator", "validation_contract", "validation_config")):
            _resolve(attempts_root, attempt_id, node_id, ref, repo_root, True)
        _resolve(attempts_root, attempt_id, node_id, declaration["effective_scientific_config"], repo_root, True)
        validation = _validation_receipt(declaration)
        _require(validation["STRUCTURAL_VERDICT"] == "PASS", "STRUCTURAL_VERDICT_FAIL")
        manifest = {"schema_version": SCHEMA, "attempt_id": attempt_id, "node_id": node_id,
                    "kind": "INITIAL" if node_id == "initial" else "CORRECTIVE",
                    "execution_state": state["state"], "launch_identity": state.get("launch_identity"),
                    "terminal_binding": declaration["terminal_binding"],
                    "evidence": dict(declaration["evidence"]), "provenance": dict(declaration["provenance"]),
                    "effective_scientific_config": declaration["effective_scientific_config"],
                    "retention": declaration["retention"], "correction": declaration["correction"],
                    "validation_receipt_sha256": _digest(_canonical(validation))}
        _require(manifest["validation_receipt_sha256"] == _digest(_canonical(validation))
                 and validation["validated_evidence"] == manifest["evidence"]
                 and validation["validation_provenance"] == manifest["provenance"]["validation"]
                 and validation["effective_scientific_config"] == manifest["effective_scientific_config"],
                 "STAGED_SELF_CHECK_FAILED")
        _write_new(meta / "validation_receipt.json", validation)
        _write_new(meta / "manifest.json", manifest)
        if fail_before_marker:
            raise ArtifactError("SIMULATED_PRE_MARKER_INTERRUPTION", "A1")
        final = {"schema_version": SCHEMA, "attempt_id": attempt_id, "node_id": node_id,
                 "manifest_sha256": _digest(_canonical(manifest)),
                 "validation_receipt_sha256": manifest["validation_receipt_sha256"],
                 "finalized_at": _now()}
        _write_new(meta / "finalization_receipt.json", final)
        return inspect(attempts_root, attempt_id, node_id)
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)


def _incident_path(attempts_root: Path, attempt_id: str, node_id: str) -> Path:
    return Path(attempts_root).resolve() / ".v2_3_incidents" / _id(attempt_id) / (_id(node_id) + ".json")


def _record_incident(attempts_root: Path, attempt_id: str, node_id: str,
                     layer: str, reason: str) -> None:
    path = _incident_path(attempts_root, attempt_id, node_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_new(path, {"schema_version": SCHEMA, "attempt_id": attempt_id,
                          "node_id": node_id, "layer": layer, "reason": reason,
                          "verified_at": _now(), "route": "A2"})


def _content_owner(attempts_root: Path, attempt_id: str, node_id: str,
                   layer: str, manifest: Mapping[str, Any]) -> str:
    current_id, current = node_id, manifest
    while current["evidence"][layer]["kind"] == "INHERITED":
        current_id = current["evidence"][layer]["parent_node_id"]
        current = _published(attempts_root, attempt_id, current_id)[0]
    return current_id


def _incident_for_layer(attempts_root: Path, attempt_id: str, node_id: str,
                        layer: str, manifest: Mapping[str, Any]) -> dict | None:
    """Sticky A2 follows only the affected layer through inherited references."""
    current_id = node_id
    current = manifest
    while True:
        path = _incident_path(attempts_root, attempt_id, current_id)
        if path.exists():
            incident, _ = _read(path)
            _require(incident.get("schema_version") == SCHEMA
                     and incident.get("attempt_id") == attempt_id
                     and incident.get("node_id") == current_id
                     and incident.get("route") == "A2", "INCIDENT_INVALID")
            if incident.get("layer") in {layer, "METADATA"}:
                return incident
        ref = current["evidence"][layer]
        if ref["kind"] != "INHERITED":
            return None
        current_id = ref["parent_node_id"]
        current = _published(attempts_root, attempt_id, current_id)[0]


def _corrections(attempts_root: Path, attempt_id: str) -> list[str]:
    domain = Path(attempts_root).resolve() / ".v2_3_corrections" / _id(attempt_id)
    if not domain.exists():
        return []
    _require(domain.is_dir() and not domain.is_symlink(), "CORRECTION_DOMAIN_INVALID")
    children = list(domain.iterdir())
    _require(not any(p.is_symlink() for p in children), "CORRECTION_DOMAIN_SYMLINK")
    return sorted(p.name for p in children if p.is_dir() and IDENTIFIER.fullmatch(p.name))


def _lineage(attempts_root: Path, attempt_id: str, purpose: str, layer: str) -> tuple[dict, bool]:
    nodes = {"initial": _published(attempts_root, attempt_id, "initial")[0]}
    for node_id in _corrections(attempts_root, attempt_id):
        state = inspect(attempts_root, attempt_id, node_id)
        if state["state"] == "FINALIZED":
            nodes[node_id] = _published(attempts_root, attempt_id, node_id)[0]
        elif state["state"] == "INVALID_FINALIZED_CLAIM":
            raise ArtifactError("LINEAGE_NODE_INVALID", "B")
    edges: dict[str, list[str]] = {}
    for node_id, manifest in nodes.items():
        if node_id == "initial":
            continue
        correction = manifest["correction"]
        if purpose in correction["purposes"] and layer in correction["affected_layers"]:
            parent = correction["parent_node_id"]
            _require(parent in nodes, "LINEAGE_PARENT_UNRESOLVED")
            edges.setdefault(parent, []).append(node_id)
    ambiguous = any(len(children) > 1 for children in edges.values())
    relevant = {"initial"} | set(edges) | {child for children in edges.values() for child in children}
    heads = sorted(relevant - set(edges))
    if len(heads) != 1:
        ambiguous = True
    return {"domain": str(Path(attempts_root).resolve() / ".v2_3_corrections" / attempt_id),
            "heads": heads, "edges": edges, "nodes": sorted(nodes)}, ambiguous


def _v21_check(reference: Mapping[str, Any], purpose: str) -> dict:
    try:
        _require(set(reference) == {"path", "sha256", "status", "purpose"}, "V2_1_REFERENCE_SCHEMA")
        _require(reference["purpose"] == purpose and reference["status"] == "PASS",
                 "V2_1_APPLICABILITY_NOT_PASS")
        value, raw = _read(Path(reference["path"]))
        _require(_digest(raw) == _hex(reference["sha256"]), "V2_1_REFERENCE_MISMATCH")
        _require(set(value) == {"schema_version", "status", "purpose", "audit_sha256", "independent_review"}
                 and value["schema_version"] == "V2_1_APPLICABILITY_RESULT_V1"
                 and value["status"] == "PASS" and value["purpose"] == purpose
                 and value["independent_review"] == "PASS", "V2_1_RESULT_NOT_VALIDATED")
        _hex(value["audit_sha256"])
        return {"status": "PASS", "reference_sha256": reference["sha256"]}
    except (ArtifactError, KeyError, TypeError) as exc:
        return {"status": "FAIL", "reason": str(exc)}


def check_reuse(attempts_root: Path, attempt_id: str, node_id: str, *, purpose: str,
                consumption_class: str, anchor: Mapping[str, Any], expected_artifacts: Mapping[str, Any],
                expected_provenance: Mapping[str, Any], v2_1_applicability: Mapping[str, Any],
                consumer_record: Path, repo_root: Path) -> dict:
    """Conjunctive C1-C6; always record the exact consumer pin and decision."""
    _require(consumption_class in CLASSES and isinstance(purpose, str) and purpose, "CONSUMPTION_INPUT_INVALID")
    checks = {"C{}".format(i): {"status": "UNKNOWN"} for i in range(1, 7)}
    route, reason, manifest, current_layer = None, None, None, None
    try:
        manifest, final, msha, fsha = _published(attempts_root, attempt_id, node_id)
        checks["C1"] = {"status": "PASS" if anchor.get("attempt_id") == attempt_id
                        and anchor.get("node_id") == node_id else "FAIL"}
        if checks["C1"]["status"] != "PASS":
            raise ArtifactError("ATTEMPT_IDENTITY_MISMATCH", "A2")
        if anchor.get("manifest_sha256") != msha or anchor.get("finalization_sha256") != fsha:
            raise ArtifactError("CONSUMER_ANCHOR_MISMATCH", "A2")
        for layer in LAYERS:
            current_layer = layer
            incident = _incident_for_layer(attempts_root, attempt_id, node_id, layer, manifest)
            if incident is not None:
                raise ArtifactError("STICKY_VERIFIED_MISMATCH", "A2_RAW" if layer == "RAW_EVIDENCE" else "A2")
            if expected_artifacts.get(layer) != manifest["evidence"][layer]:
                raise ArtifactError("EXPECTED_ARTIFACT_MISMATCH", "A2")
            _resolve(attempts_root, attempt_id, node_id, manifest["evidence"][layer], repo_root,
                     consumption_class == "FORMAL_AUTHORIZATION_SUPPORT")
        checks["C2"] = {"status": "PASS"}
        if (expected_provenance != manifest["provenance"]
                or final["validation_receipt_sha256"] != manifest["validation_receipt_sha256"]):
            raise ArtifactError("VALIDATION_PROVENANCE_MISMATCH", "A2")
        for identity in (manifest["provenance"]["derivation"][key]
                         for key in ("extractor", "extraction_contract", "extraction_config")):
            _resolve(attempts_root, attempt_id, node_id, identity, repo_root,
                     consumption_class == "FORMAL_AUTHORIZATION_SUPPORT")
        for identity in (manifest["provenance"]["validation"][key]
                         for key in ("validator", "validation_contract", "validation_config")):
            _resolve(attempts_root, attempt_id, node_id, identity, repo_root,
                     consumption_class == "FORMAL_AUTHORIZATION_SUPPORT")
        _resolve(attempts_root, attempt_id, node_id, manifest["effective_scientific_config"],
                 repo_root, consumption_class == "FORMAL_AUTHORIZATION_SUPPORT")
        checks["C3"] = {"status": "PASS"}
        checks["C4"] = _v21_check(v2_1_applicability, purpose)
        lineage_rows = {}
        any_ambiguous = False
        any_superseded = False
        for layer in LAYERS:
            lineage, ambiguous = _lineage(attempts_root, attempt_id, purpose, layer)
            owner = node_id
            ref = manifest["evidence"][layer]
            while ref["kind"] == "INHERITED":
                owner = ref["parent_node_id"]
                parent = _published(attempts_root, attempt_id, owner)[0]
                ref = parent["evidence"][layer]
            lineage_rows[layer] = {"heads": lineage["heads"], "owner_node_id": owner,
                                   "supersession": lineage["edges"]}
            any_ambiguous |= ambiguous
            any_superseded |= owner not in lineage["heads"]
        checks["C5"] = {"status": "FAIL" if any_ambiguous else "PASS",
                        "lookup_domain": lineage["domain"], "layers": lineage_rows}
        checks["C6"] = {"status": "FAIL" if any_ambiguous or any_superseded else "PASS",
                        "layers": lineage_rows}
        if checks["C4"]["status"] != "PASS" or any_ambiguous or any_superseded:
            route, reason = "B", "APPLICABILITY_OR_LINEAGE_NOT_CURRENT"
    except ArtifactError as exc:
        route, reason = exc.route, exc.code
        if exc.code == "CONTENT_BINDING_MISMATCH" and current_layer in LAYERS and manifest:
            owner = _content_owner(attempts_root, attempt_id, node_id, current_layer, manifest)
            _record_incident(attempts_root, attempt_id, owner, current_layer, exc.code)
        elif exc.code in {"FINAL_MANIFEST_MISMATCH", "VALIDATION_RECEIPT_MISMATCH"}:
            _record_incident(attempts_root, attempt_id, node_id, "METADATA", exc.code)
        if exc.code == "ATTEMPT_IDENTITY_MISMATCH":
            checks["C1"] = {"status": "FAIL"}
        elif exc.code in {"CONTENT_BINDING_MISMATCH", "EXPECTED_ARTIFACT_MISMATCH"}:
            checks["C2"] = {"status": "FAIL"}
            if current_layer == "RAW_EVIDENCE" and exc.route == "A2":
                route = "A2_RAW"
        elif exc.code in {"VALIDATION_PROVENANCE_MISMATCH", "CONSUMER_ANCHOR_MISMATCH"}:
            checks["C3"] = {"status": "FAIL"}
    decision = "REUSE_ADMISSIBLE" if all(row["status"] == "PASS" for row in checks.values()) else "REUSE_REFUSED"
    if route == "A2_RAW":
        decision = "BLOCK"
    result = {"schema_version": SCHEMA, "timestamp": _now(), "purpose": purpose,
              "consumption_class": consumption_class, "attempt_id": attempt_id, "node_id": node_id,
              "anchor": dict(anchor), "C1_C6": checks, "v2_1_applicability": dict(v2_1_applicability),
              "verification_depth": "CONTENT" if consumption_class == "FORMAL_AUTHORIZATION_SUPPORT" else "METADATA",
              "route": route, "reason": reason, "decision": decision}
    _write_new(Path(consumer_record), result)
    return result


def create_correction(attempts_root: Path, attempt_id: str, node_id: str,
                      declaration: Mapping[str, Any], *, repo_root: Path) -> dict:
    """Corrective metadata and changed layers live outside the finalized parent."""
    _require(node_id != "initial", "CORRECTION_NODE_ID_INVALID")
    _declaration(declaration, "corrective")
    c = declaration["correction"]
    _require(isinstance(c, Mapping) and set(c) == {"parent_node_id", "affected_layers", "purposes",
             "defect_class", "defect_evidence", "v2_1_change_impact", "accepted_authority"},
             "CORRECTION_SCHEMA")
    _require(c["parent_node_id"] != node_id and isinstance(c["affected_layers"], list)
             and c["affected_layers"] and set(c["affected_layers"]).issubset(LAYERS)
             and isinstance(c["purposes"], list) and c["purposes"]
             and all(isinstance(x, str) and x for x in c["purposes"]), "CORRECTION_SCOPE_INVALID")
    _require(c["defect_class"] in {"ARTIFACT", "EXTRACTOR", "VALIDATOR", "SCIENTIFIC_MECHANISM", "SCIENTIFIC_CONFIG"},
             "DEFECT_CLASS_UNRESOLVED")
    _require(isinstance(c["defect_evidence"], Mapping)
             and set(c["defect_evidence"]) == {"route", "reference"}
             and isinstance(c["defect_evidence"]["route"], str), "DEFECT_EVIDENCE_MISSING")
    _resolve(attempts_root, attempt_id, c["parent_node_id"],
             c["defect_evidence"]["reference"], repo_root, True)
    impact = c["v2_1_change_impact"]
    _require(isinstance(impact, Mapping) and set(impact) == {"status", "reference_path",
             "reference_sha256", "scientific_impact"} and impact["status"] == "PASS",
             "V2_1_CHANGE_IMPACT_UNRESOLVED")
    impact_doc, impact_raw = _read(Path(impact["reference_path"]))
    _require(_digest(impact_raw) == _hex(impact["reference_sha256"])
             and impact_doc == {"schema_version": "V2_1_CHANGE_IMPACT_RESULT_V1",
                                "status": "PASS", "review_status": "PASS",
                                "scientific_impact": impact["scientific_impact"]},
             "V2_1_CHANGE_IMPACT_UNRESOLVED")
    expected_layer = "SCIENCE" if c["defect_class"].startswith("SCIENTIFIC_") else "PLATFORM"
    _require(isinstance(c["accepted_authority"], Mapping)
             and c["accepted_authority"].get("layer") == expected_layer
             and isinstance(c["accepted_authority"].get("identity"), Mapping),
             "ACCEPTED_AUTHORITY_MISSING")
    _resolve(attempts_root, attempt_id, c["parent_node_id"],
             c["accepted_authority"]["identity"], repo_root, True)
    if expected_layer == "PLATFORM":
        _require(impact.get("scientific_impact") == "NONE", "NON_SCIENTIFIC_DEFECT_UNPROVEN")
    _require(not ("RAW_EVIDENCE" in c["affected_layers"]
                   and c["defect_evidence"].get("route") == "A2_RAW"), "RAW_A2_REPLACEMENT_FORBIDDEN")
    parent, _, pmsha, pfsha = _published(attempts_root, attempt_id, c["parent_node_id"])
    _require(_incident_for_layer(attempts_root, attempt_id, c["parent_node_id"],
                                 "RAW_EVIDENCE", parent) is None, "RAW_A2_LINEAGE_BLOCKED")
    for layer in LAYERS:
        if layer not in c["affected_layers"]:
            ref = declaration["evidence"][layer]
            _require(ref == {"kind": "INHERITED", "parent_node_id": c["parent_node_id"], "layer": layer,
                             "parent_manifest_sha256": pmsha, "parent_finalization_sha256": pfsha,
                             "size_bytes": parent["evidence"][layer]["size_bytes"],
                             "sha256": parent["evidence"][layer]["sha256"]}, "INHERITED_LAYER_BINDING_INVALID")
    node, _ = _paths(attempts_root, attempt_id, node_id)
    node.mkdir(parents=True, exist_ok=True)
    _require(not (node / "v2_3/finalization_receipt.json").exists(), "CORRECTION_NODE_ALREADY_FINALIZED")
    return finalize(attempts_root, attempt_id, declaration, repo_root=repo_root, node_id=node_id,
                    adopt=True, authority_boundary=True, _allow_correction=True)


def check_cleanup_eligibility(attempts_root: Path, attempt_id: str, node_id: str,
                              artifact_path: str) -> dict:
    manifest, _, _, _ = _published(attempts_root, attempt_id, node_id)
    rows = [row for row in manifest["retention"] if row.get("path") == artifact_path]
    _require(len(rows) == 1, "RETENTION_ITEM_UNKNOWN")
    row = rows[0]
    _require(row.get("tier") in {1, 2, 3}, "RETENTION_TIER_INVALID")
    holds = Path(attempts_root).resolve() / ".v2_3_holds" / attempt_id / node_id
    audit_hold = (holds / "audit_hold").exists()
    correction_hold = (holds / "correction_hold").exists()
    inherited = False
    for child in _corrections(attempts_root, attempt_id):
        if inspect(attempts_root, attempt_id, child)["state"] != "FINALIZED":
            continue
        child_manifest = _published(attempts_root, attempt_id, child)[0]
        inherited |= any(ref.get("kind") == "INHERITED" and ref.get("parent_node_id") == node_id
                         and manifest["evidence"][ref["layer"]].get("path") == artifact_path
                         for ref in child_manifest["evidence"].values())
    effective_tier = 1 if inherited else row["tier"]
    def retained_source(path: str) -> bool:
        if not any(item.get("tier") == 1 and item.get("path") == path
                   for item in manifest["retention"]):
            return False
        try:
            _safe_file(_paths(attempts_root, attempt_id, node_id)[0], path)
            return True
        except ArtifactError:
            return False
    regenerable = bool(row.get("regenerable_from")) and all(
        retained_source(path) for path in row.get("regenerable_from", []))
    eligible = effective_tier == 3 and not audit_hold and not correction_hold and regenerable
    return {"tier": effective_tier, "cleanup_eligible": eligible, "audit_hold": audit_hold,
            "correction_hold": correction_hold, "inherited_by_current_lineage": inherited,
            "regenerable_from_retained_tier1": regenerable}
