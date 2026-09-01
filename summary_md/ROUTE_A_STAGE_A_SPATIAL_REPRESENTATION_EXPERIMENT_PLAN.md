# ROUTE A STAGE-A SPATIAL REPRESENTATION EXPERIMENT PLAN

Status: `PREREGISTRATION_FROZEN / READY_FOR_STAGE_A_IMPLEMENTATION / HELDOUT_NOT_RUN`

This plan ends at pre-held-out freeze. It does not authorize or describe a
held-out execution command.

## 1. Experiment contract

- Experiment ID: `exp_20260829_001_route_a_spatial_feasible_region_mve`
- Question: can the frozen same-capture coarse correspondence-support provider
  form candidate-independent regions that meet frozen availability,
  no-confirmed-exclusion, anti-triviality, and reproducibility gates?
- Primary hypothesis: after development-only selection and immutable freeze,
  the provider passes Stage-A held-out readiness.
- Alternative: it fails at least one frozen gate or measurement-integrity gate.
- Primary variable: provider condition/config selected only from the frozen
  development candidate sets.
- Controls: `WHOLE_IMAGE_FEASIBLE` and infrastructure-only MVE-0.
- Detector/tracker/MIA/delay, feature/matcher semantics, observation schema,
  data split, denominators, GT firewall, and evaluation gates remain controlled.
- Stage-B temporal bridge/opportunity and all tracking metrics are out of scope.

## 2. Data and access manifest

Development train pairs: `23,27,28,30,32`.

Proposed held-out train pairs: `39,42,44,50,53`, not accessible for spatial
outcomes in this plan.

Forbidden: Pair 26, Pair 48, 25/29/45/51/69, test, val, future frames,
historical tracker candidates, and any result-conditioned replacement.

The provider full denominator is every provider-eligible source observation;
unavailable provider rows remain in Gate-A denominator. Gate-B denominator is
only valid E1-E3 offline references, with all unavailable/conflict counts
reported separately.

## 3. Frozen scientific configuration

- P1: clipped bbox, keypoint center inside/on boundary, no expansion.
- P2: minimum one unique accepted match and one legal receiver cell.
- P3 candidates: normalized `{4x4,8x8,16x16}` only.
- P4 candidates: fixed 8-neighbor square dilation `{0,1,2}` cells only.
- P5: explicit unavailable, no fallback.
- P6: exact receiver snapshot(t) retained through `t+5`, then releasable; reset
  clears all; no substitution.
- Matcher: SIFT/FLANN KNN/Lowe `<0.7`/returned-order greedy uniqueness; no H/F.
- E1: same-frame/class global one-to-one maximum-IoU plus threshold from
  `{0.3,0.5,0.7}`.
- E2: same-frame unique same-GT-ID receiver object.
- E3: any nonempty receiver-GT-bbox/region intersection retains reference;
  complete disjointness confirms exclusion.
- E4: provider closes and hashes before first GT read.
- Gate A: availability >=0.75 per direction.
- Gate B: confirmed exclusions=0 per direction; zero-event uncertainty reported.
- Gate C: median area ratio<=0.90 and >=25% valid rows area<=0.75.
- Gate D: >=8/10 directions and >=4/5 bidirectional pairs pass A-C.

RD-SA-SEL is `FROZEN`. Selector A requires every development direction to have
reliable-reference coverage `C_ref>=0.50`, then minimizes worst-direction
ambiguity, maximizes worst-direction reliable-reference median IoU, maximizes
worst- then median-direction coverage, and finally prefers higher IoU. No
eligible threshold yields `E1_REFERENCE_PROTOCOL_DEVELOPMENT_FAIL`.

Selector B requires every direction to have `RefAvail>=0.75` and zero confirmed
exclusions, plus at least 8/10 direction PASS and 4/5 bidirectional-pair PASS.
Its frozen lexicographic order is bidirectional PASS, direction PASS,
worst-reference availability, worst full availability, median availability,
worst median area, median-direction median area, worst small-area fraction,
smaller dilation, then coarser grid. No admissible configuration yields
`COARSE_SPATIAL_PROVIDER_DEVELOPMENT_FAIL` and stops the epoch.

## 4. Phase 0 — Provenance audit

Purpose: establish eligibility and reproducibility without generating proposed
held-out spatial outcomes.

Checks:

1. recover Git branch/commit/dirty-state and exact source/config hashes;
2. audit development and proposed-held-out sequence history against old
   development, G15c, held-out, test, val, and spatial-outcome exposure;
