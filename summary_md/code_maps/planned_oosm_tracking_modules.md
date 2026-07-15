# OOSM Tracking Modules Code Map

## Purpose

Small module boundaries for Phase 1/2 OOSM validation. The current Phase 2
implementation is controlled GT-box + ReID, not detector end-to-end.

## Files

```text
src/tracking/delay_injection.py
src/tracking/oosm_baselines.py
src/tracking/mot_metrics.py
scripts/phase1_identity_probe.py
scripts/phase2_candidate_geometry_stress.py
scripts/phase2_backfill_vs_current.py
scripts/phase2_gated_oosm.py
scripts/phase2_common.py
```

## `delay_injection.py`

Responsibilities:

- deterministic per-observation delay assignment
- support `UniformInt(1, T_max)` initially
- preserve both `capture_time` and `arrival_time`
- keep seed/distribution serializable in config/output metadata

## `oosm_baselines.py`

Responsibilities:

- run controlled `discard_oosm`, `fuse_at_current`, `backfill`, and
  `fuse_at_current_exp_decay`
- run `event_gated_backfill` for the Phase 2c follow-up
- maintain a small ReID prototype tracker over base GT-box observations
- associate support OOSM updates by nearest prototype
- schedule Backfill evidence at `capture_time`
- schedule Fuse-at-current evidence at `arrival_time`
- schedule exp decay evidence at `arrival_time` with
  `w = exp(-ln(2) * delay / 10)`
- gate event Backfill with observable capture/arrival candidate geometry and
  support-to-prototype margin

Avoid adaptive windows until A2 passes.

## `mot_metrics.py`

Responsibilities:

- compute compact IDF1, IDSW, and MOTA for controlled GT-box tracker outputs
- use Hungarian global ID matching via `scipy.optimize.linear_sum_assignment`
- produce stable CSV rows for Phase 2

## `phase1_identity_probe.py`

Responsibilities:

- load source GT images
- inject support-view delays
- extract/load ReID features
- write `phase1_similarity_vs_delay.csv`
- write delay/similarity plot and IDSW proxy note

## `phase2_candidate_geometry_stress.py`

Responsibilities:

- compare capture-time vs arrival-time candidate geometry
- label `geometry_flip`, `arrival_ambiguous`, `history_gap`, and
  `stable_control`
- write `phase2a_candidate_geometry.csv`
- write `phase2a_mechanism_decision.md`

This is a mechanism probe only, not the formal A2 tracker metric.

## `phase2_backfill_vs_current.py`

Responsibilities:

- run the four OOSM handling baselines
- write `phase2_tracking_metrics.csv`
- write `phase2_decision.md`
- apply A2 decision rule

## `phase2_gated_oosm.py`

Responsibilities:

- compare `event_gated_backfill` against `Discard OOSM`,
  `Fuse-at-current + exp decay`, and global `Backfill`
- write `phase2c_gated_tracking_metrics.csv`
- write `phase2c_gated_decision.md`
- reject gated Backfill unless it beats both hard baselines and does not
  increase IDSW over `Discard OOSM`

## `phase2_common.py`

Responsibilities:

- reuse Phase 1 GT bbox ROI extraction and ReID embedding code
- return base embeddings, support embeddings, delayed observations, resolved
  frame range, and device
- keep Phase 2a and Phase 2b on the same feature source
