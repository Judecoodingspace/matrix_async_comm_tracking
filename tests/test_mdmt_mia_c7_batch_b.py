from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from tracking.mdmt_mia_c7_batch_b import (
    C7BatchBError,
    aggregate_cell,
    make_validated_no_stale_window_record,
    qualify_cell,
    select_qualified_cell,
)
from tracking.mdmt_mia_c7_batch_b_package import (
    C7BatchBPackageError,
    atomic_write_json,
    build_batch_b_manifest,
    write_cell_transaction,
    write_selection_package,
)
from tracking.mdmt_mia_c7_batch_b_schema import (
    CELL_AGGREGATE_SCHEMA,
    CELL_QUALIFICATION_SCHEMA,
    SOURCE_HASH_KEYS,
    canonical_sha256,
    registered_cells,
)
from tracking.mdmt_mia_c7_batch_b_validator import (
    C7BatchBValidationError,
    reconstruct_aggregate,
    validate_committed_cell,
    validate_committed_package,
    validate_manifest,
    validate_selection,
)


ROOT = Path(__file__).resolve().parents[1]


def _cell(
    cell_id="SYNTHETIC_TINY", pair_id="SYNTHETIC_PAIR", frame_count=2,
    capacity_id="SYNTHETIC_CAPACITY", capacity_bytes=20,
):
    return {
        "cell_id": cell_id,
        "pair_id": pair_id,
        "frame_count": frame_count,
        "capacity_id": capacity_id,
        "capacity_bytes": capacity_bytes,
        "stable_pair_order": 0,
        "stable_capacity_order": 0,
    }


def _hashes(value="a"):
    return {key: value * 64 for key in SOURCE_HASH_KEYS}


def _manifest(tmp_path, value="a"):
    return build_batch_b_manifest(
        run_id="synthetic-run",
        output_root=tmp_path,
        batch_b_implementation_sha="b" * 40,
        source_hashes=_hashes(value),
        input_identity={"fixture": "synthetic-only", "digest": "c" * 64},
        config_identity={"fixture": "tiny", "digest": "d" * 64},
        synthetic_non_scientific=True,
    )


def _no_stale_windows(cell, frames=(0, 1), run_id="synthetic-run"):
    return [
        make_validated_no_stale_window_record(
            run_id=run_id,
            cell=cell,
            frame_index=frame,
            raw_evidence_sha256=("{:064x}".format(frame + 1)),
        )
        for frame in frames
    ]


def _aggregate_stub(cell, n_stale, n_eligible, n_all=None):
    n_all = cell["frame_count"] if n_all is None else n_all
    domain = list(range(max(0, n_all)))
    return {
        "schema_version": CELL_AGGREGATE_SCHEMA,
        "run_id": "synthetic-run",
        "cell_id": cell["cell_id"],
        "pair_id": cell["pair_id"],
        "capacity_id": cell["capacity_id"],
        "capacity_bytes": cell["capacity_bytes"],
        "expected_frame_domain": domain,
        "observed_frame_domain": domain,
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
        "input_window_evidence_digests": [],
        "schema_identity": "C7_VALIDATED_WINDOW_V1",
        "producer_source_authority": "C7_CORE_SEMANTICS_V3",
        "validator_source_authority": "C7_CORE_VALIDATION_V3",
    }


def _qualifications(overrides=None):
    overrides = {} if overrides is None else overrides
    records = []
    for cell in registered_cells():
        n_stale, n_eligible = overrides.get(cell["cell_id"], (0, 0))
        records.append(qualify_cell(_aggregate_stub(cell, n_stale, n_eligible)))
    return records


