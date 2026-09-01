# ROUTE A MVE INFRA IMPLEMENTATION REPORT

Scope: minimal observer-only infrastructure and non-interference validation.
No spatial candidate generation, geometry, scoring, ranking, commit, recovery,
tracker correction, GT, or tracking-performance evaluation was added.

## 1. Files changed

The non-Git MIA source snapshot at
`/mnt/data/yzm/experiments/mdmt_mia_official/variants/route_a_observer_mve0_v1`
changed only in these files:

- `demo/utils/route_a_observer_runtime.py` — run-scoped side bookkeeping.
- `mmtrack/models/mot/byte_track.py` — attach the existing observer and view to
  its local tracker before tracking.
- `mmtrack/models/trackers/byte_tracker.py` — observe final output IDs,
  materialization, and imminent removal; no return value or core argument is
  changed.
- `demo/utils/async_deadline_runtime.py` — forward an already-applied runtime-ID
  remap to the observer.
- `demo/supplement_MIA.py` — attach the existing pair-scoped observer to the
  existing packet runtime and read `MIA_ROUTE_A_INFRA_ENABLED`.
- `demo/utils/test_route_a_observer_infrastructure.py` — synthetic-only
  infrastructure invariants.
- `route_a_observer_manifest.json` — updated changed-file list and SHA-256
  provenance.

`SOURCE-PROVEN FACT` — the source snapshot is not a Git worktree. Pre-change
copies of the five modified source files are retained at
`/tmp/routea_infra_backup` for this session's diff audit.

## 2. Observation identity

`SOURCE-PROVEN FACT` — the existing observation key remains unchanged:
`[view_id, capture_frame, detector_row_index]`. No tuple conversion, packet
digest change, detector hook move, or detector-row schema change was made.

`TEST-PROVEN` — disabled/enabled Pair-26 runs each emitted 24,569 source
observations; normalized source-observation records are exactly equal.

## 3. Receiver lineage implementation

- **Birth anchor:** final `ByteTracker.track()` output IDs are observed after
  the existing frame-0 override and immediately before the unchanged return.
  An unknown `(view_id, runtime_id)` receives one lineage key.
- **Key format:** `(view_id, lineage_sequence)`, held internally as an immutable
  tuple and serialized as a two-integer JSON list. Sequence is run-scoped,
  monotonic per view, and never decremented or reused.
- **Runtime-ID mapping:** the observer owns
  `(view_id, runtime_id) -> lineage_key`. `ByteTracker.init_track()` is only a
  non-duplicating materialization fallback, not a second birth allocator.
- **Remap preservation:** after the existing packet runtime writes the existing
  ID remap to the row, it reports that event to the observer. The new runtime ID
  becomes an alias of the existing lineage; it cannot allocate a new key.
- **Lost/reactivation:** no state is changed on a gap. If the retained runtime
  ID reappears, its existing mapping resolves to the same lineage.

`SOURCE-PROVEN FACT` — no lineage method returns a value to ByteTrack, MIA, or
feedback. Receiver snapshots add only observer-output fields.

## 4. Tombstone implementation

- **Death anchor:** immediately before the existing `self.tracks.pop()` in
  `ByteTracker.pop_invalid_tracks()`.
- **Record:** exactly `lineage_key`, `birth_frame`, `death_frame` in
  `receiver_tombstones.jsonl`.
- **Alias rule:** removal of an old runtime-ID alias after a remap does not end
  the lineage while another alias remains; only removal of the final alias emits
  a tombstone.
- **Retention/reset:** all lifecycle state is held by one observer runtime and
  `reset_infrastructure()` clears it without touching the tracker. No bbox,
  Kalman, appearance, feature, cost, or matching history is retained.

`TEST-PROVEN` — the enabled Pair-26 run emitted 704 tombstones. The synthetic
test verifies a death after a remap does not tombstone the lineage until the
final alias dies, and a later reuse of the same runtime ID receives a new key.

## 5. Hypothesis history implementation

`SOURCE-PROVEN FACT` — `observe_hypothesis_newness()` stores only the key
`(source_observation_key, receiver_lineage_key)` with its
`first_seen_frame`. It reports `NEW`, `NOT_NEW`, or
`NEWNESS_UNRESOLVABLE_DUE_TO_MISSING_LINEAGE` and is never called by current
arrival processing.

`TEST-PROVEN` — synthetic checks pass for first appearance, repeated pair,
different observation, different lineage, and missing lineage. This API does
not create a Route-A candidate or assert a scientific opportunity.

