# exp_20260802_001: mobile-camera local tracklet readiness

## Goal

Qualify a mature per-UAV local tracker before asynchronous global tracklet fusion.

## Scope

- GT projected bbox + LoS, score 1.0
- Ultralytics BoT-SORT 8.4.113
- sparse optical-flow GMC ablation
- frozen OSNet ablation
- no personID, world-XY association, D1 occlusion label, or future-frame runtime input
- Pilot 0-199 locks config; Formal 180-999 evaluates 200-999

## Readiness Gate

- macro local IDF1 >= 0.80
- weighted purity >= 0.95
- minimum per-view local IDF1 >= 0.70
- correct active support coverage during D1 occlusion >= 0.90

## Status

- [x] Adapter and runner implemented
- [x] Unit/integration tests implemented
- [x] Experiment card and flowchart added
- [x] Prepare complete all-view OSNet cache
- [x] Pilot config selection
- [ ] Formal evaluation
- [x] Seven-dimension analysis

Pilot decision: `local_tracklet_quality_still_blocked`. Formal was deliberately
not run. The follow-up candidate-gate repair is tracked in `exp_20260802_002`.

Outputs remain local under `outputs/` and are not committed.
