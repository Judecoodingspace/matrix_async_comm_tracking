import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/run_mdmt_mia_c6_pre_service_semantic_suppression.py"
CHILD_PATH = ROOT / "scripts/run_mdmt_mia_c6_real_child.py"
WRAPPER_PATH = ROOT / "scripts/run_mdmt_mia_author_sync.sh"
FORMAL_PACKAGE_PATH = ROOT / "summary_md/communication/c6_pre_formal_platform_qualification/C6_FORMAL_EXECUTION_PACKAGE.json"
PLATFORM_MANIFEST_PATH = ROOT / "summary_md/communication/c6_pre_formal_platform_qualification/C6_PLATFORM_QUALIFICATION_MANIFEST.json"
BASELINE_SEAL_PATH = ROOT / "summary_md/communication/c6_run004_serviceable_baseline_derivation/C6_RUN004_BASELINE_DERIVATION_SEAL.json"
FORENSIC_PATH = ROOT / "summary_md/communication/c6_formal_forensic_logging_qualification/C6_FORMAL_FORENSIC_LOGGING_QUALIFICATION_REPORT.md"
FAKE_AUTHOR_PATH = ROOT / "tests/fixtures/fake_mdmt_mia_c6_author.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load(RUNNER_PATH, "c6_canonical_path_runner")
child = _load(CHILD_PATH, "c6_canonical_path_child")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    Path(path).write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _make_fake_generated_tree(tmp_path):
    environment = json.loads(PLATFORM_MANIFEST_PATH.read_text(encoding="utf-8"))["environment"]
    production_runtime = Path(environment["runtime_origin"]["file"])
    mia_root = tmp_path / "mia-root"
    generated_root = mia_root / "variants/c6-attempt4-path-rehearsal"
    utils_root = generated_root / "demo/utils"
    utils_root.mkdir(parents=True)
    shutil.copy2(production_runtime, utils_root / "async_deadline_runtime.py")
    shutil.copy2(FAKE_AUTHOR_PATH, generated_root / "demo/supplement_MIA.py")
    (mia_root / ".conda-env/bin").mkdir(parents=True)
    (mia_root / ".conda-env/bin/python").symlink_to(environment["python_executable"])
    (mia_root / "run_configs").mkdir()
    (mia_root / "run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py").write_text(
        "# non-scientific path rehearsal\n", encoding="utf-8"
    )
    inventory = []
    for path in sorted(item for item in generated_root.rglob("*") if item.is_file()):
        inventory.append({
            "relative_path": path.relative_to(generated_root).as_posix(),
            "raw_sha256": _sha(path),
        })
    manifest = tmp_path / "generated-manifest.json"
    _write_json(manifest, {
        "generated_source_root": str(generated_root),
        "implementation_sha": runner.MVE_IMPLEMENTATION_SHA,
        "generated_source_inventory": inventory,
    })
    seal = tmp_path / "generated-seal.json"
    _write_json(seal, {"status": "TEST_ONLY_NON_SCIENTIFIC"})
    return generated_root, manifest, seal, environment


def _make_fake_mdmt_root(tmp_path):
    root = tmp_path / "mdmt-root"
    for path in (
        root / "train/1/23-1",
        root / "train/2/23-2",
        root / "new_xml/1",
        root / "new_xml/2",
        root / "checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt",
    ):
        path.mkdir(parents=True, exist_ok=True)
    (root / "new_xml/1/23-1.xml").write_text("<test/>\n", encoding="utf-8")
    (root / "new_xml/2/23-2.xml").write_text("<test/>\n", encoding="utf-8")
    (root / "checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth").write_bytes(b"test")
    return root


