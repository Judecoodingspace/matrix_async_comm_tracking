#!/usr/bin/env python3
"""Generate an isolated MVE-0 observer-only MIA source variant.

The transformation is intentionally narrow: one pre-ByteTrack detector-copy
hook, two pre-MIA local-output snapshot hooks, and post-core digest hooks.  No
hook result is assigned to an author-pipeline variable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source match, found {count}")
    return text.replace(old, new)


def patch_byte_track(root: Path) -> None:
    path = root / "mmtrack/models/mot/byte_track.py"
    text = path.read_text(encoding="utf-8")
    old = "        det_labels = torch.zeros_like(det_labels)\n\n        track_bboxes, track_labels, track_ids, max_id = self.tracker.track(\n"
    new = "        det_labels = torch.zeros_like(det_labels)\n\n        observer = getattr(self, '_route_a_observer', None)\n        if observer is not None:\n            observer.capture_preassociation_detector(\n                frame_id, int(getattr(self, '_route_a_observer_view')),\n                outs_det['bboxes'], outs_det['labels'])\n\n        track_bboxes, track_labels, track_ids, max_id = self.tracker.track(\n"
    path.write_text(replace_once(text, old, new, "pre-ByteTrack observer hook"), encoding="utf-8")


def patch_entry(root: Path, runtime_source: Path) -> None:
    path = root / "demo/supplement_MIA.py"
    runtime_target = root / "demo/utils/route_a_observer_runtime.py"
    shutil.copy2(runtime_source, runtime_target)
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from utils.cascade_runtime import CascadeEdgeRuntime\n",
        "from utils.cascade_runtime import CascadeEdgeRuntime\nfrom utils.route_a_observer_runtime import RouteAObserverRuntime\n",
        "observer runtime import",
    )
    text = replace_once(
        text,
        "        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n",
        "        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n"
        "        observer_runtime = RouteAObserverRuntime(\n"
        "            os.environ['MIA_ROUTE_A_OUTPUT_DIR'], os.environ['MIA_ROUTE_A_CONDITION'], dirrr,\n"
        "            int(os.environ.get('MIA_ROUTE_A_DELAY_FRAMES', '5')))\n"
        "        model._route_a_observer = observer_runtime\n"
        "        model._route_a_observer_view = 1\n"
        "        model2._route_a_observer = observer_runtime\n"
        "        model2._route_a_observer_view = 2\n",
        "observer runtime initialization",
    )
    text = replace_once(
        text,
        "            track_bboxes2 = result2['track_bboxes'][0]\n"
        "            track_bboxes, det_bboxes, A_max_id = packet_runtime.deliver_local_track(\n",
        "            track_bboxes2 = result2['track_bboxes'][0]\n"
        "            observer_runtime.capture_receiver_snapshot(i, 1, track_bboxes)\n"
        "            observer_runtime.capture_receiver_snapshot(i, 2, track_bboxes2)\n"
        "            observer_runtime.process_arrivals(i)\n"
        "            track_bboxes, det_bboxes, A_max_id = packet_runtime.deliver_local_track(\n",
        "pre-MIA snapshot and arrival hooks",
    )
    hook = (
        "                observer_runtime.record_core_and_feedback(\n"
        "                    i, track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1,\n"
        "                    next_bboxes2, next_ids2, next_labels2)\n"
    )
    old_commit = (
        "                bboxes2 = torch.tensor(next_bboxes2, dtype=torch.long)\n"
        "                ids2 = torch.tensor(next_ids2, dtype=torch.long)\n"
        "                labels2 = torch.tensor(next_labels2, dtype=torch.long)\n"
    )
    new_commit = old_commit + hook
    if text.count(old_commit) != 1:
        raise RuntimeError("local-only feedback digest hook: expected one source match")
    text = text.replace(old_commit, new_commit, 1)
    normal_old = (
        "            bboxes2 = torch.tensor(next_bboxes2, dtype=torch.long)\n"
        "            ids2 = torch.tensor(next_ids2, dtype=torch.long)\n"
        "            labels2 = torch.tensor(next_labels2, dtype=torch.long)\n"
        "            # labels2 = torch.zeros_like(torch.tensor(track_bboxes2[:, 0]))\n"
    )
    normal_hook = (
        "            observer_runtime.record_core_and_feedback(\n"
        "                i, track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1,\n"
        "                next_bboxes2, next_ids2, next_labels2)\n"
    )
    normal_new = normal_old.replace("            # labels2", normal_hook + "            # labels2")
    text = replace_once(text, normal_old, normal_new, "normal feedback digest hook")
    text = replace_once(
        text,
        "        packet_runtime.finalize()\n",
        "        observer_runtime.finalize()\n        packet_runtime.finalize()\n",
        "observer finalization",
    )
    path.write_text(text, encoding="utf-8")


def audit_variant(root: Path) -> dict[str, int]:
    entry = (root / "demo/supplement_MIA.py").read_text(encoding="utf-8")
    tracker = (root / "mmtrack/models/mot/byte_track.py").read_text(encoding="utf-8")
    detector_hook = tracker.index("observer.capture_preassociation_detector(")
    tracker_call = tracker.index("self.tracker.track(", detector_hook)
    snapshot = entry.index("observer_runtime.capture_receiver_snapshot(i, 1")
    mutation = entry.index("packet_runtime.deliver_local_track(", snapshot)
    return {
        "detector_hook_before_bytetrack": int(detector_hook < tracker_call),
        "pre_mia_snapshot_before_local_delivery": int(snapshot < mutation),
        "snapshot_hook_count": int(entry.count("observer_runtime.capture_receiver_snapshot(") == 2),
        "arrival_hook_count": int(entry.count("observer_runtime.process_arrivals(i)") == 1),
        "digest_hook_count": int(entry.count("observer_runtime.record_core_and_feedback(") == 2),
        "observer_finalize_once": int(entry.count("observer_runtime.finalize()") == 1),
        "no_observer_assignment_to_core": int("= observer_runtime.process_arrivals" not in entry),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--variant-root", type=Path, required=True)
    parser.add_argument("--runtime-source", type=Path, default=Path(__file__).resolve().parents[1] / "src/tracking/mdmt_mia_route_a_observer_runtime.py")
    parser.add_argument("--copy-source", action="store_true")
    args = parser.parse_args()
    if args.copy_source:
        if args.variant_root.exists():
            raise SystemExit(f"refusing to overwrite existing variant: {args.variant_root}")
        shutil.copytree(args.source_root, args.variant_root, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    if not args.variant_root.is_dir():
        raise SystemExit("variant root does not exist; pass --copy-source for a new isolated copy")
    patch_byte_track(args.variant_root)
    patch_entry(args.variant_root, args.runtime_source)
    changed = [
        "demo/supplement_MIA.py", "demo/utils/route_a_observer_runtime.py", "mmtrack/models/mot/byte_track.py",
    ]
    manifest = {
        "base_variant": "packetized_id_supplement_cascade_v8",
        "mve": "MVE-0",
        "changed_files": changed,
        "sha256": {relative: sha256(args.variant_root / relative) for relative in changed},
        "structure_audit": audit_variant(args.variant_root),
        "cross_view_geometry_gate": "FAIL",
        "mve1_enabled": 0,
    }
    if not all(manifest["structure_audit"].values()):
        raise RuntimeError("generated observer variant failed structure audit: {}".format(manifest["structure_audit"]))
    (args.variant_root / "route_a_observer_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
