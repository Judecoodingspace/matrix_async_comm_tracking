"""Shared helpers for Phase 2 OOSM experiments."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Mapping

import numpy as np
import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tracking.delay_injection import DelayedObservation, assign_uniform_int_delays  # noqa: E402

import phase1_identity_probe as phase1  # noqa: E402


def load_phase2_inputs(
    *,
    config_path: Path,
    frame_start: int | None,
    frame_end: int | None,
    device: str | None,
) -> tuple[
    Mapping[str, object],
    dict[int, dict[int, np.ndarray]],
    dict[int, dict[int, np.ndarray]],
    list[DelayedObservation],
    int,
    int,
    str,
]:
    phase1.load_detection_helpers()
    cfg = phase1.load_config(config_path)
    frame_cfg = cfg["frames"]
    model_cfg = cfg["models"]
    delay_cfg = cfg["delay"]
    runtime_cfg = cfg.get("runtime", {})
    start = int(frame_start if frame_start is not None else frame_cfg["start"])
    end = int(frame_end if frame_end is not None else frame_cfg["end"])
    resolved_device = phase1.choose_device(str(device or runtime_cfg.get("device", "cpu")))

    base_cfg = cfg["sources"]["base"]
    support_cfg = cfg["sources"]["support"]
    base_gt = phase1.load_mot_gt(phase1.resolve_path(base_cfg["gt"]))
    support_gt = phase1.load_mot_gt(phase1.resolve_path(support_cfg["gt"]))
    base_images = phase1.list_images(phase1.resolve_path(base_cfg["image_dir"]))
    support_images = phase1.list_images(phase1.resolve_path(support_cfg["image_dir"]))

    support_keys = phase1.selected_observation_keys(
        support_gt,
        source_id=str(support_cfg["id"]),
        frame_start=start,
        frame_end=end,
    )
    delayed = assign_uniform_int_delays(
        support_keys,
        min_frames=int(delay_cfg["min_frames"]),
        max_frames=int(delay_cfg["max_frames"]),
        seed=int(delay_cfg["seed"]),
    )

    base_frame_ids = set(range(start, end + 1))
    base_frame_ids.update(int(obs.arrival_time) for obs in delayed)
    base_frame_ids.update(int(obs.capture_time) for obs in delayed)
    support_frame_ids = {int(obs.capture_time) for obs in delayed}

    extractor = phase1.FrozenYoloLayerExtractor(
        weights=phase1.resolve_path(model_cfg["detector"]),
        device=resolved_device,
        layer=int(model_cfg["yolo_reid_layer"]),
    )
    base_rois, base_meta = phase1.collect_rois(
        extractor=extractor,
        gt_by_frame=base_gt,
        images_by_frame=base_images,
        frame_ids=base_frame_ids,
        img_w=int(model_cfg["image_width"]),
        img_h=int(model_cfg["image_height"]),
        roi_size=int(model_cfg["roi_size"]),
        min_roi_size=2,
    )
    support_rois, support_meta = phase1.collect_rois(
        extractor=extractor,
        gt_by_frame=support_gt,
        images_by_frame=support_images,
        frame_ids=support_frame_ids,
        img_w=int(model_cfg["image_width"]),
        img_h=int(model_cfg["image_height"]),
        roi_size=int(model_cfg["roi_size"]),
        min_roi_size=2,
    )

    in_channels = int(max(base_rois.shape[1], support_rois.shape[1]))
    head = phase1.build_head_from_checkpoint(
        phase1.resolve_path(model_cfg["reid_head"]),
        in_channels=in_channels,
        map_location=resolved_device,
    )
    torch_device = torch.device(resolved_device)
    base_emb = phase1.embed_tensor(head, base_rois, device=torch_device)
    support_emb = phase1.embed_tensor(head, support_rois, device=torch_device)
    return (
        cfg,
        phase1.embedding_maps(base_meta, base_emb),
        phase1.embedding_maps(support_meta, support_emb),
        delayed,
        start,
        end,
        resolved_device,
    )


def write_csv(path: Path, rows: list[Mapping[str, object]], fieldnames: list[str]) -> None:
    phase1.rows_to_csv(path, rows, fieldnames)


def fmt_float(value: float) -> str:
    return phase1.fmt_float(value)


def nearest_identity(candidates: Mapping[int, np.ndarray], embedding: np.ndarray) -> tuple[int | None, float]:
    return phase1.nearest_identity(candidates, embedding)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return phase1.cosine(a, b)