@lru_cache(maxsize=1)
def _batch_a_test_module():
    path = ROOT / "tests/test_mdmt_mia_c7_batch_a_core.py"
    spec = importlib.util.spec_from_file_location("c7_batch_a_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_m5_valid_zero_is_distinct_from_invalid():
    cell = _cell()
    windows = _no_stale_windows(cell)
    aggregate = aggregate_cell(
        run_id="synthetic-run", cell=cell, expected_frame_domain=(0, 1),
        validated_windows=windows)
    assert aggregate["cell_validity"] == "VALID_ZERO"
    assert (aggregate["N_all"], aggregate["N_stale"], aggregate["N_eligible"]) == (2, 0, 0)
    assert aggregate["conditional_rate"] == {
        "status": "N/A", "numerator": 0, "denominator": 0}
    qualification = qualify_cell(aggregate)
    assert qualification["denominator_pass"] is False
    assert qualification["conditional_pass"] is False
    assert qualification["CELL_QUALIFIED"] is False
    assert reconstruct_aggregate(
        run_id="synthetic-run", cell=cell, expected_frame_domain=(0, 1),
        windows=windows) == aggregate


@pytest.mark.parametrize("eligible,expected", [(4, False), (5, True)])
def test_m5_count_gate_boundary(eligible, expected):
    cell = _cell(frame_count=300)
    qualification = qualify_cell(_aggregate_stub(cell, 20, eligible))
    assert qualification["count_pass"] is expected


@pytest.mark.parametrize("stale,expected", [(19, False), (20, True)])
def test_m5_denominator_gate_boundary(stale, expected):
    cell = _cell(frame_count=300)
    qualification = qualify_cell(_aggregate_stub(cell, stale, 5))
    assert qualification["denominator_pass"] is expected


def test_m5_exact_integer_rate_boundaries():
    cell = _cell(frame_count=300)
    exact = qualify_cell(_aggregate_stub(cell, 20, 5))
    assert exact["global_lhs"] == exact["global_rhs"] == 300
    assert exact["global_pass"] is True
    assert exact["conditional_lhs"] == exact["conditional_rhs"] == 20
    assert exact["conditional_pass"] is True
    global_fail = qualify_cell(_aggregate_stub(_cell(frame_count=301), 20, 5))
    assert global_fail["global_pass"] is False
    conditional_fail = qualify_cell(_aggregate_stub(cell, 21, 5))
    assert conditional_fail["conditional_pass"] is False


@pytest.mark.parametrize(
    "counts",
    [(-1, 0, 0), (2, 3, 0), (2, 1, 2)],
)
def test_m5_invalid_count_nesting_fails_closed(counts):
    n_all, n_stale, n_eligible = counts
    with pytest.raises(C7BatchBError):
        qualify_cell(_aggregate_stub(_cell(frame_count=max(1, n_all)), n_stale, n_eligible, n_all))


@pytest.mark.parametrize("fault", ["duplicate", "missing", "extra", "wrong_cell", "invalid_window"])
def test_m5_window_domain_and_validity_faults_fail_closed(fault):
    cell = _cell()
    windows = _no_stale_windows(cell)
    expected = (0, 1)
    if fault == "duplicate":
        windows[1] = copy.deepcopy(windows[0])
    elif fault == "missing":
        windows.pop()
    elif fault == "extra":
        windows.append(make_validated_no_stale_window_record(
            run_id="synthetic-run", cell=cell, frame_index=2,
            raw_evidence_sha256="e" * 64))
    elif fault == "wrong_cell":
        windows[0]["cell_id"] = "OTHER"
    else:
        windows[0]["validation"]["status"] = "FAIL"
    with pytest.raises(C7BatchBError):
        aggregate_cell(
            run_id="synthetic-run", cell=cell, expected_frame_domain=expected,
            validated_windows=windows)


def test_m5_independent_reconstruction_rejects_tampered_aggregate():
    cell = _cell()
    windows = _no_stale_windows(cell)
    aggregate = aggregate_cell(
        run_id="synthetic-run", cell=cell, expected_frame_domain=(0, 1),
        validated_windows=windows)
    aggregate["N_eligible"] = 1
    assert reconstruct_aggregate(
        run_id="synthetic-run", cell=cell, expected_frame_domain=(0, 1),
        windows=windows) != aggregate


def test_m6_zero_and_one_qualified(tmp_path):
    manifest = _manifest(tmp_path)
    none = select_qualified_cell(manifest, _qualifications())
    assert none["selection_outcome"] == "NO_CELL_SELECTED"
    assert none["selected_cell_id"] is None
    one_id = registered_cells()[0]["cell_id"]
    one_records = _qualifications({one_id: (40, 20)})
    one = select_qualified_cell(manifest, one_records)
    assert one["selection_outcome"] == "SELECTED_CELL"
    assert one["selected_cell_id"] == one_id
    assert validate_selection(manifest, one_records, one)["status"] == "PASS"


def test_m6_maximum_count_wins(tmp_path):
    cells = registered_cells()
    manifest = _manifest(tmp_path)
    records = _qualifications({
        cells[0]["cell_id"]: (40, 20),
        cells[1]["cell_id"]: (40, 21),
    })
    assert select_qualified_cell(manifest, records)["selected_cell_id"] == cells[1]["cell_id"]


def test_m6_exact_pareto_dominance(tmp_path):
    cells = registered_cells()
    first = cells[0]       # P23: 700 frames
    better = cells[7]      # P44: 360 frames
    records = _qualifications({
        first["cell_id"]: (48, 12),
        better["cell_id"]: (24, 12),
    })
    selection = select_qualified_cell(_manifest(tmp_path), records)
    assert selection["selected_cell_id"] == better["cell_id"]


def test_m6_incomparable_rates_use_stable_order(tmp_path):
    cells = registered_cells()
    first = cells[0]       # worse global, better conditional
    second = cells[7]      # better global, worse conditional
    records = _qualifications({
        first["cell_id"]: (20, 12),
        second["cell_id"]: (48, 12),
    })
    selection = select_qualified_cell(_manifest(tmp_path), records)
    assert selection["selected_cell_id"] == first["cell_id"]
    assert selection["comparison_trace"]["stable_tiebreak"][0] == first["cell_id"]


def test_m6_exact_equal_rates_use_stable_capacity_order(tmp_path):
    cells = registered_cells()
    first, second = cells[0], cells[1]
    records = _qualifications({first["cell_id"]: (40, 20), second["cell_id"]: (40, 20)})
    assert select_qualified_cell(_manifest(tmp_path), records)["selected_cell_id"] == first["cell_id"]


@pytest.mark.parametrize(
    "fault",
    ["missing", "extra", "duplicate", "tampered_boolean", "tampered_cross_product",
     "authority_mismatch", "invalid_cell", "weighted_field"],
)
def test_m6_incomplete_or_tampered_domains_block_selection(tmp_path, fault):
    manifest = _manifest(tmp_path)
    records = _qualifications()
    if fault == "missing":
        records.pop()
    elif fault == "extra":
        records.append(copy.deepcopy(records[0]))
    elif fault == "duplicate":
        records[-1] = copy.deepcopy(records[0])
    elif fault == "tampered_boolean":
        records[0]["CELL_QUALIFIED"] = True
    elif fault == "tampered_cross_product":
        records[0]["global_lhs"] += 1
    elif fault == "authority_mismatch":
        records[0]["batch_a_freeze_authority"] = "0" * 40
    elif fault == "invalid_cell":
        records[0]["cell_validation_status"] = "FAIL"
    else:
        records[0]["weighted_score"] = 1
    with pytest.raises(C7BatchBError):
        select_qualified_cell(manifest, records)


def test_m7_cell_transaction_inventory_seal_and_resume(tmp_path):
    manifest = _manifest(tmp_path)
    cell = _cell()
    windows = _no_stale_windows(cell)
    first = write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0, 1), windows=windows,
        synthetic_non_scientific=True)
    assert first["status"] == "COMMITTED"
    assert first["seal_reproduced"] is True
    second = write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0, 1), windows=windows,
        synthetic_non_scientific=True)
    assert second["status"] == "SKIPPED_VALID_SEALED"


