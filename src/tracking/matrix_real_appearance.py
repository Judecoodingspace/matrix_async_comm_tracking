"""Real crop-based appearance embeddings for MATRIX experiments."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

import cv2
import numpy as np
import torch

from detection.osnet_reid import crop_to_tensor, embed_crops
from detection.yolo_reid import (
    build_head_from_checkpoint,
    embed_tensor,
    feature_roi_xyxy,
    scale_xyxy,
)
from tracking.matrix_gt import MatrixObservation
from tracking.matrix_identity_cue import ObservationSensorKey, normalize_vector, observation_sensor_key


ProgressCallback = Callable[[Mapping[str, object]], None]


class UltralyticsLayerExtractor:
    """Capture one frozen Ultralytics layer without the retired split executor."""

    def __init__(self, *, weights: Path, device: str, layer: int) -> None:
        try:
            from ultralytics import YOLO  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "m3ot_gem requires Ultralytics in the active user environment"
            ) from exc
        self.device = torch.device(device)
        self.network = YOLO(str(weights.expanduser().resolve())).model.to(self.device)
        self.network.eval()
        self.layer = int(layer)
        if self.layer < 0 or self.layer >= len(self.network.model):
            raise ValueError(f"invalid Ultralytics layer {self.layer}")
        for parameter in self.network.parameters():
            parameter.requires_grad_(False)

    @torch.no_grad()
    def layer_output(self, image_path: Path, *, img_w: int, img_h: int) -> tuple[torch.Tensor, int, int]:
        bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise FileNotFoundError(f"failed to read image: {image_path}")
        orig_h, orig_w = bgr.shape[:2]
        resized = cv2.resize(bgr, (int(img_w), int(img_h)), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).contiguous().float().div_(255.0)
        captured: list[object] = []
        hook = self.network.model[self.layer].register_forward_hook(
            lambda _module, _inputs, output: captured.append(output)
        )
        try:
            _ = self.network(tensor.unsqueeze(0).to(self.device, non_blocking=True))
        finally:
            hook.remove()
        if not captured:
            raise RuntimeError(f"Ultralytics layer {self.layer} produced no output")
        output = captured[-1]
        if isinstance(output, (tuple, list)):
            tensors = [value for value in output if torch.is_tensor(value)]
            if not tensors:
                raise RuntimeError(f"Ultralytics layer {self.layer} output has no tensor")
            output = tensors[0]
        if not torch.is_tensor(output):
            raise RuntimeError(f"Ultralytics layer {self.layer} output is not a tensor")
        return output, int(orig_w), int(orig_h)


@dataclass(frozen=True)
class RealAppearanceEmbeddingTable:
    embeddings: dict[ObservationSensorKey, np.ndarray]
    backend: str
    embedding_dim: int

    def embedding_for(self, observation: MatrixObservation) -> np.ndarray | None:
        return self.embeddings.get(observation_sensor_key(observation))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.expanduser().open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def image_path_for_observation(matrix_root: Path, observation: MatrixObservation) -> Path:
    return (
        matrix_root.expanduser()
        / "image_subsets"
        / f"D{int(observation.drone_id) + 1}"
        / f"{int(observation.capture_time):04d}.png"
    )


def clip_bbox(
    bbox_xyxy: Sequence[int | float],
    *,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int] | None:
    x1, y1, x2, y2 = [float(value) for value in bbox_xyxy]
    if x2 <= 0 or y2 <= 0 or x1 >= int(image_width) or y1 >= int(image_height) or x2 <= x1 or y2 <= y1:
        return None
    left = max(0, min(int(image_width) - 1, int(np.floor(x1))))
    top = max(0, min(int(image_height) - 1, int(np.floor(y1))))
    right = max(left + 1, min(int(image_width), int(np.ceil(x2))))
    bottom = max(top + 1, min(int(image_height), int(np.ceil(y2))))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _parse_los_pairs(path: Path) -> set[tuple[int, int]]:
    if not path.is_file():
        return set()
    pairs: set[tuple[int, int]] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        parts = raw.strip().split()
        if len(parts) < 2:
            continue
        pairs.add((int(float(parts[0])), int(float(parts[1]))))
    return pairs


def los_visible_observations(
    matrix_root: Path,
    observations: Sequence[MatrixObservation],
) -> tuple[list[MatrixObservation], list[dict[str, object]]]:
    """Filter observations by MATRIX LoS without changing their runtime keys."""
    root = matrix_root.expanduser()
    los_dir = root / "matchings" / "Pedestrians" / "LoS"
    grouped: dict[tuple[int, int], list[MatrixObservation]] = defaultdict(list)
    for observation in observations:
        grouped[(int(observation.capture_time), int(observation.drone_id))].append(observation)

    visible: list[MatrixObservation] = []
    audit: list[dict[str, object]] = []
    for (frame_id, drone_id), rows in sorted(grouped.items()):
        path = los_dir / f"Drone{drone_id + 1}_3d_{frame_id:04d}.txt"
        pairs = _parse_los_pairs(path)
        for observation in rows:
            accepted = (int(observation.person_id), int(observation.position_id)) in pairs
            if accepted:
                visible.append(observation)
            audit.append(
                {
                    "frame_id": frame_id,
                    "drone_id": drone_id,
                    "sensor_key": json.dumps(observation_sensor_key(observation), separators=(",", ":")),
                    "los_visible": int(accepted),
                    "reason": "accepted" if accepted else "not_in_los",
                }
            )
    return visible, audit


def _group_by_image(
    observations: Sequence[MatrixObservation],
) -> list[tuple[tuple[int, int], list[MatrixObservation]]]:
    grouped: dict[tuple[int, int], list[MatrixObservation]] = defaultdict(list)
    for observation in observations:
        grouped[(int(observation.drone_id), int(observation.capture_time))].append(observation)
    return sorted(grouped.items())


def _notify(
    callback: ProgressCallback | None,
    *,
    backend: str,
    image_index: int,
    image_count: int,
    observation_count: int,
    total_observations: int,
    drone_id: int,
    frame_id: int,
) -> None:
    if callback is None:
        return
    callback(
        {
            "backend": backend,
            "image_index": image_index,
            "image_count": image_count,
            "observation_count": observation_count,
            "total_observations": total_observations,
            "drone_id": drone_id,
            "frame_id": frame_id,
        }
    )


def extract_osnet_embeddings(
    observations: Sequence[MatrixObservation],
    *,
    matrix_root: Path,
    model: torch.nn.Module,
    device: torch.device,
    batch_size: int,
    progress_every: int,
    progress_callback: ProgressCallback | None = None,
) -> tuple[RealAppearanceEmbeddingTable, list[dict[str, object]]]:
    embeddings: dict[ObservationSensorKey, np.ndarray] = {}
    audit: list[dict[str, object]] = []
    image_groups = _group_by_image(observations)
    completed = 0
    dimension = 0
    for image_index, ((drone_id, frame_id), rows) in enumerate(image_groups, start=1):
        image_path = image_path_for_observation(matrix_root, rows[0])
        bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if bgr is None:
            for observation in rows:
                audit.append(_crop_audit_row(observation, "osnet_x0_25_msmt17", "missing_image"))
            continue
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        tensors: list[torch.Tensor] = []
        valid: list[MatrixObservation] = []
        for observation in rows:
            clipped = clip_bbox(observation.bbox_xyxy, image_width=width, image_height=height)
            if clipped is None:
                audit.append(_crop_audit_row(observation, "osnet_x0_25_msmt17", "empty_crop"))
                continue
            tensors.append(crop_to_tensor(rgb, clipped, crop_w=128, crop_h=256))
            valid.append(observation)
            audit.append(_crop_audit_row(observation, "osnet_x0_25_msmt17", "accepted", clipped))
        if tensors:
            values = embed_crops(model, torch.stack(tensors), device=device, batch_size=batch_size)
            dimension = int(values.shape[1])
            for observation, value in zip(valid, values):
                embeddings[observation_sensor_key(observation)] = normalize_vector(value)
        completed += len(rows)
        if image_index == 1 or image_index == len(image_groups) or image_index % max(int(progress_every), 1) == 0:
            _notify(
                progress_callback,
                backend="osnet_x0_25_msmt17",
                image_index=image_index,
                image_count=len(image_groups),
                observation_count=completed,
                total_observations=len(observations),
                drone_id=drone_id,
                frame_id=frame_id,
            )
    return RealAppearanceEmbeddingTable(embeddings, "osnet_x0_25_msmt17", dimension), audit


def extract_m3ot_gem_embeddings(
    observations: Sequence[MatrixObservation],
    *,
    matrix_root: Path,
    detector_checkpoint: Path,
    head_checkpoint: Path,
    device: str,
    layer: int,
    image_width: int,
    image_height: int,
    roi_size: int,
    min_roi_size: int,
    batch_size: int,
    progress_every: int,
    progress_callback: ProgressCallback | None = None,
) -> tuple[RealAppearanceEmbeddingTable, list[dict[str, object]]]:
    extractor = UltralyticsLayerExtractor(weights=detector_checkpoint, device=device, layer=layer)
    embedding_device = torch.device(device)
    head: torch.nn.Module | None = None
    embeddings: dict[ObservationSensorKey, np.ndarray] = {}
    audit: list[dict[str, object]] = []
    image_groups = _group_by_image(observations)
    completed = 0
    dimension = 0
    for image_index, ((drone_id, frame_id), rows) in enumerate(image_groups, start=1):
        image_path = image_path_for_observation(matrix_root, rows[0])
        if not image_path.is_file():
            for observation in rows:
                audit.append(_crop_audit_row(observation, "m3ot_gem", "missing_image"))
            continue
        feature_map, orig_width, orig_height = extractor.layer_output(
            image_path,
            img_w=image_width,
            img_h=image_height,
        )
        if head is None:
            channels = int(feature_map.shape[-3])
            head = build_head_from_checkpoint(head_checkpoint, in_channels=channels).to(embedding_device)
            head.eval()
        rois: list[torch.Tensor] = []
        valid: list[MatrixObservation] = []
        for observation in rows:
            clipped = clip_bbox(observation.bbox_xyxy, image_width=orig_width, image_height=orig_height)
            if clipped is None:
                audit.append(_crop_audit_row(observation, "m3ot_gem", "empty_crop"))
                continue
            scaled = scale_xyxy(
                clipped,
                orig_w=orig_width,
                orig_h=orig_height,
                img_w=image_width,
                img_h=image_height,
            )
            roi = feature_roi_xyxy(
                feature_map,
                scaled,
                img_w=image_width,
                img_h=image_height,
                roi_size=roi_size,
                min_roi_size=min_roi_size,
            )
            if roi is None:
                audit.append(_crop_audit_row(observation, "m3ot_gem", "feature_roi_too_small", clipped))
                continue
            rois.append(roi)
            valid.append(observation)
            audit.append(_crop_audit_row(observation, "m3ot_gem", "accepted", clipped))
        if rois and head is not None:
            values = embed_tensor(head, torch.stack(rois), device=embedding_device, batch_size=batch_size)
            dimension = int(values.shape[1])
            for observation, value in zip(valid, values):
                embeddings[observation_sensor_key(observation)] = normalize_vector(value)
        completed += len(rows)
        if image_index == 1 or image_index == len(image_groups) or image_index % max(int(progress_every), 1) == 0:
            _notify(
                progress_callback,
                backend="m3ot_gem",
                image_index=image_index,
                image_count=len(image_groups),
                observation_count=completed,
                total_observations=len(observations),
                drone_id=drone_id,
                frame_id=frame_id,
            )
    return RealAppearanceEmbeddingTable(embeddings, "m3ot_gem", dimension), audit


def _crop_audit_row(
    observation: MatrixObservation,
    backend: str,
    reason: str,
    clipped_bbox: Sequence[int] | None = None,
) -> dict[str, object]:
    bbox = tuple(int(value) for value in (clipped_bbox or observation.bbox_xyxy))
    return {
        "backend": backend,
        "frame_id": int(observation.capture_time),
        "drone_id": int(observation.drone_id),
        "sensor_key": json.dumps(observation_sensor_key(observation), separators=(",", ":")),
        "bbox_x1": bbox[0],
        "bbox_y1": bbox[1],
        "bbox_x2": bbox[2],
        "bbox_y2": bbox[3],
        "accepted": int(reason == "accepted"),
        "reason": reason,
    }


def save_embedding_cache(path: Path, table: RealAppearanceEmbeddingTable) -> None:
    keys = sorted(table.embeddings)
    matrix = np.stack([table.embeddings[key] for key in keys]) if keys else np.zeros((0, 0), dtype=np.float32)
    frames = np.asarray([key[0] for key in keys], dtype=np.int32)
    drones = np.asarray([key[1] for key in keys], dtype=np.int16)
    positions = np.asarray([key[2] for key in keys], dtype=np.int64)
    boxes = np.asarray([key[3] for key in keys], dtype=np.int32).reshape((-1, 4))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(
            handle,
            backend=np.asarray([table.backend]),
            frames=frames,
            drones=drones,
            positions=positions,
            boxes=boxes,
            embeddings=matrix.astype(np.float32),
        )
    temporary.replace(path)


def load_embedding_cache(path: Path) -> RealAppearanceEmbeddingTable:
    with np.load(path, allow_pickle=False) as payload:
        backend = str(payload["backend"][0])
        matrix = np.asarray(payload["embeddings"], dtype=np.float64)
        keys = [
            (int(frame), int(drone), int(position), tuple(int(value) for value in box))
            for frame, drone, position, box in zip(
                payload["frames"], payload["drones"], payload["positions"], payload["boxes"]
            )
        ]
    embeddings = {key: normalize_vector(value) for key, value in zip(keys, matrix)}
    dimension = int(matrix.shape[1]) if matrix.ndim == 2 and matrix.size else 0
    return RealAppearanceEmbeddingTable(embeddings, backend, dimension)


def embedding_norm_mismatches(table: RealAppearanceEmbeddingTable, *, tolerance: float = 1.0e-4) -> int:
    mismatches = 0
    for value in table.embeddings.values():
        norm = float(np.linalg.norm(value))
        if not np.all(np.isfinite(value)) or abs(norm - 1.0) > float(tolerance):
            mismatches += 1
    return mismatches
