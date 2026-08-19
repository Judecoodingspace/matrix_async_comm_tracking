#!/usr/bin/env python3
"""Execute the source-only G1-G7 MDMT non-test MDA GT protocol gate.

The CLI is intentionally staged.  ``derive-non-test`` refuses to run unless a
compatible official-test exact-equivalence artifact exists.  It never imports
or runs MIA, tracking, detector inference, or any prediction evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from datasets.mdmt_mda_gt_protocol import (
    POLICY_VERSION,
    ProtocolError,
    XmlAudit,
    artifact_hashes,
    audit_identity_pairs,
    canonical_decimal,
    compare_multisets,
    csv_write,
    dataset_source_fingerprint,
    discover_xml_audits,
    duplicate_identity_stats,
    find_gt_files,
    fingerprint_payload,
    image_dimensions,
    image_paths,
    json_read,
    json_write,
    mda_rows_from_audit,
    parse_official_mda,
    policy_payload,
    repository_state,
    runtime_environment,
    sha256_file,
    source_manifest_rows,
    write_mda_rows,
)


GATE_STATE_DIR = "records"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=(
        "audit-source", "validate-official-test", "derive-non-test", "repeat-verify", "finalize-gate"))
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--official-test-gt-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-label", choices=("run_a", "run_b"), default="run_a")
    parser.add_argument("--identity-evidence", type=Path)
    parser.add_argument("--expected-xml-count", type=int, default=88)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_path(output_dir: Path, name: str) -> Path:
    return output_dir / GATE_STATE_DIR / name


def load_state(output_dir: Path, name: str) -> Dict[str, object]:
    path = state_path(output_dir, name)
    if not path.is_file():
        raise ProtocolError("required gate state is missing: {}".format(path))
    return json_read(path)


def optional_state(output_dir: Path, name: str, *, reason: str) -> Dict[str, object]:
    """Return an explicit blocked state when an earlier hard gate stopped work."""
    path = state_path(output_dir, name)
    if path.is_file():
        return json_read(path)
    return {"status": "BLOCKED_BY_UNKNOWN", "unknowns": [reason], "state_missing": name}


def audit_index(audits: Sequence[XmlAudit]) -> Dict[Tuple[str, str, int], XmlAudit]:
    values: Dict[Tuple[str, str, int], XmlAudit] = {}
    for audit in audits:
        if audit.split is None:
            continue
        key = (audit.split, audit.sequence_id, audit.view_id)
        if key in values:
            raise ProtocolError("duplicate source XML audit key: {}".format(key))
        values[key] = audit
    return values


def g1_status(audits: Sequence[XmlAudit], expected_count: int) -> Tuple[str, List[str]]:
    failures: List[str] = []
    if len(audits) != expected_count:
        failures.append("xml_file_count={} expected={}".format(len(audits), expected_count))
    for audit in audits:
        if audit.split is None:
            failures.append("split_resolution:{}".format(audit.path))
        if audit.issues:
            failures.append("source_issue:{}".format(audit.path))
    return ("PASS" if not failures else "FAIL", failures)


def run_audit_source(args: argparse.Namespace) -> int:
    audits = discover_xml_audits(args.dataset_root)
    manifest_rows = source_manifest_rows(audits)
    source_manifest = args.output_dir / "manifests" / "source_annotation_manifest.csv"
    field_report = args.output_dir / "audits" / "field_completeness_report.csv"
    policy_path = args.output_dir / "policy" / "mapping_rule_manifest.json"
    csv_write(source_manifest, manifest_rows, (
        "split", "sequence_id", "view_id", "xml_path", "xml_sha256", "parser_status", "issue_count",
        "track_count", "box_count", "valid_box_count", "eligible_box_count", "outside_box_count",
        "occluded_box_count", "issues"))
    csv_write(field_report, manifest_rows, (
        "split", "sequence_id", "view_id", "xml_path", "parser_status", "issue_count", "issues"))
    policy = policy_payload()
    json_write(policy_path, policy)
    status, failures = g1_status(audits, args.expected_xml_count)
    state = {
        "gate": "G1",
        "status": status,
        "failures": failures,
        "expected_xml_count": args.expected_xml_count,
        "observed_xml_count": len(audits),
        "source_fingerprint": dataset_source_fingerprint(args.dataset_root),
        "source_manifest_sha256": sha256_file(source_manifest),
        "field_report_sha256": sha256_file(field_report),
        "policy_sha256": sha256_file(policy_path),
        "policy_version": POLICY_VERSION,
        "recorded_at_utc": now_utc(),
    }
    json_write(state_path(args.output_dir, "g1_source_audit.json"), state)
    print("G1 status={} xml_files={} failures={}".format(status, len(audits), len(failures)), flush=True)
    return 0 if status == "PASS" else 2


def require_g1_compatible(args: argparse.Namespace) -> Dict[str, object]:
    state = load_state(args.output_dir, "g1_source_audit.json")
    if state.get("status") != "PASS":
        raise ProtocolError("G1 is not PASS")
    if state.get("source_fingerprint") != dataset_source_fingerprint(args.dataset_root):
        raise ProtocolError("source XML fingerprint drift since G1")
    policy_path = args.output_dir / "policy" / "mapping_rule_manifest.json"
    if not policy_path.is_file() or state.get("policy_sha256") != sha256_file(policy_path):
        raise ProtocolError("mapping policy fingerprint drift since G1")
    return state


def generated_root(output_dir: Path, run_label: str, split: str) -> Path:
    return output_dir / run_label / "generated_gt" / split


def write_split_gt(audits: Sequence[XmlAudit], *, split: str, destination: Path) -> Dict[Tuple[str, int], List[object]]:
    selected = [audit for audit in audits if audit.split == split]
    rows_by_file: Dict[Tuple[str, int], List[object]] = {}
    for audit in selected:
        rows = mda_rows_from_audit(audit)
        rows_by_file[(audit.sequence_id, audit.view_id)] = rows
        write_mda_rows(destination / "{}-{}.txt".format(audit.sequence_id, audit.view_id), rows)
    return rows_by_file


def outside_occluded_row(audit: XmlAudit, generated: Sequence[object]) -> Dict[str, object]:
    expected = mda_rows_from_audit(audit)
    source_outside = sum(int(box.outside) for box in audit.boxes)
    source_occluded_eligible = sum(int((not box.outside) and box.occluded) for box in audit.boxes)
    comparison = compare_multisets(expected, generated)
    return {
        "split": audit.split or "",
        "sequence_id": audit.sequence_id,
        "view_id": audit.view_id,
        "source_outside_box_count": source_outside,
        "source_occluded_eligible_box_count": source_occluded_eligible,
        "expected_eligible_row_count": len(expected),
        "generated_row_count": len(generated),
        "exact_expected_generated": comparison["exact"],
        "outside_rule_supported": int(source_outside > 0 and int(comparison["exact"]) == 1),
        "occluded_rule_supported": int(source_occluded_eligible > 0 and int(comparison["exact"]) == 1),
    }


def run_validate_official(args: argparse.Namespace) -> int:
    audits = discover_xml_audits(args.dataset_root, include_splits=("test",))
    g1 = require_g1_compatible(args)
    source_by_key = audit_index(audits)
    expected_keys = sorted((sequence_id, view_id) for (split, sequence_id, view_id) in source_by_key if split == "test")
    official_files = find_gt_files(args.official_test_gt_root)
    output_root = generated_root(args.output_dir, args.run_label, "test")
    generated_by_key = write_split_gt([source_by_key[("test", sequence_id, view_id)] for sequence_id, view_id in expected_keys], split="test", destination=output_root)

    reference_rows: List[Dict[str, object]] = []
    equivalence_rows: List[Dict[str, object]] = []
    differences: List[Dict[str, object]] = []
    outside_rows: List[Dict[str, object]] = []
    duplicate_rows: List[Dict[str, object]] = []
    hard_failures: List[str] = []
    all_keys = sorted(set(expected_keys) | set(official_files))
    for sequence_id, view_id in all_keys:
        key = (sequence_id, view_id)
        official_path = official_files.get(key)
        generated = generated_by_key.get(key, [])
        source_audit = source_by_key.get(("test", sequence_id, view_id))
        if official_path is None or source_audit is None:
            hard_failures.append("official_or_source_file_set_mismatch:{}-{}".format(sequence_id, view_id))
            reference_rows.append({"sequence_id": sequence_id, "view_id": view_id, "official_path": str(official_path or ""), "official_sha256": sha256_file(official_path) if official_path else "", "official_row_count": ""})
            equivalence_rows.append({"sequence_id": sequence_id, "view_id": view_id, "reference_row_count": "", "generated_row_count": len(generated), "exact": 0, "missing_rows": "", "extra_rows": "", "frame_projection_mismatch": "", "id_projection_mismatch": "", "bbox_projection_mismatch": "", "reason": "missing_official_or_source"})
            continue
        official = parse_official_mda(official_path)
        comparison = compare_multisets(official, generated)
        reference_rows.append({"sequence_id": sequence_id, "view_id": view_id, "official_path": str(official_path), "official_sha256": sha256_file(official_path), "official_row_count": len(official)})
        equivalence_rows.append({
            "sequence_id": sequence_id, "view_id": view_id,
            "reference_row_count": comparison["reference_row_count"], "generated_row_count": comparison["generated_row_count"],
            "exact": comparison["exact"], "missing_rows": comparison["missing_rows"], "extra_rows": comparison["extra_rows"],
            "frame_projection_mismatch": comparison["frame_projection_mismatch"], "id_projection_mismatch": comparison["id_projection_mismatch"],
            "bbox_projection_mismatch": comparison["bbox_projection_mismatch"], "reason": "",
        })
        for difference in comparison["differences"]:
            differences.append(dict({"sequence_id": sequence_id, "view_id": view_id}, **difference))
        if not int(comparison["exact"]):
            hard_failures.append("exact_multiset_mismatch:{}-{}".format(sequence_id, view_id))
        outside_rows.append(outside_occluded_row(source_audit, generated))
        for name, values in (("official", official), ("generated", generated)):
            duplicate = duplicate_identity_stats(values)
            duplicate_rows.append({"sequence_id": sequence_id, "view_id": view_id, "population": name, **duplicate})
            if duplicate["duplicate_identity_keys"]:
                hard_failures.append("duplicate_identity_key:{}:{}-{}".format(name, sequence_id, view_id))

    official_reference = args.output_dir / "manifests" / "official_test_reference_manifest.csv"
    exact_report = args.output_dir / "audits" / "official_test_exact_equivalence_report.csv"
    difference_report = args.output_dir / "audits" / "official_test_equivalence_differences.csv"
    outside_report = args.output_dir / "audits" / "official_test_outside_occluded_audit.csv"
    duplicate_report = args.output_dir / "audits" / "official_test_duplicate_identity_audit.csv"
    csv_write(official_reference, reference_rows, ("sequence_id", "view_id", "official_path", "official_sha256", "official_row_count"))
    csv_write(exact_report, equivalence_rows, ("sequence_id", "view_id", "reference_row_count", "generated_row_count", "exact", "missing_rows", "extra_rows", "frame_projection_mismatch", "id_projection_mismatch", "bbox_projection_mismatch", "reason"))
    csv_write(difference_report, differences, ("sequence_id", "view_id", "kind", "frame", "identity", "x", "y", "width", "height", "count"))
    csv_write(outside_report, outside_rows, ("split", "sequence_id", "view_id", "source_outside_box_count", "source_occluded_eligible_box_count", "expected_eligible_row_count", "generated_row_count", "exact_expected_generated", "outside_rule_supported", "occluded_rule_supported"))
    csv_write(duplicate_report, duplicate_rows, ("sequence_id", "view_id", "population", "duplicate_identity_keys", "duplicate_identity_extra_rows"))

    total_outside = sum(int(row["source_outside_box_count"]) for row in outside_rows)
    total_occluded = sum(int(row["source_occluded_eligible_box_count"]) for row in outside_rows)
    outside_supported = int(total_outside > 0 and all(int(row["exact_expected_generated"]) == 1 for row in outside_rows))
    occluded_supported = int(total_occluded > 0 and all(int(row["exact_expected_generated"]) == 1 for row in outside_rows))
    file_set_matches = set(expected_keys) == set(official_files)
    status = "PASS" if file_set_matches and not hard_failures and outside_supported and occluded_supported else "FAIL"
    if not outside_supported:
        hard_failures.append("outside_rule_not_supported")
    if not occluded_supported:
        hard_failures.append("occluded_rule_not_supported")
    state = {
        "gate": "G2",
        "run_label": args.run_label,
        "status": status,
        "source_fingerprint": g1["source_fingerprint"],
        "policy_sha256": g1["policy_sha256"],
        "converter_sha256": sha256_file(Path(__file__).resolve()),
        "module_sha256": sha256_file(Path(__file__).resolve().parents[1] / "src" / "datasets" / "mdmt_mda_gt_protocol.py"),
        "official_test_file_count": len(official_files),
        "expected_test_file_count": len(expected_keys),
        "hard_failures": sorted(set(hard_failures)),
        "outside_rule_supported": outside_supported,
        "occluded_rule_supported": occluded_supported,
        "reports": {
            "official_reference_manifest_sha256": sha256_file(official_reference),
            "exact_equivalence_report_sha256": sha256_file(exact_report),
            "differences_sha256": sha256_file(difference_report),
            "outside_occluded_audit_sha256": sha256_file(outside_report),
            "duplicate_identity_audit_sha256": sha256_file(duplicate_report),
        },
        "recorded_at_utc": now_utc(),
    }
    json_write(state_path(args.output_dir, "g2_validation_{}.json".format(args.run_label)), state)
    print("G2 status={} files={} failures={}".format(status, len(official_files), len(state["hard_failures"])), flush=True)
    return 0 if status == "PASS" else 2


def require_g2_compatible(args: argparse.Namespace) -> Dict[str, object]:
    g1 = require_g1_compatible(args)
    try:
        g2 = load_state(args.output_dir, "g2_validation_{}.json".format(args.run_label))
    except ProtocolError as exc:
        raise ProtocolError("derive-non-test requires G2 PASS artifact: {}".format(exc)) from exc
    if g2.get("status") != "PASS":
        raise ProtocolError("derive-non-test requires G2 PASS")
    if g2.get("source_fingerprint") != g1.get("source_fingerprint") or g2.get("policy_sha256") != g1.get("policy_sha256"):
        raise ProtocolError("G2 source/policy fingerprint is incompatible")
    current_converter = sha256_file(Path(__file__).resolve())
    if g2.get("converter_sha256") != current_converter:
        raise ProtocolError("converter source changed since G2")
    return g2


def structural_rows(audits: Sequence[XmlAudit], args: argparse.Namespace) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]], List[str]]:
    rows: List[Dict[str, object]] = []
    frame_rows: List[Dict[str, object]] = []
    boundary_rows: List[Dict[str, object]] = []
    failures: List[str] = []
    for audit in audits:
        if audit.split not in {"train", "val"}:
            continue
        generated = mda_rows_from_audit(audit)
        image_dir = args.dataset_root / str(audit.split) / str(audit.view_id) / "{}-{}".format(audit.sequence_id, audit.view_id)
        images = image_paths(image_dir)
        invalid_mapping = 0
        image_read_errors = 0
        boundary_count = 0
        nonpositive_geometry = 0
        image_cache: Dict[int, Tuple[int, int]] = {}
        for box in audit.eligible_boxes:
            if box.frame < 0 or box.frame >= len(images):
                invalid_mapping += 1
                continue
            if box.frame not in image_cache:
                try:
                    image_cache[box.frame] = image_dimensions(images[box.frame])
                except ProtocolError:
                    image_read_errors += 1
                    continue
            width, height = image_cache[box.frame]
            box_width = box.xbr - box.xtl
            box_height = box.ybr - box.ytl
            if box_width <= 0 or box_height <= 0:
                nonpositive_geometry += 1
            if box.xtl < 0 or box.ytl < 0 or box.xbr > width or box.ybr > height:
                boundary_count += 1
        duplicate = duplicate_identity_stats(generated)
        row_conservation = int(len(generated) == len(audit.eligible_boxes))
        rows.append({
            "split": audit.split, "sequence_id": audit.sequence_id, "view_id": audit.view_id,
            "eligible_source_rows": len(audit.eligible_boxes), "derived_rows": len(generated),
            "missing_source_rows": max(len(audit.eligible_boxes) - len(generated), 0),
            "extra_derived_rows": max(len(generated) - len(audit.eligible_boxes), 0),
            "row_conservation": row_conservation,
        })
        frame_rows.append({
            "split": audit.split, "sequence_id": audit.sequence_id, "view_id": audit.view_id,
            "image_dir": str(image_dir), "image_count": len(images), "annotated_frame_count": len({box.frame for box in audit.eligible_boxes}),
            "invalid_frame_image_mapping": invalid_mapping, "ambiguous_frame_image_mapping": 0,
            "image_dimension_read_error": image_read_errors, "frame_offset_mismatch": 0,
        })
        boundary_rows.append({
            "split": audit.split, "sequence_id": audit.sequence_id, "view_id": audit.view_id,
            "bbox_boundary_count": boundary_count, "nonpositive_geometry_count": nonpositive_geometry,
            "policy_action": "report_only_no_clip",
        })
        rows[-1].update(duplicate)
        if not row_conservation or duplicate["duplicate_identity_keys"] or invalid_mapping or image_read_errors:
            failures.append("structural_violation:{}-{}".format(audit.sequence_id, audit.view_id))
    return rows, frame_rows, boundary_rows, failures


def timeline_rows(audits: Sequence[XmlAudit], args: argparse.Namespace) -> Tuple[List[Dict[str, object]], List[str]]:
    by_pair: Dict[Tuple[str, str], Dict[int, XmlAudit]] = defaultdict(dict)
    for audit in audits:
        if audit.split in {"train", "val"}:
            by_pair[(str(audit.split), audit.sequence_id)][audit.view_id] = audit
    rows: List[Dict[str, object]] = []
    failures: List[str] = []
    for (split, sequence_id), views in sorted(by_pair.items()):
        first, second = views.get(1), views.get(2)
        if first is None or second is None:
            rows.append({"split": split, "sequence_id": sequence_id, "view_1_image_count": "", "view_2_image_count": "", "pair_complete": 0, "timeline_match": 0})
            failures.append("missing_pair_view:{}:{}".format(split, sequence_id))
            continue
        one_count = len(image_paths(args.dataset_root / split / "1" / "{}-1".format(sequence_id)))
        two_count = len(image_paths(args.dataset_root / split / "2" / "{}-2".format(sequence_id)))
        timeline_match = int(one_count == two_count)
        rows.append({"split": split, "sequence_id": sequence_id, "view_1_image_count": one_count, "view_2_image_count": two_count, "pair_complete": 1, "timeline_match": timeline_match})
        if not timeline_match:
            failures.append("dual_view_timeline_mismatch:{}:{}".format(split, sequence_id))
    return rows, failures


def load_identity_evidence(path: Optional[Path]) -> Dict[str, object]:
    if path is None or not path.is_file():
        return {"status": "BLOCKED_BY_UNKNOWN", "unknowns": ["identity_evidence_file_missing"], "sources": [], "claims": {}}
    payload = json_read(path)
    sources = payload.get("sources")
    claims = payload.get("claims")
    if not isinstance(sources, list) or not isinstance(claims, dict):
        return {"status": "BLOCKED_BY_UNKNOWN", "unknowns": ["identity_evidence_schema_invalid"], "sources": [], "claims": {}}
    required_claims = ("mdmt_cross_view_identity_association", "mda_uses_shared_gt_identity", "ids_not_view_local")
    missing = [claim for claim in required_claims if claims.get(claim) is not True]
    valid_sources = all(isinstance(source, dict) and source.get("url") and source.get("sha256") for source in sources)
    if not sources or not valid_sources:
        missing.append("authoritative_source_url_or_sha256_missing")
    status = "PASS" if not missing else "BLOCKED_BY_UNKNOWN"
    return {"status": status, "unknowns": missing, "sources": sources, "claims": claims, "input_sha256": sha256_file(path)}


def run_derive_non_test(args: argparse.Namespace) -> int:
    g2 = require_g2_compatible(args)
    conservation = []
    frame_integrity = []
    boundary = []
    g3_failures = []
    pair_audit = []
    conflicts = []
    for split in ("train", "val"):
        split_audits = discover_xml_audits(args.dataset_root, include_splits=(split,))
        write_split_gt(split_audits, split=split, destination=generated_root(args.output_dir, args.run_label, split))
        split_conservation, split_frame_integrity, split_boundary, split_failures = structural_rows(split_audits, args)
        split_timeline, timeline_failures = timeline_rows(split_audits, args)
        split_pair_audit, split_conflicts = audit_identity_pairs(split_audits)
        conservation.extend(split_conservation)
        frame_integrity.extend(split_frame_integrity)
        boundary.extend(split_boundary)
        g3_failures.extend(split_failures)
        g3_failures.extend(timeline_failures)
        pair_audit.extend(split_pair_audit)
        conflicts.extend(split_conflicts)
        del split_audits
    non_test_duplicates = [
        {"split": row["split"], "sequence_id": row["sequence_id"], "view_id": row["view_id"], "duplicate_identity_keys": row["duplicate_identity_keys"], "duplicate_identity_extra_rows": row["duplicate_identity_extra_rows"]}
        for row in conservation
    ]
    derived_rows = []
    for split in ("train", "val"):
        root = generated_root(args.output_dir, args.run_label, split)
        for (sequence_id, view_id), path in sorted(find_gt_files(root).items()):
            generated = parse_official_mda(path)
            derived_rows.append({"split": split, "sequence_id": sequence_id, "view_id": view_id, "generated_path": "generated_gt/{}/{}-{}.txt".format(split, sequence_id, view_id), "sha256": sha256_file(path), "row_count": len(generated)})
    conservation_path = args.output_dir / "audits" / "non_test_row_conservation_report.csv"
    duplicates_path = args.output_dir / "audits" / "non_test_duplicate_identity_report.csv"
    frame_path = args.output_dir / "audits" / "frame_image_integrity_report.csv"
    timeline_path = args.output_dir / "audits" / "dual_view_timeline_integrity_report.csv"
    boundary_path = args.output_dir / "audits" / "bbox_boundary_audit.csv"
    derived_manifest = args.output_dir / "manifests" / "derived_gt_manifest.csv"
    csv_write(conservation_path, conservation, ("split", "sequence_id", "view_id", "eligible_source_rows", "derived_rows", "missing_source_rows", "extra_derived_rows", "row_conservation", "duplicate_identity_keys", "duplicate_identity_extra_rows"))
    csv_write(duplicates_path, non_test_duplicates, ("split", "sequence_id", "view_id", "duplicate_identity_keys", "duplicate_identity_extra_rows"))
    csv_write(frame_path, frame_integrity, ("split", "sequence_id", "view_id", "image_dir", "image_count", "annotated_frame_count", "invalid_frame_image_mapping", "ambiguous_frame_image_mapping", "image_dimension_read_error", "frame_offset_mismatch"))
    csv_write(timeline_path, timeline, ("split", "sequence_id", "view_1_image_count", "view_2_image_count", "pair_complete", "timeline_match"))
    csv_write(boundary_path, boundary, ("split", "sequence_id", "view_id", "bbox_boundary_count", "nonpositive_geometry_count", "policy_action"))
    csv_write(derived_manifest, derived_rows, ("split", "sequence_id", "view_id", "generated_path", "sha256", "row_count"))

    pair_path = args.output_dir / "audits" / "per_pair_cross_view_identity_audit.csv"
    conflict_path = args.output_dir / "audits" / "class_conflict_manifest.csv"
    csv_write(pair_path, pair_audit, ("split", "sequence_id", "pair_complete", "same_id_same_frame_cross_view_event_count", "class_conflict_event_count", "mda_measurable"))
    csv_write(conflict_path, conflicts, ("split", "sequence_id", "frame", "identity", "view_1_labels", "view_2_labels"))
    evidence = load_identity_evidence(args.identity_evidence)
    evidence.update({
        "gate": "G4",
        "per_pair_audit_sha256": sha256_file(pair_path),
        "per_pair_all_measurable": int(all(int(row["mda_measurable"]) == 1 for row in pair_audit if row["split"] in {"train", "val"})),
    })
    if evidence["status"] == "PASS" and not evidence["per_pair_all_measurable"]:
        evidence["status"] = "BLOCKED_BY_UNKNOWN"
        evidence.setdefault("unknowns", []).append("non_test_pair_not_mda_measurable")
    evidence_path = args.output_dir / "evidence" / "cross_view_identity_semantics_evidence.json"
    json_write(evidence_path, evidence)
    primary_policy = {
        "schema_version": 1,
        "primary_population": "full_deterministic_derived_gt",
        "sensitivity_population": "class_consistent_mask_only",
        "sensitivity_action": "changes_evaluation_inclusion_only",
        "forbidden": ["source_row_mutation", "identity_mutation", "bbox_mutation", "prediction_mutation", "tracking_outcome_dependency"],
        "class_conflict_manifest_sha256": sha256_file(conflict_path),
    }
    primary_policy_path = args.output_dir / "policy" / "primary_sensitivity_manifest.json"
    json_write(primary_policy_path, primary_policy)
    g3_status = "PASS" if not g3_failures else "FAIL"
    g5_status = "PASS"
    state = {
        "gates": {"G3": g3_status, "G4": evidence["status"], "G5": g5_status},
        "run_label": args.run_label,
        "g2_state_sha256": sha256_file(state_path(args.output_dir, "g2_validation_{}.json".format(args.run_label))),
        "g3_failures": sorted(set(g3_failures)),
        "g4_unknowns": evidence.get("unknowns", []),
        "reports": {
            "row_conservation_sha256": sha256_file(conservation_path), "duplicate_identity_sha256": sha256_file(duplicates_path),
            "frame_integrity_sha256": sha256_file(frame_path), "timeline_integrity_sha256": sha256_file(timeline_path),
            "boundary_audit_sha256": sha256_file(boundary_path), "derived_manifest_sha256": sha256_file(derived_manifest),
            "per_pair_identity_sha256": sha256_file(pair_path), "class_conflict_sha256": sha256_file(conflict_path),
            "identity_evidence_sha256": sha256_file(evidence_path), "primary_sensitivity_sha256": sha256_file(primary_policy_path),
        },
        "recorded_at_utc": now_utc(),
    }
    json_write(state_path(args.output_dir, "g3_g5_{}.json".format(args.run_label)), state)
    print("G3 status={} G4 status={} G5 status={} g3_failures={}".format(g3_status, evidence["status"], g5_status, len(g3_failures)), flush=True)
    return 0 if g3_status == "PASS" else 2


def file_tree_hashes(root: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not root.is_dir():
        return values
    for path in sorted(root.rglob("*.txt"), key=lambda item: str(item)):
        values[str(path.relative_to(root))] = sha256_file(path)
    return values


def run_repeat_verify(args: argparse.Namespace) -> int:
    if args.run_label != "run_b":
        raise ProtocolError("repeat-verify requires --run-label run_b")
    run_validate_official(args)
    g2_b = load_state(args.output_dir, "g2_validation_run_b.json")
    if g2_b.get("status") != "PASS":
        return 2
    derive_exit = run_derive_non_test(args)
    if derive_exit:
        return derive_exit
    g2_a = load_state(args.output_dir, "g2_validation_run_a.json")
    g3_a = load_state(args.output_dir, "g3_g5_run_a.json")
    g3_b = load_state(args.output_dir, "g3_g5_run_b.json")
    rows: List[Dict[str, object]] = []
    mismatches = 0
    for split in ("test", "train", "val"):
        one = file_tree_hashes(generated_root(args.output_dir, "run_a", split))
        two = file_tree_hashes(generated_root(args.output_dir, "run_b", split))
        keys = sorted(set(one) | set(two))
        for key in keys:
            equal = int(one.get(key) == two.get(key) and key in one and key in two)
            mismatches += int(not equal)
            rows.append({"artifact_kind": "generated_gt", "split": split, "path": key, "run_a_sha256": one.get(key, "MISSING"), "run_b_sha256": two.get(key, "MISSING"), "identical": equal})
    for name in ("row_conservation_sha256", "duplicate_identity_sha256", "frame_integrity_sha256", "timeline_integrity_sha256", "boundary_audit_sha256", "derived_manifest_sha256", "per_pair_identity_sha256", "class_conflict_sha256", "identity_evidence_sha256", "primary_sensitivity_sha256"):
        equal = int(g3_a["reports"].get(name) == g3_b["reports"].get(name))
        mismatches += int(not equal)
        rows.append({"artifact_kind": "deterministic_audit", "split": "", "path": name, "run_a_sha256": g3_a["reports"].get(name, "MISSING"), "run_b_sha256": g3_b["reports"].get(name, "MISSING"), "identical": equal})
    report = args.output_dir / "determinism" / "deterministic_repeat_run_report.csv"
    csv_write(report, rows, ("artifact_kind", "split", "path", "run_a_sha256", "run_b_sha256", "identical"))
    manifest_paths = [
        Path("policy/mapping_rule_manifest.json"), Path("manifests/source_annotation_manifest.csv"), Path("manifests/official_test_reference_manifest.csv"),
        Path("manifests/derived_gt_manifest.csv"), Path("audits/official_test_exact_equivalence_report.csv"),
        Path("audits/non_test_row_conservation_report.csv"), Path("audits/class_conflict_manifest.csv"),
        Path("evidence/cross_view_identity_semantics_evidence.json"), Path("determinism/deterministic_repeat_run_report.csv"),
    ]
    artifact_rows = [{"path": str(path), "sha256": digest} for path, digest in artifact_hashes(args.output_dir, manifest_paths).items()]
    artifact_manifest = args.output_dir / "manifests" / "artifact_manifest.csv"
    csv_write(artifact_manifest, artifact_rows, ("path", "sha256"))
    status = "PASS" if mismatches == 0 else "FAIL"
    state = {
        "gate": "G6", "status": status, "mismatch_count": mismatches,
        "determinism_report_sha256": sha256_file(report), "artifact_manifest_sha256": sha256_file(artifact_manifest),
        "run_a_g2_sha256": sha256_file(state_path(args.output_dir, "g2_validation_run_a.json")),
        "run_b_g2_sha256": sha256_file(state_path(args.output_dir, "g2_validation_run_b.json")),
        "run_a_g3_g5_sha256": sha256_file(state_path(args.output_dir, "g3_g5_run_a.json")),
        "run_b_g3_g5_sha256": sha256_file(state_path(args.output_dir, "g3_g5_run_b.json")),
        "recorded_at_utc": now_utc(),
    }
    json_write(state_path(args.output_dir, "g6_repeat_verify.json"), state)
    print("G6 status={} mismatches={}".format(status, mismatches), flush=True)
    return 0 if status == "PASS" else 2


def generation_record(args: argparse.Namespace, run_label: str) -> Dict[str, object]:
    artifacts = []
    for split in ("test", "train", "val"):
        for path in sorted(generated_root(args.output_dir, run_label, split).glob("*.txt"), key=lambda item: item.name):
            artifacts.append({"split": split, "path": str(path), "sha256": sha256_file(path)})
    return {
        "schema_version": 1,
        "run_label": run_label,
        "recorded_at_utc": now_utc(),
        "actual_command": " ".join(__import__("sys").argv),
        "repository_state": repository_state(args.repo_root),
        "runtime_environment": runtime_environment(),
        "converter_sha256": sha256_file(Path(__file__).resolve()),
        "protocol_module_sha256": sha256_file(Path(__file__).resolve().parents[1] / "src" / "datasets" / "mdmt_mda_gt_protocol.py"),
        "mapping_policy_sha256": sha256_file(args.output_dir / "policy" / "mapping_rule_manifest.json") if (args.output_dir / "policy" / "mapping_rule_manifest.json").is_file() else "MISSING",
        "generated_files": artifacts,
    }


def markdown_gate_report(gates: Mapping[str, Mapping[str, object]], final_status: str, authorization: str) -> str:
    lines = ["# GT Protocol Gate Report", "", "## Final G7 Decision", "", "```text", final_status, "```", "", authorization, ""]
    for gate in ("G1", "G2", "G3", "G4", "G5", "G6"):
        state = gates.get(gate, {"status": "BLOCKED_BY_UNKNOWN", "unknowns": ["state_missing"]})
        lines.extend([
            "## {}".format(gate), "", "- Status: `{}`".format(state.get("status", "BLOCKED_BY_UNKNOWN")),
            "- Evidence artifact: `{}`".format(state.get("evidence", "see records/")),
            "- Observed facts: `{}`".format(json.dumps(state.get("facts", {}), sort_keys=True)),
            "- Unknowns: `{}`".format(json.dumps(state.get("unknowns", []), sort_keys=True)),
            "- Hard-gate results: `{}`".format(json.dumps(state.get("hard", {}), sort_keys=True)), "",
        ])
    return "\n".join(lines) + "\n"


def run_finalize(args: argparse.Namespace) -> int:
    g1 = optional_state(args.output_dir, "g1_source_audit.json", reason="G1_not_run")
    g2_a = optional_state(args.output_dir, "g2_validation_run_a.json", reason="G2_not_run_or_stopped")
    g3_a = optional_state(args.output_dir, "g3_g5_run_a.json", reason="G3_to_G5_not_run_after_earlier_gate")
    g6 = optional_state(args.output_dir, "g6_repeat_verify.json", reason="G6_not_run_after_earlier_gate")
    json_write(args.output_dir / "records" / "generation_record_run_a.json", generation_record(args, "run_a"))
    json_write(args.output_dir / "records" / "generation_record_run_b.json", generation_record(args, "run_b"))
    g3_gates = g3_a.get("gates", {}) if isinstance(g3_a.get("gates", {}), dict) else {}
    statuses = {
        "G1": g1.get("status", "BLOCKED_BY_UNKNOWN"),
        "G2": g2_a.get("status", "BLOCKED_BY_UNKNOWN"),
        "G3": g3_gates.get("G3", "BLOCKED_BY_UNKNOWN"),
        "G4": g3_gates.get("G4", "BLOCKED_BY_UNKNOWN"),
        "G5": g3_gates.get("G5", "BLOCKED_BY_UNKNOWN"),
        "G6": g6.get("status", "BLOCKED_BY_UNKNOWN"),
    }
    if any(status == "FAIL" for status in statuses.values()):
        final_status = "GT_PROTOCOL_GATE_FAIL"
        authorization = "Two-pair MVE is not authorized. Repair-and-continue is forbidden."
    elif any(status != "PASS" for status in statuses.values()):
        final_status = "GT_PROTOCOL_GATE_BLOCKED_BY_UNKNOWN"
        authorization = "Two-pair MVE is not authorized because a required Gate is unresolved."
    else:
        final_status = "GT_PROTOCOL_GATE_PASS"
        authorization = "Only GT/evaluation infrastructure and causal-invariant checks may proceed to two-pair MVE; development, holdout, Formal and recovery remain unauthorized."
    gate_view = {
        "G1": {"status": statuses["G1"], "evidence": "records/g1_source_audit.json", "facts": {"xml_count": g1.get("observed_xml_count")}, "unknowns": g1.get("unknowns", []), "hard": {"failures": g1.get("failures", [])}},
        "G2": {"status": statuses["G2"], "evidence": "records/g2_validation_run_a.json", "facts": {"official_file_count": g2_a.get("official_test_file_count")}, "unknowns": g2_a.get("unknowns", []), "hard": {"failures": g2_a.get("hard_failures", [])}},
        "G3": {"status": statuses["G3"], "evidence": "records/g3_g5_run_a.json", "facts": {}, "unknowns": g3_a.get("unknowns", []), "hard": {"failures": g3_a.get("g3_failures", [])}},
        "G4": {"status": statuses["G4"], "evidence": "evidence/cross_view_identity_semantics_evidence.json", "facts": {}, "unknowns": g3_a.get("g4_unknowns", g3_a.get("unknowns", [])), "hard": {}},
        "G5": {"status": statuses["G5"], "evidence": "policy/primary_sensitivity_manifest.json", "facts": {}, "unknowns": g3_a.get("unknowns", []), "hard": {}},
        "G6": {"status": statuses["G6"], "evidence": "records/g6_repeat_verify.json", "facts": {"mismatch_count": g6.get("mismatch_count")}, "unknowns": g6.get("unknowns", []), "hard": {}},
    }
    raw_report = args.output_dir / "GT_PROTOCOL_GATE_REPORT.md"
    raw_report.write_text(markdown_gate_report(gate_view, final_status, authorization), encoding="utf-8")
    final = {"gate": "G7", "status": final_status, "gates": statuses, "authorization": authorization, "recorded_at_utc": now_utc()}
    json_write(state_path(args.output_dir, "g7_final_decision.json"), final)
    print("G7 status={}".format(final_status), flush=True)
    return 0 if final_status == "GT_PROTOCOL_GATE_PASS" else 2


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "audit-source":
        return run_audit_source(args)
    if args.mode == "validate-official-test":
        return run_validate_official(args)
    if args.mode == "derive-non-test":
        return run_derive_non_test(args)
    if args.mode == "repeat-verify":
        return run_repeat_verify(args)
    if args.mode == "finalize-gate":
        return run_finalize(args)
    raise AssertionError(args.mode)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProtocolError as exc:
        print("GT_PROTOCOL_FAIL_CLOSED: {}".format(exc), flush=True)
        raise SystemExit(2)
