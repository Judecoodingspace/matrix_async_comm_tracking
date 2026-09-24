from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from tracking.mdmt_mia_c7_batch_b import (
    C7BatchBError,
    aggregate_cell,
    make_validated_no_stale_window_record,
    qualify_cell,
    raw_no_stale_evidence_from_observer,
    select_qualified_cell,
)
from tracking.mdmt_mia_c7_batch_b_package import (
    C7BatchBPackageError,
    atomic_write_json,
    atomic_write_jsonl,
    build_batch_b_manifest,
    write_cell_transaction,
    write_selection_package,
)
from tracking.mdmt_mia_c7_batch_b_schema import (
    ALLOWED_PARENT_ENV_KEYS,
    CELL_AGGREGATE_SCHEMA,
    CELL_QUALIFICATION_SCHEMA,
    EXECUTION_RESOURCE_CLASS_CHECKPOINT,
    EXECUTION_RESOURCE_CLASS_DIRECTORY,
    EXECUTION_RESOURCE_CLASS_FILE,
    MVE_AUTHORIZATION_ROLE,
    MVE_AUTHORIZATION_SCHEMA,
    MVE_AUTHORIZATION_STATUS_AUTHORIZED,
    REGISTERED_C7_CONFIG_CLASS_ID,
    REGISTERED_C7_CONFIG_FILES_KIND,
    REGISTERED_C7_INPUT_CLASS_ID,
    REGISTERED_C7_INPUT_FILES_KIND,
    REGISTERED_SOURCE_RELATIVE_PATHS,
    SOURCE_HASH_KEYS,
    authority_bindings,
    canonical_sha256,
    inventory_generated_source,
    registered_cells,
    sha256_file,
    validate_mve_authorization,
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

CHILD_PATH = ROOT / "scripts/run_mdmt_mia_c7_real_child.py"
CHILD_SPEC = importlib.util.spec_from_file_location("c7_child", CHILD_PATH)
assert CHILD_SPEC and CHILD_SPEC.loader
CHILD = importlib.util.module_from_spec(CHILD_SPEC)
CHILD_SPEC.loader.exec_module(CHILD)


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


def _manifest(tmp_path, value="a", synthetic=True):
    if not synthetic:
        fixture = _registered_provenance_fixture(tmp_path)
        return build_batch_b_manifest(
            run_id="synthetic-run",
            output_root=tmp_path,
            batch_b_implementation_sha=fixture["head"],
            source_hashes=None,
            input_identity=fixture["input_identity"],
            config_identity=fixture["config_identity"],
            synthetic_non_scientific=False,
            repo_root=fixture["repo_root"],
            wrapper_path=fixture["wrapper_path"],
            generated_source_root=fixture["generated_source_root"],
        )
    return build_batch_b_manifest(
        run_id="synthetic-run",
        output_root=tmp_path,
        batch_b_implementation_sha="b" * 40,
        source_hashes=_hashes(value),
        input_identity={"fixture": "synthetic-only", "digest": "c" * 64},
        config_identity={"fixture": "tiny", "digest": "d" * 64},
        synthetic_non_scientific=synthetic,
    )


def _registered_provenance_fixture(tmp_path):
    repo = tmp_path / "registered-provenance-repo"
    if not (repo / ".git").is_dir():
        for relative in sorted(set(REGISTERED_SOURCE_RELATIVE_PATHS.values())):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture source: {}\n".format(relative), encoding="utf-8")
        input_path = repo / "fixtures/communication_input.json"
        config_path = repo / "fixtures/c7_config.json"
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text(json.dumps({
            "schema_version": REGISTERED_C7_INPUT_CLASS_ID,
            "pair_id": "P23",
            "split": "train",
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        config_path.write_text(json.dumps({
            "schema_version": REGISTERED_C7_CONFIG_CLASS_ID,
            "device": "cuda:0",
            "stage": "mia",
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "C7 Test"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "c7@example.invalid"],
            check=True)
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", "fixture"], check=True)
    input_path = repo / "fixtures/communication_input.json"
    config_path = repo / "fixtures/c7_config.json"
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True).stdout.strip()
    return {
        "repo_root": repo.resolve(),
        "head": head,
        "wrapper_path": (
            repo / REGISTERED_SOURCE_RELATIVE_PATHS["wrapper"]).resolve(),
        "generated_source_root": (tmp_path / "generated-author-source").resolve(),
        "input_path": input_path.resolve(),
        "config_path": config_path.resolve(),
        "input_identity": {
            "kind": "REGISTERED_C7_INPUT_FILES_V1",
            "files": [{"path": str(input_path.resolve()), "sha256": sha256_file(input_path)}],
        },
        "config_identity": {
            "kind": "REGISTERED_C7_CONFIG_FILES_V1",
            "files": [{"path": str(config_path.resolve()), "sha256": sha256_file(config_path)}],
        },
    }


def _build_registered_fixture_manifest(tmp_path, fixture, **overrides):
    arguments = {
        "run_id": "registered-fixture-run",
        "output_root": tmp_path / "registered-output",
        "batch_b_implementation_sha": fixture["head"],
        "source_hashes": None,
        "input_identity": fixture["input_identity"],
        "config_identity": fixture["config_identity"],
        "synthetic_non_scientific": False,
        "repo_root": fixture["repo_root"],
        "wrapper_path": fixture["wrapper_path"],
        "generated_source_root": fixture["generated_source_root"],
    }
    arguments.update(overrides)
    return build_batch_b_manifest(**arguments)


def _no_stale_windows(cell, frames=(0, 1), run_id="synthetic-run"):
    return [
        make_validated_no_stale_window_record(
            run_id=run_id,
            cell=cell,
            frame_index=frame,
            raw_observation_evidence=_raw_observer_evidence(frame=frame, stale=False),
        )
        for frame in frames
    ]


def _raw_observer_evidence(frame=0, stale=False):
    batch_a = _batch_a_test_module()
    observer = batch_a.C7CoreObserver()
    rows = batch_a.np.empty((0, 6), dtype=batch_a.np.float32)

    def provider(packet_id, provider_frame):
        confirmed = (9,) if stale else ()
        return batch_a._snapshot_c5_receiver_state(
            provider_frame, packet_id, rows, rows, confirmed, {}, 0)

    server = batch_a._C4SharedLogicalServer(
        "fifo", 10000, sequence_name="synthetic", run_id="batch-b-raw",
        condition="test", pair_id="synthetic", ledger_enabled=False)
    server.begin_frame(frame, c7_observer=observer, c7_context_provider=provider)
    wire = batch_a._wire(version=1, confirmed=(9,))
    encoded = json.dumps(wire, sort_keys=True, separators=(",", ":"))
    server.admit(
        "id_state", frame, wire, encoded,
        __import__("hashlib").sha256(encoded.encode("utf-8")).hexdigest(),
        c7_observer=observer, c7_context_provider=provider)
    server.finalize_pending(frame, observer)
    return raw_no_stale_evidence_from_observer(frame, observer)


def _seal_all_synthetic_cells(tmp_path, manifest, cells=None):
    for cell in (manifest["cells"] if cells is None else cells):
        write_cell_transaction(
            output_root=tmp_path,
            manifest=manifest,
            cell=cell,
            expected_frame_domain=manifest["authorized_frame_domains"][cell["cell_id"]],
            windows=_no_stale_windows(cell, (0,)),
            synthetic_non_scientific=True,
        )


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
            raw_observation_evidence=_raw_observer_evidence(frame=2, stale=False)))
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


def test_p1_bb_01_stale_raw_evidence_cannot_be_forged_as_no_stale():
    cell = _cell(frame_count=1)
    stale_raw = _raw_observer_evidence(frame=0, stale=True)
    with pytest.raises(C7BatchBError, match="suppressible stale"):
        make_validated_no_stale_window_record(
            run_id="synthetic-run", cell=cell, frame_index=0,
            raw_observation_evidence=stale_raw)

    forged = _no_stale_windows(cell, (0,))[0]
    forged["evidence"] = stale_raw
    forged["evidence_sha256"] = canonical_sha256(stale_raw)
    forged["validation"]["raw_evidence_sha256"] = canonical_sha256(stale_raw)
    forged["validation_sha256"] = canonical_sha256(forged["validation"])
    with pytest.raises(C7BatchBValidationError):
        reconstruct_aggregate(
            run_id="synthetic-run", cell=cell, expected_frame_domain=(0,),
            windows=[forged])


@pytest.mark.parametrize("fault", ["missing_true_first_service", "observer_failure"])
def test_p1_bb_01_incomplete_raw_no_stale_evidence_is_rejected(fault):
    cell = _cell(frame_count=1)
    evidence = _raw_observer_evidence(frame=0, stale=False)
    if fault == "missing_true_first_service":
        evidence["observations"] = [
            row for row in evidence["observations"]
            if row["observation_kind"] != "true_first_service"
        ]
    else:
        evidence["observer_failures"].append({"frame": 0, "reason": "forced"})
    with pytest.raises(C7BatchBError):
        make_validated_no_stale_window_record(
            run_id="synthetic-run", cell=cell, frame_index=0,
            raw_observation_evidence=evidence)


def test_no_stale_rejects_whole_stale_packet_event_chain_omission():
    cell = _cell(frame_count=1)
    evidence = _raw_observer_evidence(frame=0, stale=True)
    omitted_kinds = {"true_first_service", "service_slice", "completion"}
    evidence["observations"] = [
        row for row in evidence["observations"]
        if row["observation_kind"] not in omitted_kinds
    ]
    assert [row["observation_kind"] for row in evidence["observations"]] == [
        "frame_open", "enqueue", "frame_close"]
    assert [row["event"]["event_ordinal"] for row in evidence["observations"]] == [1, 2, 6]

    with pytest.raises(C7BatchBError, match="service-slice byte ledger"):
        make_validated_no_stale_window_record(
            run_id="synthetic-run", cell=cell, frame_index=0,
            raw_observation_evidence=evidence)

    forged = _no_stale_windows(cell, (0,))[0]
    forged["evidence"] = evidence
    forged["evidence_sha256"] = canonical_sha256(evidence)
    forged["validation"].update({
        "true_first_service_count": 0,
        "id_state_true_first_service_count": 0,
        "stale_classification_count": 0,
        "stale_present": False,
        "raw_evidence_sha256": canonical_sha256(evidence),
    })
    forged["validation_sha256"] = canonical_sha256(forged["validation"])
    with pytest.raises(C7BatchBValidationError, match="service-slice byte ledger"):
        reconstruct_aggregate(
            run_id="synthetic-run", cell=cell, expected_frame_domain=(0,),
            windows=[forged])


def test_p1_bb_02_unregistered_cell_cannot_enter_real_manifest_domain(tmp_path):
    manifest = _manifest(tmp_path, synthetic=False)
    cell = _cell()
    with pytest.raises(C7BatchBPackageError, match="exact member"):
        write_cell_transaction(
            output_root=tmp_path, manifest=manifest, cell=cell,
            expected_frame_domain=(0, 1), windows=_no_stale_windows(cell),
            synthetic_non_scientific=False)
    assert not (tmp_path / "cells" / cell["cell_id"]).exists()


def test_p1_bb_02_wrong_registered_frame_domain_is_rejected_before_seal(tmp_path):
    manifest = _manifest(tmp_path, synthetic=False)
    cell = dict(registered_cells()[0])
    wrong_domain = tuple(range(100))
    with pytest.raises(C7BatchBPackageError, match="manifest authority"):
        write_cell_transaction(
            output_root=tmp_path, manifest=manifest, cell=cell,
            expected_frame_domain=wrong_domain, windows=[],
            synthetic_non_scientific=False)
    assert not (tmp_path / "cells" / cell["cell_id"]).exists()


def test_p1_bb_02_synthetic_cell_cannot_validate_as_registered_cell(tmp_path):
    cell = dict(registered_cells()[0])
    synthetic_manifest = _manifest(tmp_path, synthetic=True)
    write_cell_transaction(
        output_root=tmp_path, manifest=synthetic_manifest, cell=cell,
        expected_frame_domain=(0,), windows=_no_stale_windows(cell, (0,)),
        synthetic_non_scientific=True)
    real_manifest = _manifest(tmp_path, synthetic=False)
    with pytest.raises(C7BatchBValidationError, match="authority mismatch"):
        validate_committed_cell(
            tmp_path / "cells" / cell["cell_id"], expected_manifest=real_manifest)


def test_p1_bb_03_handbuilt_qualifications_cannot_create_package(tmp_path):
    manifest = _manifest(tmp_path)
    with pytest.raises(C7BatchBPackageError, match="caller-supplied"):
        write_selection_package(
            output_root=tmp_path, manifest=manifest,
            qualifications=_qualifications())
    assert not (tmp_path / "package").exists()


def test_p1_bb_03_missing_one_of_21_sealed_cells_blocks_package(tmp_path):
    manifest = _manifest(tmp_path)
    _seal_all_synthetic_cells(tmp_path, manifest, manifest["cells"][:-1])
    with pytest.raises((C7BatchBValidationError, C7BatchBPackageError)):
        write_selection_package(output_root=tmp_path, manifest=manifest)
    assert not (tmp_path / "package").exists()


def test_p1_bb_03_tampered_cell_seal_blocks_package(tmp_path):
    manifest = _manifest(tmp_path)
    _seal_all_synthetic_cells(tmp_path, manifest)
    seal_path = tmp_path / "cells" / manifest["cells"][0]["cell_id"] / "cell_seal.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["seal_sha256"] = "0" * 64
    atomic_write_json(seal_path, seal)
    with pytest.raises((C7BatchBValidationError, C7BatchBPackageError)):
        write_selection_package(output_root=tmp_path, manifest=manifest)
    assert not (tmp_path / "package").exists()


def test_m6_zero_and_one_qualified(tmp_path):
    manifest = _manifest(tmp_path, synthetic=False)
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
    manifest = _manifest(tmp_path, synthetic=False)
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
    selection = select_qualified_cell(_manifest(tmp_path, synthetic=False), records)
    assert selection["selected_cell_id"] == better["cell_id"]


def test_m6_incomparable_rates_use_stable_order(tmp_path):
    cells = registered_cells()
    first = cells[0]       # worse global, better conditional
    second = cells[7]      # better global, worse conditional
    records = _qualifications({
        first["cell_id"]: (20, 12),
        second["cell_id"]: (48, 12),
    })
    selection = select_qualified_cell(_manifest(tmp_path, synthetic=False), records)
    assert selection["selected_cell_id"] == first["cell_id"]
    assert selection["comparison_trace"]["stable_tiebreak"][0] == first["cell_id"]


def test_m6_exact_equal_rates_use_stable_capacity_order(tmp_path):
    cells = registered_cells()
    first, second = cells[0], cells[1]
    records = _qualifications({first["cell_id"]: (40, 20), second["cell_id"]: (40, 20)})
    assert select_qualified_cell(
        _manifest(tmp_path, synthetic=False), records)["selected_cell_id"] == first["cell_id"]


@pytest.mark.parametrize(
    "fault",
    ["missing", "extra", "duplicate", "tampered_boolean", "tampered_cross_product",
     "authority_mismatch", "invalid_cell", "weighted_field"],
)
def test_m6_incomplete_or_tampered_domains_block_selection(tmp_path, fault):
    manifest = _manifest(tmp_path, synthetic=False)
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
    cell = dict(registered_cells()[0])
    windows = _no_stale_windows(cell, (0,))
    first = write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0,), windows=windows,
        synthetic_non_scientific=True)
    assert first["status"] == "COMMITTED"
    assert first["seal_reproduced"] is True
    second = write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0,), windows=windows,
        synthetic_non_scientific=True)
    assert second["status"] == "SKIPPED_VALID_SEALED"


