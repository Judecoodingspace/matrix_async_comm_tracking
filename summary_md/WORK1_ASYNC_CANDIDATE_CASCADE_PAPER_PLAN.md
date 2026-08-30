# WORK 1 ASYNC CANDIDATE CASCADE PAPER PLAN

Status: `WORK1_READY_FOR_MINIMAL_INTERVENTION_DESIGN`

## 1. One-sentence scientific question

Does communication asynchrony change MIA's current-frame association
candidate/Supplement eligibility in a way that produces destructive tracking
cascade and compensatory opportunities, and can preserving only an already
legal same-frame eligibility stabilize that opportunity without general
late-observation reassociation?

## 2. Existing evidence

### `REPOSITORY_PROVEN_FACT`

- In frozen E023 v8, `supplement_MIA.py:339-404` performs three current-frame
  ID-state mutation/delivery stages: `new_A_to_B`, `new_B_to_A` and
  `old_unmatched_repair`.
- `mdmt_mia_async_deadline_runtime.py:342-364` queues a delayed ID-state packet
  and returns the pre-mutation rows, `matched_ids` and confirmed-ID state to the
  current branch; timely delivery returns the post-mutation state.
- `supplement_MIA.py:408-447` then recomputes `A/B_old_not_matched_*` from that
  resulting mutable state and passes those exact lists to
  `not_matched_supplement()`.
- `supplement.py:137-149` shows that a successful High-score Supplement appends
  `[source_runtime_id, selected_target_bbox, 0.999]` to the target rows and the
  Supplement ledger; it also mutates matched/confirmed-ID lists.
- E023's `S_cf`/`Yec` path is explicitly a synchronous shadow membership-only
  intervention. It is diagnostic-only and is not a legal deployable input.
- The planned non-test onset experiment was not run. Its GT protocol gate
  failed exact official-test equivalence, so development, holdout and onset
  selection remain absent.
- Route A is planned but its Stage-A development and held-out have not run; it
  contributes no Work 1 performance evidence.

### `FORMAL_EXPERIMENT_EVIDENCE`

- E023 Formal used 14 official MDMT test pairs, passed all 40 measurement
  gates and reproduced `Y00` exactly.
- Delayed ID state harmed MDA at both delays: `D_ID(d1)=0.013350`, 95% CI
  `[0.003154,0.023453]`, and `D_ID(d5)=0.025750`, 95% CI
  `[0.012466,0.039962]`; both had 13/14 positive pair directions.
- At d5, the membership edge was compensatory:
  `R_edge=Yec-Y10=-0.018329`, 95% CI `[-0.036894,-0.004305]`, with 10/14
  negative pair directions. At d1 its CI crossed zero.
- At d5, timely Supplement had additional marginal value:
  `C_comp=0.049913`, 95% CI `[0.014343,0.096598]`, with 10/14 positive pair
  directions. At d1 its CI crossed zero.
- Process evidence at d5 recorded 3,520 Y10 disagreement candidates, 3,506
  High-score triggers and 2,169 successful bbox write-ins. Y10 had write-ins in
  all 14 pairs; Yec had 18 triggers and zero write-ins.

### `INFERENCE`

- The smallest intervention family suggested by the combined source and formal
  evidence is preservation of an eligibility that already existed in a legal
  current-frame state, not creation of a new cross-time/cross-view candidate.
- A pre-ID-mutation eligibility snapshot may remove accidental dependence on
  whether downstream Supplement reads the pre- or post-delivery mutable state.
  This is a falsifiable intervention hypothesis, not an established benefit.
- The compensatory edge can coexist with direct ID-delay harm; preserving the
  edge is not equivalent to making delay beneficial.

### `UNRESOLVED`

- The d5 mechanism has not been replicated on legal non-test data, and no
  compensation onset within d1-d5 has been validated.
- E023 identifies the combined ID-state-block-to-membership edge; it does not
  attribute the disagreement separately to `new_A_to_B`, `new_B_to_A`,
  `old_unmatched_repair`, row-ID mutation, `matched_ids` or confirmed-ID state.
- It is unknown whether preserving pre-ID eligibility retains beneficial
  opportunities without also retaining candidates that timely reconciliation
  correctly removed.
- No deployable intervention has been implemented or evaluated, and MDA,
  IDF1, MOTA and IDSW cannot yet support an intervention claim.

Diagnostic oracle results (`S_cf`, `Yec`, shadow state, GT identity and
counterfactual membership) remain diagnostic-only throughout Work 1.

## 3. Candidate-set causal chain

```text
communication delay
  -- VERIFIED BY SOURCE -->
ID-state packets are queued; the current branch observes pre-mutation state
  -- VERIFIED BY SOURCE + E023 MEMBERSHIP CONTRAST -->
post-ID get_matched_ids() produces a different old-unmatched eligibility set
  -- VERIFIED BY E023 PROCESS TRACE -->
different candidates reach not_matched_supplement() and bbox write-in
  -- PARTIALLY VERIFIED -->
d5 MDA compensation partially offsets direct delay harm
```

The last arrow is only partially verified because the primary MDA contrast is
supported at d5 but not d1, secondary tracking metrics do not share one common
ranking, and non-test onset/replication was not run.

The following remains unverified:

```text
deployable eligibility preservation
-> safer or more stable Supplement consumption
-> formal tracking improvement
```

## 4. Paper-sized claim

The maximum current Work 1 claim is:

> In the audited MDMT/MIA runtime, asynchronous ID-state delivery changes the
> old-unmatched candidate membership consumed by High-score Supplement. On the
> 14-pair E023 official-test experiment this pathway coexists with direct
> ID-delay harm and provides net MDA compensation at five frames, while the
> same pathway is unresolved at one frame.