def test_m7_incomplete_staging_is_quarantined_and_recomputed(tmp_path):
    manifest = _manifest(tmp_path)
    cell = _cell()
    staging = tmp_path / "cells" / ".SYNTHETIC_TINY.staging"
    staging.mkdir(parents=True)
    (staging / "partial").write_text("incomplete", encoding="utf-8")
    result = write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0, 1), windows=_no_stale_windows(cell),
        synthetic_non_scientific=True)
    assert result["status"] == "COMMITTED"
    assert list((tmp_path / "cells").glob("*.quarantine-incomplete-staging-*"))


def test_m7_final_without_terminal_is_quarantined(tmp_path):
    manifest = _manifest(tmp_path)
    cell = _cell()
    final = tmp_path / "cells" / cell["cell_id"]
    final.mkdir(parents=True)
    (final / "partial").write_text("incomplete", encoding="utf-8")
    result = write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0, 1), windows=_no_stale_windows(cell),
        synthetic_non_scientific=True)
    assert result["status"] == "COMMITTED"
    assert list((tmp_path / "cells").glob("*.quarantine-missing-terminal-*"))


@pytest.mark.parametrize("fault", ["digest", "unexpected_file", "terminal"])
def test_m7_committed_cell_tamper_fails_closed(tmp_path, fault):
    manifest = _manifest(tmp_path)
    cell = _cell()
    write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0, 1), windows=_no_stale_windows(cell),
        synthetic_non_scientific=True)
    final = tmp_path / "cells" / cell["cell_id"]
    if fault == "digest":
        aggregate = json.loads((final / "cell_aggregate.json").read_text())
        aggregate["N_eligible"] = 1
        atomic_write_json(final / "cell_aggregate.json", aggregate)
    elif fault == "unexpected_file":
        (final / "unexpected").write_text("x", encoding="utf-8")
    else:
        terminal = json.loads((final / "CELL_COMMITTED.json").read_text())
        terminal["seal_sha256"] = "0" * 64
        atomic_write_json(final / "CELL_COMMITTED.json", terminal)
    with pytest.raises(C7BatchBValidationError):
        validate_committed_cell(final)


