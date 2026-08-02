"""Frozen appearance cache keyed by dataset-neutral MDMT detection keys."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from tracking.matrix_identity_cue import normalize_vector
from tracking.tracklet_packets import DetectionKey


@dataclass(frozen=True)
class MDMTEmbeddingTable:
    embeddings: Mapping[DetectionKey, np.ndarray]
    backend: str
    embedding_dim: int


def save_mdmt_embedding_cache(path: Path, table: MDMTEmbeddingTable) -> None:
    keys = sorted(
        table.embeddings,
        key=lambda key: (key.sequence_id, key.view_id, key.frame_id, key.detection_index),
    )
    matrix = (
        np.stack([table.embeddings[key] for key in keys]).astype(np.float32)
        if keys
        else np.zeros((0, 0), dtype=np.float32)
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(
            handle,
            backend=np.asarray([table.backend]),
            sequence_ids=np.asarray([key.sequence_id for key in keys]),
            view_ids=np.asarray([key.view_id for key in keys], dtype=np.int16),
            frame_ids=np.asarray([key.frame_id for key in keys], dtype=np.int32),
            detection_indices=np.asarray([key.detection_index for key in keys], dtype=np.int32),
            embeddings=matrix,
        )
    temporary.replace(path)


def load_mdmt_embedding_cache(path: Path) -> MDMTEmbeddingTable:
    with np.load(path, allow_pickle=False) as payload:
        backend = str(payload["backend"][0])
        matrix = np.asarray(payload["embeddings"], dtype=np.float64)
        keys = [
            DetectionKey(str(sequence_id), int(view_id), int(frame_id), int(detection_index))
            for sequence_id, view_id, frame_id, detection_index in zip(
                payload["sequence_ids"],
                payload["view_ids"],
                payload["frame_ids"],
                payload["detection_indices"],
            )
        ]
    embeddings = {key: normalize_vector(value) for key, value in zip(keys, matrix)}
    dimension = int(matrix.shape[1]) if matrix.ndim == 2 and matrix.size else 0
    return MDMTEmbeddingTable(embeddings, backend, dimension)


def embedding_cache_gate(
    table: MDMTEmbeddingTable,
    expected_keys: set[DetectionKey],
    *,
    norm_tolerance: float = 1.0e-4,
) -> dict[str, object]:
    covered = sum(key in table.embeddings for key in expected_keys)
    invalid = sum(
        not np.all(np.isfinite(value))
        or abs(float(np.linalg.norm(value)) - 1.0) > float(norm_tolerance)
        for key, value in table.embeddings.items()
        if key in expected_keys
    )
    return {
        "expected": len(expected_keys),
        "covered": covered,
        "coverage": covered / max(len(expected_keys), 1),
        "invalid_embeddings": invalid,
    }
