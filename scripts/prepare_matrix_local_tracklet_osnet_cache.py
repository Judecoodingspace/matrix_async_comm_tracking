#!/usr/bin/env python3
"""Extend the frozen OSNet cache to all LoS-visible per-view detections."""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Iterator, Sequence

import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from detection.osnet_reid import build_torchreid_osnet_x025  # noqa: E402
from tracking.matrix_gt import load_matrix_observations  # noqa: E402
from tracking.matrix_gt import MatrixObservation  # noqa: E402
from tracking.matrix_identity_cue import observation_sensor_key  # noqa: E402
from tracking.matrix_real_appearance import (  # noqa: E402
    RealAppearanceEmbeddingTable,
    extract_osnet_embeddings,
    load_embedding_cache,
    los_visible_observations,
    save_embedding_cache,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, default=Path("MATRIX/MATRIX_30x30"))
    parser.add_argument("--frame-start", type=int, default=0)
    parser.add_argument("--frame-end", type=int, default=999)
    parser.add_argument("--drone-ids", nargs="*", type=int, default=list(range(8)))
    parser.add_argument(
        "--base-cache",
        type=Path,
        default=Path("outputs/20260731_matrix_real_embedding_quality_transfer/embedding_cache/osnet_x0_25_msmt17.npz"),
    )
    parser.add_argument("--output-cache", type=Path, required=True)
    parser.add_argument("--torchreid-path", type=Path, default=Path(".venvs/deep-person-reid"))
    parser.add_argument("--osnet-checkpoint", type=Path, default=Path("weights/osnet_x0_25_msmt17.pth"))
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--load-chunk-frames", type=int, default=25)
    parser.add_argument("--checkpoint-every-observations", type=int, default=5000)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def frame_chunks(frame_start: int, frame_end: int, chunk_size: int) -> Iterator[tuple[int, int]]:
    """Yield inclusive frame chunks so the long JSON stage can report progress."""
    if chunk_size <= 0:
        raise ValueError("load chunk size must be positive")
    current = int(frame_start)
    while current <= int(frame_end):
        last = min(current + int(chunk_size) - 1, int(frame_end))
        yield current, last
        current = last + 1


def embedding_chunks(
    observations: Sequence[MatrixObservation],
    max_observations: int,
) -> list[list[MatrixObservation]]:
    """Pack complete image groups into resumable extraction checkpoints."""
    if max_observations <= 0:
        raise ValueError("checkpoint observation count must be positive")
    grouped: dict[tuple[int, int], list[MatrixObservation]] = defaultdict(list)
    for observation in observations:
        grouped[(int(observation.drone_id), int(observation.capture_time))].append(observation)
    chunks: list[list[MatrixObservation]] = []
    current: list[MatrixObservation] = []
    for key in sorted(grouped):
        rows = sorted(grouped[key], key=observation_sensor_key)
        if current and len(current) + len(rows) > int(max_observations):
            chunks.append(current)
            current = []
        current.extend(rows)
    if current:
        chunks.append(current)
    return chunks


