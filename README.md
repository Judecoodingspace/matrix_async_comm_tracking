# OOSM MDMOT Validation

Minimal project for validating whether delayed cross-view observations help
identity-level multi-drone tracking.

The current research question is not split YOLO or backend semantic fusion. The
first goal is to falsify or support two assumptions:

- A1: delayed OOSM observations contain useful identity information that
  in-sequence observations do not fully preserve.
- A2: backfilling delayed observations to their capture time is meaningfully
  better than fusing them at arrival time.

## Current Assets

Data is linked rather than copied:

```text
data/M3OT -> /home/nvidia/datasets/M3OT_raw/M3OT
```

Migrated checkpoints:

```text
weights/m3ot_detector_best.pt
weights/visdrone_detector_best.pt
weights/gem_proj_head_l15.pt
```

`m3ot_detector_best.pt` is the preferred detector for M3OT RGB/IR work.
`visdrone_detector_best.pt` is retained only as a historical baseline.

## Useful Starting Sequences

The first smoke should use synchronized M3OT RGB validation streams:

```text
data/M3OT/1/rgb/val/1-08/img1
data/M3OT/1/rgb/val/1-08/gt/gt.txt
data/M3OT/2/rgb/val/2-08/img1
data/M3OT/2/rgb/val/2-08/gt/gt.txt
```

These streams have 600 aligned frames and 4530 shared `(frame_id, track_id)`
pairs, so they are suitable for the A1/A2 smoke.

## Migrated Code

Reusable source:

```text
src/detection/yolo_reid.py
src/detection/osnet_reid.py
src/jetson_split_executor.py
```

Reference scripts:

```text
scripts/analyze_m3ot_source_alignment.py
scripts/visualize_m3ot_mot_gt.py
scripts/train_m3ot_yolo_reid_head.py
scripts/evaluate_m3ot_osnet_promotion_probe.py
```

These scripts are migration references, not the final OOSM experiment API.
New A1/A2 scripts should be smaller and tracker-focused.

## Experiment Records

Research state is tracked in Markdown, not only terminal output:

```text
summary_md/current_experiment_stage.md
summary_md/current_status.md
summary_md/experiments/INDEX.md
summary_md/codex_notes/
summary_md/decisions/
summary_md/code_maps/
summary_md/analysis_framework.md
```

## Experiment Flowcharts

Mermaid diagrams for experiment design visualization:

```text
mermaid/README.md
mermaid/templates/
mermaid/exp_XXXX/
```

ASCII concept diagrams for quick experiment catch-up:

```text
ascii_diagrams/README.md
```

## Terminology

```text
GLOSSARY.md     # living glossary — plain-language analogies + precise definitions
```

Every formal run should have an experiment card under:

```text
summary_md/experiments/YYYY-M-D/
```

Raw run artifacts belong under `outputs/`, but reusable conclusions must be
summarized in `summary_md/`.

## Next Implementation Targets

```text
scripts/phase1_identity_probe.py
scripts/phase2_backfill_vs_current.py
src/tracking/delay_injection.py
src/tracking/oosm_baselines.py
src/tracking/mot_metrics.py
```

Phase 1 should write:

```text
outputs/20260616_oosm_backfill_validation/phase1_similarity_vs_delay.csv
outputs/20260616_oosm_backfill_validation/phase1_similarity_vs_delay.png
outputs/20260616_oosm_backfill_validation/idsw_correlation_by_delay.md
```

Phase 2 should write:

```text
outputs/20260616_oosm_backfill_validation/phase2_tracking_metrics.csv
outputs/20260616_oosm_backfill_validation/phase2_decision.md
```