3. verify proposed held-out images have not been opened by Stage-A provider,
   selector, debugger, or evaluator;
4. freeze raw frame filename sets/counts and pair-direction denominators using
   metadata only;
5. verify feature extractor/matcher code/config and deterministic environment;
6. record GT access paths and enforce provider denylist.

If a proposed held-out pair is ineligible before any spatial outcome read, stop
and invoke the separately preregistered provenance replacement rule. Since that
replacement rule is not specified in the current freeze, conflict currently
terminates as `STOP_AND_REPORT_SPLIT_PROVENANCE_CONFLICT`; no ad hoc replacement.

Outputs: provenance audit Markdown/JSON, split manifest, source/config hashes,
access denylist, and `HELDOUT_NOT_YET_ACCESSED` attestation.

Stop: provenance gap, contamination, forbidden file read, or nonreproducible
feature configuration.

## 5. Phase 1 — Synthetic/unit validation

No scientific dataset outcome and no held-out image read.

Required tests:

- bbox clipping and inclusive boundary-only local features;
- zero-local-feature and all P5 unavailable statuses;
- one unique match accepted; no old H minimum;
- exact source(t)/receiver(t) retrieval and rejection of t±1/t+5 substitute;
- FLANN/Lowe/greedy one-to-one parity and deterministic correspondence digest;
- normalized cell mapping for 4/8/16 grids;
- 8-neighbor square dilation radius 0/1/2, clipping, canonical mask, area/ratio;
- receiver cache expiry after packet processing and reset;
- immutable ledger schema/digests/full-denominator accounting;
- provider rejects GT paths/schema/imports;
- evaluator refuses an open/incomplete/digest-mismatched ledger;
- E1 one-to-one assignment/threshold, E2 conflicts, E3 any-intersection cases;
- exact Gate A-D boundary/reporting tests;
- absence of candidate, lineage, pruning, newness, tracker-write, and tracking-
  metric APIs in Stage-A provider/reporter.

Output: unit report, schema manifest, deterministic-repeat report, firewall
audit, and no-held-out-access attestation.

Stop: any failed invariant or forbidden dependency.

## 6. Phase 2 — Non-interference validation

Run a fixed approved non-held-out input with spatial feature/cache/provider OFF
and ON. This is validation, not a spatial scientific result.

Compare:

- detector observation keys, rows, scores, labels;
- ByteTrack row count/order, IDs, bboxes, scores/labels;
- runtime ID/remap/lifecycle semantics;
- MIA inputs/outputs and NMS/Supplement-visible rows;
- feedback arrays and next-frame core digests;
- final per-view tracking JSON and tracker mutation count.

Normalize only new observer feature/region ledgers and sequence effects.

Required: `CORE_OUTPUT_DIFF = 0` and tracker mutation count remains zero.

Outputs: OFF/ON manifests, semantic/digest comparison JSON, and non-interference
report.

Stop: any core difference. Do not debug using held-out pairs.

## 7. Phase 3 — Development run and selection

Precondition: frozen RD-SA-SEL encoded in config and its selector unit tests
passed before any run.

Data: only pairs `23,27,28,30,32`, both directions, complete denominators.

Provider grid/dilation matrix: exactly 3x3=9 configurations. No added grid,
dilation, bbox margin, matcher, minimum-match threshold, or fallback.

#### Selector A execution

Offline E1 candidates are exactly 0.3/0.5/0.7. Unit is a pair-direction;
`D_u` includes all legal-class source detector observations. `D_u=0` stops as
`E1_ZERO_DENOMINATOR_UNIT`.

An accepted assignment is ambiguous when another same-class IoU edge in the
same detector row or GT column also meets the threshold. For each threshold:

```text
C_ref,u      = accepted non-ambiguous references / D_u
A_amb,u      = ambiguous accepted / accepted, or 1 when accepted=0
M_iou,u      = median reliable-reference IoU
A_amb_max    = max_u A_amb,u
M_iou_min    = min_u M_iou,u
C_ref_min    = min_u C_ref,u
C_ref_median = median_u C_ref,u
```

Eligibility requires `C_ref,u>=0.50` in all 10 units. Sort by lower
`A_amb_max`, higher `M_iou_min`, higher `C_ref_min`, higher `C_ref_median`, then
higher threshold. Spatial/Gate-B/Gate-C evidence is inaccessible to Selector A.
Freeze the selected threshold before Selector B. No eligible threshold stops as
`E1_REFERENCE_PROTOCOL_DEVELOPMENT_FAIL`; joint search is forbidden.

#### Selector B execution

