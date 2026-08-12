# E023 Formal Run Plan

Status: `NOT_READY`

This plan freezes the intended 14-pair run. It does not authorize execution.

## Scientific Questions

The Formal run is a confirmatory test of three predefined questions. It is not
designed to reproduce the direction observed in the two-pair MVE.

1. `Q1 / D_ID`: Does ID-state delay degrade tracking under timely Supplement?
2. `Q2 / C_comp`: Is timely Supplement more valuable when ID state is delayed?
3. `Q3 / R_edge`: Is the net candidate-membership pathway destructive,
   negligible, or compensatory?

All three signs of `R_edge = Yec - Y10` remain admissible. In particular,
`Yec < Y10` must not be treated as an implementation failure when the frozen
causal and measurement gates pass.

## Frozen Cohort

Dataset root:

```text
/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking
```

Official test pairs, fixed before Formal:

```text
26, 31, 34, 48, 52, 55, 56, 57, 59, 61, 62, 68, 71, 73
```

Each pair contains view 1 and view 2. No pair may be removed because of its
observed metric. A technically invalid pair remains an experiment failure until
the predefined clean-restart policy succeeds.

## Frozen Conditions

Local Track and Homography remain timely in every condition. First-frame GT
initialization remains synchronous and is reported separately as offline init.

| Condition | ID delay | Supplement delay | High-score membership |
| --- | ---: | ---: | --- |
| `Y00` | 0 | 0 | synchronous |
| `Y10_d1` | 1 | 0 | `S_delay` |
| `Yec_d1` | 1 | 0 | oracle `S_cf` |
| `Y01_d1` | 0 | 1 | synchronous; Supplement expires |
| `Y11_d1` | 1 | 1 | `S_delay`; Supplement expires |
| `Y10_d5` | 5 | 0 | `S_delay` |
| `Yec_d5` | 5 | 0 | oracle `S_cf` |
| `Y01_d5` | 0 | 5 | synchronous; Supplement expires |
| `Y11_d5` | 5 | 5 | `S_delay`; Supplement expires |

The scientific run matrix is therefore:

```text
14 pairs x 9 conditions = 126 pair-condition runs
```

Detector-cache preparation is infrastructure work and is not an additional
scientific condition.

## Frozen Runtime Inputs

- Detector/tracker: paper-aligned CARAFE + ByteTrack MIA.
- Detector checkpoint:
  `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth`
- Checkpoint SHA256:
  `f50882a6814b08d8f9ee2db278825258b52d16463fff6fb45ff45484df7d9e96`
- Upstream MIA commit: `551f90d998087ea2d02df75700e3c7739c4ecbe1`.
- MMDetection commit: `3b72b12fe9b14de906d1363982b9fba05e7d47c1`.
- Runtime seed: `7`.
- Bootstrap: `10000` paired resamples, seed `7`.
- Device: `cuda:0`.
- No jitter, packet loss, replay, history rewrite, detector retraining or ReID.

The current v4 source manifest SHA256 is:

```text
8c8ba03125c818696c01bc71123a60fcf2b74fa47aeeecec587796d3ae99b840
```

This hash is recorded for readiness evidence only. A new hash produced by an
approved diagnostic or fail-fast correction requires a fresh MVE invariance
gate before Formal.

## Failure And Restart Policy

Every attempt must have a unique attempt ID and manifest containing:

```text
attempt_id
condition
pair_id
start_status
end_status
repository_commit
source/config hashes
clean_start_confirmation
failure_reason
replacement_attempt_id
```

Allowed recovery:

1. Mark the interrupted attempt `ABORTED` and preserve its logs.
2. Exclude every partial output from scientific evaluation.
3. Start the same frozen pair-condition from a clean, isolated attempt root.
4. Record the replacement attempt ID.

Forbidden recovery:

- merging files or tracker state from different attempts;
- treating output-file existence as proof of completion;
- changing parameters for a difficult pair;
- silently replacing or excluding a failed pair;
- resuming tracker state unless an independently validated equivalence gate is
  added to the Contract.

The current launcher does not yet implement this complete policy. This is a
blocking readiness item.

## Immediate Stop Conditions

Formal must stop before launching another pair-condition if any completed
attempt reports:

```text
Y00 reference mismatch
row conservation or selected_Yec != S_cf failure
shadow quarantine or actual-input mutation
future/runtime-GT/source-bypass read
published-history rewrite or feedback mismatch
condition/source/config drift
logging-dependent prediction
partial/corrupt output accepted as complete
```

The current launcher aggregates these gates only after all conditions finish.
Per-attempt fail-fast validation is therefore a blocker.

## Expected Artifacts

- pair- and condition-level MDA/MOTA/IDF1/IDSW;
- `D_ID`, `R_edge`, `M_delay`, `M_sync`, and `C_comp` by delay;
- paired confidence intervals and pair-direction counts;
- complete R5d frame/candidate traces;
- per-attempt manifests and incident records;
- final measurement gate and decision report.

## Launch Boundary

The entry point is frozen as:

```text
scripts/phase3_mdmt_mia_id_supplement_cascade_audit.py --mode formal
```

No executable Formal command is authorized while
`FORMAL_READINESS_REPORT.md` remains `NOT_READY`.
