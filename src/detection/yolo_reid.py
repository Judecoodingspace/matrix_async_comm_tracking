from __future__ import annotations

import csv
import math
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    from jetson_split_executor import YoloSplitExecutorJetson as YoloSplitExecutor
except ImportError:
    from jetson_split_executor import YoloSplitExecutor


BoxXYWH = Tuple[float, float, float, float]
BoxXYXY = Tuple[float, float, float, float]


@dataclass(frozen=True)
class MotBox:
    frame_id: int
    track_id: int
    box_xywh: BoxXYWH
    class_id: int
    visibility: float


@dataclass
class FeatureBank:
    rois: torch.Tensor
    frame_ids: np.ndarray
    track_ids: np.ndarray
    source_ids: np.ndarray
    source_names: Tuple[str, str]
    split_name: str

    @property
    def n_samples(self) -> int:
        return int(self.rois.shape[0])

    @property
    def channels(self) -> int:
        return int(self.rois.shape[1])


def stable_hash_int(value: str) -> int:
    return sum((idx + 1) * ord(ch) for idx, ch in enumerate(str(value)))


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def fmt_float(value: float) -> str:
    return "" if not math.isfinite(float(value)) else f"{float(value):.6f}"


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_mot_gt(path: Path) -> Dict[int, Dict[int, MotBox]]:
    if not path.is_file():
        raise FileNotFoundError(f"GT not found: {path}")
    by_frame: Dict[int, Dict[int, MotBox]] = defaultdict(dict)
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split(",")
            if len(parts) < 6:
                raise ValueError(f"{path}:{line_no}: expected at least 6 comma-separated fields")
            frame_id = int(float(parts[0]))
            track_id = int(float(parts[1]))
            x, y, w, h = [float(value) for value in parts[2:6]]
            class_id = int(float(parts[7])) if len(parts) > 7 else 1
            visibility = float(parts[8]) if len(parts) > 8 else 1.0
            if w <= 0 or h <= 0:
                continue
            by_frame[frame_id][track_id] = MotBox(
                frame_id=frame_id,
                track_id=track_id,
                box_xywh=(x, y, w, h),
                class_id=class_id,
                visibility=visibility,
            )
    return dict(by_frame)


def list_images(image_dir: Path) -> Dict[int, Path]:
    out: Dict[int, Path] = {}
    for child in sorted(image_dir.expanduser().iterdir()):
        if child.is_file() and child.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            try:
                out[int(child.stem)] = child
            except ValueError:
                continue
    return out


def preprocess_image(image_path: Path, *, device: torch.device, img_w: int, img_h: int) -> tuple[torch.Tensor, int, int]:
    bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")
    orig_h, orig_w = bgr.shape[:2]
    resized = cv2.resize(bgr, (int(img_w), int(img_h)), interpolation=cv2.INTER_LINEAR)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    tensor = torch.from_numpy(rgb).permute(2, 0, 1).contiguous().float() / 255.0
    return tensor.unsqueeze(0).to(device, non_blocking=True), orig_w, orig_h


def xywh_to_xyxy(box_xywh: BoxXYWH) -> BoxXYXY:
    x, y, w, h = [float(value) for value in box_xywh]
    return x, y, x + w, y + h


def scale_xyxy(box: Sequence[float], *, orig_w: int, orig_h: int, img_w: int, img_h: int) -> BoxXYXY:
    sx = float(img_w) / max(float(orig_w), 1.0)
    sy = float(img_h) / max(float(orig_h), 1.0)
    x1, y1, x2, y2 = [float(value) for value in box]
    return x1 * sx, y1 * sy, x2 * sx, y2 * sy