def load_visible_observations_chunked(
    args: argparse.Namespace,
    *,
    started: float,
) -> list[MatrixObservation]:
    wanted_views = set(args.drone_ids)
    visible: list[MatrixObservation] = []
    total_frames = int(args.frame_end) - int(args.frame_start) + 1
    for chunk_start, chunk_end in frame_chunks(
        args.frame_start,
        args.frame_end,
        args.load_chunk_frames,
    ):
        observations = load_matrix_observations(
            args.matrix_root,
            frame_start=chunk_start,
            frame_end=chunk_end,
        )
        chunk_visible, _ = los_visible_observations(args.matrix_root, observations)
        visible.extend(row for row in chunk_visible if int(row.drone_id) in wanted_views)
        completed_frames = chunk_end - int(args.frame_start) + 1
        elapsed = time.perf_counter() - started
        eta = elapsed / max(completed_frames, 1) * max(total_frames - completed_frames, 0)
        print(
            f"[1/3][prepare] frames={chunk_start}-{chunk_end} "
            f"loaded={completed_frames}/{total_frames} visible={len(visible)} "
            f"elapsed={elapsed:.1f}s eta={eta:.1f}s",
            flush=True,
        )
    return visible


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    print("[1/3][prepare] loading all-view LoS observations", flush=True)
    visible = load_visible_observations_chunked(args, started=started)
    if not args.base_cache.is_file():
        raise FileNotFoundError(f"base OSNet cache does not exist: {args.base_cache}")
    print(f"[1/3][prepare] loading base cache={args.base_cache}", flush=True)
    merged = load_embedding_cache(args.base_cache)
    if args.resume and args.output_cache.is_file():
        print(f"[1/3][prepare] resume: loading checkpoint={args.output_cache}", flush=True)
        resumed = load_embedding_cache(args.output_cache)
        merged = RealAppearanceEmbeddingTable(
            embeddings={**merged.embeddings, **resumed.embeddings},
            backend=resumed.backend,
            embedding_dim=resumed.embedding_dim,
        )
    missing = [row for row in visible if observation_sensor_key(row) not in merged.embeddings]
    print(
        f"[1/3][prepare] visible={len(visible)} cached={len(visible) - len(missing)} missing={len(missing)}",
        flush=True,
    )
    if missing:
        print(f"[2/3][extract] device={args.device} loading frozen OSNet", flush=True)
        model, random_init, source = build_torchreid_osnet_x025(
            checkpoint=args.osnet_checkpoint,
            device=torch.device(args.device),
            torchreid_path=args.torchreid_path,
            pretrained=False,
        )
        if random_init:
            raise RuntimeError(f"refusing random OSNet weights: {source}")
        extraction_started = time.perf_counter()
        chunks = embedding_chunks(missing, args.checkpoint_every_observations)
        completed_before = 0
        for chunk_index, chunk in enumerate(chunks, start=1):
            chunk_offset = completed_before

            def progress(payload: dict[str, object]) -> None:
                elapsed = time.perf_counter() - extraction_started
                done = chunk_offset + int(payload["observation_count"])
                total = len(missing)
                eta = elapsed / max(done, 1) * max(total - done, 0)
                print(
                    f"[2/3][extract][osnet][D{int(payload['drone_id']) + 1}] "
                    f"frame={payload['frame_id']}/{args.frame_end} obs={done}/{total} "
                    f"chunk={chunk_index}/{len(chunks)} elapsed={elapsed:.1f}s eta={eta:.1f}s "
                    f"checkpoint={args.output_cache}",
                    flush=True,
                )

            extracted, _ = extract_osnet_embeddings(
                chunk,
                matrix_root=args.matrix_root,
                model=model,
                device=torch.device(args.device),
                batch_size=args.batch_size,
                progress_every=args.progress_every,
                progress_callback=progress,
            )
            merged = RealAppearanceEmbeddingTable(
                embeddings={**merged.embeddings, **extracted.embeddings},
                backend="osnet_x0_25_msmt17",
                embedding_dim=extracted.embedding_dim or merged.embedding_dim,
            )
            completed_before += len(chunk)
            save_embedding_cache(args.output_cache, merged)
            print(
                f"[2/3][extract] checkpoint saved chunk={chunk_index}/{len(chunks)} "
                f"completed={completed_before}/{len(missing)} path={args.output_cache}",
                flush=True,
            )
    elif not args.output_cache.is_file():
        save_embedding_cache(args.output_cache, merged)
    covered = sum(observation_sensor_key(row) in merged.embeddings for row in visible)
    coverage = covered / max(len(visible), 1)
    print(
        f"[3/3][finalize] covered={covered}/{len(visible)} coverage={coverage:.6f} "
        f"output={args.output_cache}",
        flush=True,
    )
    if coverage < 0.95:
        raise RuntimeError(f"embedding coverage remains below gate: {coverage:.2%}")


if __name__ == "__main__":
    main()
