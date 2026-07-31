"""Simulated identity-cue helpers for controlled MATRIX tracker experiments."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, Sequence, Tuple

import numpy as np

from tracking.matrix_gt import MatrixObservation


ObservationSensorKey = Tuple[int, int, int, Tuple[int, int, int, int]]
ObservationEmbeddingMap = Mapping[ObservationSensorKey, np.ndarray]


@dataclass(frozen=True)
class SimulatedIdentityCueConfig:
    dim: int = 128
    noise_sigma: float = 0.15
    view_bias_sigma: float = 0.08
    seed: int = 7


def observation_sensor_key(obs: MatrixObservation) -> ObservationSensorKey:
    """Key an observation without using GT person_id."""
    return (
        int(obs.capture_time),
        int(obs.drone_id),
        int(obs.position_id),
        tuple(int(value) for value in obs.bbox_xyxy),
    )


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(arr))
    if norm <= 1.0e-12:
        return np.zeros_like(arr, dtype=np.float64)
    return arr / norm


def cosine_similarity(left: np.ndarray | None, right: np.ndarray | None) -> float | None:
    if left is None or right is None:
        return None
    left_norm = normalize_vector(left)
    right_norm = normalize_vector(right)
    if not np.any(left_norm) or not np.any(right_norm):
        return None
    return float(np.dot(left_norm, right_norm))


def _stable_seed(*parts: object) -> int:
    text = ":".join(str(part) for part in parts)
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="little", signed=False) % (2**32)


def _unit_gaussian(seed: int, dim: int) -> np.ndarray:
    rng = np.random.default_rng(int(seed))
    return normalize_vector(rng.normal(0.0, 1.0, int(dim)))


class SimulatedIdentityCueTable:
    """Generate noisy appearance-like embeddings from hidden identity prototypes.

    GT person_id is used only to create the synthetic sensor observation. Runtime
    association looks up embeddings by observation_sensor_key(), which excludes
    person_id.
    """

    def __init__(self, embeddings: Mapping[ObservationSensorKey, np.ndarray], *, config: SimulatedIdentityCueConfig):
        self.embeddings = {key: normalize_vector(value) for key, value in embeddings.items()}
        self.config = config

    @classmethod
    def from_observations(
        cls,
        observations: Sequence[MatrixObservation],
        *,
        config: SimulatedIdentityCueConfig,
    ) -> "SimulatedIdentityCueTable":
        prototypes: dict[int, np.ndarray] = {}
        view_biases: dict[int, np.ndarray] = {}
        embeddings: dict[ObservationSensorKey, np.ndarray] = {}
        for obs in observations:
            person_id = int(obs.person_id)
            drone_id = int(obs.drone_id)
            if person_id not in prototypes:
                prototypes[person_id] = _unit_gaussian(_stable_seed(config.seed, "prototype", person_id), config.dim)
            if drone_id not in view_biases:
                view_biases[drone_id] = _unit_gaussian(_stable_seed(config.seed, "view", drone_id), config.dim)
            noise_rng = np.random.default_rng(
                _stable_seed(
                    config.seed,
                    "obs",
                    int(obs.capture_time),
                    int(obs.drone_id),
                    int(obs.position_id),
                    tuple(int(value) for value in obs.bbox_xyxy),
                )
            )
            noise = noise_rng.normal(0.0, float(config.noise_sigma), int(config.dim))
            embedding = (
                prototypes[person_id]
                + float(config.view_bias_sigma) * view_biases[drone_id]
                + noise
            )
            embeddings[observation_sensor_key(obs)] = normalize_vector(embedding)
        return cls(embeddings, config=config)

    def embedding_for(self, obs: MatrixObservation) -> np.ndarray | None:
        return self.embeddings.get(observation_sensor_key(obs))


def cue_config_for_strength(strength: str, *, seed: int, dim: int = 128) -> SimulatedIdentityCueConfig:
    value = str(strength).lower()
    if value == "strong":
        return SimulatedIdentityCueConfig(dim=dim, noise_sigma=0.05, view_bias_sigma=0.02, seed=seed)
    if value == "medium":
        return SimulatedIdentityCueConfig(dim=dim, noise_sigma=0.15, view_bias_sigma=0.08, seed=seed)
    if value == "weak":
        return SimulatedIdentityCueConfig(dim=dim, noise_sigma=0.30, view_bias_sigma=0.15, seed=seed)
    raise ValueError(f"unknown identity cue strength: {strength}")
