"""V2-1 change-impact evidence. This module never authorizes a Formal run."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Mapping


class ImpactError(ValueError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=str(root), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode:
        raise ImpactError("GIT_INPUT_INVALID: {}".format(" ".join(args)))
    return result.stdout


def _commit(root: Path, value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ImpactError("EXACT_COMMIT_SHA_REQUIRED")
    observed = _git(root, "rev-parse", "--verify", value + "^{commit}").decode().strip()
    if observed != value:
        raise ImpactError("COMMIT_IDENTITY_MISMATCH")
    return observed


def semantic_identity(mapping: Mapping[str, Any]) -> str:
    """Exclude locators and Git identity: a proven rename can preserve semantics."""
    units = []
    for unit in mapping["behavior_units"]:
        units.append({key: unit[key] for key in (
            "behavior_unit_id", "dependency_edges", "protected_invariants",
            "validation_level", "dynamic_dependency_status")})
    return digest({"mapping_scope": mapping["mapping_scope"],
                   "protected_invariants": mapping["protected_invariants"],
                   "behavior_units": sorted(units, key=lambda row: row["behavior_unit_id"]),
                   "evidence": mapping["evidence"],
                   "reviewed_unknown_scopes": mapping.get("reviewed_unknown_scopes", [])})


def mapping_digest(mapping: Mapping[str, Any]) -> str:
    return digest({key: value for key, value in mapping.items() if key != "mapping_digest"})


def validate_mapping(mapping: Mapping[str, Any]) -> dict:
    if mapping.get("schema_version") != "GOVERNANCE_V2_DEPENDENCY_MAP_V1":
        raise ImpactError("MAP_SCHEMA_INVALID")
    if mapping.get("dependency_mapping_identity") != semantic_identity(mapping):
        raise ImpactError("MAP_SEMANTIC_IDENTITY_MISMATCH")
    if mapping.get("mapping_digest") != mapping_digest(mapping):
        raise ImpactError("MAP_DIGEST_MISMATCH")
    units = mapping["behavior_units"]
    ids = [row["behavior_unit_id"] for row in units]
    if len(ids) != len(set(ids)) or not ids:
        raise ImpactError("MAP_UNIT_IDS_INVALID")
    known = set(ids)
    invariants = set(mapping["protected_invariants"])
    for row in units:
        if (row["validation_level"] not in {"L0", "L1", "L2", "L3"}
                or row["dynamic_dependency_status"] not in {"CLOSED", "UNMAPPED"}
                or not set(row["dependency_edges"]).issubset(known)
                or not set(row["protected_invariants"]).issubset(invariants)
                or not row["source_locator"]):
            raise ImpactError("MAP_UNIT_INVALID: " + row["behavior_unit_id"])
        for locator in row["source_locator"]:
            if not locator.get("path") or not locator.get("symbol") or not locator.get("match_tokens"):
                raise ImpactError("MAP_LOCATOR_INVALID")
    for row in mapping["evidence"]:
        if not set(row["proven_behavior_units"]).issubset(known):
            raise ImpactError("MAP_EVIDENCE_INVALID")
    scope_keys = set()
    for row in mapping.get("reviewed_unknown_scopes", []):
        key = (row.get("diff_sha256"), row.get("hunk_sha256"))
        if (key in scope_keys or not all(re.fullmatch(r"[0-9a-f]{64}", item or "") for item in key)
                or not set(row.get("potential_behavior_units", [])).issubset(known)
                or not row.get("potential_behavior_units") or not row.get("scope_basis")
                or not row.get("path") or not row.get("hunk")):
            raise ImpactError("MAP_REVIEWED_UNKNOWN_SCOPE_INVALID")
        scope_keys.add(key)
    return dict(mapping)


def make_mapping(raw: Mapping[str, Any]) -> dict:
    mapping = dict(raw)
    mapping["dependency_mapping_identity"] = semantic_identity(mapping)
    mapping["mapping_digest"] = mapping_digest(mapping)
    return validate_mapping(mapping)


def _source_paths(mapping: Mapping[str, Any]) -> list:
    return sorted({loc["path"] for unit in mapping["behavior_units"]
                   if unit["validation_level"] != "L0"
                   for loc in unit["source_locator"]})


def make_applicability(mapping: Mapping[str, Any], root: Path, anchor_sha: str) -> dict:
    """Bind a semantic map once to exact audited source bytes, not every commit."""
    _commit(root, anchor_sha)
    files = {}
    for path in _source_paths(mapping):
        try:
            files[path] = hashlib.sha256(_git(root, "show", anchor_sha + ":" + path)).hexdigest()
        except ImpactError as exc:
            raise ImpactError("MAP_ANCHOR_SOURCE_MISSING: " + path) from exc
    return {"schema_version": "GOVERNANCE_V2_MAP_APPLICABILITY_V1",
            "dependency_mapping_identity": mapping["dependency_mapping_identity"],
            "mapping_digest": mapping["mapping_digest"],
            "anchor_implementation_sha": anchor_sha,
            "audited_source_sha256": files}


def check_applicability(mapping: Mapping[str, Any], claim: Mapping[str, Any],
                        root: Path, base: str, target: str) -> dict:
    """A changed source requires a new reviewed claim; unrelated commits do not."""
    anchor = claim.get("anchor_implementation_sha")
    if (claim.get("schema_version") != "GOVERNANCE_V2_MAP_APPLICABILITY_V1"
            or claim.get("dependency_mapping_identity") != mapping["dependency_mapping_identity"]
            or claim.get("mapping_digest") != mapping["mapping_digest"]
            or set(claim.get("audited_source_sha256", {})) != set(_source_paths(mapping))):
        return {"status": "BLOCK", "reason": "MAP_APPLICABILITY_CLAIM_INVALID"}
    try:
        _commit(root, anchor)
        if make_applicability(mapping, root, anchor) != claim:
            return {"status": "BLOCK", "reason": "MAP_ANCHOR_BYTES_MISMATCH"}
        if _git(root, "merge-base", "--is-ancestor", target, anchor) == b"":
            # merge-base --is-ancestor returns empty stdout on success, but
            # _git already checked the return code. Retrospective diffs are
            # examples, never qualification of their old execution authority.
            return {"status": "RETROSPECTIVE", "anchor_implementation_sha": anchor}
    except ImpactError:
        pass
    try:
        _git(root, "merge-base", "--is-ancestor", anchor, base)
        for path, expected in claim["audited_source_sha256"].items():
            if hashlib.sha256(_git(root, "show", base + ":" + path)).hexdigest() != expected:
                return {"status": "BLOCK", "reason": "BASE_MAP_SOURCE_DRIFT", "path": path}
        return {"status": "APPLICABLE_TO_BASE", "anchor_implementation_sha": anchor,
                "target_requires_delta_review": True}
    except ImpactError:
        return {"status": "BLOCK", "reason": "UNPROVEN_MAP_APPLICABILITY"}


def _hunks(diff: str) -> list:
    path = None
    hunks = []
    current = None
    old_line = new_line = 0
    for line in diff.splitlines():
        if line.startswith("diff --git a/"):
            path = line.split(" b/", 1)[1]
            current = None
        elif line.startswith("@@ "):
            bounds = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if bounds is None:
                raise ImpactError("DIFF_HUNK_INVALID")
            old_line, new_line = int(bounds.group(1)), int(bounds.group(2))
            current = {"path": path, "header": line, "changed_lines": []}
            hunks.append(current)
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            current["changed_lines"].append({"side": "target", "line": new_line, "text": line[1:]})
            new_line += 1
        elif current is not None and line.startswith("-") and not line.startswith("---"):
            current["changed_lines"].append({"side": "base", "line": old_line, "text": line[1:]})
            old_line += 1
        elif current is not None and line.startswith(" "):
            old_line += 1
            new_line += 1
    return hunks


def _symbol_at(source: bytes, line: int) -> str:
    try:
        tree = ast.parse(source.decode("utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return "<unparseable>"
    selected = "<module>"
    def visit(node: ast.AST, prefix: str = "") -> None:
        nonlocal selected
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                end = getattr(child, "end_lineno", None)
                if child.lineno <= line <= (end or child.lineno):
                    name = prefix + child.name
                    selected = name
                    visit(child, name + ".")
            elif not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, prefix)
    visit(tree)
    return selected


def _closure(unit_id: str, by_id: Mapping[str, dict]) -> set:
    """dependency_edges point from a consumer to the behavior it depends on."""
    visited = set()
    pending = [unit_id]
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        pending.extend(by_id[current]["dependency_edges"])
    return visited


def _downstream_closure(start: set, by_id: Mapping[str, dict]) -> set:
    """Reverse dependency_edges: a changed dependency may affect its consumers."""
    reverse = {unit_id: set() for unit_id in by_id}
    for consumer, row in by_id.items():
        for dependency in row["dependency_edges"]:
            reverse[dependency].add(consumer)
    affected = set(start)
    pending = list(start)
    while pending:
        for consumer in reverse[pending.pop()]:
            if consumer not in affected:
                affected.add(consumer)
                pending.append(consumer)
    return affected


def _hunk_digest(hunk: Mapping[str, Any]) -> str:
    return digest({key: hunk[key] for key in ("path", "header", "changed_lines")})


def _scope_unknown(item: dict, potential: set, by_id: Mapping[str, dict],
                   evidence_rows: list, basis: str) -> dict:
    affected = _downstream_closure(potential, by_id)
    item.update({"unknown_scope_kind": "SCOPED_UNKNOWN",
                 "potential_behavior_units": sorted(affected),
                 "potential_invariants": sorted({inv for unit in affected
                                                 for inv in by_id[unit]["protected_invariants"]}),
                 "potential_evidence_families": sorted(row["evidence_id"] for row in evidence_rows
                     if set().union(*(_closure(unit, by_id) for unit in row["proven_behavior_units"]))
                     & affected),
                 "scope_basis": basis})
    return item


def _unbounded_unknown(item: dict, by_id: Mapping[str, dict], evidence_rows: list) -> dict:
    item.update({"unknown_scope_kind": "UNBOUNDED_UNKNOWN",
                 "potential_behavior_units": sorted(by_id),
                 "potential_invariants": sorted({inv for row in by_id.values()
                                                 for inv in row["protected_invariants"]}),
                 "potential_evidence_families": sorted(row["evidence_id"] for row in evidence_rows),
                 "scope_basis": "No exact reviewed hunk scope; all mapped closures remain potentially affected"})
    return item


def classify_evidence(evidence: Mapping[str, Any], by_id: Mapping[str, dict],
                      changed: set, *, unknown_paths: list = None,
                      applicability_blocked: bool = False) -> dict:
    """Classify one evidence family from its protected behavior closure."""
    proven = set(evidence["proven_behavior_units"])
    dependency_closure = set().union(*(_closure(unit, by_id) for unit in proven))
    direct = sorted(proven & changed)
    upstream = sorted((dependency_closure - proven) & changed)
    dynamic = sorted(unit for unit in dependency_closure
                     if by_id[unit]["dynamic_dependency_status"] == "UNMAPPED")
    relevant_unknown = [item for item in (unknown_paths or [])
                        if item.get("unknown_scope_kind") != "SCOPED_UNKNOWN"
                        or evidence["evidence_id"] in item.get("potential_evidence_families", [])]
    if relevant_unknown or applicability_blocked or dynamic:
        classification = "UNMAPPED"
        condition = "BLOCK until unknown dependency or applicability is independently closed"
    elif direct:
        classification = "NON_INHERITABLE"
        condition = "rerun proof for changed behavior units: " + ", ".join(direct)
    elif upstream:
        classification = "CONDITIONALLY_INHERITABLE"
        condition = "PASS qualification of changed upstream units: " + ", ".join(upstream)
    else:
        classification = "INHERITABLE"
        condition = "protected dependency closure unchanged in this diff"
    return {"evidence_id": evidence["evidence_id"],
            "classification": classification, "condition": condition,
            "protected_dependency_closure": sorted(dependency_closure),
            "unresolved_dynamic_units": dynamic,
            "blocking_unknown_hunks": [item.get("hunk_sha256", item.get("reason"))
                                       for item in relevant_unknown],
            "direct_changed_units": direct, "upstream_changed_units": upstream}


def audit_diff(root: Path, base: str, target: str, mapping: Mapping[str, Any],
               claim: Mapping[str, Any]) -> dict:
    """Produce a candidate CIM from real Git bytes. BLOCK is the safe default."""
    mapping = validate_mapping(mapping)
    base, target = _commit(root, base), _commit(root, target)
    raw_diff = _git(root, "diff", "--binary", "--no-ext-diff", "--no-renames", base, target, "--")
    raw_names = _git(root, "diff", "--name-only", "--no-renames", base, target, "--")
    paths = [line for line in raw_names.decode().splitlines() if line]
    hunks = _hunks(raw_diff.decode("utf-8", errors="replace"))
    diff_sha = hashlib.sha256(raw_diff).hexdigest()
    reviewed_scopes = {(row["diff_sha256"], row["hunk_sha256"]): row
                       for row in mapping.get("reviewed_unknown_scopes", [])}
    by_id = {row["behavior_unit_id"]: row for row in mapping["behavior_units"]}
    changed = set()
    unknown = []
    covered_paths = set()
    details = []
    for hunk in hunks:
        matched = set()
        source_cache = {}
        def source_for(side: str) -> bytes:
            if side not in source_cache:
                revision = target if side == "target" else base
                source_cache[side] = _git(root, "show", revision + ":" + hunk["path"])
            return source_cache[side]
        for unit in mapping["behavior_units"]:
            for loc in unit["source_locator"]:
                if loc["path"] != hunk["path"]:
                    continue
                allowed_symbols = {value.strip() for value in re.split(r"\s+(?:/|or)\s+", loc["symbol"])}
                for change in hunk["changed_lines"]:
                    if not any(token == "*" or token in change["text"] for token in loc["match_tokens"]):
                        continue
                    if loc["symbol"] == "test-only qualification":
                        matched.add(unit["behavior_unit_id"])
                        continue
                    try:
                        symbol = _symbol_at(source_for(change["side"]), change["line"])
                    except ImpactError:
                        continue
                    if symbol in allowed_symbols:
                        matched.add(unit["behavior_unit_id"])
        if not matched:
            hunk_sha = _hunk_digest(hunk)
            item = {"path": hunk["path"], "hunk": hunk["header"],
                    "hunk_sha256": hunk_sha, "reason": "NO_REVIEWED_BEHAVIOR_MATCH"}
            reviewed = reviewed_scopes.get((diff_sha, hunk_sha))
            if reviewed and reviewed["path"] == hunk["path"] and reviewed["hunk"] == hunk["header"]:
                item = _scope_unknown(item, set(reviewed["potential_behavior_units"]),
                                      by_id, mapping["evidence"], reviewed["scope_basis"])
                item["reviewed_scope_diff_sha256"] = diff_sha
            else:
                item = _unbounded_unknown(item, by_id, mapping["evidence"])
            unknown.append(item)
        changed.update(matched)
        covered_paths.add(hunk["path"])
        details.append({"path": hunk["path"], "hunk": hunk["header"],
                        "behavior_unit_ids": sorted(matched)})
    for path in paths:
        if path not in covered_paths:
            unknown.append(_unbounded_unknown({"path": path, "reason": "NON_TEXT_OR_NO_HUNK"},
                                               by_id, mapping["evidence"]))
    affected_behavior = _downstream_closure(changed, by_id)
    affected = {inv for unit_id in affected_behavior
                for inv in by_id[unit_id]["protected_invariants"]}
    applicable = check_applicability(mapping, claim, root, base, target)
    dynamic_unknown = sorted(unit_id for unit_id in changed
                             if by_id[unit_id]["dynamic_dependency_status"] == "UNMAPPED")
    if dynamic_unknown:
        unknown.extend(_scope_unknown({"behavior_unit_id": unit_id,
                                      "path": by_id[unit_id]["source_locator"][0]["path"],
                                      "changed_hunks": [row["hunk"] for row in details
                                                        if unit_id in row["behavior_unit_ids"]],
                                      "reason": "DYNAMIC_DEPENDENCY_UNMAPPED"},
                                     {unit_id}, by_id, mapping["evidence"],
                                     "Declared UNMAPPED dynamic node and its downstream dependency closure")
                       for unit_id in dynamic_unknown)
    inherited = []
    required = set()
    for evidence in mapping["evidence"]:
        row = classify_evidence(evidence, by_id, changed,
                                unknown_paths=unknown, applicability_blocked=applicable["status"] == "BLOCK")
        inherited.append(row)
        if row["classification"] == "NON_INHERITABLE":
            required.add(evidence["validation_gate"])
        elif row["classification"] == "CONDITIONALLY_INHERITABLE":
            required.update(by_id[unit]["requalification_gate"] for unit in row["upstream_changed_units"])
    required.update(by_id[unit]["requalification_gate"] for unit in changed)
    if unknown:
        required.add("INDEPENDENT_DEPENDENCY_CLOSURE_REVIEW")
    levels = sorted({by_id[unit]["validation_level"] for unit in changed})
    return {"schema_version": "CHANGE_IMPACT_MANIFEST_V1",
            "role": "TEAM_A_CANDIDATE_EVIDENCE_NOT_AUTHORIZATION",
            "base_implementation_sha": base, "target_implementation_sha": target,
            "diff_sha256": diff_sha, "changed_files": paths,
            "dependency_mapping_identity": mapping["dependency_mapping_identity"],
            "mapping_digest": mapping["mapping_digest"],
            "mapping_applicability": applicable,
            "changed_behavior_units": sorted(changed), "changed_hunks": details,
            "affected_behavior_units": sorted(affected_behavior),
            "affected_invariants": sorted(affected), "unmapped_unknown_paths": unknown,
            "evidence_inheritance": inherited, "required_requalification_layers": levels,
            "minimum_requalification": sorted(required),
            "candidate_verdict": "BLOCK" if unknown or applicable["status"] == "BLOCK"
            else "CANDIDATE_REVIEWABLE_TEAM_B_PENDING"}