def test_m7_incomplete_staging_is_quarantined_and_recomputed(tmp_path):
    manifest = _manifest(tmp_path)
    cell = dict(registered_cells()[0])
    staging = tmp_path / "cells" / ".{}.staging".format(cell["cell_id"])
    staging.mkdir(parents=True)
    (staging / "partial").write_text("incomplete", encoding="utf-8")
    result = write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0,), windows=_no_stale_windows(cell, (0,)),
        synthetic_non_scientific=True)
    assert result["status"] == "COMMITTED"
    assert list((tmp_path / "cells").glob("*.quarantine-incomplete-staging-*"))


def test_m7_final_without_terminal_is_quarantined(tmp_path):
    manifest = _manifest(tmp_path)
    cell = dict(registered_cells()[0])
    final = tmp_path / "cells" / cell["cell_id"]
    final.mkdir(parents=True)
    (final / "partial").write_text("incomplete", encoding="utf-8")
    result = write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0,), windows=_no_stale_windows(cell, (0,)),
        synthetic_non_scientific=True)
    assert result["status"] == "COMMITTED"
    assert list((tmp_path / "cells").glob("*.quarantine-missing-terminal-*"))


@pytest.mark.parametrize("fault", ["digest", "unexpected_file", "terminal"])
def test_m7_committed_cell_tamper_fails_closed(tmp_path, fault):
    manifest = _manifest(tmp_path)
    cell = dict(registered_cells()[0])
    write_cell_transaction(
        output_root=tmp_path, manifest=manifest, cell=cell,
        expected_frame_domain=(0,), windows=_no_stale_windows(cell, (0,)),
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
    cell = dict(registered_cells()[0])
    first_manifest = _manifest(tmp_path, "a")
    write_cell_transaction(
        output_root=tmp_path, manifest=first_manifest, cell=cell,
        expected_frame_domain=(0,), windows=_no_stale_windows(cell, (0,)),
        synthetic_non_scientific=True)
    with pytest.raises(C7BatchBPackageError, match="mismatched"):
        write_cell_transaction(
            output_root=tmp_path, manifest=_manifest(tmp_path, "f"), cell=cell,
            expected_frame_domain=(0,), windows=_no_stale_windows(cell, (0,)),
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
    _seal_all_synthetic_cells(tmp_path, manifest)
    result = write_selection_package(output_root=tmp_path, manifest=manifest)
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
    cell = dict(registered_cells()[0])
    with pytest.raises(C7BatchBError):
        write_cell_transaction(
            output_root=tmp_path, manifest=manifest, cell=cell,
            expected_frame_domain=(0,), windows=[],
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


def test_p1_bb_04_real_child_self_authorization_cannot_execute_wrapper(tmp_path):
    path = ROOT / "scripts/run_mdmt_mia_c7_real_child.py"
    spec = importlib.util.spec_from_file_location("c7_real_child", path)
    assert spec and spec.loader
    child = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(child)
    sentinel = tmp_path / "wrapper-executed"
    wrapper = tmp_path / "would_execute.sh"
    wrapper.write_text(
        "#!/bin/sh\nprintf executed > '{}'\n".format(sentinel), encoding="utf-8")
    wrapper.chmod(0o755)
    child_spec = {
        "authorities": __import__(
            "tracking.mdmt_mia_c7_batch_b_schema",
            fromlist=["authority_bindings"],
        ).authority_bindings(),
        "mode": "REAL_C7_CELL",
        "dry_run": False,
        "execution_authorized": True,
        "self_authorized": True,
        "output_root": str(tmp_path / "child-output"),
        "cell": dict(registered_cells()[0]),
        "author_wrapper_path": str(wrapper),
        "author_wrapper_sha256": __import__(
            "tracking.mdmt_mia_c7_batch_b_schema", fromlist=["sha256_file"]
        ).sha256_file(wrapper),
        "author_output_root": str(tmp_path / "author-output"),
        "generated_source_root": str(tmp_path / "generated-source"),
        "split": "train",
    }
    with pytest.raises(child.C7ChildError, match="MVE authorization path is required"):
        child.execute_child(child_spec)
    assert not sentinel.exists()


def test_p2_bb_01_registered_manifest_binds_observed_provenance(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    manifest = _build_registered_fixture_manifest(tmp_path, fixture)
    assert manifest["batch_b_implementation_sha"] == fixture["head"]
    assert manifest["repository_identity"] == {
        "mode": "REGISTERED_C7",
        "repo_root": str(fixture["repo_root"]),
        "git_head": fixture["head"],
        "worktree_clean": True,
    }
    for key, relative in REGISTERED_SOURCE_RELATIVE_PATHS.items():
        path = (fixture["repo_root"] / relative).resolve()
        assert manifest["source_paths"][key] == str(path)
        assert manifest["source_hashes"][key] == sha256_file(path)
    assert manifest["execution_paths"]["wrapper_path"] == str(fixture["wrapper_path"])
    assert manifest["execution_paths"]["wrapper_sha256"] == sha256_file(
        fixture["wrapper_path"])
    assert manifest["input_identity"]["files"][0]["path"] == str(fixture["input_path"])
    assert manifest["config_identity"]["files"][0]["path"] == str(fixture["config_path"])
    assert validate_manifest(manifest)["status"] == "PASS"


def test_p2_bb_01_registered_manifest_rejects_false_40_hex_head(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    with pytest.raises(C7BatchBPackageError, match="actual Git HEAD"):
        _build_registered_fixture_manifest(
            tmp_path, fixture, batch_b_implementation_sha="f" * 40)


def test_p2_bb_01_registered_manifest_rejects_dirty_worktree(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    dirty = fixture["repo_root"] / REGISTERED_SOURCE_RELATIVE_PATHS["runtime"]
    dirty.write_text(dirty.read_text(encoding="utf-8") + "dirty\n", encoding="utf-8")
    with pytest.raises(C7BatchBPackageError, match="clean worktree"):
        _build_registered_fixture_manifest(tmp_path, fixture)


def test_p2_bb_01_registered_manifest_rejects_wrapper_hash_mismatch(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    claimed = {
        key: sha256_file(fixture["repo_root"] / relative)
        for key, relative in REGISTERED_SOURCE_RELATIVE_PATHS.items()
    }
    claimed["wrapper"] = "0" * 64
    with pytest.raises(C7BatchBPackageError, match="actual files"):
        _build_registered_fixture_manifest(tmp_path, fixture, source_hashes=claimed)


@pytest.mark.parametrize("identity_name", ["input_identity", "config_identity"])
def test_p2_bb_01_registered_manifest_rejects_input_config_digest_mismatch(
    tmp_path, identity_name,
):
    fixture = _registered_provenance_fixture(tmp_path)
    corrupted = copy.deepcopy(fixture[identity_name])
    corrupted["files"][0]["sha256"] = "0" * 64
    with pytest.raises(C7BatchBPackageError, match="digest mismatch"):
        _build_registered_fixture_manifest(
            tmp_path, fixture, **{identity_name: corrupted})


@pytest.mark.parametrize("target", ["source", "wrapper", "input", "config"])
def test_p2_bb_01_validator_rejects_observed_provenance_tamper(tmp_path, target):
    fixture = _registered_provenance_fixture(tmp_path)
    manifest = _build_registered_fixture_manifest(tmp_path, fixture)
    paths = {
        "source": fixture["repo_root"] / REGISTERED_SOURCE_RELATIVE_PATHS["runtime"],
        "wrapper": fixture["wrapper_path"],
        "input": fixture["input_path"],
        "config": fixture["config_path"],
    }
    path = paths[target]
    path.write_text(path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(C7BatchBValidationError, match="digest"):
        validate_manifest(manifest)


def test_p2_bb_01_synthetic_placeholder_cannot_validate_as_registered(tmp_path):
    manifest = _manifest(tmp_path, synthetic=True)
    manifest["synthetic_non_scientific"] = False
    manifest["transaction_domain_kind"] = "REGISTERED_C7"
    with pytest.raises(C7BatchBValidationError):
        validate_manifest(manifest)


def test_p2_bb_02_unknown_parent_environment_excluded_at_subprocess_boundary(tmp_path):
    launcher_path = ROOT / "scripts/run_mdmt_mia_c7_outcome_blind_census.py"
    spec = importlib.util.spec_from_file_location("c7_launcher_environment", launcher_path)
    assert spec and spec.loader
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    windows_path = tmp_path / "empty_windows.jsonl"
    atomic_write_jsonl(windows_path, [])
    output_root = tmp_path / "child-environment"
    child_spec = {
        "authorities": __import__(
            "tracking.mdmt_mia_c7_batch_b_schema",
            fromlist=["authority_bindings"],
        ).authority_bindings(),
        "mode": "SYNTHETIC_NON_SCIENTIFIC",
        "synthetic_non_scientific": True,
        "window_source": str(windows_path),
        "output_root": str(output_root),
    }
    spec_path = tmp_path / "environment_child_spec.json"
    atomic_write_json(spec_path, child_spec)
    sentinels = {
        "UNRELATED_PARENT_SENTINEL": "absent-a",
        "TRACKING_RESULT_PATH_SENTINEL": "absent-b",
        "OLD_EXPERIMENT_ARTIFACT_SENTINEL": "absent-c",
        "ARBITRARY_PARENT_STATE_SENTINEL": "absent-d",
        "MIA_HISTORICAL_SENTINEL": "absent-mia",
        "MDMT_MIA_C6_HISTORICAL_SENTINEL": "absent-c6",
    }
    parent = {
        "PATH": "/synthetic/allowlisted/runtime/bin",
        "LANG": "C.UTF-8",
        "PYTHONPATH": "/parent/must/not/win",
        "PYTHONHASHSEED": "999",
        "MDMT_MIA_C7_CHILD_BOUNDARY": "parent-must-not-win",
        **sentinels,
    }
    child_environment = launcher.controlled_environment(parent)
    assert set(child_environment) == {
        "PATH", "LANG", "PYTHONNOUSERSITE", "PYTHONHASHSEED", "PYTHONPATH",
        "MDMT_MIA_C7_CHILD_BOUNDARY",
    }
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_mdmt_mia_c7_real_child.py"),
         "--spec", str(spec_path)],
        cwd=ROOT, env=child_environment, check=False)
    assert completed.returncode == 0
    status = json.loads((output_root / "CHILD_STATUS.json").read_text(encoding="utf-8"))
    observed_keys = set(status["environment_keys"])
    assert observed_keys.isdisjoint(sentinels)
    assert observed_keys <= set(ALLOWED_PARENT_ENV_KEYS) | {
        "PYTHONNOUSERSITE", "PYTHONHASHSEED", "PYTHONPATH",
        "MDMT_MIA_C7_CHILD_BOUNDARY",
    }
    assert status["allowed_parent_environment"]["PATH"] == parent["PATH"]
    assert status["allowed_parent_environment"]["LANG"] == parent["LANG"]
    assert status["bound_environment"] == {
        "PYTHONNOUSERSITE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONPATH": str(ROOT / "src"),
        "MDMT_MIA_C7_CHILD_BOUNDARY": "1",
    }


def _write_registered_input(path: Path, **fields) -> None:
    payload = {"schema_version": REGISTERED_C7_INPUT_CLASS_ID, **fields}
    atomic_write_json(path, payload)


def _write_registered_config(path: Path, **fields) -> None:
    payload = {"schema_version": REGISTERED_C7_CONFIG_CLASS_ID, **fields}
    atomic_write_json(path, payload)


def _registered_file_identity(path: Path, kind: str) -> dict[str, Any]:
    return {"kind": kind, "files": [{"path": str(path), "sha256": sha256_file(path)}]}


def test_p2_final_01_valid_registered_communication_input_and_config_pass(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    manifest = _build_registered_fixture_manifest(tmp_path, fixture)
    assert manifest["input_identity"]["files"][0]["path"] == str(fixture["input_path"])
    assert manifest["config_identity"]["files"][0]["path"] == str(fixture["config_path"])
    assert validate_manifest(manifest)["status"] == "PASS"


def test_p2_final_01_registered_input_rejects_outcome_key_with_correct_digest(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    contaminated = tmp_path / "contaminated_input.json"
    contaminated.write_text(json.dumps({
        "schema_version": REGISTERED_C7_INPUT_CLASS_ID,
        "idf1": 0.91,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity = _registered_file_identity(contaminated, REGISTERED_C7_INPUT_FILES_KIND)
    with pytest.raises(C7BatchBPackageError, match="communication-only"):
        _build_registered_fixture_manifest(tmp_path, fixture, input_identity=identity)


def test_p2_final_01_registered_config_rejects_outcome_key_with_correct_digest(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    contaminated = tmp_path / "contaminated_config.json"
    contaminated.write_text(json.dumps({
        "schema_version": REGISTERED_C7_CONFIG_CLASS_ID,
        "idsw": 7,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity = _registered_file_identity(contaminated, REGISTERED_C7_CONFIG_FILES_KIND)
    with pytest.raises(C7BatchBPackageError, match="communication-only"):
        _build_registered_fixture_manifest(tmp_path, fixture, config_identity=identity)


def test_p2_final_01_registered_input_rejects_outcome_value_with_correct_digest(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    contaminated = tmp_path / "contaminated_input.json"
    contaminated.write_text(json.dumps({
        "schema_version": REGISTERED_C7_INPUT_CLASS_ID,
        "split": "tracking_result/IDF1=0.91",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity = _registered_file_identity(contaminated, REGISTERED_C7_INPUT_FILES_KIND)
    with pytest.raises(C7BatchBPackageError, match="forbidden outcome"):
        _build_registered_fixture_manifest(tmp_path, fixture, input_identity=identity)


def test_p2_final_01_registered_config_rejects_outcome_value_with_correct_digest(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    contaminated = tmp_path / "contaminated_config.json"
    contaminated.write_text(json.dumps({
        "schema_version": REGISTERED_C7_CONFIG_CLASS_ID,
        "device": "tracking_result/IDF1=0.91",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity = _registered_file_identity(contaminated, REGISTERED_C7_CONFIG_FILES_KIND)
    with pytest.raises(C7BatchBPackageError, match="forbidden outcome"):
        _build_registered_fixture_manifest(tmp_path, fixture, config_identity=identity)


def test_p2_final_01_registered_config_rejects_outcome_path_with_correct_digest(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    contaminated = tmp_path / "contaminated_config.json"
    contaminated.write_text(json.dumps({
        "schema_version": REGISTERED_C7_CONFIG_CLASS_ID,
        "mia_config_path": "/path/to/tracking_results/config.py",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity = _registered_file_identity(contaminated, REGISTERED_C7_CONFIG_FILES_KIND)
    with pytest.raises(C7BatchBPackageError, match="forbidden outcome"):
        _build_registered_fixture_manifest(tmp_path, fixture, config_identity=identity)


def test_p2_final_01_registered_input_rejects_outcome_path_with_correct_digest(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    contaminated = tmp_path / "contaminated_input.json"
    contaminated.write_text(json.dumps({
        "schema_version": REGISTERED_C7_INPUT_CLASS_ID,
        "run_input_root": "/path/to/tracking_results/run_inputs",
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity = _registered_file_identity(contaminated, REGISTERED_C7_INPUT_FILES_KIND)
    with pytest.raises(C7BatchBPackageError, match="forbidden outcome"):
        _build_registered_fixture_manifest(tmp_path, fixture, input_identity=identity)


def test_p2_final_01_innocuous_filename_with_outcome_content_rejected(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    innocuous = tmp_path / "input.json"
    innocuous.write_text(json.dumps({
        "schema_version": REGISTERED_C7_INPUT_CLASS_ID,
        "tracking_outcome": {"idf1": 0.91},
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    identity = _registered_file_identity(innocuous, REGISTERED_C7_INPUT_FILES_KIND)
    with pytest.raises(C7BatchBPackageError, match="communication-only"):
        _build_registered_fixture_manifest(tmp_path, fixture, input_identity=identity)


def test_p2_final_01_validator_rejects_forged_registered_outcome_content_with_correct_digest(
    tmp_path,
):
    fixture = _registered_provenance_fixture(tmp_path)
    manifest = _build_registered_fixture_manifest(tmp_path, fixture)
    # Simulate a forged manifest that records the correct SHA-256 of an
    # outcome-contaminated file. The validator must reject based on actual
    # content, not trust the manifest digest.
    contaminated = tmp_path / "forged_input.json"
    contaminated.write_text(json.dumps({
        "schema_version": REGISTERED_C7_INPUT_CLASS_ID,
        "mota": 0.85,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    forged_identity = {
        "kind": REGISTERED_C7_INPUT_FILES_KIND,
        "files": [{"path": str(contaminated), "sha256": sha256_file(contaminated)}],
        "digest": canonical_sha256([
            {"path": str(contaminated), "sha256": sha256_file(contaminated)}]),
    }
    manifest["input_identity"] = forged_identity
    with pytest.raises(C7BatchBValidationError, match="communication-only"):
        validate_manifest(manifest)


def test_p2_final_01_mutation_after_manifest_rejects_registered_input(tmp_path):
    fixture = _registered_provenance_fixture(tmp_path)
    manifest = _build_registered_fixture_manifest(tmp_path, fixture)
    fixture["input_path"].write_text(json.dumps({
        "schema_version": REGISTERED_C7_INPUT_CLASS_ID,
        "hota": 0.7,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(C7BatchBValidationError, match="digest"):
        validate_manifest(manifest)


def test_synthetic_tiny_e2e_uses_child_disk_validator_writer_and_selector(tmp_path):
    batch_a = _batch_a_test_module()
    _, _, evidence = batch_a._case_a()
    evidence_path = tmp_path / "batch_a_evidence.json"
    atomic_write_json(evidence_path, evidence)
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
    cell = manifest["cells"][0]
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
    window_sources = {cell["cell_id"]: tmp_path / "window_source.jsonl"}
    raw_no_stale = _raw_observer_evidence(frame=0, stale=False)
    for other in manifest["cells"][1:]:
        path = tmp_path / "window_source_{}.jsonl".format(other["cell_id"])
        atomic_write_jsonl(path, [make_validated_no_stale_window_record(
            run_id="synthetic-run", cell=other, frame_index=0,
            raw_observation_evidence=raw_no_stale)])
        window_sources[other["cell_id"]] = path
    result = launcher.execute_synthetic_launch(
        output_root=output_root, manifest=manifest, window_sources=window_sources)
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
        expected_manifest=manifest)["status"] == "PASS"
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


def _mve_test_resources(tmp_path: Path) -> dict[str, Any]:
    """Create fake but structurally valid MVE execution resources."""
    resources_root = tmp_path / "mve_resources"
    resources_root.mkdir()

    mdmt_root = resources_root / "mdmt"
    mdmt_root.mkdir()
    (mdmt_root / "train").mkdir()
    (mdmt_root / "train" / "1").mkdir()
    (mdmt_root / "train" / "2").mkdir()
    (mdmt_root / "new_xml" / "1").mkdir(parents=True)
    (mdmt_root / "new_xml" / "2").mkdir(parents=True)
    (mdmt_root / "checkpoints" / "work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt").mkdir(parents=True)

    seq1 = mdmt_root / "train" / "1" / "23-1"
    seq1.mkdir()
    seq2 = mdmt_root / "train" / "2" / "23-2"
    seq2.mkdir()

    xml1 = mdmt_root / "new_xml" / "1" / "23-1.xml"
    xml1.write_text("<xml>view1</xml>", encoding="utf-8")
    xml2 = mdmt_root / "new_xml" / "2" / "23-2.xml"
    xml2.write_text("<xml>view2</xml>", encoding="utf-8")

    checkpoint = mdmt_root / "checkpoints" / "work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt" / "epoch_12.pth"
    checkpoint.write_bytes(b"FAKE_CHECKPOINT_BYTES")

    config = resources_root / "mia_config.py"
    config.write_text(
        "model = dict(init_cfg=dict(type='Pretrained', checkpoint={!r}))\n".format(
            str(checkpoint)),
        encoding="utf-8",
    )

    mia_root = resources_root / "mia"
    mia_root.mkdir()
    upstream = mia_root / "upstream"
    upstream.mkdir()
    generated_source_base = mia_root / "variants" / "packetized_active_sync"
    (generated_source_base / "demo").mkdir(parents=True)
    (generated_source_base / "demo" / "supplement_MIA.py").write_text(
        "from utils.active_packet_runtime import PacketRuntime\n",
        encoding="utf-8",
    )

    # These roots are created by the wrapper/child at runtime; pre-create them
    # so structural validation passes without executing the wrapper.
    (tmp_path / "run_inputs").mkdir()
    (tmp_path / "author_outputs").mkdir()

    return {
        "mdmt_root": str(mdmt_root),
        "mia_root": str(mia_root),
        "mia_source_root": str(tmp_path / "generated_source"),
        "mia_config_path": str(config),
        "mia_config_sha256": sha256_file(config),
        "mia_run_input_root": str(tmp_path / "run_inputs"),
        "mia_output_root": str(tmp_path / "author_outputs"),
        "device": "cpu",
        "checkpoint_path": str(checkpoint),
        "checkpoint_sha256": sha256_file(checkpoint),
        "sequence_resources": [
            {
                "role": "view1_sequence",
                "canonical_path": str(seq1),
                "resource_class": EXECUTION_RESOURCE_CLASS_DIRECTORY,
            },
            {
                "role": "view2_sequence",
                "canonical_path": str(seq2),
                "resource_class": EXECUTION_RESOURCE_CLASS_DIRECTORY,
            },
        ],
        "xml_resources": [
            {
                "role": "view1_xml",
                "canonical_path": str(xml1),
                "sha256": sha256_file(xml1),
                "resource_class": EXECUTION_RESOURCE_CLASS_FILE,
            },
            {
                "role": "view2_xml",
                "canonical_path": str(xml2),
                "sha256": sha256_file(xml2),
                "resource_class": EXECUTION_RESOURCE_CLASS_FILE,
            },
        ],
    }


def _mve_authorization(
    tmp_path: Path,
    *,
    harness_head: str,
    resources: dict[str, Any] | None = None,
    mutations: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Build a valid MVE authorization file; mutations override fields."""
    if resources is None:
        resources = _mve_test_resources(tmp_path)
    if mutations is not None:
        resources = {**resources, **mutations}

    wrapper_path = ROOT / "scripts/run_mdmt_mia_author_sync.sh"
    preparer_path = ROOT / "scripts/prepare_mdmt_mia_async_packet_variant.py"

    authorization = {
        "schema_version": MVE_AUTHORIZATION_SCHEMA,
        "authorization_role": MVE_AUTHORIZATION_ROLE,
        "status": MVE_AUTHORIZATION_STATUS_AUTHORIZED,
        "scientific_core_authority": "9140104ca2bf3d395b3012dcae32506e5abfb9cf",
        "execution_harness_authority": harness_head,
        "mve_run_id": "exp_20260923_001_p23_p20",
        "mve_cell_id": "P23__P20",
        "pair_id": "P23",
        "capacity_id": "P20",
        "split": "train",
        "execution_scope": "ONE_NATIVE_P23_PRODUCTION_UNIT",
        "output_root": str(tmp_path / "mve_output"),
        "execution_resources": resources,
        "wrapper_identity": {
            "canonical_path": str(wrapper_path),
            "sha256": sha256_file(wrapper_path),
        },
        "generated_source_preparer_identity": {
            "canonical_path": str(preparer_path),
            "sha256": sha256_file(preparer_path),
        },
        "outcome_blind_policy": "NO_TRACKING_OUTCOME_READ",
        "single_run_scope": True,
    }
    auth_path = tmp_path / "MVE_AUTHORIZATION.json"
    atomic_write_json(auth_path, authorization)
    return auth_path, authorization


def _mve_cell() -> dict[str, Any]:
    return {
        "cell_id": "P23__P20",
        "pair_id": "P23",
        "frame_count": 700,
        "capacity_id": "P20",
        "capacity_bytes": 16649,
        "stable_pair_order": 0,
        "stable_capacity_order": 0,
    }


def _mve_spec(tmp_path: Path, auth_path: Path, harness_head: str, **overrides) -> dict[str, Any]:
    spec = {
        "schema_version": "C7_CHILD_SPEC_V1",
        "mode": "REAL_C7_CELL",
        "dry_run": False,
        "authorities": authority_bindings(),
        "run_id": "exp_20260923_001_p23_p20",
        "cell": _mve_cell(),
        "split": "train",
        "output_root": str(tmp_path / "mve_output"),
        "mve_authorization_path": str(auth_path),
    }
    spec.update(overrides)
    return spec


def _mock_subprocess_for_mve(
    monkeypatch, tmp_path: Path, *, wrapper_returncode: int = 0,
    mutate_generated: bool = False, mutate_config: bool = False,
    observed: dict[str, Any] | None = None,
):
    """Mock subprocess.run for MVE tests: preparer and wrapper only."""
    original_run = subprocess.run
    _mock_git_identity(monkeypatch)

    def _command_has(command: list[str], substring: str) -> bool:
        return any(substring in arg for arg in command)

    def _fake_run(args, **kwargs):
        command = [str(a) for a in args]

        # generated-source preparer
        if _command_has(command, "prepare_mdmt_mia_async_packet_variant.py"):
            if observed is not None:
                observed["preparer_command"] = command
            variant_root = None
            for index, arg in enumerate(command):
                if arg == "--variant-root" and index + 1 < len(command):
                    variant_root = Path(command[index + 1])
                    break
            if variant_root is not None:
                variant_root.mkdir(parents=True, exist_ok=True)
                (variant_root / "demo").mkdir()
                (variant_root / "demo" / "supplement_MIA.py").write_text("# generated\n")
                (variant_root / "async_deadline_manifest.json").write_text("{}\n")
            if mutate_config:
                config = tmp_path / "mve_resources" / "mia_config.py"
                config.write_text(config.read_text(encoding="utf-8") + "# changed\n")
            class _Result:
                stdout = ""
                stderr = ""
                returncode = 0
            return _Result()

        # wrapper
        if _command_has(command, "run_mdmt_mia_author_sync.sh"):
            env = kwargs.get("env", {})
            if observed is not None:
                observed["wrapper_environment"] = dict(env)
            # Verify explicit environment binding.
            assert env.get("MDMT_ROOT")
            assert env.get("MIA_ROOT")
            assert env.get("MIA_SOURCE_ROOT")
            assert env.get("MIA_CONFIG")
            assert env.get("MIA_RUN_INPUT_ROOT")
            assert env.get("MIA_OUTPUT_ROOT")
            assert env.get("DEVICE")

            if mutate_generated:
                source_root = env.get("MIA_SOURCE_ROOT")
                if source_root:
                    (Path(source_root) / "demo" / "supplement_MIA.py").write_text("# mutated\n")

            class _Result:
                stdout = "[author-sync] complete"
                stderr = ""
                returncode = wrapper_returncode
            return _Result()

        return original_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _fake_run)


def _mock_git_identity(
    monkeypatch, *, head: str = "MOCK_HARNESS_HEAD", clean: bool = True,
) -> None:
    monkeypatch.setattr(
        CHILD,
        "_observe_git_identity",
        lambda expected_root: {
            "repo_root": str(Path(expected_root).resolve()),
            "head": head,
            "worktree_clean": clean,
        },
    )


def test_mve_observes_actual_repo_root_head_and_porcelain_status(tmp_path, monkeypatch):
    calls = []
    responses = {
        ("rev-parse", "--show-toplevel"): str(tmp_path),
        ("rev-parse", "HEAD"): "OBSERVED_HEAD",
        ("status", "--porcelain", "--untracked-files=all"): "",
    }

    def _fake_run_git(*args, **kwargs):
        calls.append((args, kwargs))
        return responses[args]

    monkeypatch.setattr(CHILD, "_run_git", _fake_run_git)
    observed = CHILD._observe_git_identity(tmp_path)
    assert observed == {
        "repo_root": str(tmp_path.resolve()),
        "head": "OBSERVED_HEAD",
        "worktree_clean": True,
    }
    assert [args for args, _ in calls] == [
        ("rev-parse", "--show-toplevel"),
        ("rev-parse", "HEAD"),
        ("status", "--porcelain", "--untracked-files=all"),
    ]


def test_mve_uses_qualified_generated_source_base_only(tmp_path, monkeypatch):
    observed = {}
    _mock_subprocess_for_mve(monkeypatch, tmp_path, observed=observed)
    auth_path, authorization = _mve_authorization(
        tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")

    CHILD.execute_child(spec)

    resources = authorization["execution_resources"]
    mia_root = Path(resources["mia_root"]).resolve()
    command = observed["preparer_command"]
    source_root = Path(command[command.index("--source-root") + 1])
    variant_root = Path(command[command.index("--variant-root") + 1])
    assert source_root == mia_root / "variants" / "packetized_active_sync"
    assert source_root != mia_root / "upstream"
    assert variant_root == Path(resources["mia_source_root"])
    assert observed["wrapper_environment"]["MIA_ROOT"] == str(mia_root)
    assert observed["wrapper_environment"]["MIA_SOURCE_ROOT"] == str(
        Path(resources["mia_source_root"]).resolve())


def test_mve_missing_generated_source_base_rejects_before_preparer(
    tmp_path, monkeypatch,
):
    resources = _mve_test_resources(tmp_path)
    base_root = (
        Path(resources["mia_root"]) / "variants" / "packetized_active_sync")
    (base_root / "demo" / "supplement_MIA.py").unlink()
    (base_root / "demo").rmdir()
    base_root.rmdir()
    auth_path, _ = _mve_authorization(
        tmp_path, harness_head="MOCK_HARNESS_HEAD", resources=resources)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    _mock_git_identity(monkeypatch)

    def _must_not_run(*args, **kwargs):
        raise AssertionError("preparer reached with missing generated-source base")

    monkeypatch.setattr(subprocess, "run", _must_not_run)
    with pytest.raises(CHILD.C7ChildError, match="base root does not exist"):
        CHILD.execute_child(spec)


def test_mve_missing_generated_source_base_entry_rejects_before_preparer(
    tmp_path, monkeypatch,
):
    resources = _mve_test_resources(tmp_path)
    base_entry = (
        Path(resources["mia_root"])
        / "variants" / "packetized_active_sync" / "demo" / "supplement_MIA.py"
    )
    base_entry.unlink()
    auth_path, _ = _mve_authorization(
        tmp_path, harness_head="MOCK_HARNESS_HEAD", resources=resources)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    _mock_git_identity(monkeypatch)

    def _must_not_run(*args, **kwargs):
        raise AssertionError("preparer reached with missing generated-source base entry")

    monkeypatch.setattr(subprocess, "run", _must_not_run)
    with pytest.raises(CHILD.C7ChildError, match="base entry does not exist"):
        CHILD.execute_child(spec)


def test_mve_non_dry_without_authorization_rejects(tmp_path):
    spec = {
        "schema_version": "C7_CHILD_SPEC_V1",
        "mode": "REAL_C7_CELL",
        "dry_run": False,
        "authorities": authority_bindings(),
        "run_id": "exp_20260923_001_p23_p20",
        "cell": _mve_cell(),
        "output_root": str(tmp_path / "out"),
    }
    with pytest.raises(CHILD.C7ChildError, match="authorization"):
        CHILD.execute_child(spec)


def test_mve_wrong_authorization_role_rejects(tmp_path, monkeypatch):
    _mock_git_identity(monkeypatch)
    auth_path, authorization = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    authorization["authorization_role"] = "BAD_ROLE"
    atomic_write_json(auth_path, authorization)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="role"):
        CHILD.execute_child(spec)


def test_mve_wrong_run_id_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD", run_id="wrong-run")
    with pytest.raises(CHILD.C7ChildError, match="run_id"):
        CHILD.execute_child(spec)


def test_mve_wrong_cell_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    cell = _mve_cell()
    cell["cell_id"] = "P44__P20"
    cell["pair_id"] = "P44"
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD", cell=cell)
    with pytest.raises(CHILD.C7ChildError, match="cell_id"):
        CHILD.execute_child(spec)


def test_mve_wrong_capacity_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    cell = _mve_cell()
    cell["capacity_id"] = "P30"
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD", cell=cell)
    with pytest.raises(CHILD.C7ChildError, match="capacity_id"):
        CHILD.execute_child(spec)


def test_mve_wrong_capacity_bytes_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    cell = _mve_cell()
    cell["capacity_bytes"] = 29620
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD", cell=cell)
    with pytest.raises(CHILD.C7ChildError, match="capacity_bytes"):
        CHILD.execute_child(spec)


@pytest.mark.parametrize("field", ["stable_pair_order", "stable_capacity_order", "frame_count"])
def test_mve_canonical_registered_cell_field_mismatch_rejects(
    tmp_path, monkeypatch, field,
):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    cell = _mve_cell()
    cell[field] += 1
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD", cell=cell)
    with pytest.raises(CHILD.C7ChildError, match=field):
        CHILD.execute_child(spec)


def test_mve_wrong_output_root_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD", output_root=str(tmp_path / "other"))
    with pytest.raises(CHILD.C7ChildError, match="output_root"):
        CHILD.execute_child(spec)


def test_mve_wrong_implementation_head_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="EXPECTED_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "ACTUAL_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="execution_harness_authority"):
        CHILD.execute_child(spec)


def test_mve_caller_supplied_fake_head_cannot_override_observed_head(tmp_path, monkeypatch):
    _mock_git_identity(monkeypatch, head="OBSERVED_HEAD")
    auth_path, _ = _mve_authorization(tmp_path, harness_head="OBSERVED_HEAD")
    spec = _mve_spec(
        tmp_path,
        auth_path,
        "IGNORED",
        execution_harness_head="CALLER_FORGED_HEAD",
    )
    with pytest.raises(CHILD.C7ChildError, match="caller execution_harness_head is forbidden"):
        CHILD.execute_child(spec)


def test_mve_dirty_actual_worktree_rejects_before_materialization(tmp_path, monkeypatch):
    _mock_git_identity(monkeypatch, clean=False)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")

    def _must_not_run(*args, **kwargs):
        raise AssertionError("subprocess boundary reached after dirty-worktree rejection")

    monkeypatch.setattr(subprocess, "run", _must_not_run)
    with pytest.raises(CHILD.C7ChildError, match="worktree must be clean"):
        CHILD.execute_child(spec)
    assert not (tmp_path / "generated_source").exists()


def test_mve_wrong_scientific_core_authority_rejects(tmp_path, monkeypatch):
    _mock_git_identity(monkeypatch)
    auth_path, authorization = _mve_authorization(
        tmp_path, harness_head="MOCK_HARNESS_HEAD")
    authorization["scientific_core_authority"] = "0" * 40
    atomic_write_json(auth_path, authorization)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="scientific_core_authority"):
        CHILD.execute_child(spec)


def test_mve_split_mismatch_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD", split="val")
    with pytest.raises(CHILD.C7ChildError, match="split"):
        CHILD.execute_child(spec)


def test_mve_unsupported_execution_scope_rejects(tmp_path, monkeypatch):
    _mock_git_identity(monkeypatch)
    auth_path, authorization = _mve_authorization(
        tmp_path, harness_head="MOCK_HARNESS_HEAD")
    authorization["execution_scope"] = "ANOTHER_MODE"
    atomic_write_json(auth_path, authorization)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="execution_scope"):
        CHILD.execute_child(spec)


def test_mve_wrong_wrapper_digest_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, authorization = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    authorization["wrapper_identity"]["sha256"] = "0" * 64
    atomic_write_json(auth_path, authorization)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="wrapper digest"):
        CHILD.execute_child(spec)


def test_mve_wrong_config_digest_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    resources = _mve_test_resources(tmp_path)
    resources["mia_config_sha256"] = "0" * 64
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD", resources=resources)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="digest mismatch"):
        CHILD.execute_child(spec)


def test_mve_config_changed_after_gate_before_launch_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path, mutate_config=True)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="launch resource validation.*digest"):
        CHILD.execute_child(spec)


def test_mve_wrong_checkpoint_digest_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    resources = _mve_test_resources(tmp_path)
    resources["checkpoint_sha256"] = "0" * 64
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD", resources=resources)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="digest mismatch"):
        CHILD.execute_child(spec)


def test_mve_native_p23_sequence_resource_mismatch_rejects(tmp_path, monkeypatch):
    _mock_git_identity(monkeypatch)
    resources = _mve_test_resources(tmp_path)
    wrong_sequence = Path(resources["mdmt_root"]) / "train" / "1" / "99-1"
    wrong_sequence.mkdir()
    resources["sequence_resources"][0]["canonical_path"] = str(wrong_sequence)
    auth_path, _ = _mve_authorization(
        tmp_path, harness_head="MOCK_HARNESS_HEAD", resources=resources)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="native pair input"):
        CHILD.execute_child(spec)


def test_mve_preexisting_effective_run_input_rejects(tmp_path, monkeypatch):
    _mock_git_identity(monkeypatch)
    resources = _mve_test_resources(tmp_path)
    stale_slot = Path(resources["mia_run_input_root"]) / "23" / "train"
    stale_slot.mkdir(parents=True)
    (stale_slot / "unexpected-input").write_text("wrong\n", encoding="utf-8")
    auth_path, _ = _mve_authorization(
        tmp_path, harness_head="MOCK_HARNESS_HEAD", resources=resources)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="run-input slot"):
        CHILD.execute_child(spec)


def test_mve_xml_digest_mismatch_rejects(tmp_path, monkeypatch):
    _mock_git_identity(monkeypatch)
    resources = _mve_test_resources(tmp_path)
    resources["xml_resources"][0]["sha256"] = "0" * 64
    auth_path, _ = _mve_authorization(
        tmp_path, harness_head="MOCK_HARNESS_HEAD", resources=resources)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="XML.*digest mismatch|digest mismatch"):
        CHILD.execute_child(spec)


def test_mve_hidden_execution_resource_mismatch_rejects(tmp_path, monkeypatch):
    """If authorization config path differs from what wrapper would default to, fail closed."""
    original_run = subprocess.run
    captured = []

    def _wrapper_capturing_run(args, **kwargs):
        command = [str(a) for a in args]
        if any("run_mdmt_mia_author_sync.sh" in arg for arg in command):
            captured.append(kwargs.get("env", {}))
            class _Result:
                stdout = ""
                stderr = ""
                returncode = 0
            return _Result()
        if any("prepare_mdmt_mia_async_packet_variant.py" in arg for arg in command):
            for index, arg in enumerate(command):
                if arg == "--variant-root" and index + 1 < len(command):
                    variant_root = Path(command[index + 1])
                    variant_root.mkdir(parents=True, exist_ok=True)
                    (variant_root / "demo").mkdir()
                    (variant_root / "demo" / "supplement_MIA.py").write_text("# generated\n")
                    (variant_root / "async_deadline_manifest.json").write_text("{}\n")
                    break
            class _Result:
                stdout = ""
                stderr = ""
                returncode = 0
            return _Result()
        return original_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _wrapper_capturing_run)
    _mock_git_identity(monkeypatch)
    resources = _mve_test_resources(tmp_path)
    other_config = tmp_path / "other_config.py"
    other_config.write_text(
        "model = dict(init_cfg=dict(checkpoint={!r}))\n".format(
            resources["checkpoint_path"]),
        encoding="utf-8",
    )
    resources["mia_config_path"] = str(other_config)
    resources["mia_config_sha256"] = sha256_file(other_config)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD", resources=resources)
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    CHILD.execute_child(spec)
    assert captured
    assert captured[0]["MIA_CONFIG"] == str(other_config)


def test_mve_unknown_parent_env_sentinel_not_forwarded(tmp_path, monkeypatch):
    original_run = subprocess.run
    captured = []

    def _wrapper_capturing_run(args, **kwargs):
        command = [str(a) for a in args]
        if any("run_mdmt_mia_author_sync.sh" in arg for arg in command):
            captured.append(kwargs.get("env", {}))
            class _Result:
                stdout = ""
                stderr = ""
                returncode = 0
            return _Result()
        if any("prepare_mdmt_mia_async_packet_variant.py" in arg for arg in command):
            for index, arg in enumerate(command):
                if arg == "--variant-root" and index + 1 < len(command):
                    variant_root = Path(command[index + 1])
                    variant_root.mkdir(parents=True, exist_ok=True)
                    (variant_root / "demo").mkdir()
                    (variant_root / "demo" / "supplement_MIA.py").write_text("# generated\n")
                    (variant_root / "async_deadline_manifest.json").write_text("{}\n")
                    break
            class _Result:
                stdout = ""
                stderr = ""
                returncode = 0
            return _Result()
        return original_run(args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _wrapper_capturing_run)
    _mock_git_identity(monkeypatch)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    monkeypatch.setenv("C7_MVE_FORBIDDEN_PARENT_SENTINEL", "DO_NOT_FORWARD")
    CHILD.execute_child(spec)
    assert captured
    assert captured[0]["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "C7_MVE_FORBIDDEN_PARENT_SENTINEL" not in captured[0]
    status_path = Path(spec["output_root"]) / "CHILD_STATUS.json"

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert "C7_MVE_FORBIDDEN_PARENT_SENTINEL" not in status["allowed_parent_environment"]
    assert "C7_MVE_FORBIDDEN_PARENT_SENTINEL" not in status["bound_environment"]

def test_real_c7_evidence_mode_rejects_successful_wrapper_without_observer_run(
    tmp_path, monkeypatch,
):
    observed = {}
    _mock_subprocess_for_mve(monkeypatch, tmp_path, observed=observed)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(
        tmp_path, auth_path, "MOCK_HARNESS_HEAD", mode="REAL_C7_EVIDENCE_CELL")
    with pytest.raises(CHILD.C7ChildError, match="observer evidence is absent or invalid"):
        CHILD.execute_child(spec)
    assert "--c7-evidence" in observed["preparer_command"]
    service = json.loads(observed["wrapper_environment"]["MIA_C7_SERVICE_CONFIG"])
    assert service["capacity_id"] == "P20"
    assert service["rate_logical_bytes_per_frame"] == 16649
    assert service["mode"] == "fifo"
    assert not (Path(spec["output_root"]) / "windows.jsonl").exists()
    assert not (Path(spec["output_root"]) / "CHILD_STATUS.json").exists()


def test_mve_valid_authorization_gate_opens_to_wrapper_boundary(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    status = CHILD.execute_child(spec)
    assert status["status"] == "EXECUTED"
    assert status["real_input_executed"] is True
    assert status["authorization_valid"] is True
    assert status["generated_source_materialized"] is True
    assert status["generated_source_inventory_stable"] is True
    assert status["wrapper_returncode"] == 0
    assert "outcome_quarantine_paths" in status


def test_mve_generated_source_inventory_is_deterministic(tmp_path):
    root = tmp_path / "generated"
    root.mkdir()
    (root / "a.py").write_text("a\n")
    (root / "b").mkdir()
    (root / "b" / "c.py").write_text("c\n")
    inv1 = inventory_generated_source(root)
    inv2 = inventory_generated_source(root)
    assert inv1["inventory_sha256"] == inv2["inventory_sha256"]
    assert inv1["file_count"] == 2


def test_mve_generated_source_mutation_after_inventory_rejects(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path, mutate_generated=True)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="inventory changed"):
        CHILD.execute_child(spec)


def test_mve_wrapper_failure_reports_engineering_status(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path, wrapper_returncode=1)
    auth_path, _ = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    with pytest.raises(CHILD.C7ChildError, match="wrapper execution failed"):
        CHILD.execute_child(spec)
    status_path = Path(spec["output_root"]) / "CHILD_STATUS.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["status"] == "WRAPPER_FAILED"
    assert status["wrapper_returncode"] == 1
    assert "N_stale" not in json.dumps(status)
    assert "N_eligible" not in json.dumps(status)


def test_mve_status_does_not_read_outcome_quarantine(tmp_path, monkeypatch):
    _mock_subprocess_for_mve(monkeypatch, tmp_path)
    auth_path, authorization = _mve_authorization(tmp_path, harness_head="MOCK_HARNESS_HEAD")
    spec = _mve_spec(tmp_path, auth_path, "MOCK_HARNESS_HEAD")
    mia_output_root = Path(authorization["execution_resources"]["mia_output_root"])
    quarantine = mia_output_root / "mia" / "train_23" / "results"
    quarantine.mkdir(parents=True)
    quarantine_file = quarantine / "tracking_result.txt"
    quarantine_file.write_text("idf1=0.99\n", encoding="utf-8")
    status = CHILD.execute_child(spec)
    # Status contains paths only; it does not read or include result content.
    assert status["outcome_quarantine_paths"]["result_dir"] == str(quarantine)
    status_text = json.dumps(status)
    assert "idf1" not in status_text
    assert "0.99" not in status_text