def iou_xyxy(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = [float(value) for value in a]
    bx1, by1, bx2, by2 = [float(value) for value in b]
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0.0 else 0.0


def feature_roi_xyxy(
    fmap: torch.Tensor,
    box_xyxy: Sequence[float],
    *,
    img_w: int,
    img_h: int,
    roi_size: int,
    min_roi_size: int,
) -> torch.Tensor | None:
    if fmap.ndim == 4:
        fmap = fmap[0]
    if fmap.ndim != 3:
        return None
    _, feat_h, feat_w = fmap.shape
    x1, y1, x2, y2 = [float(value) for value in box_xyxy]
    fx1 = max(0, min(feat_w - 1, int(math.floor(x1 / max(float(img_w), 1.0) * feat_w))))
    fy1 = max(0, min(feat_h - 1, int(math.floor(y1 / max(float(img_h), 1.0) * feat_h))))
    fx2 = max(0, min(feat_w, int(math.ceil(x2 / max(float(img_w), 1.0) * feat_w))))
    fy2 = max(0, min(feat_h, int(math.ceil(y2 / max(float(img_h), 1.0) * feat_h))))
    if fx2 - fx1 < min_roi_size or fy2 - fy1 < min_roi_size:
        return None
    roi = fmap[:, fy1:fy2, fx1:fx2]
    if roi.numel() == 0:
        return None
    resized = F.interpolate(
        roi.unsqueeze(0).to(dtype=torch.float32),
        size=(int(roi_size), int(roi_size)),
        mode="bilinear",
        align_corners=False,
    )
    return resized[0].detach().cpu()


def feature_roi_xywh(
    fmap: torch.Tensor,
    box_xywh: BoxXYWH,
    *,
    orig_w: int,
    orig_h: int,
    img_w: int,
    img_h: int,
    roi_size: int,
    min_roi_size: int,
) -> torch.Tensor | None:
    scaled_xyxy = scale_xyxy(xywh_to_xyxy(box_xywh), orig_w=orig_w, orig_h=orig_h, img_w=img_w, img_h=img_h)
    return feature_roi_xyxy(
        fmap,
        scaled_xyxy,
        img_w=img_w,
        img_h=img_h,
        roi_size=roi_size,
        min_roi_size=min_roi_size,
    )


class FrozenYoloLayerExtractor:
    def __init__(self, *, weights: Path, device: str, layer: int) -> None:
        self.layer = int(layer)
        self.executor = YoloSplitExecutor(model_path=weights.expanduser().resolve(), device=torch.device(device))
        self.device = self.executor.device
        self.executor.net.eval()
        n_layers = len(self.executor.net.model)
        if self.layer < 0 or self.layer >= n_layers:
            raise ValueError(f"Invalid layer {self.layer}; model has {n_layers} layers")
        for param in self.executor.net.parameters():
            param.requires_grad_(False)

    @torch.no_grad()
    def layer_output(self, image_path: Path, *, img_w: int, img_h: int) -> tuple[torch.Tensor, int, int]:
        layer_output, _, orig_w, orig_h = self.layer_and_raw_output(image_path, img_w=img_w, img_h=img_h)
        return layer_output, orig_w, orig_h

    @torch.no_grad()
    def layer_and_raw_output(self, image_path: Path, *, img_w: int, img_h: int) -> tuple[torch.Tensor, Any, int, int]:
        tensor, orig_w, orig_h = preprocess_image(image_path, device=self.device, img_w=img_w, img_h=img_h)
        outputs: Dict[int, Any] = {}
        layer_output: torch.Tensor | None = None
        x = tensor
        for idx, module in enumerate(self.executor.net.model):
            x_in = x if idx == 0 else self.executor._build_module_input(idx, outputs)
            outputs[idx] = module(x_in)
            if idx == self.layer:
                layer_output = outputs[idx]
        if layer_output is None:
            raise RuntimeError(f"Layer {self.layer} was not produced")
        return layer_output, outputs[len(self.executor.net.model) - 1], orig_w, orig_h


def inverse_softplus(value: float) -> float:
    return float(math.log(math.exp(value) - 1.0))


class GeMPool(nn.Module):
    def __init__(self, *, init_p: float = 3.0, min_p: float = 1.0, max_p: float = 8.0, eps: float = 1e-6) -> None:
        super().__init__()
        self.min_p = float(min_p)
        self.max_p = float(max_p)
        self.eps = float(eps)
        self.raw_p = nn.Parameter(torch.tensor(inverse_softplus(float(init_p) - self.min_p), dtype=torch.float32))

    def effective_p(self) -> torch.Tensor:
        p = self.min_p + F.softplus(self.raw_p)
        return torch.clamp(p, min=self.min_p, max=self.max_p)

    def forward(self, x: torch.Tensor, att: torch.Tensor | None = None) -> torch.Tensor:
        x_pos = torch.clamp(x, min=self.eps)
        p = self.effective_p()
        if att is None:
            pooled = x_pos.pow(p).mean(dim=(2, 3))
        else:
            pooled = (x_pos.pow(p) * att).sum(dim=(2, 3))
        return torch.clamp(pooled, min=self.eps).pow(1.0 / p)


class MeanMaxL2Head(nn.Module):
    trainable = False

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor | None]:
        mean = x.mean(dim=(2, 3))
        max_values = x.amax(dim=(2, 3))
        emb = F.normalize(torch.cat([mean, max_values], dim=1), dim=1)
        return emb, None


