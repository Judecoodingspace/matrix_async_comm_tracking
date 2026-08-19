#!/usr/bin/env python3
"""Run one author-code MDMT tracking step without altering the upstream tree.

This is intentionally not a new tracker.  It loads the frozen author config,
uses the author's ``mmtrack.apis.inference_mot`` implementation and supplies
the first-frame XML initialization required by that implementation.
"""

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as element_tree
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mia-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--xml", type=Path, required=True)
    parser.add_argument("--frame-id", type=int, default=0)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def read_author_initialization(xml_path: Path, frame_id: int) -> tuple[Any, Any, Any]:
    """Mirror the author XML filter without importing the demo package."""
    import torch

    boxes: list[list[int]] = []
    identities: list[int] = []
    for track in element_tree.parse(xml_path).getroot().findall("track"):
        identity = int(track.attrib["id"])
        for box in track.findall("box"):
            if int(box.attrib["frame"]) != frame_id:
                continue
            left, top = int(box.attrib["xtl"]), int(box.attrib["ytl"])
            right, bottom = int(box.attrib["xbr"]), int(box.attrib["ybr"])
            outside = int(box.attrib["outside"])
            # This condition exactly follows demo/utils/common.py::read_xml_r.
            border = (
                (left <= 10 and top <= 10)
                or (right >= 1920 and top <= 0)
                or (left <= 10 and bottom >= 1070)
                or (right >= 1910 and bottom >= 1070)
            )
            if not outside and not border:
                boxes.append([left, top, right, bottom, 1])
                identities.append(identity)
            break

    bboxes = torch.tensor(boxes, dtype=torch.long)
    ids = torch.tensor(identities, dtype=torch.long)
    return bboxes, ids, torch.zeros_like(ids)


def serialise_rows(rows: Any) -> list[list[float]]:
    if rows is None:
        return []
    return [[float(value) for value in row] for row in rows.tolist()]


def main() -> None:
    args = parse_args()
    upstream = args.mia_root / "upstream"
    if not upstream.is_dir():
        raise SystemExit(f"Missing upstream checkout: {upstream}")
    for required in (args.config, args.checkpoint, args.image, args.xml):
        if not required.is_file():
            raise SystemExit(f"Missing required file: {required}")

    print("[1/3][smoke] importing frozen MIA-Net API", flush=True)
    from mmtrack.apis import inference_mot, init_model

    print(f"[2/3][smoke] loading model device={args.device}", flush=True)
    # The author config loads this detector checkpoint through
    # model.detector.init_cfg. Loading it as top-level ByteTrack weights would
    # produce a misleading detector.* key mismatch.
    model = init_model(str(args.config), checkpoint=None, device=args.device)
    bboxes, ids, labels = read_author_initialization(args.xml, args.frame_id)
    print(
        f"[3/3][smoke] inference image={args.image.name} init_boxes={len(ids)}",
        flush=True,
    )
    result, max_id = inference_mot(
        model,
        str(args.image),
        frame_id=args.frame_id,
        bboxes1=bboxes,
        ids1=ids,
        labels1=labels,
        max_id=0,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "image": str(args.image),
        "xml": str(args.xml),
        "frame_id": args.frame_id,
        "device": args.device,
        "detector_checkpoint": str(args.checkpoint),
        "initialization_box_count": len(ids),
        "det_bbox_count": len(result["det_bboxes"][0]),
        "track_bbox_count": len(result["track_bboxes"][0]),
        "max_id": int(max_id),
        "track_bboxes": serialise_rows(result["track_bboxes"][0]),
    }
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[done][smoke] output={args.output}", flush=True)


if __name__ == "__main__":
    main()