def _rehearsal_spec(tmp_path, monkeypatch):
    generated_root, manifest, seal, environment = _make_fake_generated_tree(tmp_path)
    logical_root = os.path.relpath(
        tmp_path / "summary_md/communication/c6_formal_rehearsal/attempt4_probe", ROOT
    )
    package = json.loads(FORMAL_PACKAGE_PATH.read_text(encoding="utf-8"))
    cell = package["cells"][0]
    package["cells"][0]["output_root"] = logical_root
    package["roots"] = [row["output_root"] for row in package["cells"]]
    package["authorities"]["real_child_sha256"] = _sha(CHILD_PATH)
    package["authorities"]["generated_source_manifest_sha256"] = _sha(manifest)
    package["authorities"]["generated_source_qualification_seal_sha256"] = _sha(seal)
    test_package = tmp_path / "formal-package.json"
    _write_json(test_package, package)
    parent = {
        "schema_version": "C6_FORMAL_AUTHORIZATION_V1",
        "stage": "C6_FORMAL",
        "execution_authorized": True,
        "formal_allowed": True,
        "contract_sha": package["contract_sha"],
        "plan_sha": package["plan_sha"],
        "authorities": package["authorities"],
        "platform_qualification_authority": runner.PLATFORM_QUALIFICATION_AUTHORITY_SHA,
        "metrics": package["metrics"],
        "cells": package["cells"],
        "retry_policy": package["retry_policy"],
        "storage_policy": package["storage_policy"],
        "environment_binding": environment,
        "tracking_outcome_read_allowed": False,
        "science_adaptation_allowed": False,
    }
    parent_path = tmp_path / "formal-parent.json"
    _write_json(parent_path, parent)
    issuance_path = tmp_path / "formal-issuance.json"
    _write_json(issuance_path, {
        "schema_version": "C6_FORMAL_AUTHORIZATION_ISSUANCE_V1",
        "stage": "C6_FORMAL_EXECUTION_AUTHORIZATION_DECISION",
        "status": "ISSUED",
        "formal_stage": "C6_FORMAL",
        "authorization_path": str(parent_path),
        "authorization_sha256": _sha(parent_path),
    })
    monkeypatch.setattr(runner, "FORMAL_PACKAGE_PATH", test_package)
    monkeypatch.setattr(runner, "FORMAL_PACKAGE_SHA256", _sha(test_package))
    monkeypatch.setattr(runner, "MVE_GENERATED_MANIFEST_SHA256", _sha(manifest))
    monkeypatch.setattr(runner, "MVE_GENERATED_QUALIFICATION_SEAL_SHA256", _sha(seal))
    monkeypatch.setattr(runner, "FORMAL_ISSUANCE_AUTHORITY_PATH", issuance_path)
    monkeypatch.setattr(runner, "_require_repository_tracked_issuance", lambda _path, _raw: None)
    monkeypatch.setenv("MDMT_ROOT", str(_make_fake_mdmt_root(tmp_path)))
    author_record = tmp_path / "fake-author-record.json"
    monkeypatch.setenv("FAKE_C6_AUTHOR_RECORD", str(author_record))
    auth = {
        "schema_version": "C6_REAL_CELL_EXECUTION_AUTHORIZATION_V1",
        "stage": "C6_REAL_CELL",
        "execution_authorized": True,
        "run_scope": "EXACTLY_ONE_C6_CELL",
        "parent_policy": "C6_FORMAL",
        "parent_authorization_path": str(parent_path),
        "parent_authorization_sha256": _sha(parent_path),
        "execution_mode": "REAL_CHILD",
        "cell": cell["cell"],
        "pair": cell["pair"],
        "role": cell["role"],
        "service_condition": cell["service_condition"],
        "service_rate": cell["service_rate"],
        "serviceable_id_state_serviced_bytes_baseline": cell["serviceable_id_state_serviced_bytes_baseline"],
        "evidence_shape_profile": cell["evidence_shape_profile"],
        "output_root": logical_root,
        "formal_package_sha256": _sha(test_package),
        "implementation_sha": runner.MVE_IMPLEMENTATION_SHA,
        "generated_source_manifest_sha256": _sha(manifest),
        "generated_source_qualification_seal_sha256": _sha(seal),
        "real_child_sha256": _sha(CHILD_PATH),
        "forensic_logging_qualification_path": "summary_md/communication/c6_formal_forensic_logging_qualification/C6_FORMAL_FORENSIC_LOGGING_QUALIFICATION_REPORT.md",
        "forensic_logging_qualification_sha256": _sha(FORENSIC_PATH),
        "science_adaptation_allowed": False,
        "tracking_outcome_read_allowed": False,
        "formal_aggregation_allowed": False,
    }
    spec = {
        "schema_version": "C6_PRODUCTION_LAUNCH_SPEC_V1",
        "stage": "C6_REAL_CELL",
        "run_id": "c6-attempt4-production-path-rehearsal",
        "authorization": auth,
        "output_root": logical_root,
        "logical_output_root": logical_root,
        "generated_root": str(generated_root),
        "generated_manifest_path": str(manifest),
        "generated_manifest_sha256": _sha(manifest),
        "generated_qualification_seal_path": str(seal),
        "generated_qualification_seal_sha256": _sha(seal),
        "fixture_path": str(CHILD_PATH),
        "fixture_sha256": _sha(CHILD_PATH),
        "production_launcher_path": str(RUNNER_PATH),
        "production_launcher_sha256": _sha(RUNNER_PATH),
        "author_wrapper_path": str(WRAPPER_PATH),
        "author_wrapper_sha256": _sha(WRAPPER_PATH),
        "orchestration_path": str(Path(__file__).resolve()),
        "orchestration_sha256": _sha(Path(__file__).resolve()),
        "cells": [cell["cell"]],
        "service_rates": {cell["cell"]: cell["service_rate"]},
        "service_conditions": {cell["cell"]: cell["service_condition"]},
        "expected_baseline_derivation_seal_sha256": _sha(BASELINE_SEAL_PATH),
        "python_executable": environment["python_executable"],
        "working_directory": str(ROOT),
        "child_environment": {"PYTHONNOUSERSITE": "1", "PYTHONHASHSEED": "0"},
        "fault": "",
        "prelaunch_negative_tests": {"attempt4_canonical_path_rehearsal": True},
        "evidence_shape_profile": "REAL_C6_CELL",
        "expected_deterministic_core_sha256": "",
    }
    return spec, Path(logical_root), author_record


