# exp_20260802_002: BoT-SORT candidate gate repair

## Goal

Test whether candidate recall and appearance authority explain the failed
mobile-camera local-tracklet Pilot before changing tracker families.

## Scope

- Reuse audited GMC and frozen OSNet cache
- Scan `proximity_thresh={0.1,0.3,0.5}`
- Compare standard soft appearance cost with OSNet hard identity veto
- Keep GT bbox, frames 0-199, buffer 5, match threshold 0.8
- Do not run Formal unless the full local-readiness gate passes

## Status

- [x] Adapter supports configurable proximity and hard identity veto
- [x] Unit and full regression tests pass
- [x] Pilot 0-199 complete
- [x] Seven-dimension analysis complete
- [x] Formal correctly blocked

## Result

Decision: `hard_veto_tradeoff_only`.

`p=0.3 + hard veto` reaches purity `0.973078` but IDF1 only `0.077409` because
hard-gate same-pair recall is `0.429553`. The best trade-off is `p=0.1 + hard
veto`: IDF1 `0.137546`, purity `0.946417`, coverage `0.997379`. No pipeline
passes readiness, so Formal remains paused. Next compare an OC-SORT baseline.

Outputs remain local under
`outputs/20260802_matrix_botsort_candidate_gate_repair_pilot/`.
