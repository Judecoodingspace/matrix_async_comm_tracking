#!/usr/bin/env python3
"""V2-2 child for the selected H_R communication production path."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from tracking.mdmt_mia_c7_batch_b_schema import ALLOWED_PARENT_ENV_KEYS, inventory_generated_source
from tracking.mdmt_mia_hr_evidence import (
    _inside, EFFECTIVE_NAME, NORMALIZED_NAME, HREvidenceError, collect_raw,
    digest, file_digest, load_authorization, normalized_from_raw, source_paths, write_json,
)
from run_mdmt_mia_c7_real_child import _materialize_generated_source


class HRChildError(RuntimeError):
    pass


def _git_identity() -> str:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True).strip()
    if status:
        raise HRChildError("EXECUTION_WORKTREE_NOT_CLEAN")
    return head


def _attempt_root(auth: dict) -> Path:
    attempt_id = os.environ.get("V2_2_ATTEMPT_ID")
    output_root = os.environ.get("V2_2_OUTPUT_ROOT")
    if attempt_id != auth["attempt_id"] or not output_root:
        raise HRChildError("V2_2_CONTEXT_MISMATCH")
    root = Path(auth["attempt_root"]).resolve()
    if Path(output_root).resolve() != root / "output" or root.name != attempt_id:
        raise HRChildError("V2_2_ATTEMPT_ROOT_MISMATCH")
    return root


def _tiny_input(root: Path, auth: dict) -> None:
    """The frozen wrapper supports an existing sequence directory with fewer images."""
    if not auth["qualification_only"]:
        return
    count = auth["qualification_frame_count"]
    if count < 2 or count > 5:
        raise HRChildError("QUALIFICATION_FRAME_COUNT_INVALID")
    mdmt = Path(auth["mdmt_root"])
    base = root / "output/hr/source_runtime/run_inputs/66/train"
    for view in (1, 2):
        sequence = "66-" + str(view)
        source = mdmt / "train" / str(view) / sequence
        images = sorted(path for path in source.iterdir() if path.suffix.lower() in {".jpg", ".png", ".jpeg"})
        if len(images) < count:
            raise HRChildError("QUALIFICATION_SOURCE_TOO_SHORT")
        target = base / str(view) / sequence
        target.mkdir(parents=True, exist_ok=False)
        for image in images[:count]:
            (target / image.name).symlink_to(image)
    # The wrapper creates the XML symlinks itself.  H_R never opens outcome data.


def controlled_environment(root: Path, auth: dict, parent: dict[str, str]) -> dict[str, str]:
    source = root / "output/hr/source_runtime"
    observer_root = source / "raw_c7"
    inherited = parent.get("MIA_C7_EVIDENCE_ROOT")
    if inherited and Path(inherited).resolve() != observer_root.resolve():
        raise HRChildError("INHERITED_C7_EVIDENCE_ROOT_MISMATCH")
    environment = {key: parent[key] for key in ALLOWED_PARENT_ENV_KEYS if key in parent and not key.startswith("MIA_")}
    environment.update({
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT / "src"),
        "MDMT_MIA_C7_CHILD_BOUNDARY": "1", "MDMT_MIA_C7_OBSERVATIONAL": "1",
        "MDMT_MIA_C7_CAPACITY_BYTES": str(auth["cell"]["capacity_bytes"]),
        "MDMT_ROOT": auth["mdmt_root"], "MIA_ROOT": auth["mia_root"],
        "MIA_SOURCE_ROOT": str(source / "generated_source"),
        "MIA_CONFIG": auth["mia_config_path"],
        "MIA_RUN_INPUT_ROOT": str(source / "run_inputs"),
        "MIA_OUTPUT_ROOT": str(source / "author_outputs"),
        "DEVICE": auth["device"],
        "MIA_ACTIVE_PACKET_STAGES": "all",
        "MIA_PACKET_CENSUS_RUN_ID": auth["run_id"],
        "MIA_C7_EVIDENCE_ROOT": str(observer_root),
        "MIA_C7_SERVICE_CONFIG": json.dumps({
            "schema_version": "C7_REGISTERED_FIFO_SERVICE_V1", "mode": "fifo",
            "capacity_id": auth["cell"]["capacity_id"],
            "rate_logical_bytes_per_frame": auth["cell"]["capacity_bytes"],
            "ledger_enabled": True, "run_id": auth["run_id"],
            "pair_id": auth["cell"]["pair_id"],
        }, sort_keys=True, separators=(",", ":")),
        "MIA_C6_SUPPRESSION_CONFIG": json.dumps({
            "enabled": True, "run_id": auth["run_id"],
            "output_dir": str(source / "suppression"),
        }, sort_keys=True, separators=(",", ":")),
    })
    if "MIA_C4_SERVICE_CONFIG" in environment or not _inside(Path(environment["MIA_C7_EVIDENCE_ROOT"]), root / "output"):
        raise HRChildError("CONTROLLED_ENVIRONMENT_INVALID")
    return environment


def execute(auth_path: Path) -> dict:
    preliminary = json.loads(auth_path.read_text(encoding="utf-8"))
    root = _attempt_root(preliminary)
    auth = load_authorization(auth_path, root, ROOT)
    if _git_identity() != auth["source_sha"]:
        raise HRChildError("SOURCE_SHA_MISMATCH")
    source = root / "output/hr/source_runtime"
    generated = source / "generated_source"
    resources = {
        "mia_root": auth["mia_root"], "mia_source_root": str(generated),
    }
    c7_authorization = {
        "generated_source_preparer_identity": {
            "canonical_path": auth["preparer_path"], "sha256": auth["preparer_sha256"],
        },
        "execution_resources": resources,
    }
    source.mkdir(parents=True, exist_ok=True)
    _tiny_input(root, auth)
    before = _materialize_generated_source(c7_authorization, c7_evidence=True)
    manifest = json.loads((generated / "async_deadline_manifest.json").read_text(encoding="utf-8"))
    manifest_identity = digest(json.dumps(
        {key: value for key, value in manifest.items() if key != "variant_root"},
        sort_keys=True, separators=(",", ":")).encode("utf-8"))
    if manifest_identity != auth["generated_source_manifest_sha256"]:
        raise HRChildError("GENERATED_SOURCE_MANIFEST_MISMATCH")
    wrapper = Path(auth["wrapper_path"])
    if file_digest(wrapper) != auth["wrapper_sha256"]:
        raise HRChildError("WRAPPER_IDENTITY_MISMATCH")
    environment = controlled_environment(root, auth, dict(os.environ))
    completed = subprocess.run(
        [str(wrapper), "mia", "train", "66"], cwd=ROOT, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    write_json(source / "wrapper_status.json", {
        "returncode": completed.returncode, "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    })
    if completed.returncode != 0:
        raise HRChildError("AUTHOR_WRAPPER_FAILED:" + str(completed.returncode))
    after = inventory_generated_source(generated)
    if before["inventory_sha256"] != after["inventory_sha256"]:
        raise HRChildError("GENERATED_SOURCE_MUTATED")
    raw = collect_raw(root, auth, before)
    normalized, effective = normalized_from_raw(raw, auth)
    if auth["schema_version"] in {"H_R_FORMAL_AUTHORIZATION_V1", "H_R_FORMAL_AUTHORIZATION_V2"}:
        observed = {
            "run_id": effective["run_id"], "cell_id": effective["cell_id"],
            "pair_id": effective["pair_id"], "capacity_id": effective["capacity_id"],
            "capacity_bytes": effective["capacity_bytes"],
            "mode": "fifo" if effective["observed_fifo"] else "non_fifo",
            "rate_logical_bytes_per_frame": effective["observed_effective_rate"],
            "ledger_enabled": effective["observed_ledger_enabled"],
            "suppression_enabled": effective["observed_suppression_enabled"],
        }
        if observed != auth["formal_effective_config_expectation"]:
            raise HRChildError("FORMAL_EFFECTIVE_CONFIG_MISMATCH")
    hr = root / "output/hr"
    write_json(hr / NORMALIZED_NAME, normalized)
    write_json(hr / EFFECTIVE_NAME, effective)
    if normalized_from_raw(raw, auth) != (normalized, effective):
        raise HRChildError("NONDETERMINISTIC_NORMALIZATION")
    write_json(hr / "H_R_EXTRACTION_CONFIG.json", {
        "schema_version": "H_R_EXTRACTION_CONFIG_V1",
        "authorization_hash": auth["authorization_hash"],
        "raw_sha256": file_digest(raw), "source_families": sorted(source_paths(root)),
    })
    write_json(hr / "H_R_VALIDATION_CONFIG.json", {
        "schema_version": "H_R_VALIDATION_CONFIG_V1",
        "authorization_hash": auth["authorization_hash"],
        "selected_cell": auth["cell"],
        "raw_sha256": file_digest(raw),
        "normalized_sha256": file_digest(hr / NORMALIZED_NAME),
    })
    status = {
        "schema_version": "H_R_STRUCTURAL_VALIDATION_V1",
        "STRUCTURAL_VERDICT": "PASS", "attempt_id": auth["attempt_id"],
        "authorization_hash": auth["authorization_hash"], "source_sha": auth["source_sha"],
        "raw_sha256": file_digest(raw),
        "normalized_sha256": file_digest(hr / NORMALIZED_NAME),
        "effective_sha256": file_digest(hr / EFFECTIVE_NAME),
        "generated_source_inventory_sha256": before["inventory_sha256"],
        "tracking_outcome_read": False,
    }
    write_json(hr / "H_R_STRUCTURAL_VALIDATION.json", status)
    write_json(hr / "H_R_CHILD_STATUS.json", {
        "schema_version": "H_R_CHILD_STATUS_V1", "status": "EXECUTED",
        "real_generated_runtime_executed": True, "STRUCTURAL_VERDICT": "PASS",
        "tracking_outcome_read": False,
    })
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(execute(args.authorization), sort_keys=True))
        return 0
    except (HREvidenceError, HRChildError, OSError, ValueError) as exc:
        print("H_R_CHILD_FAILED:" + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
