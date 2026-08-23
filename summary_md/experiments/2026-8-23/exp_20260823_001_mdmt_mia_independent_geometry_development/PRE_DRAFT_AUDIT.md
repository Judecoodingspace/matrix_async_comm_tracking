# PRE-DRAFT AUDIT

## 1. Files actually read

- Project rules/state: `AGENTS.md`, `README.md`, `spec.md`,
  `summary_md/current_experiment_stage.md`, `summary_md/current_status.md`, and
  the Route-A row in `summary_md/experiments/INDEX.md`.
- Planning rules: `.agents/skills/research-planner/SKILL.md` and
  `references/experiment-contract-template.md`.
- Parent experiment:
  `summary_md/experiments/2026-8-22/exp_20260822_001_mdmt_mia_route_a_observer_mve/`
  `EXPERIMENT_CONTRACT.md`, `EXEC_PLAN.md`, `RESULTS.md`, and `DECISION.md`.
- Route-A evidence: `learning/MVE_CHANGE_EXPLAINER.md` and
  `learning/ROUTE_A_CROSS_VIEW_GEOMETRY_SOURCE_AUDIT.md`.
- Active inherited source under
  `/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_id_supplement_cascade_v8/`:
  `demo/supplement_MIA.py`, `demo/utils/matching_pure.py`,
  `demo/utils/trans_matrix.py`, and `demo/utils/common.py`.
- MDMT train directory names and image-name sets only. No image content,
  XML/GT, SIFT output, H output, tracker output, or Route-A outcome was read.

`experiment_validation_plan.md`, named by `AGENTS.md`, is not present in this
workspace. The workspace root is also not a Git worktree, so the requested
branch cannot be verified locally.

## 2. Actual original MIA global-SIFT call chain

```text
supplement_MIA.py
  current tracker rows
    -> calculate_cent_corner_pst
    -> get_matched_ids
    -> pts_src / pts_dst
    -> supp_compute_transf_matrix(pts_src, pts_dst, f_last, image1, image2)
         if matched-row points >= 5:
           findHomography(matched target centres)
         else:
           matching(image1, image2) three times
             -> SIFT detectAndCompute
             -> FLANN KNN
             -> Lowe ratio + one-to-one filtering
             -> findHomography(..., RANSAC, 5.0)
           compare raw image matrices with association-derived f_last
           or fall back to f_last
    -> returned f / updated f_last
    -> ID mutation and Supplement
```

Direct evidence:

- `matching_pure.py:22-27,49-63,66-91,133-137` contains the raw image SIFT,
  FLANN, ratio-test, and RANSAC computation.
- `trans_matrix.py:supp_compute_transf_matrix:20-88` combines the raw path with
  matched-row triggering and `f_last` selection/fallback.
- `common.py:get_matched_ids:162-243` derives centre correspondences from
  tracker rows and runtime IDs.
- `supplement_MIA.py:312-325,359-364` invokes the mixed helper after
  `get_matched_ids`; ID mutation and Supplement follow at lines 338-452.

## 3. Reusable code concepts

`REUSABLE_AS_REFERENCE`, not import-as-is:

- `cv2.SIFT_create()` and `detectAndCompute` on two raw images;
- image-only descriptor matching;
- explicit one-to-one feature-pair filtering;
- `cv2.findHomography` with RANSAC;
- extraction of the RANSAC mask and raw feature reprojection diagnostics;
- finite 3x3 shape checks from `_is_valid_homography`.

The clean provider should reproduce only these image-derived concepts in a
small dependency-isolated module. It should not import the whole author helper,
which also imports XML/detector utilities and exposes mixed target-dependent
paths.

## 4. Code that must be isolated or forbidden

`FORBIDDEN_FOR_INDEPENDENT_GEOMETRY`:

- `get_matched_ids` and `get_matched_ids_frame1`;
- tracker rows, runtime IDs, bbox centres, candidate lists, or GT tie points;
- `supp_compute_transf_matrix` and `local_compute_transf_matrix` as provider
  APIs;
- `f`, `f_last`, held-H selection, or any previous-frame fallback;
- the `len(pts_src)` target-dependent switch that decides whether global image
  matching runs;
- three-run selection against `f_last`;
- downstream candidate/tracking outcomes and `S_cf`/shadow state.

## 5. G14 train-pair enumeration readiness

The local MDMT train split has 25 sequence-level pairs:

```text
23 25 27 28 29 30 32 39 42 44 45 50 51
53 54 58 63 64 65 66 69 70 74 76 78
```

For every listed ID, both `<id>-1` and `<id>-2` directories exist, their JPEG
counts are equal, and their exact JPEG filename sets match. Pair 26 and Pair 48
are absent from train. The directory state is therefore sufficient to implement
the G14 selection procedure later.

No five-pair sample was drawn in this planning round. Implementation M1 must
persist the eligible pool and selected five pairs before any geometry module is
invoked or any diagnostic file exists.

## 6. Prompt-to-repository conflicts

### CONTRACT_CONFLICT-1 — branch provenance unavailable locally

- Prompt context names branch
  `exp/20260822-001-route-a-observer-mve-plan`.
- Local evidence: `git status --short` returns “not a git repository”.
- Consequence: a branch/commit cannot be asserted in the contract as FACT.
- Required implementation-time resolution: execute in a verified Git worktree
  and record branch, commit, dirty state, and code digests. Until then the branch
  is a suggestion, not observed provenance.

### CONTRACT_CONFLICT-2 — bootstrap document absent

- `AGENTS.md` asks for `experiment_validation_plan.md`.
- The file is absent from the workspace.
- Consequence: this plan uses the experiment contract template and the active
  Route-A contract as the available planning authority; implementation must stop
  if a restored validation plan adds conflicting requirements.

No scientific conflict was found with G1-G15b. The prompt's description of an
existing raw image registration capability is source-supported. The source also
confirms why it must be extracted from the target-conditioned caller.

