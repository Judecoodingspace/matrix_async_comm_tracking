#!/usr/bin/env python3
"""Prepare resumable frozen OSNet embeddings for MDMT GT-box detections."""

from __future__ import annotations

import argparse
import time
from collections import defaultdict
from pathlib import Path

import cv2
import torch

from datasets.mdmt import build_runtime_detections, discover_mdmt_sequence_ids, load_mdmt_view
from datasets.mdmt_embeddings import MDMTEmbeddingTable, load_mdmt_embedding_cache, save_mdmt_embedding_cache
from detection.osnet_reid import build_torchreid_osnet_x025, crop_to_tensor, embed_crops
from tracking.matrix_identity_cue import normalize_vector
from tracking.tracklet_packets import DetectionKey, LocalDetection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--splits", nargs="+", default=["val"])
    parser.add_argument("--sequence-ids", nargs="+", default=None)
    parser.add_argument("--view-ids", nargs="+", type=int, default=[1, 2])
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=None)
    parser.add_argument("--labels", nargs="+", default=["person"])
    parser.add_argument("--include-occluded", action="store_true")
    parser.add_argument("--torchreid-path", type=Path, default=Path(".venvs/deep-person-reid"))
    parser.add_argument("--osnet-checkpoint", type=Path, default=Path("weights/osnet_x0_25_msmt17.pth"))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--checkpoint-every-images", type=int, default=100)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output-cache", type=Path, required=True)
    return parser.parse_args()


def collect_detections(args: argparse.Namespace) -> list[tuple[Path, tuple[LocalDetection, ...]]]:
    groups: list[tuple[Path, tuple[LocalDetection, ...]]] = []
    for split in args.splits:
        sequence_ids = args.sequence_ids or discover_mdmt_sequence_ids(args.dataset_root, split=split)
        for sequence_id in sequence_ids:
            for view_id in args.view_ids:
                view = load_mdmt_view(
                    args.dataset_root,
                    split=split,
                    sequence_id=sequence_id,
                    view_id=view_id,
                )
                by_frame, _ = build_runtime_detections(
                    view,
                    frame_start=args.frame_start,
                    frame_end=(
                        len(view.image_paths) - 1
                        if args.frame_end is None
                        else min(args.frame_end, len(view.image_paths) - 1)
                    ),
                    labels=args.labels,
                    include_occluded=args.include_occluded,
                )
                for frame_id, detections in sorted(by_frame.items()):
                    if detections:
                        groups.append((view.image_paths[frame_id], detections))
    return groups


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    print(f"[1/3][prepare] splits={args.splits} views={args.view_ids}", flush=True)
    groups = collect_detections(args)
    expected = {
        row.sensor_key
        for _, detections in groups
        for row in detections
        if isinstance(row.sensor_key, DetectionKey)
    }
    existing: dict[DetectionKey, object] = {}
    if args.resume and args.output_cache.is_file():
        existing = dict(load_mdmt_embedding_cache(args.output_cache).embeddings)
    missing_groups = [
        (path, tuple(row for row in detections if row.sensor_key not in existing))
        for path, detections in groups
    ]
    missing_groups = [(path, rows) for path, rows in missing_groups if rows]
    print(
        f"[1/3][prepare] images={len(groups)} expected={len(expected)} "
        f"cached={len(expected) - sum(len(rows) for _, rows in missing_groups)} "
        f"missing={sum(len(rows) for _, rows in missing_groups)}",
        flush=True,
    )
    if missing_groups:
        model, random_init, source = build_torchreid_osnet_x025(
            checkpoint=args.osnet_checkpoint,
            device=torch.device(args.device),
            torchreid_path=args.torchreid_path,
            pretrained=False,
        )
        if random_init:
            raise RuntimeError(f"refusing random OSNet weights: {source}")
        embeddings = dict(existing)
        processed = 0
        total = sum(len(rows) for _, rows in missing_groups)
        for image_index, (image_path, detections) in enumerate(missing_groups, start=1):
            bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if bgr is None:
                raise FileNotFoundError(image_path)
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            tensors = [crop_to_tensor(rgb, row.bbox_xyxy, crop_w=128, crop_h=256) for row in detections]
            values = embed_crops(
                model,
                torch.stack(tensors),
                device=torch.device(args.device),
                batch_size=args.batch_size,
            )
            for detection, value in zip(detections, values):
                embeddings[detection.sensor_key] = normalize_vector(value)
            processed += len(detections)
            checkpoint_due = (
                image_index == len(missing_groups)
                or image_index % max(args.checkpoint_every_images, 1) == 0
            )
            if checkpoint_due:
                table = MDMTEmbeddingTable(embeddings, "osnet_x0_25_msmt17", int(values.shape[1]))
                save_mdmt_embedding_cache(args.output_cache, table)
            if image_index == 1 or image_index == len(missing_groups) or image_index % max(args.progress_every, 1) == 0:
                elapsed = time.perf_counter() - started
                eta = elapsed / max(processed, 1) * max(total - processed, 0)
                key = detections[-1].sensor_key
                print(
                    f"[2/3][extract][osnet] image={image_index}/{len(missing_groups)} "
                    f"sequence={key.sequence_id} view={key.view_id} frame={key.frame_id} "
                    f"obs={processed}/{total} elapsed={elapsed:.1f}s eta={eta:.1f}s "
                    f"checkpoint={args.output_cache}",
                    flush=True,
                )
    table = load_mdmt_embedding_cache(args.output_cache)
    covered = sum(key in table.embeddings for key in expected)
    invalid = sum(
        not torch.isfinite(torch.as_tensor(table.embeddings[key])).all().item()
        or abs(float(torch.linalg.vector_norm(torch.as_tensor(table.embeddings[key]))) - 1.0) > 1.0e-4
        for key in expected
        if key in table.embeddings
    )
    coverage = covered / max(len(expected), 1)
    print(
        f"[3/3][finalize] covered={covered}/{len(expected)} coverage={coverage:.6f} "
        f"invalid={invalid} output={args.output_cache}",
        flush=True,
    )
    if coverage < 0.95 or invalid:
        raise RuntimeError("MDMT embedding cache failed coverage/norm gate")


if __name__ == "__main__":
    main()
