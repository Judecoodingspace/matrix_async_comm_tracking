# Route-A Observer MVE-0 Change Explainer

## Purpose

`exp_20260822_001_mdmt_mia_route_a_observer_mve` adds observation provenance
and causal side-state only. The implementation cannot create candidates while
`CROSS_VIEW_GEOMETRY_GATE=FAIL`, and it has no tracker/MIA consumer.

## Source boundaries

| Boundary | Change | Core effect |
| --- | --- | --- |
| detector output → ByteTrack | `RouteAObserverRuntime.capture_preassociation_detector()` is called after `results2outs()` and before `self.tracker.track()` | Copies detector rows only; no return value. |
| local ByteTrack output → MIA | `capture_receiver_snapshot()` is called for both views immediately after author `inference_mot()` output and before `deliver_local_track()` or MIA mutation | Copies tracker rows only. |
| delayed packet arrival | `process_arrivals()` maintains its own five-frame queue | `DROP_LATE` discards; Route A builds a side-only tube; no candidate with geometry FAIL. |
| post-core output | `record_core_and_feedback()` hashes published rows and next-frame feedback | Logs hashes only. |

## Files

- `src/tracking/mdmt_mia_route_a_observer_runtime.py`: independent ledger,
  packet schema, tube, diagnostics, and fail-closed geometry record.
- `scripts/prepare_mdmt_mia_route_a_observer_variant.py`: makes a detached copy
  of frozen E023 v8 and patches only the hook anchors above.
- `scripts/run_mdmt_mia_route_a_observer_mve.py`: creates detector-cache seeds,
  runs the frozen seven-run matrix, and rejects digest inequality.
- `tests/test_mdmt_mia_route_a_observer_runtime.py`: tests tube construction,
  no-candidate geometry behavior, and patch-boundary ordering.

## Explicit non-changes

The implementation does not change ByteTrack association results, tracker state,
IDs, NMS, MIA H/ID/Supplement logic, next-frame feedback, GT access, shadow
membership, ReID, or any recovery policy. Its observed core/feedback digest
equality against `DROP_LATE` is the run-time evidence for those boundaries.