def test_m7_resume_manifest_mismatch_hard_fails(tmp_path):
    cell = _cell()
    first_manifest = _manifest(tmp_path, "a")
    write_cell_transaction(
        output_root=tmp_path, manifest=first_manifest, cell=cell,
        expected_frame_domain=(0, 1), windows=_no_stale_windows(cell),
        synthetic_non_scientific=True)
    with pytest.raises(C7BatchBPackageError, match="mismatched"):
        write_cell_transaction(
            output_root=tmp_path, manifest=_manifest(tmp_path, "f"), cell=cell,
            expected_frame_domain=(0, 1), windows=_no_stale_windows(cell),
            synthetic_non_scientific=True)


@pytest.mark.parametrize("fault", ["authority", "schema", "source", "forbidden"])
def test_m7_manifest_binding_and_firewall_faults(fault, tmp_path):
    manifest = _manifest(tmp_path)
    if fault == "authority":
        manifest["authorities"]["batch_a_freeze_authority"] = "0" * 40
    elif fault == "schema":
        manifest["schema_identities"]["batch_a_validation"] = "OTHER"
    elif fault == "source":
        manifest["source_hashes"]["runtime"] = "bad"
    else:
        manifest["input_identity"]["IDF1"] = 1
    with pytest.raises(C7BatchBValidationError):
        validate_manifest(manifest)


def test_m7_package_transaction_and_tamper(tmp_path):
    manifest = _manifest(tmp_path)
    qualifications = _qualifications()
    result = write_selection_package(
        output_root=tmp_path, manifest=manifest, qualifications=qualifications)
    assert result["status"] == "COMMITTED"
    assert result["seal_reproduced"] is True
    package = tmp_path / "package"
    selection = json.loads((package / "C7_SELECTION.json").read_text())
    selection["qualified_subset"] = [registered_cells()[0]["cell_id"]]
    atomic_write_json(package / "C7_SELECTION.json", selection)
    with pytest.raises(C7BatchBValidationError):
        validate_committed_package(package)


def test_m7_failed_cell_validation_produces_no_authoritative_final(tmp_path):
    manifest = _manifest(tmp_path)
    cell = _cell()
    with pytest.raises(C7BatchBError):
        write_cell_transaction(
            output_root=tmp_path, manifest=manifest, cell=cell,
            expected_frame_domain=(0, 1), windows=_no_stale_windows(cell, (0,)),
            synthetic_non_scientific=True)
    assert not (tmp_path / "cells" / cell["cell_id"]).exists()
    quarantines = list((tmp_path / "cells").glob("*.quarantine-failed-transaction-*"))
    assert quarantines
    assert not any((path / "cell_seal.json").exists() for path in quarantines)