Evaluate exactly nine configurations. For unit `u`:

```text
Avail_u     = provider-valid / provider-eligible
RefAvail_u  = reference-eligible AND provider-valid / reference-eligible
X_u         = confirmed exclusion count
MedArea_u   = median area_ratio over valid regions
SmallFrac_u = fraction valid with area_ratio<=0.75
UNIT_PASS_u = Avail_u>=0.75 AND X_u=0
              AND MedArea_u<=0.90 AND SmallFrac_u>=0.25
```

Configuration admissibility requires `X_u=0` and `RefAvail_u>=0.75` for all 10
units, `UNIT_PASS` in at least 8/10 directions, and both-direction PASS for at
least 4/5 pairs. No pooled rescue.

Sort admissible configurations by higher bidirectional PASS count, higher
direction PASS count, higher `min RefAvail`, higher `min Avail`, higher median
`Avail`, lower `max MedArea`, lower median `MedArea`, higher `min SmallFrac`,
smaller dilation, then coarser grid. Complexity tie-breaks apply only after all
scientific metrics tie. No admissible configuration stops as
`COARSE_SPATIAL_PROVIDER_DEVELOPMENT_FAIL` and
`STOP_CURRENT_STAGE_A_EPOCH`.

Required raw outputs:

- immutable provider ledgers for each approved configuration;
- separate E1-E3 evaluator ledgers;
- per-direction availability, unavailable reasons, reference eligibility,
  exclusions, zero-event uncertainty, area distributions, A/B/C;
- selector input table, selected row or terminal failure, tie-break trace;
- access/completeness/determinism/provenance audits.

Development may diagnose and select only inside frozen candidate sets. It
cannot change family, Lowe ratio, P1/P2/P5/P6, E1-E4, or Gates A-D.

Stop: either frozen development-failure label, added candidate, joint search,
manual override, nondeterminism, forbidden metric, GT-before-ledger-close, or
any proposed-held-out read.

## 8. Phase 4 — Pre-held-out freeze

No held-out provider/evaluator execution occurs.

Generate one immutable manifest containing:

- selected IoU threshold, grid, and dilation or frozen development-failure
  terminal state;
- exact matcher and P1-P6/E1-E4/Gates A-D;
- development selector policy and complete tie-break trace;
- final proposed-held-out pair list after provenance audit;
- provider/evaluator/reporter code commit and dirty-state;
- config/schema/input/feature/environment digests;
- seed/threading/library versions if applicable;
- data-split provenance, timestamp, and complete access audit;
- state `HELDOUT_NOT_YET_ACCESSED`.

Run a manifest-integrity review. Any post-freeze scientific change creates a
new experiment epoch and cannot reuse viewed held-out evidence.

Output: pre-held-out freeze manifest and audit only.

Stop: missing digest/provenance, unresolved selection, split conflict, or any
held-out spatial outcome.

## 9. Held-out boundary

The following are explicitly forbidden now:

- running provider on Pair39/42/44/50/53;
- generating held-out regions or Gate A/B/C/D values;
- using held-out for debugging, selection, tuning, or pair replacement;
- revealing any Stage-A held-out result.

Current and terminal status for this task: `HELDOUT_NOT_RUN`.

## 10. Expected runtime and resume governance

Phase 0-2 condition counts derive from unit tests and one fixed non-held-out
comparison. Phase 3, once RD-SA-SEL is frozen, evaluates 9 provider configs on
5 development pairs x 2 directions plus three E1 thresholds; exact observation
denominator is frozen from the development manifest before provider output.

Checkpoint/resume may reuse only records with exact pair/frame/config/code/
environment/input digests. Attempts cannot mix, and resume cannot change
selection candidate sets or reveal held-out evidence.

## 11. Decision and next actions

RD-SA-SEL is frozen. After explicit implementation authorization, the only
allowed sequence is Phase 0 -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4,
stopping at `HELDOUT_NOT_YET_ACCESSED`.

Bad results are accepted. No rescue by family switching, new candidates,
threshold/gate changes, unavailable/exclusion deletion, fallback, or viewed-
held-out replacement.

Stage-A success/failure cannot be concluded in this plan because held-out is
forbidden and not run.

## 12. Planning verdict

`READY_FOR_STAGE_A_IMPLEMENTATION`

The phases, selectors, inputs, controls, gates, outputs, and stop rules are
scientifically frozen. This document does not itself authorize code or
development execution and contains no held-out execution command. Current
status remains `DEVELOPMENT_NOT_RUN / HELDOUT_NOT_RUN`.
