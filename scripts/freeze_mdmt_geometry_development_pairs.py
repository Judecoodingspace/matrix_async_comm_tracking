#!/usr/bin/env python3
"""Freeze the G14 MDMT-train geometry-development manifest without image reads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
from datetime import datetime, timezone


EXPERIMENT_ID = "exp_20260823_001_mdmt_mia_independent_geometry_development"
SELECTION_SEED = 7
SELECTION_ALGORITHM = "random.Random(7).sample(sorted_eligible_pair_ids, 5)"
EXCLUDED_PAIR_IDS = ("26", "48")


def sha256_text(lines: list[str]) -> str:
    payload = "".join(f"{line}\n" for line in lines).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def git_provenance() -> dict[str, object]:
    try:
        branch = git_value(["branch", "--show-current"])
        commit = git_value(["rev-parse", "HEAD"])
        dirty = bool(git_value(["status", "--porcelain=v1"]))
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("M1 requires a usable Git worktree with HEAD provenance") from exc
    if not branch or not commit:
        raise RuntimeError("M1 requires a non-detached Git branch and commit")
    return {"git_branch": branch, "git_commit": commit, "git_dirty_status": dirty}


def jpeg_names(view_dir: Path) -> list[str]:
    if not view_dir.is_dir():
        return []
    return sorted(
        child.name
        for child in view_dir.iterdir()
        if child.is_file() and child.suffix.lower() in {".jpg", ".jpeg"}
    )


def pair_id_from_view_one(name: str) -> str | None:
    if not name.endswith("-1"):
        return None
    pair_id = name[:-2]
    return pair_id if pair_id.isdigit() else None


def enumerate_eligible_pairs(train_root: Path) -> tuple[list[str], dict[str, dict[str, object]]]:
    view_one_root = train_root / "1"
    view_two_root = train_root / "2"
    if not view_one_root.is_dir() or not view_two_root.is_dir():
        raise RuntimeError("expected train/1 and train/2 image roots")

    eligible: list[str] = []
    pair_metadata: dict[str, dict[str, object]] = {}
    for child in sorted(view_one_root.iterdir(), key=lambda item: item.name):
        pair_id = pair_id_from_view_one(child.name)
        if pair_id is None:
            continue
        view_two = view_two_root / f"{pair_id}-2"
        names_one = jpeg_names(child)
        names_two = jpeg_names(view_two)
        if not names_one or names_one != names_two:
            continue
        if pair_id in EXCLUDED_PAIR_IDS:
            continue
        eligible.append(pair_id)
        name_digest = sha256_text(names_one)
        pair_metadata[pair_id] = {
            "view_1_relative_path": str(child.relative_to(train_root)),
            "view_2_relative_path": str(view_two.relative_to(train_root)),
            "frame_count": len(names_one),
            "frame_filename_set_digest": name_digest,
        }

    eligible = sorted(eligible, key=lambda value: int(value))
    if len(eligible) < 5:
        raise RuntimeError("fewer than five eligible train pair IDs")
    return eligible, pair_metadata


def canonical_json_digest(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_root = args.data_root.resolve()
    train_root = data_root / "train"
    output = args.output.resolve()
    script_path = Path(__file__).resolve()

    if not train_root.is_dir():
        raise RuntimeError("M1 permits only a data root containing train/")
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing manifest: {output}")
    if len(args.output.parts) == 0:
        raise RuntimeError("manifest output path is invalid")

    eligible_pair_ids, pair_metadata = enumerate_eligible_pairs(train_root)
    selected_pair_ids = random.Random(SELECTION_SEED).sample(eligible_pair_ids, 5)
    provenance = git_provenance()

    manifest: dict[str, object] = {
        "experiment_id": EXPERIMENT_ID,
        "dataset_root_resolved": str(data_root),
        "split": "train",
        "eligible_pair_ids": eligible_pair_ids,
        "excluded_pair_ids": list(EXCLUDED_PAIR_IDS),
        "selected_pair_ids": selected_pair_ids,
        "selection_seed": SELECTION_SEED,
        "selection_algorithm": SELECTION_ALGORITHM,
        "selection_python_version": sys.version,
        "selection_platform": platform.platform(),
        "freeze_script_digest": sha256_file(script_path),
        "pair_frame_metadata": pair_metadata,
        "manifest_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "diagnostics_started": False,
        **provenance,
    }
    manifest["manifest_digest"] = canonical_json_digest(manifest)

    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
