#!/usr/bin/env python3
"""Create, audit, and manifest the isolated Work 1 observer derivative.

The frozen parent is read-only.  This script is deliberately not invoked by
the implementation pass; it only becomes useful after fixture authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


FROZEN_HASHES = {
    "demo/supplement_MIA.py": "4c8674425462dc8e14dc1f53eaaa62a83d93879e45b4cb46a05b38ea78008616",
    "demo/utils/cascade_runtime.py": "b5fd31173e32b7c9c317391d06211dd49f628fec1e960addf0d5a899b732bcf2",
    "demo/utils/supplement.py": "415484d61c9b805f26ba77032af8a2e67617266a861420557f0d886ff1be5ec6",
    "cascade_edge_manifest.json": "0eb11be11898af2c8b9ba3de8140ca5beac9de3df5ba9213bdafe715b9b9e5ed",
    "demo/utils/common.py": "c87dfcf6d6a785e0042b4bf348fa87733b61de78e92d6c32c60c8c1cc31d3b93",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, before: str, after: str, label: str) -> str:
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return text.replace(before, after, 1)


def prepare(parent: Path, destination: Path, observer: Path) -> dict[str, object]:
    if destination.exists():
        raise RuntimeError(f"refusing existing derivative destination: {destination}")
    for relative, expected in FROZEN_HASHES.items():
        actual = sha256(parent / relative)
        if actual != expected:
            raise RuntimeError(f"frozen parent hash mismatch: {relative}")
    shutil.copytree(parent, destination)
    shutil.copy2(observer, destination / "demo/utils/work1_eligibility_observer.py")
    entrypoint = destination / "demo/supplement_MIA.py"
    text = entrypoint.read_text(encoding="utf-8")
    text = replace_once(text, "from utils.cascade_runtime import CascadeEdgeRuntime\n",
        "from utils.cascade_runtime import CascadeEdgeRuntime\nfrom utils.work1_eligibility_observer import Work1EligibilityObserver\n", "observer import")
    text = replace_once(text, "        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n",
        "        work1_observer = None\n        if os.environ.get('MIA_WORK1_OBSERVER', '0') == '1':\n            work1_observer = Work1EligibilityObserver.from_environment(os.environ['MIA_WORK1_OUTPUT_DIR'])\n        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n", "observer construction")
    pre_anchor = "            # print(track_bboxes[:, 0])\n            # print(sorted(matched_ids))\n"
    pre_hook = "            if work1_observer is not None:\n                work1_observer.capture_pre_id(i, track_bboxes, track_bboxes2, A_old_not_matched_ids, A_old_not_matched_pts, A_old_not_matched_pts_corner, B_old_not_matched_ids, B_old_not_matched_pts, B_old_not_matched_pts_corner, lineage_args=(track_bboxes, track_bboxes2, cent_allclass, cent_allclass2, corner_allclass, corner_allclass2, A_max_id, B_max_id, coID_confirme))\n"
    text = replace_once(text, pre_anchor, pre_hook + pre_anchor, "pre-ID hook")
    post_anchor = "            high_score_diagnostics_A = cascade_runtime.new_diagnostic_buffer()\n"
    post_hook = "            if work1_observer is not None:\n                work1_observer.observe_post_id_and_probe(i, track_bboxes, track_bboxes2, A_high_lineage, B_high_lineage, A_old_not_matched_pts, A_old_not_matched_pts_corner, B_old_not_matched_pts, B_old_not_matched_pts_corner, f1, f2, det_bboxes, det_bboxes2)\n"
    text = replace_once(text, post_anchor, post_hook + post_anchor, "post-ID hook")
    high_anchor = "            cascade_runtime.record_high_score_outcomes(i, 1, high_score_diagnostics_A)\n"
    high_hook = "            if work1_observer is not None:\n                work1_observer.record_author_high_score_output(i, high_score_diagnostics_A, high_score_diagnostics_B)\n"
    text = replace_once(text, high_anchor, high_hook + high_anchor, "author output hook")
    terminal_anchor = "            # labels2 = torch.zeros_like(torch.tensor(track_bboxes2[:, 0]))\n            #####################################################################\n\n            result_dict[\"frame={}\".format(i)] = track_bboxes[:, 0:5].tolist()\n"
    terminal_hook = "            if work1_observer is not None:\n                work1_observer.record_core_terminal(i, track_bboxes, track_bboxes2, next_bboxes1, next_ids1, next_labels1, next_bboxes2, next_ids2, next_labels2)\n                work1_observer.end_frame(i)\n"
    text = replace_once(text, terminal_anchor, "            # labels2 = torch.zeros_like(torch.tensor(track_bboxes2[:, 0]))\n            #####################################################################\n\n" + terminal_hook + "            result_dict[\"frame={}\".format(i)] = track_bboxes[:, 0:5].tolist()\n", "terminal hook")
    final_anchor = "    cascade_runtime.finalize()\n"
    text = replace_once(text, final_anchor, final_anchor + "    if work1_observer is not None:\n        work1_observer.finalize()\n", "finalize hook")
    entrypoint.write_text(text, encoding="utf-8")
    protected = ["demo/utils/cascade_runtime.py", "demo/utils/supplement.py", "demo/utils/common.py"]
    for relative in protected:
        if sha256(parent / relative) != sha256(destination / relative):
            raise RuntimeError(f"protected source changed in derivative: {relative}")
    manifest = {
        "kind": "WORK1_OBSERVER_DERIVATIVE", "parent": str(parent), "parent_hashes": FROZEN_HASHES,
        "changed_files": {"demo/supplement_MIA.py": sha256(entrypoint), "demo/utils/work1_eligibility_observer.py": sha256(destination / "demo/utils/work1_eligibility_observer.py")},
        "structure_audit": {"hook_calls": 5, "hook_returns_assigned": False, "protected_files_byte_identical": True},
    }
    (destination / "work1_variant_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.parent, args.destination, args.observer), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
