# ROUTE A MVE INFRA IMPLEMENTATION PLAN

## A. Files to modify

- `demo/utils/route_a_observer_runtime.py`
- `mmtrack/models/mot/byte_track.py`
- `mmtrack/models/trackers/byte_tracker.py`
- `demo/utils/async_deadline_runtime.py`
- `demo/supplement_MIA.py`
- a small observer-infrastructure unit test beside the observer helper

## B. For each file

- `route_a_observer_runtime.py`: add run-scoped, side-only lineage mapping,
  lifecycle/tombstone records, receiver-snapshot lineage resolution, and a
  three-field hypothesis-history API. This closes the lineage, tombstone, and
  newness-history gaps.
- `byte_track.py`: pass the already-attached observer and view to the local
  tracker before it runs. This is plumbing only; detector capture remains
  unchanged.
- `byte_tracker.py`: observe final returned tracker IDs as the sole normal birth
  anchor; observe `init_track` only as a non-duplicating materialization
  fallback; observe invalid IDs immediately before the existing pop. This closes
  lineage birth and death observation without changing matching or state.
- `async_deadline_runtime.py`: forward an already-decided MIA runtime-ID remap
  to the observer after the existing row mutation. This preserves a side
  lineage across a remap without changing the remap.
- `supplement_MIA.py`: attach the pair-scoped observer to the existing packet
  runtime. No ordering, payload, or feedback change.
- unit test: exercise only synthetic side infrastructure events, including
  birth, update, loss/reactivation, remap, death/reuse, tombstone reset and
  hypothesis first-seen behavior.

## C. Explicit files NOT to modify

- detector code, detector thresholds, configs, SIFT/FLANN/H/G15c code
- MIA matching/supplement helpers, NMS, Kalman implementation, feature bank
- candidate-generation, scoring, ranking, commit, feedback, or tracker APIs
- existing formal results, Pair selection, GT/XML/MDA evaluation code

## D. Non-interference strategy

All hooks are `None`-returning observer calls after their core decision or
immediately before an unchanged removal. The observer receives copied/scalar
metadata only and never supplies a tracker/MIA input. First run synthetic
invariant tests; then run a fixed small MVE-0 baseline with infrastructure
disabled/enabled and compare pre-existing core/feedback digests plus final
tracking outputs. Any core difference is `NON_INTERFERENCE_FAIL` and stops the
work.

## E. Stop conditions

- Any core-output, feedback, runtime-ID, or tracker-state difference.
- A source conflict preventing immutable lineage preservation across remap.
- Missing runtime prerequisites that prevent the required non-interference
  comparison.

On a stop condition, write the report and do not enter candidate generation or
a Route A scientific experiment.
