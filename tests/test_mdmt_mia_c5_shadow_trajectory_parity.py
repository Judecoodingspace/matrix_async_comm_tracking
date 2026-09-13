from tracking.mdmt_mia_async_deadline_runtime import _C4SharedLogicalServer


class FailingShadow(object):
    def __init__(self):
        self.failures = 0

    def observe_first_service(self, item, context):
        raise RuntimeError("synthetic shadow fault")

    def _failure(self, stage, error):
        self.failures += 1


def _run(observer=None):
    server = _C4SharedLogicalServer("fifo", 5, ledger_enabled=False)
    server.begin_frame(0, observer, lambda packet_id, frame: None)
    server.admit("id_state", 0, {"kind": "id_state"}, "abcdefgh", "digest", None, 0,
                 observer, lambda packet_id, frame: None)
    server.begin_frame(1, observer, lambda packet_id, frame: None)
    server.finalize_pending(1)
    return server.normalized_events()


def test_shadow_callback_failure_preserves_c4_service_trajectory():
    baseline = _run()
    failing = FailingShadow()
    observed = _run(failing)
    assert observed == baseline
    assert failing.failures == 1
