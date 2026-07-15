from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Mapping, Sequence

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


def _conv_bn_relu(in_channels: int, out_channels: int, *, kernel_size: int, stride: int = 1, padding: int | None = None) -> nn.Sequential:
    if padding is None:
        padding = kernel_size // 2
    return nn.Sequential(
        nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, stride=stride, padding=padding, bias=False),
        nn.BatchNorm2d(out_channels),
        nn.ReLU(inplace=True),
    )


class ChannelGate(nn.Module):
    def __init__(self, channels: int, *, reduction: int = 16) -> None:
        super().__init__()
        hidden = max(int(channels) // int(reduction), 4)
        self.net = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(channels, hidden, kernel_size=1, bias=True),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden, channels, kernel_size=1, bias=True),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x * self.net(x)


class LiteOSBlock(nn.Module):
    """Small omni-scale residual block inspired by OSNet.

    This is a local lightweight implementation for experiment probing. It is
    intentionally dependency-free; load a trained checkpoint for formal AUC
    conclusions.
    """

    def __init__(self, channels: int) -> None:
        super().__init__()
        width = max(int(channels) // 4, 8)
        self.reduce = _conv_bn_relu(channels, width, kernel_size=1, padding=0)
        self.stream1 = nn.Sequential(_conv_bn_relu(width, width, kernel_size=3))
        self.stream2 = nn.Sequential(_conv_bn_relu(width, width, kernel_size=3), _conv_bn_relu(width, width, kernel_size=3))
        self.stream3 = nn.Sequential(
            _conv_bn_relu(width, width, kernel_size=3),
            _conv_bn_relu(width, width, kernel_size=3),
            _conv_bn_relu(width, width, kernel_size=3),
        )
        self.stream4 = nn.Sequential(
            _conv_bn_relu(width, width, kernel_size=3),
            _conv_bn_relu(width, width, kernel_size=3),
            _conv_bn_relu(width, width, kernel_size=3),
            _conv_bn_relu(width, width, kernel_size=3),
        )
        self.gate1 = ChannelGate(width)
        self.gate2 = ChannelGate(width)
        self.gate3 = ChannelGate(width)
        self.gate4 = ChannelGate(width)
        self.expand = nn.Sequential(
            nn.Conv2d(width, channels, kernel_size=1, bias=False),
            nn.BatchNorm2d(channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = self.reduce(x)
        out = (
            self.gate1(self.stream1(z))
            + self.gate2(self.stream2(z))
            + self.gate3(self.stream3(z))
            + self.gate4(self.stream4(z))
        )
        return F.relu(self.expand(out) + x, inplace=True)


class OSNetX025(nn.Module):
    def __init__(self, *, embedding_dim: int = 256) -> None:
        super().__init__()
        channels = (16, 64, 96, 128)
        self.stem = nn.Sequential(
            _conv_bn_relu(3, channels[0], kernel_size=7, stride=2, padding=3),
            nn.MaxPool2d(kernel_size=3, stride=2, padding=1),
        )
        self.stage1 = nn.Sequential(LiteOSBlock(channels[0]), _conv_bn_relu(channels[0], channels[1], kernel_size=1, padding=0))
        self.down1 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.stage2 = nn.Sequential(LiteOSBlock(channels[1]), LiteOSBlock(channels[1]), _conv_bn_relu(channels[1], channels[2], kernel_size=1, padding=0))
        self.down2 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.stage3 = nn.Sequential(LiteOSBlock(channels[2]), LiteOSBlock(channels[2]), _conv_bn_relu(channels[2], channels[3], kernel_size=1, padding=0))
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(channels[3], int(embedding_dim), bias=False),
            nn.BatchNorm1d(int(embedding_dim)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        x = self.down1(self.stage1(x))
        x = self.down2(self.stage2(x))
        x = self.stage3(x)
        x = self.pool(x).flatten(1)
        return F.normalize(self.fc(x), dim=1)


def build_osnet_x025(*, checkpoint: Path | None = None, embedding_dim: int = 256, device: str | torch.device = "cpu") -> tuple[nn.Module, bool]:
    model = OSNetX025(embedding_dim=int(embedding_dim))
    random_init = True
    if checkpoint is not None:
        payload = torch.load(checkpoint.expanduser(), map_location="cpu")
        state_dict = payload.get("state_dict", payload) if isinstance(payload, Mapping) else payload
        cleaned = {str(k).removeprefix("module.").removeprefix("model."): v for k, v in state_dict.items()}
        missing, unexpected = model.load_state_dict(cleaned, strict=False)
        if unexpected:
            raise RuntimeError(f"Unexpected OSNet checkpoint keys: {unexpected[:8]}")
        # Missing classifier keys are fine for embedding-only checkpoints, but
        # missing backbone keys mean the AUC result is not meaningful.
        backbone_missing = [key for key in missing if not key.startswith("classifier")]
        if backbone_missing:
            raise RuntimeError(f"OSNet checkpoint missing backbone keys: {backbone_missing[:8]}")
        random_init = False
    model.to(device)
    model.eval()
    return model, random_init


class NormalizeEmbeddingWrapper(nn.Module):
    def __init__(self, model: nn.Module) -> None:
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.model(x)
        if isinstance(out, (tuple, list)):
            out = out[-1]
        return F.normalize(out, dim=1)


def build_torchreid_osnet_x025(
    *,
    checkpoint: Path | None = None,
    device: str | torch.device = "cpu",
    torchreid_path: Path | None = None,
    pretrained: bool = True,
) -> tuple[nn.Module, bool, str]:
    if torchreid_path is not None:
        path = str(torchreid_path.expanduser().resolve())
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        from torchreid import models  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError(
            "torchreid backend requested but torchreid is unavailable. "
            "Install it into an isolated directory and pass --torchreid-path."
        ) from exc

    if checkpoint is None:
        model = models.build_model(
            name="osnet_x0_25",
            num_classes=1000,
            loss="softmax",
            pretrained=bool(pretrained),
            use_gpu=torch.device(device).type == "cuda",
        )
        random_init = not bool(pretrained)
        source = "torchreid_imagenet_pretrained" if pretrained else "torchreid_random_init"
    else:
        model = models.build_model(
            name="osnet_x0_25",
            num_classes=1000,
            loss="softmax",
            pretrained=False,
            use_gpu=torch.device(device).type == "cuda",
        )
        payload = torch.load(checkpoint.expanduser(), map_location="cpu")
        state_dict = payload.get("state_dict", payload) if isinstance(payload, Mapping) else payload
        model_dict = model.state_dict()
        loadable = {}
        for key, value in state_dict.items():
            clean = str(key).removeprefix("module.").removeprefix("model.")
            if clean in model_dict and torch.is_tensor(value) and model_dict[clean].shape == value.shape:
                loadable[clean] = value
        if not loadable:
            raise RuntimeError(f"No compatible OSNet weights found in checkpoint: {checkpoint}")
        model_dict.update(loadable)
        model.load_state_dict(model_dict)
        random_init = False
        source = str(checkpoint)

    wrapped = NormalizeEmbeddingWrapper(model).to(device)
    wrapped.eval()
    return wrapped, random_init, source


def parse_box(value: str) -> tuple[float, float, float, float]:
    parts = [float(item) for item in str(value).split(",")]
    if len(parts) != 4:
        raise ValueError(f"Expected xyxy box with 4 values, got: {value}")
    x1, y1, x2, y2 = parts
    return x1, y1, x2, y2


def load_resized_rgb(image_path: Path, *, img_w: int, img_h: int) -> np.ndarray:
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")
    resized = cv2.resize(bgr, (int(img_w), int(img_h)), interpolation=cv2.INTER_LINEAR)
    return cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)


def crop_to_tensor(
    rgb_image: np.ndarray,
    box: Sequence[float],
    *,
    crop_w: int = 128,
    crop_h: int = 256,
) -> torch.Tensor:
    h, w = rgb_image.shape[:2]
    x1, y1, x2, y2 = [float(value) for value in box]
    ix1 = max(0, min(w - 1, int(math.floor(x1))))
    iy1 = max(0, min(h - 1, int(math.floor(y1))))
    ix2 = max(ix1 + 1, min(w, int(math.ceil(x2))))
    iy2 = max(iy1 + 1, min(h, int(math.ceil(y2))))
    crop = rgb_image[iy1:iy2, ix1:ix2]
    if crop.size == 0:
        crop = np.zeros((int(crop_h), int(crop_w), 3), dtype=np.uint8)
    resized = cv2.resize(crop, (int(crop_w), int(crop_h)), interpolation=cv2.INTER_LINEAR)
    tensor = torch.from_numpy(resized).permute(2, 0, 1).contiguous().float() / 255.0
    mean = torch.tensor([0.485, 0.456, 0.406], dtype=torch.float32).view(3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225], dtype=torch.float32).view(3, 1, 1)
    return (tensor - mean) / std


@torch.no_grad()
def embed_crops(model: nn.Module, crops: torch.Tensor, *, device: torch.device, batch_size: int) -> np.ndarray:
    embeddings: List[np.ndarray] = []
    for start in range(0, int(crops.shape[0]), int(batch_size)):
        batch = crops[start : start + int(batch_size)].to(device, non_blocking=True)
        emb = model(batch)
        embeddings.append(emb.detach().cpu().numpy())
    return np.concatenate(embeddings, axis=0) if embeddings else np.zeros((0, 0), dtype=np.float32)


@dataclass(frozen=True)
class LatencyResult:
    batch_size: int
    samples: int
    mean_ms_per_roi: float
    p50_ms_per_roi: float
    p95_ms_per_roi: float
    max_ms_per_roi: float


@torch.no_grad()
def latency_smoke(
    model: nn.Module,
    crops: torch.Tensor,
    *,
    device: torch.device,
    batch_sizes: Iterable[int],
    warmup: int = 5,
    runs: int = 30,
) -> List[LatencyResult]:
    results: List[LatencyResult] = []
    for batch_size in batch_sizes:
        batch = crops[: int(batch_size)]
        if int(batch.shape[0]) < int(batch_size):
            repeats = int(math.ceil(int(batch_size) / max(int(batch.shape[0]), 1)))
            batch = batch.repeat((repeats, 1, 1, 1))[: int(batch_size)]
        batch = batch.to(device, non_blocking=True)
        for _ in range(int(warmup)):
            _ = model(batch)
        if device.type == "cuda":
            torch.cuda.synchronize(device)
        timings: List[float] = []
        for _ in range(int(runs)):
            t0 = time.perf_counter()
            _ = model(batch)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0 / max(int(batch_size), 1)
            timings.append(float(elapsed_ms))
        values = np.asarray(timings, dtype=np.float64)
        results.append(
            LatencyResult(
                batch_size=int(batch_size),
                samples=int(len(values)),
                mean_ms_per_roi=float(values.mean()),
                p50_ms_per_roi=float(np.percentile(values, 50)),
                p95_ms_per_roi=float(np.percentile(values, 95)),
                max_ms_per_roi=float(values.max()),
            )
        )
    return results