## 6. Infrastructure invariant tests

| Invariant | Status | Evidence |
| --- | --- | --- |
| birth → one new lineage | PASS | synthetic test |
| normal update → same lineage | PASS | synthetic test |
| lost → re-active → same lineage | PASS | synthetic test |
| runtime-ID remap → same lineage | PASS (synthetic) | synthetic test |
| true death → tombstone | PASS | synthetic test; 704 Pair-26 tombstones |
| runtime-ID reuse → new lineage | PASS (synthetic) | synthetic test |
| live lineage death frame is null | PASS (synthetic) | lifecycle object before death |
| reset clears run-scoped side lifecycle/history | PASS (synthetic) | synthetic test |
| first-seen history semantics | PASS (synthetic) | synthetic test |
| missing lineage fail-closed | PASS (synthetic) | synthetic test |
| actual runtime-ID remap in Pair-26 | NOT EXERCISED | enabled event count has no remap event |

The synthetic command was:

```bash
python3 demo/utils/test_route_a_observer_infrastructure.py
```

It printed `ROUTE_A_OBSERVER_INFRA_TEST_PASS`. It is not a Route-A scientific
result.

## 7. Non-interference validation

- **Baseline:** frozen Pair-26, `ROUTE_A_OBSERVER_MVE`, complete 300-frame
  inherited run, cached detections read from the frozen 2026-08-22 MVE-0 cache.
- **A:** `MIA_ROUTE_A_INFRA_ENABLED=0`.
- **B:** identical command/input/cache with `MIA_ROUTE_A_INFRA_ENABLED=1`.
- **Output:**
  [comparison JSON](/mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/outputs/20260829_route_a_mve_infra_noninterference/non_interference_comparison.json)

`TEST-PROVEN` — `CORE_OUTPUT_DIFF = 0`.

| Compared observable | Result |
| --- | --- |
| detector/source observation semantics | equal, 24,569 rows each |
| post-ByteTrack/pre-MIA row semantics | equal, 22,692 rows each |
| MIA arrival/tube/candidate semantics | equal, 24,132 arrivals each; 0 candidates |
| core and next-frame feedback digest ledger | byte-identical SHA-256 `8e2896…088f2` |
| final view-1 tracking JSON | byte-identical SHA-256 `dc5441…cfc0` |
| final view-2 tracking JSON | byte-identical SHA-256 `b60daf…fd1c` |
| tracker mutation count | 0 in both runs |

Observer `sequence`, receiver-lineage fields, and their derived snapshot digest
were deliberately excluded from the observer-log semantic comparison: enabled
mode creates additional side records and therefore advances only the observer's
own sequence counter.

## 8. Scientific boundary audit

| Core path | Finding |
| --- | --- |
| detector / threshold | NO CHANGE SOURCE/TEST PROVEN |
| ByteTrack matching, cost, assignment | NO CHANGE SOURCE/TEST PROVEN; no matching input or return changed, observable rows equal |
| Kalman mean / covariance | NO CHANGE SOURCE/TEST PROVEN; no new access or write, core digest equal |
| track survival / expiry timing | NO CHANGE SOURCE/TEST PROVEN; hook precedes unchanged pop only |
| runtime IDs / remap semantics | NO CHANGE SOURCE/TEST PROVEN; row semantics and final JSON equal |
| NMS | NO CHANGE SOURCE/TEST PROVEN; final tracking JSON and core digest equal |
| MIA association | NO CHANGE SOURCE/TEST PROVEN; no new input/return and candidate semantics equal |
| feature bank | NO CHANGE SOURCE/TEST PROVEN; no new access exists |
| feedback / next-frame state | NO CHANGE SOURCE/TEST PROVEN; feedback digest ledger byte-identical |

## 9. Remaining blockers

- An independently causal, candidate-independent spatial context is still
  absent; MVE-0 remains geometry fail-closed.
- No authorized spatial hard-impossible gate or candidate-generation path
  exists. The history API must not be invoked as a scientific candidate result
  until a separate research decision authorizes that layer.
- Runtime-ID remap continuity has passed only a synthetic infrastructure test;
  it did not occur in the fixed Pair-26 non-interference run.

## 10. Final verdict

`MINIMAL_INFRASTRUCTURE_READY_FOR_ROUTE_A_MVE`

This verdict means the observer-only lineage, tombstone, and newness-history
infrastructure is implemented and passed the defined non-interference check. It
does not authorize, implement, or demonstrate
`NEW_ASSOCIATION_OPPORTUNITY_CREATED`.
