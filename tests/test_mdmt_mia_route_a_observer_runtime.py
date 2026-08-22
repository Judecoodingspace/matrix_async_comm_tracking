from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

from tracking.mdmt_mia_route_a_observer_runtime import RouteAObserverRuntime


ROOT = Path(__file__).resolve().parents[1]


def test_route_a_mve0_builds_tube_but_creates_no_cross_view_candidate(tmp_path: Path) -> None:
    runtime = RouteAObserverRuntime(tmp_path, "ROUTE_A_OBSERVER_MVE", "26-1")
    runtime.capture_preassociation_detector(1, 1, np.asarray([[1, 2, 5, 7, 0.8]]), np.asarray([0]))
    for frame in range(1, 7):
        runtime.capture_receiver_snapshot(frame, 2, np.asarray([[3, 3, 4, 8, 9, 0.9]]))
        runtime.process_arrivals(frame)
        runtime.record_core_and_feedback(frame, np.empty((0, 6)), np.empty((0, 6)),
                                         np.empty((0, 4)), np.empty((0,)), np.empty((0,)),
                                         np.empty((0, 4)), np.empty((0,)), np.empty((0,)))
    manifest_path, assertion_path = runtime.finalize()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["cross_view_geometry_gate"] == "FAIL"
    assert manifest["counts"]["evidence_tube_construction_count"] == 1
    assert manifest["counts"]["route_a_only_new_candidate_count"] == 0
    assert json.loads((tmp_path / "candidate_events.jsonl").read_text().strip())["candidate_created"] == 0
    assert "NOT_APPLICABLE_GEOMETRY_FAIL_CLOSED" in assertion_path.read_text(encoding="utf-8")


def test_drop_late_does_not_construct_tube(tmp_path: Path) -> None:
    runtime = RouteAObserverRuntime(tmp_path, "DROP_LATE", "48-1")
    runtime.capture_preassociation_detector(1, 1, np.asarray([[1, 2, 5, 7, 0.8]]), np.asarray([0]))
    runtime.process_arrivals(6)
    manifest_path, _ = runtime.finalize()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["counts"]["late_arrival_count"] == 1
    assert manifest["counts"]["evidence_tube_construction_count"] == 0
    assert "DROPPED_BEFORE_REASONING" in (tmp_path / "packet_events.jsonl").read_text(encoding="utf-8")


def test_variant_patcher_places_observer_hooks_before_core_boundaries(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "route_a_patcher", ROOT / "scripts/prepare_mdmt_mia_route_a_observer_variant.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "demo/utils").mkdir(parents=True)
    (tmp_path / "mmtrack/models/mot").mkdir(parents=True)
    (tmp_path / "demo/supplement_MIA.py").write_text(
        "from utils.cascade_runtime import CascadeEdgeRuntime\n"
        "        cascade_runtime = CascadeEdgeRuntime(args.result_dir, args.method, dirrr)\n"
        "            track_bboxes2 = result2['track_bboxes'][0]\n"
        "            track_bboxes, det_bboxes, A_max_id = packet_runtime.deliver_local_track(\n"
        "                bboxes2 = torch.tensor(next_bboxes2, dtype=torch.long)\n"
        "                ids2 = torch.tensor(next_ids2, dtype=torch.long)\n"
        "                labels2 = torch.tensor(next_labels2, dtype=torch.long)\n"
        "            bboxes2 = torch.tensor(next_bboxes2, dtype=torch.long)\n"
        "            ids2 = torch.tensor(next_ids2, dtype=torch.long)\n"
        "            labels2 = torch.tensor(next_labels2, dtype=torch.long)\n"
        "            # labels2 = torch.zeros_like(torch.tensor(track_bboxes2[:, 0]))\n"
        "        packet_runtime.finalize()\n",
        encoding="utf-8",
    )
    (tmp_path / "mmtrack/models/mot/byte_track.py").write_text(
        "        det_labels = torch.zeros_like(det_labels)\n\n"
        "        track_bboxes, track_labels, track_ids, max_id = self.tracker.track(\n",
        encoding="utf-8",
    )
    module.patch_byte_track(tmp_path)
    module.patch_entry(tmp_path, ROOT / "src/tracking/mdmt_mia_route_a_observer_runtime.py")
    audit = module.audit_variant(tmp_path)
    assert all(audit.values())