After a successful intervention evaluation, Work 1 may additionally claim that
a deployment-only, same-frame eligibility-preservation mechanism stabilizes
this specific pathway under its frozen evaluation conditions.

Work 1 may not claim a general Route A framework, universal compensation onset,
general late-observation reassociation, or that oracle `Yec` is a deployable
method.

## 5. Minimal intervention candidates

Ranked by `closest-to-observed-mechanism`:

### 1. Pre-ID candidate-eligibility preservation

- Intervention target: the old-unmatched eligibility that exists immediately
  before current-frame ID mutation/delivery.
- Modified state: an immutable, frame-scoped eligibility record keyed to the
  already existing candidate row/observation; Supplement consumes it once and
  it then expires.
- Legal information: current-frame tracker rows, matched/confirmed state and
  detector observations already available on the author branch before the ID
  stages. No `S_cf`, GT, shadow output or future state.
- New model required: no.
- Direct mechanism correspondence: yes; it prevents later mutable ID state
  from silently deleting an already present Supplement-processing opportunity.
- Largest scientific risk: it may preserve candidates that synchronous ID
  reconciliation correctly made ineligible, increasing false write-ins.

Minimality test: it targets the observed membership transition; changes only
frame-scoped eligibility; introduces a safety/precision question but no new
geometry problem; removing it should restore the original cascade; and it can
operate without Spatial Bridge, Temporal Bridge or general reassociation.

### 2. Transaction-consistent ID/Supplement consumption

- Intervention target: serial consumption of different mutable association
  versions by the ID block and High-score Supplement.
- Modified state: an immutable association-version token plus one
  transaction-scoped read snapshot for both consumers.
- Legal information: only current-frame state already available to both author
  branches; no oracle or GT.
- New model required: no.
- Direct mechanism correspondence: yes, but it changes a wider execution
  boundary than candidate-only preservation.
- Largest scientific risk: transaction semantics may change legitimate ID
  reconciliation as well as Supplement eligibility, weakening causal
  attribution to the candidate edge.

This candidate is not a revival of E023's rejected atomic joint-commit claim;
it is only a version-consistent read-context hypothesis.

### 3. Version-aware validation of pre-existing eligibility

- Intervention target: a delayed ID remap/version update invalidating an
  eligibility relation that was already created legally.
- Modified state: eligibility record plus capture/version and immutable local
  row/lineage reference; late evidence may validate or retire it but cannot
  generate a new candidate.
- Legal information: emitted ID remap/version metadata and existing
  observation/lineage infrastructure only.
- New model required: no.
- Direct mechanism correspondence: partial; it addresses delayed consumption
  but adds lifecycle/version semantics beyond the current candidate-only edge.
- Largest scientific risk: it can expand into Route A-style cross-time lineage
  resolution if not restricted to an already existing same-frame eligibility.

## 6. Recommended first intervention

Recommend **Pre-ID candidate-eligibility preservation**.

The source boundary is sufficiently explicit for design: the pre-ID
`get_matched_ids()` result exists before `capture_prebranch` and is overwritten
by later recomputations, while High-score Supplement consumes only the final
post-ID list. Preserving only the pre-existing frame-scoped eligibility is the
smallest change that directly tests the observed mechanism and uses no oracle
or new model.

This recommendation authorizes only a separate falsifiable MVE contract. It
does not authorize implementation or claim that unioning, ranking or committing
candidates is safe.

## 7. Minimal experiment chain

### MVE

Freeze one comparison: current mutable eligibility versus the immutable
pre-ID eligibility record, with identical detector, tracker, ID stages,
Supplement matcher/thresholds, delay and feedback. First require source/row
conservation, logging invariance and exact proof that the intervention consumes
only deployment-time current-frame information. Primary mechanism outputs are
candidate membership, eligibility additions/removals and High-score
trigger/write-in counts; safety grading is deferred until a valid GT protocol
exists, and tracking improvement is not an MVE pass condition.

### Development/formal validation

After a legal non-test evaluation protocol exists, use a frozen development
cohort to test whether the intervention reduces destructive candidate-loss
events without increasing unsafe write-ins, then freeze one method and evaluate
once on untouched holdout. Do not tune on the 14 E023 official-test pairs and
do not use `S_cf` as a method input.

### Final evaluation

Compare synchronous MIA, delayed unmodified MIA and the frozen minimal
intervention under the same delay conditions. Report MDA as the primary
cross-device endpoint and IDF1/MOTA/IDSW separately, together with candidate
and write-in mechanism traces. A mechanism change without formal tracking
evidence is not a completed paper result.

## 8. Paper completion criterion

```text
phenomenon + mechanism + minimal intervention + formal evidence
```

- Phenomenon: `EXISTS` — E023 formally shows direct ID-delay harm and d5
  compensation on 14 official test pairs.
- Mechanism: `PARTIAL_BUT_ACTIONABLE` — the ID-state-to-old-unmatched-to-
  Supplement edge is source-proven and causally supported at d5; non-test
  onset and substage attribution remain unresolved.
- Minimal intervention: `MISSING` — one candidate family is recommended but
  has not been implemented or tested.
- Formal intervention evidence: `MISSING` — no legal non-test development/
  holdout result exists, and the prior onset protocol stopped at the GT gate.

Work 1 is therefore not paper-complete, but it is ready for a narrowly scoped
minimal-intervention design. Route A remains `PARKED_AFTER_PLANNING` and was not
executed in this task.

```text
ROUTE_A_NOT_EXECUTED_IN_THIS_TASK
```
