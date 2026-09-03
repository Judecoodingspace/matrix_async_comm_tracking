# Packet Census homography-fallback successor contract

## Identity and scope

- Successor branch: `exp/20260903-001-mdmt-mia-p39-homography-fallback-successor-census`
- Predecessor baseline: `0e2880f1cd860ac1134dcbacb5f2fb94a2d1dda0`
- Successor formal identity: `mdmt-mia-packet-census-z0-train-all-hfallback-v1`
- Published successor repair baseline:
  `79040009f040897128751027639cef3e81e18e54`.
- Population: the same 25 frozen train pairs, 12,026 Census frame units.
- Condition: Z0 only; seed 7; `cuda:0`.
- Successor author variant:
  `/mnt/data/yzm/experiments/mdmt_mia_official/variants/packet_census_homography_fallback_successor_v1`.
- Successor author entry SHA-256:
  `8f4a75ec1e41831a4767aa00e7c027df542d5cb43c2333987204f9bc5e4b246d`.
- Successor fallback module SHA-256:
  `ba14dbd9ab27a822a454c496fb1c3d657e3a9884a06e02e1b353485e11f87f73`.

The predecessor formal run is **INVALID / HISTORICAL ONLY**. Its completed
pairs (`23, 25, 27, 28, 29, 30, 32`) and its Pair 39 failure artifacts must
not enter successor validation or aggregation.

## Frozen repair decision

`HOLD_LAST_VALID_HOMOGRAPHY_FAIL_CLOSED_OTHERWISE`

A homography is structurally valid exactly when it is a NumPy `ndarray` of
shape `(3, 3)`, floating dtype, and all values are finite. No rank,
determinant, condition-number, reprojection, inlier, normalization, or manual
geometry gate is added.

1. A valid RANSAC result follows the existing normal behavior and replaces
   `f_last` with its copy.
2. An absent or structurally invalid current RANSAC result reuses an exact
   copy of a valid `f_last`; absent valid history raises
   `NO_VALID_HOMOGRAPHY_STATE`.
3. When all low-match candidates and history are valid, the predecessor cosine
   selection is preserved exactly.
4. If any low-match candidate is invalid, no candidate is selected and a
   valid `f_last` is reused exactly; invalid history fails closed.
5. No identity matrix, hand-authored H, alternate estimator, or new
   candidate-selection/geometry-quality rule is permitted.

The successor-only audit is outside packet wire records, tracker feedback,
candidate selection, and RNG. It writes only `frame_id`, `repair_branch`,
`current_matrix_valid`, `history_matrix_valid`, and `action`, whose action is
one of `USE_CURRENT_VALID_H`, `HOLD_LAST_VALID_H`, or `FAIL_NO_VALID_H`.

## Directed-validation and restart gates

Pair 39 must run from frame 0 through all 400 frames in OFF-A, OFF-B, and ON.
OFF-A/ OFF-B and OFF-A/ON author-semantic artifact equality is required;
ON additionally requires C1--C8 and exactly one successful finalization.
Frame 175 must exercise the original invalid-matching condition with valid
historical H and `HOLD_LAST_VALID_H`; identity use is forbidden.

Only after those gates, the successor repair publication, and a fresh
successor preflight may a new output root
`outputs/packet_census_z0_train_all_hfallback_v1/` begin at Pair 23. The
directed Pair 39 records do not substitute for formal Pair 39. No scientific
summary may be read before 25/25 successor pairs and 12,026/12,026 frames.

## Formal-preflight freeze

The formal preflight requires the successor branch and requires the published
repair baseline above to be an ancestor of the checked worktree HEAD. The
preflight manifest additionally freezes hashes of the current runner, tools,
summarizer, RNG wrapper, successor author entry, fallback module, copied
runtime, config, checkpoint, and all 25 input identities. This permits the
dedicated formal-contract/preflight tooling commit while retaining the
validated repair baseline as the immutable source anchor.
