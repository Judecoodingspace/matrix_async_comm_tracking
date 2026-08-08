# exp_20260804_001: MDMT sync cross-view tracklet association feasibility

## Goal

Before resuming the asynchronous delay sweep, establish synchronous support headroom on MDMT person-only tracklets.

## Work

- Add reject-all calibration fallback and separate measurement/calibration gates.
- Compare online candidate policies and causal OSNet tracklet memories under one-vector packets.
- Add diagnostic Oracle identity, LOSO val calibration, independent gap/AAS bootstrap, and locked Formal config.
- Keep official-test Formal blocked until all val gates pass.

## Acceptance

- Full regression suite and py_compile pass.
- Pilot writes `measurement_valid`, `calibration_feasible`, `sync_headroom_pass`, and `formal_allowed` independently.
- Failed thresholds produce zero runtime associations.
- Formal refuses a config with `formal_allowed=false`.

Labels: `experiment`, `analysis`

