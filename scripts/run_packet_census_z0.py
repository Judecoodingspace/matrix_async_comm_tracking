#!/usr/bin/env python3
"""Fail-closed Census-ON Z0 runner for the frozen all-train-pair cohort.

The command is intentionally inert until ``preflight`` is explicitly invoked.
It never offers flags that can change the cohort, delays, seed, device, or
measurement definitions frozen in the packet-census contract.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

from tracking.packet_census_run_tools import (
    CENSUS_RUN_ID,
    EXECUTION_BASELINE_COMMIT,
    FROZEN_BRANCH,
    FROZEN_CHECKPOINT,
    PacketCensusToolError,
    Z0_DELAYS,
    atomic_write_json,
    build_manifest,
    freeze_manifest,
    inspect_pair,
    read_json,
    validate_pair_attempt,
    verify_frozen_manifest,
    write_pair_validation,
)


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = Path("/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking")
MIA_ROOT = Path("/mnt/data/yzm/experiments/mdmt_mia_official")
VARIANT_ROOT = MIA_ROOT / "variants" / "packet_census_homography_fallback_successor_v1"
FROZEN_PYTHON = MIA_ROOT / ".conda-env" / "bin" / "python"
CONTRACT_PATH = WORKTREE_ROOT / "summary_md" / "PACKET_CENSUS_HOMOGRAPHY_FALLBACK_SUCCESSOR_CONTRACT.md"
RNG_WRAPPER = WORKTREE_ROOT / "scripts" / "step4_packet_census_author_rng_wrapper.py"
AUTHOR_ENTRY = VARIANT_ROOT / "demo" / "supplement_MIA.py"
RUN_CONFIG = MIA_ROOT / "run_configs" / "one_carafe_bytetrack_full_mdmt_reproduction.py"
CHECKPOINT = DATASET_ROOT / "checkpoints" / "work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt" / "epoch_12.pth"

PAIR_SPECS = (
    ("23", 700, "282a2099ddecd8b77d4f13f879e1c0a024970a9cf96ce9301b49c95ed5b1a4ce", "5bd42006e58b648c7665e6128a7611b824ab756fbba2e8409061eac1761e01db"),
    ("25", 500, "a0d4a0f8cdd0c122e176988125620efb3fee9fc4fd6d858f286abb674a2f18ef", "599c79752e132395c350428e72182b302202ff7511d2f4dd8e8b491d906d045a"),
    ("27", 340, "d76767b69f7548fbbce6baba581b2f4adf86acfb48c0874a4e618b8f64811f9c", "dbaf97416487646a5e10fe4f39fa163757e21fcbab822a48fc5be0bbe0a8a5ce"),
    ("28", 700, "0e25d50aa712c2b158952e37a9a42dc40a1a43c5b11447a9e7a529a1db8caf8d", "b6cd62f69134b75b98fbaccea69b47824a7ab8c8706d2d3cefd19b5fec134028"),
    ("29", 700, "21d276e660750bf3775f4b2228b0cf4a9a03faff330ef09d0387bd845bfa9099", "923dd5dd49b5815e237ca69e55a7a172af95b3d8f88802a66a1de81fdfb9cb19"),
    ("30", 700, "cca8db1b096016b9cac3ad5c663004a4daabbf0e4a87e1b9192ba3e4cf72ae2b", "4b0b49b414c9a7a7f63958e5178607fc1af1db9f24d83644ef5972f895c95e8d"),
    ("32", 300, "8b36b5b018a9d1e78f3b7c7eda7a5d30034f1441bc32583e3b7b9c53852a64c6", "e65b6e2081dfbd06542d07c6fbfea686ac8be82ce136f1dc31888f0a42cfead9"),
    ("39", 400, "4184f004a5d1ac036b72ea8b02cdd0baf2124447532cf659a0f93891be83ae1d", "0493d68ed9a40b673e10223c9e3dfbe5696802cc067f89a19956a6158b292a58"),
    ("42", 450, "2c07e7b5f81ef53243a5f017bef97819657ff4a41c251cdc3d3d31d02cecbf54", "d73d490329a7ba3017c70a6ac8782e75d2e49a355b427757e59d7aaaed814f47"),
    ("44", 360, "d3c90b1a425d4abd01bb7dc133d490047951868ec517740ccbace615920d9c42", "394dfd0e79b12f0dc668379bac12b51ec2a484649db6c986cb14be2624217d11"),
    ("45", 400, "5b9d5df2bf134b4e2c03879ff2af11e786e46352b35501417ae78d61f95b6178", "350a3386ecd12e53e8b2566ac43616878e83268804462b8af6fc496f1963999e"),
    ("50", 460, "6a90f5a96705f7b9a4eb1d1a04caeab14359ecc46843f567ad62f6140b397a62", "47be71261d0694514e43e60835668b308c1630a08e6453afc94b4fb57e53bf50"),
    ("51", 430, "208de8ebb3ba2b5ba4101ed154079d8d421aa906fa71228dfdad05710815f096", "eed45364a7a962cd2d6b63054baa0787b17568380792b29dd1b70e00190e91de"),
    ("53", 500, "b8f967ca046ba78d220c73337eb034cd2464ee947a3ccbf462913af698a40ad6", "f46d2e3b94e2dbe97d0df16e0495d41236ffbf66ff829b0bcc05e7264d1441b0"),
    ("54", 220, "c7044b50f8a8da63c32fcca3728fd8d8badc1b2bc8b5fe6c19b274f40a7e0fd8", "8409e65962635e311022a24b2bec9ee3d20087afb80d20460dd4ad3172685fc7"),
    ("58", 390, "5f9f02cc55e206dd8b02b28f18027f1dde7d1cd3df154502f1cef470d71e870d", "c211777dd4bcdf7d41420390a431411927914cd74d6192c97d2ddcfffc1c0551"),
    ("63", 700, "6a80df0bd21d51c6177dc05606f522d13632f644627018376fba220eb3ab7cdc", "28077e189063ff5bd8594a77278f7a0dc4ddc3b797d3f7569833fd2fb0d18279"),
    ("64", 490, "7b26bd76ac8df057286468686866ca213c7887814decc8ec19ce75de362d3759", "32c0437ec2890d7642d141c1f1b524cd331cbccf17b9f63cd5f1b0d94a59e85a"),
    ("65", 370, "c814178d205a8f223ed3f67f13364208fed97d25fd632148fd29be144a9ad0a2", "918680e06ad6e7d848ae1f608706a8d24d18c6d4bac258e1a5428c7a8041369d"),
    ("66", 300, "f6821485d17ab8efed97218f83beb3e7133f5889beed3130e45e97ea9091432a", "0bd8e00e6f6070b1641042466123065c66bb7e4c9cf0bc8af1b808a0ff556cfa"),
    ("69", 700, "2e55549df7d10e081308fa74d1c802ea2339157f9fb14af263c895fcbd03bd23", "52103273f046b4abc68609c1d81fcd35d657a8d9924e821a16a1694e39644a36"),
    ("70", 348, "f560cf9a9581f86322386d10c96b8331de9cc7043afff97c18f46420960b594c", "a58b7850ed05ded62076050e851d6053db0f04ce5fabcf9578faa7c71c1ee952"),
    ("74", 700, "178cdaa0a8f5ac463655a7b66ff6cf9e41cb35921a35e6fe02ab41deb80cf87a", "532d939be2cb63ecc25aed2a6d53b191bb68bf8504124aaec9a788efb0b6ec86"),
    ("76", 520, "c0939f6359f620550a90d2bc500c317614625dbbf3621d00fbcbec62dec34b37", "7c90d265f5fc2f98a5199b83f421ee2668a8f34704151ad85e55c8930d734920"),
    ("78", 348, "01f9b1a4edaec6240a69b26882a7e6e5c725f76894c8f51b30e5bc1aee162ebb", "2b5f8505e35e7c1899f8ec25c4cae4a67c725ad795120fdfba512874715d4e88"),
)

ASSET_HASHES = {
    AUTHOR_ENTRY: "8f4a75ec1e41831a4767aa00e7c027df542d5cb43c2333987204f9bc5e4b246d",
    VARIANT_ROOT / "demo" / "utils" / "trans_matrix.py": "ba14dbd9ab27a822a454c496fb1c3d657e3a9884a06e02e1b353485e11f87f73",
    VARIANT_ROOT / "demo" / "utils" / "async_deadline_runtime.py": "58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300",
    WORKTREE_ROOT / "src" / "tracking" / "mdmt_mia_async_deadline_runtime.py": "58dc55c15bacae8f63ca1ca05432736a1499356e76e32e58399249d9ce6d2300",
    VARIANT_ROOT / "mmtrack" / "models" / "__init__.py": "643e5aa1e06057b79b9d45fa166f3c86e197b352aaf272ad102e64aabc63c2d1",
    VARIANT_ROOT / "mmtrack" / "apis" / "__init__.py": "3238282a8464af32864d6e7557846bf14d76474fd2dbceeddc5622d73cc833bf",
    RUN_CONFIG: "6f472813987fdfecd4751d0ff5729c264c4595430745a43f75b32f891e7f288a",
    CHECKPOINT: "f50882a6814b08d8f9ee2db278825258b52d16463fff6fb45ff45484df7d9e96",
    MIA_ROOT / "upstream" / "configs" / "_base_" / "models" / "new_faster_rcnn_r50_fpn.py": "8a62bb8d993640f13ba9218d844955b9b0d04510dfe905567b77fd1617b566b1",
    MIA_ROOT / "upstream" / "configs" / "_base_" / "datasets" / "test_challenge.py": "f05b77f867e7a27ae072006e5aa1a50a7445c539e74e834c7fd9099d5d8889ba",
    MIA_ROOT / "upstream" / "configs" / "_base_" / "default_runtime.py": "be4151073d5053562b18651294b6b109d8220bcebff7f437fc0f506785201ecf",
}


def _utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_value(arguments):
    return subprocess.check_output(["git", "-C", str(WORKTREE_ROOT), *arguments], text=True).strip()


def _git_is_ancestor(ancestor, descendant):
    return subprocess.run(["git", "-C", str(WORKTREE_ROOT), "merge-base", "--is-ancestor",
                           str(ancestor), str(descendant)], check=False).returncode == 0


def verify_frozen_environment():
    if _git_value(["branch", "--show-current"]) != FROZEN_BRANCH:
        raise PacketCensusToolError("PACKET_CENSUS_CONTRACT_DRIFT: branch")
    current_head = _git_value(["rev-parse", "HEAD"])
    if not _git_is_ancestor(EXECUTION_BASELINE_COMMIT, current_head):
        raise PacketCensusToolError("PACKET_CENSUS_CONTRACT_DRIFT: execution baseline ancestry")
    if _git_value(["status", "--porcelain", "--untracked-files=no"]):
        raise PacketCensusToolError("PACKET_CENSUS_CONTRACT_DRIFT: tracked worktree dirty")
    runtime_inputs = {}
    for path, expected in ASSET_HASHES.items():
        if not path.is_file() or _sha256(path) != expected:
            raise PacketCensusToolError("PACKET_CENSUS_CONTRACT_DRIFT: {}".format(path))
        runtime_inputs[str(path)] = expected
    if not FROZEN_PYTHON.is_file():
        raise PacketCensusToolError("missing frozen author Python: {}".format(FROZEN_PYTHON))
    return runtime_inputs


def _verify_manifest_identity(manifest):
    if manifest.get("contract_sha256") != _sha256(CONTRACT_PATH):
        raise PacketCensusToolError("PACKET_CENSUS_CONTRACT_DRIFT: manifest contract hash")
    tooling_paths = [WORKTREE_ROOT / "src" / "tracking" / "packet_census_run_tools.py", Path(__file__),
                     WORKTREE_ROOT / "scripts" / "summarize_packet_census_z0.py", RNG_WRAPPER]
    observed = {str(path): _sha256(path) for path in tooling_paths}
    if manifest.get("tooling_sha256") != observed:
        raise PacketCensusToolError("PACKET_CENSUS_CONTRACT_DRIFT: manifest tooling hash")


def _state_path(output_root):
    return Path(output_root) / "RUN_STATE.json"


def _write_state(output_root, state):
    atomic_write_json(_state_path(output_root), state)


def _load_state(output_root):
    return read_json(_state_path(output_root))


def _pair_record(manifest, pair_id):
    for item in manifest["pairs"]:
        if item["pair_id"] == str(pair_id):
            return item
    raise PacketCensusToolError("unknown frozen pair: {}".format(pair_id))


def _link(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists() or destination.is_symlink():
        if destination.resolve() != source.resolve():
            raise PacketCensusToolError("existing input link mismatch: {}".format(destination))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.symlink_to(source)


def _prepare_attempt_inputs(attempt_root, pair):
    input_root = Path(attempt_root).resolve() / "input"
    _link(pair["view1_image_dir"], input_root / "1" / pair["view1_sequence"])
    _link(pair["view2_image_dir"], input_root / "2" / pair["view2_sequence"])
    _link(pair["view1_xml_path"], input_root / "xml" / Path(pair["view1_xml_path"]).name)
    _link(pair["view2_xml_path"], input_root / "xml" / Path(pair["view2_xml_path"]).name)
    return input_root / "1", input_root / "xml"


def _last_log_line(path):
    path = Path(path)
    if not path.is_file():
        return ""
    with path.open("rb") as handle:
        handle.seek(max(0, path.stat().st_size - 4096))
        lines = handle.read().decode("utf-8", errors="replace").replace("\r", "\n").splitlines()
    return lines[-1] if lines else ""


def _run_author(attempt_root, pair):
    attempt_root = Path(attempt_root).resolve()
    input_dir, xml_dir = _prepare_attempt_inputs(attempt_root, pair)
    result_dir = Path(attempt_root) / "results"
    environment = os.environ.copy()
    environment.update({
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "7",
        "PYTHONPATH": ":".join([str(VARIANT_ROOT), str(VARIANT_ROOT / "demo"), str(VARIANT_ROOT / "demo" / "utils")]),
        "MIA_ASYNC_CHANNEL_DELAYS": json.dumps(Z0_DELAYS, sort_keys=True),
        "MIA_ACTIVE_PACKET_STAGES": "all",
        "MIA_PACKET_CENSUS_RUN_ID": CENSUS_RUN_ID,
        "MIA_HOMOGRAPHY_REPAIR_AUDIT_PATH": str(Path(attempt_root) / "homography_repair_audit.jsonl"),
    })
    command = [
        str(FROZEN_PYTHON), str(RNG_WRAPPER), "--rng-report", str(Path(attempt_root) / "torch_rng.json"),
        "--entry", str(AUTHOR_ENTRY), "--seed", "7", "--", "--config", str(RUN_CONFIG),
        "--input", str(input_dir) + "/", "--xml_dir", str(xml_dir) + "/", "--result_dir", str(result_dir),
        "--method", "mia_train_{}".format(pair["pair_id"]), "--output", str(Path(attempt_root) / "view1"),
        "--output2", str(Path(attempt_root) / "view2"), "--device", "cuda:0",
    ]
    atomic_write_json(Path(attempt_root) / "command.json", {
        "argv": command, "environment": {key: environment[key] for key in sorted(environment)
                                             if key.startswith("MIA_") or key in ("PYTHONHASHSEED", "PYTHONNOUSERSITE", "PYTHONPATH")},
        "pair_id": pair["pair_id"], "census": True, "condition": "Z0",
    })
    log_path = Path(attempt_root) / "author.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=str(attempt_root), env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, bufsize=1)
        assert process.stdout is not None
        for line in process.stdout:
            log.write(line)
            log.flush()
            print("[{}] {}".format(pair["pair_id"], line.rstrip("\n")), flush=True)
        returncode = process.wait()
    if returncode:
        raise OSError("author process failed with return code {}".format(returncode))


def _next_attempt_root(output_root, pair_id):
    pair_root = Path(output_root) / "pairs" / str(pair_id)
    for number in range(1, 1000):
        path = pair_root / "attempt_{:03d}".format(number)
        if not path.exists():
            path.mkdir(parents=True)
            return path, number
    raise PacketCensusToolError("attempt allocation exhausted")


def _run_one(output_root, manifest, state, pair_id):
    pair = _pair_record(manifest, pair_id)
    attempt_root, number = _next_attempt_root(output_root, pair_id)
    state.update({"state": "PILOT_RUNNING" if pair_id == "23" else "COHORT_RUNNING", "current_pair": pair_id,
                  "current_attempt": number, "updated_at_utc": _utc_now()})
    _write_state(output_root, state)
    try:
        _run_author(attempt_root, pair)
    except OSError as exc:
        state.update({"state": "ENGINEERING_FAILED", "failed_pair": pair_id, "failed_attempt": number,
                      "failure_reason": str(exc), "updated_at_utc": _utc_now()})
        _write_state(output_root, state)
        raise PacketCensusToolError("engineering author failure: {}".format(exc)) from exc
    try:
        report, _, _, _ = validate_pair_attempt(attempt_root, pair)
    except PacketCensusToolError as exc:
        state.update({"state": "PACKET_CENSUS_RUN_INCOMPLETE", "failed_pair": pair_id,
                      "failed_attempt": number, "failure_reason": str(exc), "updated_at_utc": _utc_now()})
        _write_state(output_root, state)
        raise
    write_pair_validation(attempt_root, report)
    if not report["passed"]:
        state.update({"state": "PACKET_CENSUS_RUN_INCOMPLETE", "failed_pair": pair_id, "failed_attempt": number,
                      "failure_reason": list(report["failures"]), "updated_at_utc": _utc_now()})
        _write_state(output_root, state)
        raise PacketCensusToolError("contract validation failure: {}".format(report["failures"]))
    accepted = state.setdefault("accepted_attempts", {})
    accepted[pair_id] = {"attempt": number, "path": str(attempt_root), "validation_sha256": _sha256(Path(attempt_root) / "validation.json")}
    state["updated_at_utc"] = _utc_now()
    _write_state(output_root, state)
    return state


def command_preflight(output_root):
    output_root = Path(output_root).resolve()
    if output_root.exists():
        raise PacketCensusToolError("formal output root already exists")
    runtime_inputs = verify_frozen_environment()
    pair_records = [inspect_pair(pair, count, DATASET_ROOT, (xml1, xml2)) for pair, count, xml1, xml2 in PAIR_SPECS]
    tooling_paths = [WORKTREE_ROOT / "src" / "tracking" / "packet_census_run_tools.py", Path(__file__),
                     WORKTREE_ROOT / "scripts" / "summarize_packet_census_z0.py", RNG_WRAPPER]
    manifest = build_manifest(CONTRACT_PATH, runtime_inputs, tooling_paths, pair_records, _utc_now())
    freeze_manifest(output_root, manifest)
    _write_state(output_root, {"schema_version": "packet-census-z0-run-state-v1", "state": "PREFLIGHT_PASSED",
                               "accepted_attempts": {}, "updated_at_utc": _utc_now()})
    print("PREFLIGHT_PASSED {} pairs / {} frame units".format(manifest["expected_pair_count"], manifest["expected_census_frame_unit_count"]))


def command_pilot(output_root):
    output_root = Path(output_root).resolve()
    verify_frozen_environment()
    manifest = verify_frozen_manifest(output_root)
    _verify_manifest_identity(manifest)
    state = _load_state(output_root)
    if state.get("state") != "PREFLIGHT_PASSED":
        raise PacketCensusToolError("pilot requires PREFLIGHT_PASSED")
    _run_one(output_root, manifest, state, "23")
    state = _load_state(output_root)
    state.update({"state": "PILOT_VALIDATED", "updated_at_utc": _utc_now()})
    _write_state(output_root, state)
    print("PILOT_VALIDATED pair=23")


def command_cohort(output_root):
    output_root = Path(output_root).resolve()
    verify_frozen_environment()
    manifest = verify_frozen_manifest(output_root)
    _verify_manifest_identity(manifest)
    state = _load_state(output_root)
    if state.get("state") not in ("PILOT_VALIDATED", "COHORT_RUNNING"):
        raise PacketCensusToolError("cohort requires PILOT_VALIDATED or resumable COHORT_RUNNING")
    for pair_id in manifest["pair_order"][1:]:
        if pair_id in state.get("accepted_attempts", {}):
            continue
        state = _run_one(output_root, manifest, state, pair_id)
    state.update({"state": "COHORT_VALIDATED", "updated_at_utc": _utc_now()})
    _write_state(output_root, state)
    print("COHORT_VALIDATED pairs=25")


def command_retry(output_root, pair_id, reason):
    output_root = Path(output_root).resolve()
    banned = ("count", "byte", "content", "outlier", "hypothesis", "tracking", "quality")
    if not reason.strip() or any(word in reason.lower() for word in banned):
        raise PacketCensusToolError("retry reason is not a permissible engineering reason")
    summary_path = Path(output_root) / "PACKET_CENSUS_DESCRIPTIVE_SUMMARY.json"
    if summary_path.exists():
        raise PacketCensusToolError("retry forbidden after descriptive summary exists")
    manifest = verify_frozen_manifest(output_root)
    _verify_manifest_identity(manifest)
    state = _load_state(output_root)
    if state.get("state") != "ENGINEERING_FAILED" or state.get("failed_pair") != str(pair_id):
        raise PacketCensusToolError("retry must target the recorded engineering-failed pair")
    state.update({"state": "RETRY_AUTHORIZED", "retry_reason": reason, "updated_at_utc": _utc_now()})
    _write_state(output_root, state)
    _run_one(output_root, manifest, state, str(pair_id))
    state = _load_state(output_root)
    state.update({"state": "PILOT_VALIDATED" if str(pair_id) == "23" else "COHORT_RUNNING", "updated_at_utc": _utc_now()})
    _write_state(output_root, state)


def command_status(output_root):
    output_root = Path(output_root).resolve()
    state = _load_state(output_root)
    current_pair = state.get("current_pair", "")
    current_attempt = state.get("current_attempt")
    last_line = ""
    if current_pair and current_attempt:
        log = Path(output_root) / "pairs" / current_pair / "attempt_{:03d}".format(int(current_attempt)) / "author.log"
        last_line = _last_log_line(log)
    result = {"state": state.get("state"), "current_pair": current_pair, "current_attempt": current_attempt,
              "validated_pair_count": len(state.get("accepted_attempts", {})), "remaining_pair_count": 25 - len(state.get("accepted_attempts", {})),
              "last_author_progress_line": last_line}
    print(json.dumps(result, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "pilot", "cohort", "status"):
        command = subparsers.add_parser(name)
        command.add_argument("--output-root", type=Path, required=True)
    retry = subparsers.add_parser("retry-pair")
    retry.add_argument("--output-root", type=Path, required=True)
    retry.add_argument("--pair", required=True)
    retry.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            command_preflight(args.output_root)
        elif args.command == "pilot":
            command_pilot(args.output_root)
        elif args.command == "cohort":
            command_cohort(args.output_root)
        elif args.command == "retry-pair":
            command_retry(args.output_root, args.pair, args.reason)
        else:
            command_status(args.output_root)
    except PacketCensusToolError as exc:
        print("PACKET_CENSUS_RUN_INCOMPLETE: {}".format(exc), file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
