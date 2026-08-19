from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

from tracking.mdmt_mia_async_deadline_runtime import PacketRuntime


ROOT = Path(__file__).resolve().parents[1]


def _rows(track_id: int = 3) -> np.ndarray:
    return np.asarray([[track_id, 10, 20, 30, 40, 0.9]], dtype=np.float32)


def _runtime(tmp_path: Path, monkeypatch, **delays: int) -> PacketRuntime:
    monkeypatch.setenv("MIA_ASYNC_CHANNEL_DELAYS", json.dumps(delays))
    return PacketRuntime(tmp_path, "mia_test_26", "26-1")


def test_delayed_local_preserves_local_rows_but_blocks_cross_view(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, local=2)
    rows = _rows()
    delivered, _, _ = runtime.deliver_local_track(1, 1, rows, np.empty((0, 5), dtype=np.float32), 3)
    assert np.array_equal(delivered, rows)
    runtime.begin_frame(1, rows, rows, [], [])
    assert not runtime.local_cross_view_ready(1)
    runtime.begin_frame(3, rows, rows, [], [])
    _, manifest = runtime.finalize()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["packet_expired_count"] == 1


def test_delayed_homography_uses_latest_arrived_matrix(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, homography=2)
    seed, fresh = np.eye(3), np.eye(3) * 2
    runtime.seed_homography(0, "A_to_B", seed)
    held, _ = runtime.deliver_homography(1, "A_to_B", fresh, seed, 7)
    assert np.array_equal(held, seed)
    runtime.begin_frame(3, _rows(), _rows(), [], [])
    still_latest, _ = runtime.deliver_homography(3, "A_to_B", fresh * 3, fresh, 7)
    assert np.array_equal(still_latest, fresh)


def test_delayed_id_remap_applies_only_after_arrival(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, id_state=1)
    before, after = _rows(3), _rows(2)
    returned = runtime.deliver_id_state(2, "new_A_to_B", before, before, after, before,
                                        [], [], [(2, 3)], [(2, 3)], 3, 3)
    assert int(returned[0][0, 0]) == 3
    rows1, rows2, _, _ = runtime.begin_frame(3, before, before, [], [])
    assert int(rows1[0, 0]) == 2
    assert int(rows2[0, 0]) == 3


def test_delayed_supplement_expires_without_current_frame_mutation(tmp_path: Path, monkeypatch) -> None:
    runtime = _runtime(tmp_path, monkeypatch, supplement=1)
    before, after = _rows(3), _rows(2)
    returned = runtime.deliver_supplement(2, "high_score", before, before, after, after,
                                          [], [], [(2, 3)], [(2, 3)], np.empty((0, 6)), np.empty((0, 6)))
    assert int(returned[0][0, 0]) == 3
    runtime.begin_frame(3, before, before, [], [])
    _, manifest = runtime.finalize()
    assert json.loads(manifest.read_text(encoding="utf-8"))["packet_expired_count"] == 1


def test_async_condition_matrix_matches_predeclared_experiment_grid() -> None:
    path = ROOT / "scripts/phase3_mdmt_mia_async_state_channel_audit.py"
    spec = importlib.util.spec_from_file_location("async_audit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    delays = (0, 1, 2, 5, 10)
    assert len(module.condition_matrix("formal", delays, (1, 5))) == 27
    pilot = module.condition_matrix("pilot", delays, (1, 5))
    assert len(pilot) == 28
    assert pilot[-1][0] == "all_channels_d5_repeat"


def test_confirmed_id_patch_only_emits_currently_paired_h_points(tmp_path: Path) -> None:
    path = ROOT / "scripts/prepare_mdmt_mia_async_packet_variant.py"
    spec = importlib.util.spec_from_file_location("async_patcher", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    common = tmp_path / "demo/utils/common.py"
    common.parent.mkdir(parents=True)
    common.write_text(
        '        if trac_id in coID_confirme:\n'
        '            print("trac_id", trac_id)\n'
        '            matched_ids_cache.append(trac_id)\n'
        '            pts_src.append(cent_allclass[m])\n'
        '            print("cent_allclass[m]", cent_allclass[m])\n'
        '            for n, dots2 in enumerate(track_bboxes2):\n'
        '                trac2_id = dots2[0]\n'
        '                if trac2_id == trac_id:\n'
        '                    pts_dst.append(cent_allclass2[n])\n'
        '                    print("cent_allclass2[n]", cent_allclass2[n])\n'
        '            continue\n',
        encoding="utf-8",
    )
    module.patch_confirmed_match_points(tmp_path)
    patched = common.read_text(encoding="utf-8")
    assert 'pts_src.append(cent_allclass[m])' in patched
    assert 'pts_dst.append(cent_allclass2[n])' in patched
    assert '                    break' in patched
