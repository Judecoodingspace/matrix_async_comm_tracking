# MVE-0 Results

## Scope and verdict boundary

This is an observer-only plumbing and invariance result. It is not an identity,
tracking-performance, lineage, or Route-A mechanism result.

- Verdict: `MVE_INCONCLUSIVE_DUE_TO_GEOMETRY`
- `CROSS_VIEW_GEOMETRY_GATE=FAIL`
- MVE-1 executed: `0`
- Cross-view candidates created: `0`

The required independent, causally available transform was absent. The runtime
therefore recorded `NOT_APPLICABLE_GEOMETRY_FAIL_CLOSED` for A12 and emitted no
cross-view candidate or side hypothesis.

## Completed matrix

- Detector-cache seeds: Pair 26 and Pair 48, frozen v8, write mode.
- MVE-0: Pair 26 and Pair 48 × `DROP_LATE`, `NAIVE_ARRIVAL`, and
  `ROUTE_A_OBSERVER_MVE`.
- Exact repeat: Pair 48 × `ROUTE_A_OBSERVER_MVE`.
- Completed MVE pair-runs: `7/7`.
- First launch aborted before a seed run could start because relative paths were
  evaluated from the attempt cwd. It is retained under
  `outputs/20260822_mdmt_mia_route_a_observer_mve_aborted_infra_001/`.
  The one permitted clean restart used unchanged scientific inputs.

## Observer measurements

| Pair | Condition | Source observations | Late arrivals | Tubes | Candidates | Tracker mutations |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 26 | DROP_LATE | 24,569 | 24,132 | 0 | 0 | 0 |
| 26 | NAIVE_ARRIVAL | 24,569 | 24,132 | 0 | 0 | 0 |
| 26 | ROUTE_A_OBSERVER_MVE | 24,569 | 24,132 | 24,132 | 0 | 0 |
| 48 | DROP_LATE | 29,909 | 29,648 | 0 | 0 | 0 |
| 48 | NAIVE_ARRIVAL | 29,909 | 29,648 | 0 | 0 | 0 |
| 48 | ROUTE_A_OBSERVER_MVE | 29,909 | 29,648 | 29,648 | 0 | 0 |
| 48 | ROUTE_A_OBSERVER_MVE (repeat) | 29,909 | 29,648 | 29,648 | 0 | 0 |

`packet_not_yet_arrived_count` is 437 for Pair 26 and 261 for Pair 48 because
the full inherited sequence ends before those final emitted packets can arrive.
They were not consumed.

## Safety and determinism gates

- A1–A11: PASS in every completed run.
- A12: `NOT_APPLICABLE_GEOMETRY_FAIL_CLOSED` in every completed run; this is the
  registered MVE-0 boundary, not an A12 pass.
- Core and next-frame-feedback digest equality: passed for Naive and Route A
  against `DROP_LATE` on both pairs (299 frames on Pair 26; 699 on Pair 48).
- Pair-48 Route-A repeat: exact digest equality across all 699 frames.
- `tracker_mutation_count`, `core_output_digest_mismatch_count`, and
  `feedback_digest_mismatch_count`: all zero.

## Raw evidence

All raw artifacts are under
`outputs/20260822_mdmt_mia_route_a_observer_mve/`, especially
`manifest.json`, `geometry_provenance.json`, `condition_summary.csv`,
`hard_assertions.csv`, and `tracker_invariance.csv`.

No MVE-1, recovery design, tracker correction, or performance analysis was run.
