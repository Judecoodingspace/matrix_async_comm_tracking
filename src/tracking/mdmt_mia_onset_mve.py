"""Fail-closed orchestration primitives for the Pair53/66 non-test MVE.

This module deliberately contains no detector, tracker, author-process, or
scientific-decision execution.  It freezes orchestration, acceptance and
embargo boundaries which a separately authorized launcher may consume later.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from evaluation.mdmt_mia_paper import cross_view_mda, load_author_json, load_mot_gt

MVE_PAIRS = ("53", "66")
DELAYS = (1, 3, 5)
Y01_AUTHORITY = "Y01_SINGLETON_AUTHORITY_PARITY_AUDIT"
LOGICAL_TO_PHYSICAL = (
    ("Y00", "Y00", 0), ("Y01", "Y01_d1", 1),
    ("Y10_d1", "Y10_d1", 1), ("Y11_d1", "Y11_d1", 1), ("Yec_d1", "Yec_d1", 1),
    ("Y10_d3", "Y10_d3", 3), ("Y11_d3", "Y11_d3", 3), ("Yec_d3", "Yec_d3", 3),
    ("Y10_d5", "Y10_d5", 5), ("Y11_d5", "Y11_d5", 5), ("Yec_d5", "Yec_d5", 5),
)
FORBIDDEN_SUMMARY_TOKENS = ("r_edge", "c_comp", "d_id", "supports compensation", "refutes compensation", "onset")


class MvePreflightError(RuntimeError):
    pass


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def condition_records(pairs: Sequence[str] = MVE_PAIRS) -> list[dict[str, object]]:
    if tuple(str(pair) for pair in pairs) != MVE_PAIRS:
        raise MvePreflightError("MVE pair identity drift")
    records = []
    for pair in pairs:
        for logical, physical, delay in LOGICAL_TO_PHYSICAL:
            records.append({"pair": str(pair), "logical_condition": logical,
                            "physical_realization": physical, "delay_frames": delay,
                            "y01_authority": Y01_AUTHORITY if logical == "Y01" else ""})
    return records


def validate_condition_records(records: Sequence[Mapping[str, object]]) -> None:
    expected = {(pair, logical, physical, delay) for pair in MVE_PAIRS for logical, physical, delay in LOGICAL_TO_PHYSICAL}
    actual = {(str(row.get("pair")), str(row.get("logical_condition")), str(row.get("physical_realization")), int(row.get("delay_frames", -1))) for row in records}
    if actual != expected or len(records) != 22 or len(actual) != 22:
        raise MvePreflightError("authoritative 22-run condition manifest mismatch")
    if any(row[1] == "Y01" and row[2] != "Y01_d1" for row in actual):
        raise MvePreflightError("Y01 physical realization drift")


def write_condition_manifest(path: Path, provenance: Mapping[str, str]) -> str:
    records = condition_records()
    validate_condition_records(records)
    payload = {"schema_version": 1, "records": records, "provenance": dict(provenance)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json(payload))
    return sha256_bytes(path.read_bytes())


@dataclass(frozen=True)
class AttemptIdentity:
    run_id: str
    pair: str
    logical_condition: str
    physical_realization: str
    attempt_id: str

    def relative_root(self) -> Path:
        return Path("attempts") / self.pair / self.logical_condition / self.attempt_id


def create_attempt(root: Path, identity: AttemptIdentity, fingerprints: Mapping[str, str]) -> Path:
    destination = root / identity.relative_root()
    if destination.exists():
        raise MvePreflightError("attempt overwrite forbidden")
    destination.mkdir(parents=True)
    manifest = {"identity": identity.__dict__, "fingerprints": dict(fingerprints), "status": "STARTED"}
    (destination / "attempt_manifest.json").write_bytes(canonical_json(manifest))
    return destination


def complete_attempt(attempt: Path, artifact_hashes: Mapping[str, str], gates: Mapping[str, bool]) -> None:
    if not artifact_hashes or not gates or not all(bool(value) for value in gates.values()):
        raise MvePreflightError("partial or invalid attempt cannot complete")
    manifest = json.loads((attempt / "attempt_manifest.json").read_text())
    manifest.update({"status": "COMPLETE", "artifact_hashes": dict(artifact_hashes), "runtime_gates": dict(gates)})
    (attempt / "attempt_manifest.json").write_bytes(canonical_json(manifest))


def promote_attempt(root: Path, attempt: Path) -> Path:
    manifest = json.loads((attempt / "attempt_manifest.json").read_text())
    if manifest.get("status") != "COMPLETE" or not all(manifest.get("runtime_gates", {}).values()):
        raise MvePreflightError("only complete gate-valid attempt may be accepted")
    target = root / "accepted" / manifest["identity"]["pair"] / manifest["identity"]["logical_condition"]
    if target.exists():
        raise MvePreflightError("accepted artifact overwrite forbidden")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(attempt.resolve(), target_is_directory=True)
    return target


def accepted_count(root: Path) -> int:
    return len(list((root / "accepted").glob("*/*"))) if (root / "accepted").exists() else 0


def runtime_gate_template() -> dict[str, bool]:
    return {name: False for name in ("y00_parity", "lineage", "shadow_quarantine", "actual_input_nonmutation",
                                     "future_read", "runtime_gt", "packet_conservation", "feedback_parity", "logger_invariance")}


def synchronous_reference_spec(pair: str, output_root: Path) -> dict[str, object]:
    """Describe, but do not execute, the all-zero synchronous Y00 reference."""
    if str(pair) not in MVE_PAIRS:
        raise MvePreflightError("reference pair identity drift")
    return {
        "pair": str(pair),
        "logical_condition": "Y00",
        "delays": {"local": 0, "homography": 0, "id_state": 0, "supplement": 0},
        "output_root": str(output_root / "references" / str(pair) / "Y00"),
        "execution": "NOT_LAUNCHED",
    }


def exact_artifact_parity(artifacts: Mapping[str, bytes]) -> dict[str, object]:
    """Fail closed unless named artifacts are byte-identical to the reference."""
    required = {"reference", "candidate"}
    if set(artifacts) != required:
        raise MvePreflightError("parity artifact surface mismatch")
    digests = {name: sha256_bytes(value) for name, value in artifacts.items()}
    return {"equal": artifacts["reference"] == artifacts["candidate"], "sha256": digests}


def evaluate_source_mda(prediction_view1: Path, prediction_view2: Path, gt_view1: Path, gt_view2: Path) -> dict[str, object]:
    """Use unchanged evaluator semantics; never emit the scientific value publicly."""
    value, rows = cross_view_mda(load_author_json(prediction_view1), load_author_json(prediction_view2),
                                 load_mot_gt(gt_view1), load_mot_gt(gt_view2))
    if not math.isfinite(value):
        raise MvePreflightError("non-finite Source-MDA result")
    return {"computed": True, "frame_records": len(rows), "private_metric": value}


def contrast_computability(metric_rows: Sequence[Mapping[str, object]]) -> dict[str, bool]:
    keys = {(str(row["pair"]), str(row["logical_condition"])) for row in metric_rows}
    required = {(pair, logical) for pair in MVE_PAIRS for logical, _, _ in LOGICAL_TO_PHYSICAL}
    complete = keys == required and all(math.isfinite(float(row["private_metric"])) for row in metric_rows)
    return {"D_ID_COMPUTABLE": complete, "R_EDGE_COMPUTABLE": complete, "C_COMP_COMPUTABLE": complete}


def public_mve_summary(*, accepted: int, runtime_gates: Mapping[str, bool], computability: Mapping[str, bool]) -> dict[str, object]:
    if set(computability) != {"D_ID_COMPUTABLE", "R_EDGE_COMPUTABLE", "C_COMP_COMPUTABLE"}:
        raise MvePreflightError("unexpected contrast-computability surface")
    payload = {"accepted_runs": int(accepted), "required_runs": 22,
               "runtime_gates": {key: bool(value) for key, value in runtime_gates.items()},
               # Public MVE status must disclose neither numerical values nor
               # the scientific contrast names.  Their fixed order is held in
               # the Contract; these are only boolean implementation slots.
               "contrast_computability": [bool(computability[key]) for key in
                                            ("D_ID_COMPUTABLE", "R_EDGE_COMPUTABLE", "C_COMP_COMPUTABLE")]}
    rendered = canonical_json(payload).decode("utf-8").lower()
    if any(token in rendered for token in FORBIDDEN_SUMMARY_TOKENS):
        raise MvePreflightError("scientific outcome leakage in MVE summary")
    return payload


def assert_public_surface(value: object) -> None:
    """Guard reports from accidentally carrying embargoed scientific wording."""
    rendered = canonical_json(value).decode("utf-8").lower()
    if any(token in rendered for token in FORBIDDEN_SUMMARY_TOKENS):
        raise MvePreflightError("scientific outcome leakage in public surface")


def implementation_freeze_payload(fingerprints: Mapping[str, str], *, mve_pass: bool) -> dict[str, object]:
    if not mve_pass:
        raise MvePreflightError("MVE_PASS freeze cannot be created before MVE pass")
    required = {"commit", "condition_manifest", "e023", "source_mda", "evaluator", "homography", "cohort", "y01_authority"}
    if not required.issubset(fingerprints):
        raise MvePreflightError("implementation-freeze fingerprint incomplete")
    return {"schema_version": 1, "state": "MVE_PASS_FREEZE", "fingerprints": dict(fingerprints),
            "development_delays": [1, 2, 3, 4, 5], "bootstrap": 10000, "direction_threshold": "10/15"}
