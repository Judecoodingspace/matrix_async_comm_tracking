from tracking.mot_metrics import Prediction, compute_identity_metrics


def test_metrics_no_switch_perfect_identity() -> None:
    predictions = [
        Prediction(frame_id=1, gt_id=1, pred_id=10),
        Prediction(frame_id=2, gt_id=1, pred_id=10),
        Prediction(frame_id=1, gt_id=2, pred_id=20),
        Prediction(frame_id=2, gt_id=2, pred_id=20),
    ]
    metrics = compute_identity_metrics(predictions)
    assert metrics.idf1 == 1.0
    assert metrics.idsw == 0
    assert metrics.mota == 1.0


def test_metrics_counts_one_id_switch() -> None:
    predictions = [
        Prediction(frame_id=1, gt_id=1, pred_id=10),
        Prediction(frame_id=2, gt_id=1, pred_id=11),
        Prediction(frame_id=3, gt_id=1, pred_id=11),
    ]
    metrics = compute_identity_metrics(predictions)
    assert metrics.idsw == 1
    assert metrics.mota == 1.0 - (1.0 / 3.0)
    assert metrics.idf1 == 2.0 / 3.0
