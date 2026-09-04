from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path

import numpy as np
import pytest


E023_RUNTIME = Path(
    "/mnt/data/yzm/experiments/mdmt_mia_official/variants/"
    "packetized_id_supplement_cascade_v8/demo/utils/async_deadline_runtime.py"
)


def _load_e023_runtime():
    spec = importlib.util.spec_from_file_location("e023_y01_runtime", E023_RUNTIME)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PacketRuntime


def _rows(ids: tuple[int, ...]) -> np.ndarray:
    return np.asarray([[track_id, 10, 20, 30, 40, 0.9] for track_id in ids], dtype=np.float32)


def _digest_prediction_state(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for array in arrays:
        value = np.ascontiguousarray(array)
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(str(tuple(value.shape)).encode("ascii"))
        digest.update(value.tobytes())
    return digest.hexdigest()


def _author_prediction_artifact(track_rows_1: np.ndarray, track_rows_2: np.ndarray) -> tuple[bytes, bytes]:
    """Use the frozen E023 `result_dict` -> `json.dump(indent=4)` path.

    The author loop assigns `track_bboxes[:, 0:5].tolist()` to a `frame=<i>`
    key for each view, then writes each dictionary with ``json.dump(indent=4)``.
    This fixture supplies no detector/MIA result; it only gives that frozen
    prediction serialization path the runtime-returned rows.
    """
    artifacts = []
    for rows in (track_rows_1, track_rows_2):
        result_dict = {"frame=4": rows[:, 0:5].tolist()}
        handle = io.StringIO()
        json.dump(result_dict, handle, indent=4)
        artifacts.append(handle.getvalue().encode("utf-8"))
    return tuple(artifacts)


def _run_expired_supplement_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, delay: int) -> dict[str, object]:
    PacketRuntime = _load_e023_runtime()
    monkeypatch.setenv("MIA_ASYNC_CHANNEL_DELAYS", json.dumps({"supplement": delay}))
    runtime = PacketRuntime(tmp_path, "synthetic_y01", "fixture-1")
    before_1, before_2 = _rows((101, 202)), _rows((303, 404))
    after_1, after_2 = _rows((901, 202)), _rows((303, 804))
    supplement_1, supplement_2 = _rows((501,)), _rows((601,))
    runtime.begin_frame(4, before_1, before_2, [101], [101])
    returned = runtime.deliver_supplement(
        4, "high_score", before_1, before_2, after_1, after_2,
        [101], [101], [901], [901], supplement_1, supplement_2,
    )
    # The author performs a second, low-score Supplement delivery before it
    # serializes `result_dict`.  It is also delayed/expired under Y01.
    returned = runtime.deliver_supplement(
        4, "low_score", returned[0], returned[1], after_1, after_2,
        returned[2], returned[3], [901], [901], supplement_1, supplement_2,
    )
    # This is the prediction-facing current-frame state returned to the author
    # loop.  It is intentionally not a transport-trace comparison.
    feedback = runtime.commit_fused_state_to_tracker(4, returned[0], returned[1], 404, 404)
    prediction_1, prediction_2 = _author_prediction_artifact(returned[0], returned[1])
    arrival = 4 + delay
    next_state = runtime.begin_frame(arrival, before_1, before_2, [101], [101])
    trace_path, manifest_path = runtime.finalize()
    trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    expired = [event for event in trace if event["kind"] == "supplement" and event["packet_action"] == "expired"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "arrival": arrival,
        "returned_digest": _digest_prediction_state(returned[0], returned[1], returned[4], returned[5]),
        "feedback_digest": _digest_prediction_state(*feedback[2:]),
        "next_state_digest": _digest_prediction_state(next_state[0], next_state[1]),
        "prediction_view1_bytes": prediction_1,
        "prediction_view2_bytes": prediction_2,
        "prediction_view1_sha256": hashlib.sha256(prediction_1).hexdigest(),
        "prediction_view2_sha256": hashlib.sha256(prediction_2).hexdigest(),
        "expired": expired,
        "manifest": manifest,
    }


def test_y01_positive_supplement_delays_share_prediction_facing_expired_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = {
        delay: _run_expired_supplement_fixture(tmp_path / f"d{delay}", monkeypatch, delay)
        for delay in (1, 3, 5)
    }
    assert {result["arrival"] for result in results.values()} == {5, 7, 9}
    assert len({result["returned_digest"] for result in results.values()}) == 1
    assert len({result["feedback_digest"] for result in results.values()}) == 1
    assert len({result["next_state_digest"] for result in results.values()}) == 1
    assert len({result["prediction_view1_bytes"] for result in results.values()}) == 1
    assert len({result["prediction_view2_bytes"] for result in results.values()}) == 1
    for delay, result in results.items():
        assert len(result["expired"]) == 2
        assert result["expired"][0]["capture_frame"] == 4
        assert result["expired"][0]["arrival_frame"] == 4 + delay
        assert result["manifest"]["packet_expired_count"] == 2