class GemL2Head(nn.Module):
    trainable = True

    def __init__(self) -> None:
        super().__init__()
        self.pool = GeMPool()

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor | None]:
        emb = F.normalize(self.pool(x), dim=1)
        return emb, None


class ProjectedReIDHead(nn.Module):
    trainable = True

    def __init__(
        self,
        *,
        in_channels: int,
        num_classes: int,
        embed_dim: int,
        hidden_dim: int,
        use_attention: bool,
        part_k: int | None = None,
    ) -> None:
        super().__init__()
        self.use_attention = bool(use_attention)
        self.part_k = int(part_k) if part_k else None
        self.pool = GeMPool()
        self.attn = nn.Conv2d(in_channels, 1, kernel_size=1) if self.use_attention else None
        pool_dim = in_channels * (self.part_k if self.part_k else 1)
        self.projector = nn.Sequential(
            nn.Linear(pool_dim, int(hidden_dim), bias=False),
            nn.BatchNorm1d(int(hidden_dim)),
            nn.ReLU(inplace=True),
            nn.Linear(int(hidden_dim), int(embed_dim), bias=False),
            nn.BatchNorm1d(int(embed_dim)),
        )
        self.classifier = nn.Linear(int(embed_dim), int(num_classes))

    def _attention(self, x: torch.Tensor) -> torch.Tensor | None:
        if self.attn is None:
            return None
        logits = self.attn(x)
        b, _, h, w = logits.shape
        return F.softmax(logits.view(b, 1, h * w), dim=2).view(b, 1, h, w)

    def _pool_one(self, x: torch.Tensor) -> torch.Tensor:
        return self.pool(x, self._attention(x))

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor | None]:
        if self.part_k:
            parts = torch.chunk(x, chunks=self.part_k, dim=2)
            pooled = torch.cat([self._pool_one(part) for part in parts], dim=1)
        else:
            pooled = self._pool_one(x)
        projected = self.projector(pooled)
        emb = F.normalize(projected, dim=1)
        logits = self.classifier(projected)
        return emb, logits


def build_reid_head(
    variant: str,
    *,
    in_channels: int,
    num_classes: int,
    embed_dim: int = 256,
    hidden_dim: int = 512,
    part_k: int = 4,
) -> nn.Module:
    if variant == "meanmax_l2":
        return MeanMaxL2Head()
    if variant == "gem_l2":
        return GemL2Head()
    if variant == "gem_proj":
        return ProjectedReIDHead(
            in_channels=in_channels,
            num_classes=num_classes,
            embed_dim=embed_dim,
            hidden_dim=hidden_dim,
            use_attention=False,
        )
    if variant == "attn_gem_proj":
        return ProjectedReIDHead(
            in_channels=in_channels,
            num_classes=num_classes,
            embed_dim=embed_dim,
            hidden_dim=hidden_dim,
            use_attention=True,
        )
    if variant == "part_attn_gem_proj":
        return ProjectedReIDHead(
            in_channels=in_channels,
            num_classes=num_classes,
            embed_dim=embed_dim,
            hidden_dim=hidden_dim,
            use_attention=True,
            part_k=part_k,
        )
    raise ValueError(f"Unknown variant: {variant}")


