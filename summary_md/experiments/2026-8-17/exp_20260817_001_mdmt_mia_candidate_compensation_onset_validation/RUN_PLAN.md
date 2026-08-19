# RUN_PLAN

Status: `NOT EXECUTABLE — R1-R3 RESOLVED; IMPLEMENTATION AND GT PROTOCOL GATE
PENDING`

The commands below define the intended interface. They must not be run until
the matching files exist, tests pass and the preceding gate is explicitly
authorized.

## Frozen Research Policy

- R1: deterministic train/val MDA GT conversion is conditionally approved only
  after exact official-test row/frame/ID reproduction and a separate non-test
  structural and cross-view identity-semantics audit. The converter has no
  semantic repair authority.
- R2: canonically order the 25 train pairs, then use the fixed split algorithm
  with `seed=7` once to freeze 15 development and 10 train-holdout pairs. Keep
  the five MDMT val pairs as a separately reported cross-MDMT-split holdout.
- R3: scan only `d1..d5` and select the earliest delay passing Contract Gate
  A-F. Gate F requires actual delay-only candidate -> High-score Supplement
  write-in in at least `10/15` development pairs.
- If no delay passes Gate A-F, stop before confirmation and report no reliable
  onset within d1-d5. A `d6+` sweep requires a new experiment registration.

No command in this file was generated or executed as part of recording these
decisions.

## 0. Environment

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking

export MIA_ROOT=/mnt/data/yzm/experiments/mdmt_mia_official
export MDMT_ROOT=/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking
export MIA_PYTHON="$MIA_ROOT/.conda-env/bin/python"
```

## 1. Protocol Equivalence

Generate train/val MDA GT only after exact official-test reproduction:

```bash
PYTHONNOUSERSITE=1 PYTHONPATH=src \
"$MIA_PYTHON" scripts/prepare_mdmt_non_test_mda_gt.py \
  --dataset-root "$MDMT_ROOT" \
  --official-test-gt-root data/MDMT_official_mda_gt \
  --splits train val test \
  --seed 7 \
  --output-dir outputs/20260817_mdmt_non_test_mda_gt_protocol
```

Required decision before continuing:

```text
non_test_gt_protocol_equivalent
```

## 2. Isolated Variant

```bash
PYTHONNOUSERSITE=1 PYTHONPATH=src \
"$MIA_PYTHON" scripts/prepare_mdmt_mia_onset_validation_variant.py \
  --source-root "$MIA_ROOT/variants/packetized_id_supplement_cascade_v8" \
  --variant-root "$MIA_ROOT/variants/packetized_candidate_compensation_onset_v1" \
  --copy-source
```

## 3. Unit And Static Verification

```bash
PYTHONPATH=src "$MIA_PYTHON" -m pytest \
  tests/test_mdmt_mia_candidate_compensation_onset.py -q

PYTHONPATH=src "$MIA_PYTHON" -m py_compile \
  scripts/prepare_mdmt_non_test_mda_gt.py \
  scripts/prepare_mdmt_mia_onset_validation_variant.py \
  scripts/phase3_mdmt_mia_candidate_compensation_onset.py
```

## 4. Two-Pair MVE

```bash
PYTHONNOUSERSITE=1 PYTHONPATH=src \
"$MIA_PYTHON" scripts/phase3_mdmt_mia_candidate_compensation_onset.py \
  --mode mve \
  --mia-root "$MIA_ROOT" \
  --dataset-root "$MDMT_ROOT" \
  --non-test-mda-gt-root outputs/20260817_mdmt_non_test_mda_gt_protocol/generated_gt \
  --onset-source "$MIA_ROOT/variants/packetized_candidate_compensation_onset_v1" \
  --split val \
  --pair-ids 22 72 \
  --delay-frames 1 3 5 \
  --seed 7 --device cuda:0 \
  --progress-every 1 --resume \
  --run-id exp_20260817_001_onset_mve_v1 \
  --output-dir outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/mve
```

Do not continue until an MVE audit explicitly writes `development_allowed=1`.

## 5. Development Sweep

```bash
PYTHONNOUSERSITE=1 PYTHONPATH=src \
"$MIA_PYTHON" scripts/phase3_mdmt_mia_candidate_compensation_onset.py \
  --mode development \
  --mia-root "$MIA_ROOT" \
  --dataset-root "$MDMT_ROOT" \
  --non-test-mda-gt-root outputs/20260817_mdmt_non_test_mda_gt_protocol/generated_gt \
  --onset-source "$MIA_ROOT/variants/packetized_candidate_compensation_onset_v1" \
  --cohort-manifest outputs/20260817_mdmt_non_test_mda_gt_protocol/cohort_manifest.csv \
  --delay-frames 1 2 3 4 5 \
  --mve-evidence-dir outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/mve/evaluation \
  --seed 7 --bootstrap-reps 10000 --device cuda:0 \
  --progress-every 1 --resume \
  --run-id exp_20260817_001_onset_development_v1 \
  --output-dir outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/development
```

This run may write `onset_selection.json` exactly once. Do not edit that file.

## 6. Holdout Confirmation

```bash
PYTHONNOUSERSITE=1 PYTHONPATH=src \
"$MIA_PYTHON" scripts/phase3_mdmt_mia_candidate_compensation_onset.py \
  --mode confirm \
  --mia-root "$MIA_ROOT" \
  --dataset-root "$MDMT_ROOT" \
  --non-test-mda-gt-root outputs/20260817_mdmt_non_test_mda_gt_protocol/generated_gt \
  --onset-source "$MIA_ROOT/variants/packetized_candidate_compensation_onset_v1" \
  --cohort-manifest outputs/20260817_mdmt_non_test_mda_gt_protocol/cohort_manifest.csv \
  --onset-selection outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/development/onset_selection.json \
  --development-evidence-dir outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/development/evaluation \
  --seed 7 --bootstrap-reps 10000 --device cuda:0 \
  --progress-every 1 --resume \
  --run-id exp_20260817_001_onset_confirm_v1 \
  --output-dir outputs/20260817_mdmt_mia_candidate_compensation_onset_validation/confirmation
```

## 7. Analysis

After the confirmation run finishes:

1. Build an observation-only evidence package.
2. Apply `ANALYSIS_PLAN.md` without changing the registered rules.
3. Complete `RESULTS.md` and `DECISION.md`.
4. Update current stage/status and the experiment index.
5. Create a separate recovery contract only if the final decision permits it.
