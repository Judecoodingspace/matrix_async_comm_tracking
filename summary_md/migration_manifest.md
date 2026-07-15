# Migration Manifest

Created for `/home/nvidia/oosm-mdmot-validation` from
`/home/nvidia/uav-multi-collab`.

## Why This Project Exists

The source repository contains a large history of split YOLO, backend semantic
fusion, communication selection, M3OT association, and proposal-calibration
experiments. The new project keeps only the pieces needed to validate OOSM
identity-level tracking hypotheses A1/A2.

## Migrated Code

```text
src/jetson_split_executor.py
src/detection/__init__.py
src/detection/yolo_reid.py
src/detection/osnet_reid.py
scripts/analyze_m3ot_source_alignment.py
scripts/visualize_m3ot_mot_gt.py
scripts/train_m3ot_yolo_reid_head.py
scripts/evaluate_m3ot_osnet_promotion_probe.py
```

## Migrated Checkpoints

```text
weights/m3ot_detector_best.pt
  from outputs/train_m3ot/exp_20260518_001_m3ot_balanced_finetune_eval/weights/best.pt

weights/visdrone_detector_best.pt
  from weights/best.pt

weights/gem_proj_head_l15.pt
  from outputs/m3ot_reid/exp_20260519_001_m3ot_yolo_reid_head_l15_train300_test300_cuda/gem_proj_head.pt
```

## Data Link

```text
data/M3OT -> /home/nvidia/datasets/M3OT_raw/M3OT
```

The raw M3OT `gt.txt` files preserve `track_id` and are required for A1/A2.
The YOLO-converted labels from the old project are not enough for identity
metrics.

## Intentionally Not Migrated

```text
src/compression/
src/phase2_execution/
src/swarm_selection/
scripts/run_backend_review_experiment.py
scripts/run_communication_selection_*.py
scripts/run_multi_front_*.py
old backend_review outputs
old communication_selector outputs
```

These are useful historical baselines but not part of the OOSM validation core.

## Immediate Next Step

Implement `scripts/phase1_identity_probe.py` using:

```text
src/detection/yolo_reid.py::load_mot_gt
src/detection/yolo_reid.py::list_images
weights/m3ot_detector_best.pt
weights/gem_proj_head_l15.pt
configs/m3ot_oosm_smoke.yaml
```