def build_head_from_checkpoint(
    checkpoint_path: Path,
    *,
    in_channels: int,
    variant: str | None = None,
    map_location: str | torch.device = "cpu",
) -> nn.Module:
    payload = torch.load(checkpoint_path.expanduser(), map_location=map_location)
    state_dict = payload["state_dict"] if isinstance(payload, Mapping) and "state_dict" in payload else payload
    ckpt_variant = str(payload.get("variant", "")) if isinstance(payload, Mapping) else ""
    variant = variant or ckpt_variant
    if not variant:
        raise ValueError("Variant must be provided when checkpoint has no variant metadata")
    args = payload.get("args", {}) if isinstance(payload, Mapping) else {}
    classifier_weight = state_dict.get("classifier.weight")
    num_classes = int(classifier_weight.shape[0]) if torch.is_tensor(classifier_weight) else int(args.get("num_classes", 1))
    model = build_reid_head(
        variant,
        in_channels=in_channels,
        num_classes=num_classes,
        embed_dim=int(args.get("embed_dim", 256)),
        hidden_dim=int(args.get("hidden_dim", 512)),
        part_k=int(args.get("part_k", 4)),
    )
    model.load_state_dict(state_dict)
    return model


def batch_hard_triplet_loss(embeddings: torch.Tensor, labels: torch.Tensor, *, margin: float) -> torch.Tensor:
    distances = torch.cdist(embeddings, embeddings, p=2)
    same = labels[:, None].eq(labels[None, :])
    eye = torch.eye(labels.numel(), dtype=torch.bool, device=labels.device)
    positive_mask = same & ~eye
    negative_mask = ~same
    valid = positive_mask.any(dim=1) & negative_mask.any(dim=1)
    if not bool(valid.any()):
        return embeddings.sum() * 0.0
    pos_dist = distances.masked_fill(~positive_mask, -1.0)
    hardest_pos = pos_dist.max(dim=1).values
    neg_dist = distances.masked_fill(~negative_mask, float("inf"))
    hardest_neg = neg_dist.min(dim=1).values
    losses = F.relu(hardest_pos - hardest_neg + float(margin))
    return losses[valid].mean()


def gem_p_value(model: nn.Module) -> float | None:
    for module in model.modules():
        if isinstance(module, GeMPool):
            return float(module.effective_p().detach().cpu())
    return None


@torch.no_grad()
def embed_tensor(model: nn.Module, rois: torch.Tensor, *, device: torch.device, batch_size: int = 512) -> np.ndarray:
    model.to(device)
    model.eval()
    embeddings: List[np.ndarray] = []
    for start in range(0, int(rois.shape[0]), int(batch_size)):
        batch = rois[start : start + int(batch_size)].to(device, non_blocking=True)
        emb, _ = model(batch)
        embeddings.append(emb.detach().cpu().numpy())
    return np.concatenate(embeddings, axis=0) if embeddings else np.zeros((0, 0), dtype=np.float32)


def auc_from_scores(pos_scores: Sequence[float], neg_scores: Sequence[float]) -> float:
    if not pos_scores or not neg_scores:
        return float("nan")
    labeled = [(float(score), 1) for score in pos_scores] + [(float(score), 0) for score in neg_scores]
    labeled.sort(key=lambda item: item[0])
    rank_sum_pos = 0.0
    rank = 1
    idx = 0
    while idx < len(labeled):
        end = idx + 1
        while end < len(labeled) and labeled[end][0] == labeled[idx][0]:
            end += 1
        avg_rank = (rank + rank + (end - idx) - 1) / 2.0
        rank_sum_pos += avg_rank * sum(label for _, label in labeled[idx:end])
        rank += end - idx
        idx = end
    n_pos = len(pos_scores)
    n_neg = len(neg_scores)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def average_precision(sorted_is_positive: np.ndarray) -> float:
    n_pos = int(sorted_is_positive.sum())
    if n_pos <= 0:
        return float("nan")
    cum_pos = np.cumsum(sorted_is_positive)
    ranks = np.arange(1, sorted_is_positive.size + 1)
    precision_at_k = cum_pos / ranks
    return float((precision_at_k * sorted_is_positive).sum() / n_pos)