def test_m7_real_launcher_path_dry_run_only(tmp_path):
    path = ROOT / "scripts/run_mdmt_mia_c7_outcome_blind_census.py"
    spec = importlib.util.spec_from_file_location("c7_launcher", path)
    assert spec and spec.loader
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    wrapper = ROOT / "scripts/run_mdmt_mia_author_sync.sh"
    status = launcher.dry_run_real_launcher_path({
        "output_root": str(tmp_path / "dry-run"),
        "cell": dict(registered_cells()[0]),
        "author_wrapper_path": str(wrapper),
        "author_wrapper_sha256": __import__(
            "tracking.mdmt_mia_c7_batch_b_schema", fromlist=["sha256_file"]
        ).sha256_file(wrapper),
        "author_output_root": str(tmp_path / "author"),
        "generated_source_root": str(tmp_path / "generated"),
        "split": "train",
    })
    assert status["status"] == "PATH_VALID"
    assert status["real_input_executed"] is False


def test_synthetic_tiny_e2e_uses_child_disk_validator_writer_and_selector(tmp_path):
    batch_a = _batch_a_test_module()
    _, _, evidence = batch_a._case_a()
    evidence_path = tmp_path / "batch_a_evidence.json"
    atomic_write_json(evidence_path, evidence)
    cell = _cell(frame_count=1, capacity_bytes=60)
    fixture_spec = {
        "synthetic_non_scientific": True,
        "run_id": "synthetic-run",
        "cell": cell,
        "windows": [{
            "kind": "BATCH_A_CORE",
            "frame_index": 0,
            "evidence_path": str(evidence_path),
        }],
        "output_path": str(tmp_path / "window_source.jsonl"),
    }
    fixture_spec_path = tmp_path / "fixture_spec.json"
    atomic_write_json(fixture_spec_path, fixture_spec)
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tests/fixtures/run_mdmt_mia_c7_tiny_runtime.py"),
         "--spec", str(fixture_spec_path)],
        cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
        check=False)
    assert completed.returncode == 0
    launcher_path = ROOT / "scripts/run_mdmt_mia_c7_outcome_blind_census.py"
    spec = importlib.util.spec_from_file_location("c7_launcher_e2e", launcher_path)
    assert spec and spec.loader
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    output_root = tmp_path / "e2e-output"
    manifest = launcher.build_frozen_manifest(
        run_id="synthetic-run", output_root=output_root,
        batch_b_implementation_sha="b" * 40,
        input_identity={"fixture": "synthetic-only", "digest": "c" * 64},
        config_identity={"fixture": "tiny", "digest": "d" * 64},
        synthetic_non_scientific=True)
    result = launcher.execute_synthetic_launch(
        output_root=output_root, manifest=manifest, synthetic_cell=cell,
        expected_frame_domain=(0,), window_source=tmp_path / "window_source.jsonl",
        qualifications=_qualifications())
    assert result == {
        "schema_version": "C7_SYNTHETIC_E2E_STATUS_V1",
        "status": "PASS",
        "synthetic_non_scientific": True,
        "child_status": "PASS",
        "cell_transaction_status": "COMMITTED",
        "package_transaction_status": "COMMITTED",
        "seal_reproduced": True,
        "real_input_executed": False,
    }
    assert validate_committed_cell(
        output_root / "cells" / cell["cell_id"],
        expected_manifest_sha256=canonical_sha256(manifest))["status"] == "PASS"
    assert validate_committed_package(output_root / "package")["status"] == "PASS"


def test_outcome_firewall_static_production_dependencies():
    production = [
        ROOT / "src/tracking/mdmt_mia_c7_batch_b.py",
        ROOT / "src/tracking/mdmt_mia_c7_batch_b_validator.py",
        ROOT / "src/tracking/mdmt_mia_c7_batch_b_package.py",
        ROOT / "scripts/run_mdmt_mia_c7_outcome_blind_census.py",
        ROOT / "scripts/run_mdmt_mia_c7_real_child.py",
    ]
    forbidden = ("idf1", "idsw", "mota", "hota", "evaluation.mdmt_mia_paper")
    for path in production:
        source = path.read_text(encoding="utf-8").casefold()
        assert all(token not in source for token in forbidden), path
