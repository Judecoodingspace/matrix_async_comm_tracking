"""Tests for real MATRIX appearance extraction and transfer calibration."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from phase2_matrix_real_embedding_quality_transfer import (  # noqa: E402
    ProgressPrinter,
    calibrate_thresholds,
    decide,
    finalize_existing_outputs,
    identity_lookup_key_uses_person_id,
    stable_identity_fold,
)
from detection.osnet_reid import strip_checkpoint_prefix  # noqa: E402
from tracking.matrix_gt import MatrixObservation  # noqa: E402
from tracking.matrix_identity_cue import observation_sensor_key  # noqa: E402
from tracking.matrix_real_appearance import (  # noqa: E402
    RealAppearanceEmbeddingTable,
    clip_bbox,
    embedding_norm_mismatches,
    extract_m3ot_gem_embeddings,
    extract_osnet_embeddings,
    image_path_for_observation,
    load_embedding_cache,
    los_visible_observations,
    save_embedding_cache,
)
from tracking.matrix_reanchoring import run_primary_only_sort  # noqa: E402


def _observation(
    *,
    frame: int = 0,
    drone: int = 0,
    person: int = 1,
    position: int = 10,
    bbox: tuple[int, int, int, int] = (1, 1, 9, 19),
) -> MatrixObservation:
    return MatrixObservation(
        frame_id=frame,
        drone_id=drone,
        person_id=person,
        position_id=position,
        world_xyz=(float(person), 0.0, 0.0),
        bbox_xyxy=bbox,
        capture_time=frame,
        arrival_time=frame,
        delay=0,
    )


def test_clip_bbox_rejects_outside_and_clips_partial() -> None:
    assert clip_bbox((20, 1, 30, 10), image_width=16, image_height=16) is None
    assert clip_bbox((-2, -3, 8, 9), image_width=16, image_height=16) == (0, 0, 8, 9)


def test_checkpoint_prefix_stripping_is_python38_compatible() -> None:
    assert strip_checkpoint_prefix("module.model.conv.weight") == "conv.weight"
    assert strip_checkpoint_prefix("conv.weight") == "conv.weight"


def test_image_path_and_runtime_key_do_not_depend_on_person_id(tmp_path: Path) -> None:
    left = _observation(person=1)
    right = _observation(person=99)
    assert image_path_for_observation(tmp_path, left) == tmp_path / "image_subsets" / "D1" / "0000.png"
    assert observation_sensor_key(left) == observation_sensor_key(right)


def test_identity_lookup_person_id_gate_is_behavioral() -> None:
    observation = _observation(person=1)
    assert identity_lookup_key_uses_person_id([observation]) == 0
    assert identity_lookup_key_uses_person_id(
        [observation], key_fn=lambda row: (row.person_id, row.capture_time)
    ) == 1


def test_embedding_cache_round_trip_excludes_identity(tmp_path: Path) -> None:
    observation = _observation()
    table = RealAppearanceEmbeddingTable(
        embeddings={observation_sensor_key(observation): np.asarray([0.6, 0.8])},
        backend="test",
        embedding_dim=2,
    )
    path = tmp_path / "cache.npz"
    save_embedding_cache(path, table)
    restored = load_embedding_cache(path)
    assert restored.backend == "test"
    assert np.allclose(restored.embedding_for(observation), np.asarray([0.6, 0.8]))
    assert embedding_norm_mismatches(restored) == 0


def test_los_filter_uses_person_position_only_offline(tmp_path: Path) -> None:
    los_dir = tmp_path / "matchings" / "Pedestrians" / "LoS"
    los_dir.mkdir(parents=True)
    (los_dir / "Drone1_3d_0000.txt").write_text("1 10\n", encoding="utf-8")
    accepted = _observation(person=1, position=10)
    rejected = _observation(person=2, position=20, bbox=(2, 2, 8, 18))
    visible, audit = los_visible_observations(tmp_path, [accepted, rejected])
    assert visible == [accepted]
    assert sum(int(row["los_visible"]) for row in audit) == 1


class _FakeEmbeddingModel(torch.nn.Module):
    def forward(self, values: torch.Tensor) -> torch.Tensor:
        means = values.mean(dim=(2, 3))
        return torch.nn.functional.normalize(means, dim=1)


def test_osnet_extraction_is_normalized_and_reports_progress(tmp_path: Path) -> None:
    image_dir = tmp_path / "image_subsets" / "D1"
    image_dir.mkdir(parents=True)
    image = np.full((24, 16, 3), 127, dtype=np.uint8)
    assert cv2.imwrite(str(image_dir / "0000.png"), image)
    events: list[dict[str, object]] = []
    table, audit = extract_osnet_embeddings(
        [_observation()],
        matrix_root=tmp_path,
        model=_FakeEmbeddingModel(),
        device=torch.device("cpu"),
        batch_size=4,
        progress_every=1,
        progress_callback=lambda event: events.append(dict(event)),
    )
    assert len(table.embeddings) == 1
    assert embedding_norm_mismatches(table) == 0
    assert audit[0]["accepted"] == 1
    assert events[0]["observation_count"] == 1


def test_m3ot_gem_extraction_uses_direct_layer_backend(tmp_path: Path, monkeypatch) -> None:
    image_dir = tmp_path / "image_subsets" / "D1"
    image_dir.mkdir(parents=True)
    assert cv2.imwrite(str(image_dir / "0000.png"), np.full((24, 16, 3), 100, dtype=np.uint8))

    class FakeExtractor:
        def __init__(self, **_kwargs) -> None:
            pass

        def layer_output(self, _path, *, img_w: int, img_h: int):
            return torch.ones((1, 4, 8, 8)), 16, 24

    import tracking.matrix_real_appearance as module

    monkeypatch.setattr(module, "UltralyticsLayerExtractor", FakeExtractor)
    monkeypatch.setattr(module, "build_head_from_checkpoint", lambda *_args, **_kwargs: torch.nn.Identity())
    monkeypatch.setattr(
        module,
        "embed_tensor",
        lambda _head, rois, **_kwargs: np.tile(np.asarray([[3.0, 4.0]]), (len(rois), 1)),
    )
    table, audit = extract_m3ot_gem_embeddings(
        [_observation()],
        matrix_root=tmp_path,
        detector_checkpoint=tmp_path / "detector.pt",
        head_checkpoint=tmp_path / "head.pt",
        device="cpu",
        layer=15,
        image_width=640,
        image_height=512,
        roi_size=8,
        min_roi_size=1,
        batch_size=4,
        progress_every=1,
    )
    assert np.allclose(table.embedding_for(_observation()), np.asarray([0.6, 0.8]))
    assert audit[0]["accepted"] == 1


def test_identity_fold_is_stable_and_disjoint() -> None:
    first = {person for person in range(40) if stable_identity_fold(person, seed=7) == 0}
    second = {person for person in range(40) if stable_identity_fold(person, seed=7) == 1}
    assert first
    assert second
    assert not first & second
    assert first | second == set(range(40))


def test_calibration_uses_opposite_fold_only() -> None:
    rows = [
        {"backend": "model", "target_fold": 0, "pair_label": "same", "score": "0.80"},
        {"backend": "model", "target_fold": 0, "pair_label": "different", "score": "0.20"},
        {"backend": "model", "target_fold": 1, "pair_label": "same", "score": "0.40"},
        {"backend": "model", "target_fold": 1, "pair_label": "different", "score": "0.30"},
    ]
    calibrated = calibrate_thresholds(rows, backends=["model"], false_accept_cost=5.0)
    by_eval = {int(row["evaluation_fold"]): row for row in calibrated}
    assert by_eval[0]["calibration_fold"] == 1
    assert by_eval[1]["calibration_fold"] == 0
    assert float(by_eval[0]["selected_threshold"]) < float(by_eval[1]["selected_threshold"])


def test_tracker_progress_callback_reports_frames() -> None:
    frames: list[int] = []
    observations = [_observation(frame=frame) for frame in range(3)]
    run_primary_only_sort(
        observations,
        truth_observations=observations,
        delay_profile="fixed_0",
        delay_frames=0,
        delay_ms=0.0,
        frame_start=0,
        frame_end=2,
        distance_threshold=2.0,
        primary_drone_id=0,
        progress_callback=frames.append,
        progress_every=1,
    )
    assert frames == [0, 1, 2]


def test_progress_printer_flushes_visible_condition_text(capsys) -> None:
    printer = ProgressPrinter(frame_start=0, frame_end=9, progress_every=1)
    callback = printer.condition_callback(
        condition_index=2,
        condition_total=10,
        description="model=test fold=0 delay=fixed_2",
        condition_started=printer.started,
    )
    callback(4)
    text = capsys.readouterr().out
    assert "condition=2/10" in text
    assert "frame=4/9" in text


def test_decision_distinguishes_supported_and_boundary_contradiction() -> None:
    quality = [{"backend": "model", "quality_relation": "above"}]
    transfer = [
        {
            "backend": "model",
            "delay_ms": delay,
            "pipeline": "fixed_lag_world_xy_covariance_real_appearance",
            "threshold_role": "selected",
            "mean_survival_delta_vs_drop": "0.10",
            "mean_window_idsw_delta_vs_drop": "-1.0",
            "mean_survival_delta_vs_covariance": "0.08",
            "survival_vs_covariance_ci_low": "0.02",
        }
        for delay in ("1000.000", "1500.000")
    ]
    result = decide(quality, transfer, measurement_valid=True)
    assert result["decision"] == "tracking_transfer_supported"
    below = decide([{**quality[0], "quality_relation": "below"}], transfer, measurement_valid=True)
    assert below["decision"] == "simulated_boundary_not_transferable"


def test_finalize_only_rebuilds_behavioral_measurement_gate(tmp_path: Path) -> None:
    def write(path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    quality = [{"backend": "model", "mean_similarity_margin": "0.10", "quality_relation": "above"}]
    transfer = [
        {
            "backend": "model",
            "delay_ms": delay,
            "pipeline": "fixed_lag_world_xy_covariance_real_appearance",
            "threshold_role": "selected",
            "mean_survival_delta_vs_drop": "0.10",
            "mean_window_idsw_delta_vs_drop": "-1.0",
            "mean_survival_delta_vs_covariance": "0.08",
            "survival_vs_covariance_ci_low": "0.02",
        }
        for delay in ("1000.000", "1500.000")
    ]
    measurement = [
        {
            "measurement_valid": 0,
            "primary_perturbation_mismatches": 0,
            "embedding_norm_mismatches": 0,
            "identity_lookup_key_uses_person_id": 1,
            "calibration_evaluation_fold_overlap": 0,
            "reference_reproduction_status": "checked",
            "reference_reproduction_mismatches": 0,
            "expected_condition_checkpoints": 2,
            "completed_condition_checkpoints": 2,
            "coverage": json.dumps([{"embedding_coverage": "1.000000"}]),
        }
    ]
    write(tmp_path / "real_embedding_quality_summary.csv", quality)
    write(tmp_path / "real_embedding_transfer_summary.csv", transfer)
    write(tmp_path / "real_embedding_measurement_gate.csv", measurement)

    decision = finalize_existing_outputs(tmp_path)
    updated = list(csv.DictReader((tmp_path / "real_embedding_measurement_gate.csv").open(encoding="utf-8")))[0]
    assert decision["decision"] == "tracking_transfer_supported"
    assert updated["measurement_valid"] == "1"
    assert updated["identity_lookup_key_uses_person_id"] == "0"