def test_r18_r19_r20_exact_real_subprocess_canonical_path_rehearsal(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    spec, logical_root, author_record = _rehearsal_spec(tmp_path, monkeypatch)
    assert not logical_root.is_absolute()
    result = runner.launch_c6_stage(spec)
    resolved_root = (ROOT / logical_root).resolve()
    cell = spec["cells"][0]
    cell_root = resolved_root / "cells" / cell
    expected_runtime = cell_root / "mia/train_23/results/mia_train_23"
    expected_c6 = cell_root / "c6"
    record = json.loads(author_record.read_text(encoding="utf-8"))
    assert result["child_exit_code"] == 0
    assert result["validator_output"]["status"] == "PASS"
    assert Path(record["MIA_OUTPUT_ROOT"]) == cell_root
    assert Path(record["MIA_RUN_INPUT_ROOT"]) == resolved_root / "run_input" / cell
    assert Path(record["MPLCONFIGDIR"]) == resolved_root / "_runtime_cache/matplotlib"
    assert Path(record["MIA_C6_SUPPRESSION_CONFIG"]["output_dir"]) == expected_c6
    assert all(Path(record[key]).is_absolute() for key in (
        "MIA_OUTPUT_ROOT", "MIA_RUN_INPUT_ROOT", "MPLCONFIGDIR", "result_dir", "output", "output2"
    ))
    assert Path(record["cwd"]) == cell_root / "mia/train_23"
    assert Path(record["result_dir"]) / "mia_train_23" == expected_runtime
    assert result["evidence"][0]["runtime_root"] == expected_runtime
    assert result["evidence"][0]["c6_root"] == expected_c6
    assert (expected_c6 / "c6_first_service_decisions_23-1.jsonl").is_file()
    assert (expected_c6 / "c6_suppression_seal_23-1.json").is_file()
    assert (cell_root / "mia/train_23/author.log").is_file()
    assert not any(path.name == "summary_md" for path in (cell_root / "mia/train_23").rglob("summary_md"))
    assert record["tracking_outcome_read"] is False
    assert record["scientific_nontrivial_workload_executed"] is False


def test_r21_status_and_finalizer_share_canonical_root(tmp_path, monkeypatch):
    monkeypatch.setattr(child, "ROOT", tmp_path)
    logical_root = Path("relative-attempt4-finalizer")
    spec = {
        "output_root": str(logical_root),
        "cells": ["pair_23__FIFO_strong"],
        "service_conditions": {"pair_23__FIFO_strong": "FIFO_strong"},
        "service_rates": {"pair_23__FIFO_strong": 16649},
        "generated_root": str(tmp_path / "generated"),
        "python_executable": sys.executable,
    }
    resolved_root = (tmp_path / logical_root).resolve()
    cell_root = resolved_root / "cells/pair_23__FIFO_strong"
    runtime_root = cell_root / "mia/train_23/results/mia_train_23"
    c6_root = cell_root / "c6"
    runtime_root.mkdir(parents=True)
    c6_root.mkdir()
    for name in (
        "async_packet_manifest_probe.json", "c4_service_ledger_probe.jsonl",
        "c4_service_summary_probe.json", "packet_census_emissions_probe.jsonl",
        "packet_census_terminals_probe.jsonl", "packet_census_finalization_probe.jsonl",
        "packet_census_validation_probe.json",
    ):
        (runtime_root / name).write_text("{}\n", encoding="utf-8")
    (c6_root / "c6_first_service_decisions_probe.jsonl").write_text("{}\n", encoding="utf-8")
    (c6_root / "c6_suppression_seal_probe.json").write_text("{}\n", encoding="utf-8")
    assert child._canonical_output_root(spec) == resolved_root
    assert child._finalize_existing(spec) == 0
    assert (resolved_root / "C6_CHILD_STATUS.json").is_file()
    assert (cell_root / "C6_CHILD_CELL_STATUS.json").is_file()
    assert not (Path.cwd() / logical_root / "C6_CHILD_STATUS.json").exists()
