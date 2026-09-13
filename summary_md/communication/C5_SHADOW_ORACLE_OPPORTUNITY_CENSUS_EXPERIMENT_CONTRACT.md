# C5 Shadow Oracle Opportunity Census Experiment Contract

```text
DOCUMENT_ROLE = C5_SHADOW_ORACLE_OPPORTUNITY_CENSUS_EXPERIMENT_CONTRACT
EXPERIMENT_ID = NOT_FROZEN_BY_THIS_CONTRACT
CONTRACT_STATUS = DRAFT_COMPLETE
EXECUTION_STATUS = NOT_AUTHORIZED
CLAUSE_CLASSIFICATION_VOCABULARY =
FROZEN_SCIENTIFIC_DECISION,
MANDATORY_IMPLEMENTATION_QUALIFICATION,
CLAIM_BOUNDARY,
NON_AUTHORIZATION
```

## 1. Purpose and stage role

**FROZEN_SCIENTIFIC_DECISION**

This Contract formalizes the C5 Shadow Oracle Opportunity Census as a
pre-intervention qualification / pre-experiment stage. It asks whether the
frozen C4 FIFO trajectory contains whole ID-State packets that are already
currently non-applicable when the shared FIFO server is about to begin serving
them.

The Census measures opportunity occurrence on the unchanged baseline
trajectory. It does not remove work, alter service, or measure intervention
utility.

```text
C5_SHADOW_CENSUS_STAGE_ROLE = PRE_INTERVENTION_QUALIFICATION_PRE_EXPERIMENT
MECHANISM_OCCURRENCE_EQUALS_POLICY_UTILITY = NO
```

**NON_AUTHORIZATION**

This Contract does not authorize implementation, execution, packet skipping,
or the later closed-loop Oracle Probe.

## 2. Upstream authorities

**FROZEN_SCIENTIFIC_DECISION**

- Repository: `https://github.com/Judecoodingspace/matrix_async_comm_tracking`
- Frozen C4 implementation authority:
  `23afc5740cbaafacd77b78e5eac246e3abdf0b20`
- Frozen C4 scientific state: `C4_MECHANISM_SUPPORTED`
- Scientific freeze source:
  `C5_SHADOW_CENSUS_AUTHORITATIVE_DECISION_BLOCK_R1_R3`
- Upstream C4 governance directory: `summary_md/communication/`
- Upstream C4 MVE contract:
  `COMMUNICATION_C4_BASELINE_QUALIFICATION_MVE_CONTRACT.md`
- Upstream C4 implementation evidence:
  `COMMUNICATION_C4_BASELINE_QUALIFICATION_IMPLEMENTATION_EVIDENCE.md`

C4 established the causal chain, within its frozen three-class mixed-object,
category-agnostic pipeline:

```text
finite logical communication service
-> queue / completion delay / pending work
-> semantic freshness / availability degradation
-> task-relevant tracking degradation
```

The inherited C4 service is one shared logical FIFO with fixed `R` logical
bytes/frame, non-preemptive cross-frame service, and atomic application only
after packet completion. C4 uses MDA as its primary metric and IDSW as its
secondary metric.

## 3. Scientific question and hypotheses

**FROZEN_SCIENTIFIC_DECISION**

Research question:

> Does the frozen C4 FIFO trajectory contain whole ID-State packets that, at
> the moment they are about to begin consuming service, are already currently
> non-applicable under the frozen delayed-consumer semantics?

Primary falsifiable opportunity hypothesis:

> At least one pre-registered FRONTIER cell has non-zero
> `whole_packet_non_applicable_wire_bytes`.

Plausible alternative hypothesis:

> All three pre-registered FRONTIER cells have zero
> `whole_packet_non_applicable_wire_bytes` under the exact conservative
> whole-packet predicate.

This Census does not test whether skipping saves service, improves MDA or
IDSW, or defines a deployable policy.

## 4. Evidence classification and scope

**FROZEN_SCIENTIFIC_DECISION — FACT**

- C4 mechanism support and its FIFO trajectories are frozen upstream.
- The delayed-consumer task-effect set for ID-State packets is
  `{remap_events, confirmed_ids}`.
- Delayed `matched_ids` mutation is recomputed later in the audited author
  flow and is not an independent retain criterion here.
- Delayed consumption does not restore `track_rows_view1/2`.
- `(view_id, source_track_id)` is not a universally stable cross-time
  lifecycle key.
- A causally legal first-service observation boundary exists at
  `_C4SharedLogicalServer._start_next`, provided receiver state is captured
  synchronously before the first service-byte decrement.

**FROZEN_SCIENTIFIC_DECISION — INFERENCE**

Non-zero opportunity bytes would establish that the frozen baseline trajectory
contains transport work classified as currently non-applicable by the frozen
predicate. It would not establish that removing that work relieves service or
improves tracking.

**MANDATORY_IMPLEMENTATION_QUALIFICATION — ASSUMPTION**

A future shadow implementation can observe the exact first-service event and
record the predicate without changing the pre-existing C4 trajectory. That
assumption must be mechanically qualified before any Census execution.

**CLAIM_BOUNDARY — UNKNOWN**

- Whether any frozen frontier cell contains non-zero opportunity bytes.
- Whether a future intervention would produce queue relief or tracking benefit.
- Any Supplement or all-channel applicability result.

```text
C5_SHADOW_CENSUS_SCOPE = ID_STATE_ONLY
SUPPLEMENT = UNCHANGED_NOT_CLASSIFIED_NOT_INCLUDED
REPACKETIZATION = NOT_AUTHORIZED
```

## 5. Causal information boundary

**FROZEN_SCIENTIFIC_DECISION**

The observer is a `CURRENT_STATE_APPLICABILITY_ORACLE`. It is privileged
because it may read receiver-side state unavailable to the ordinary service,
but it is not future-looking.

Allowed at the decision event:

- packet contents;
- current receiver live rows;
- current receiver confirmed state;
- current receiver `_applied_id_map`;
- current receiver `_last_id_packet_version`;
- current communication-service state.

Forbidden:

- future receiver rows or receiver state;
- future association/remap outcomes;
- future packet generation or completion;
- future track termination;
- future MDA, IDSW, GT, or other evaluation outcome;
- post-arrival outcome information.

```text
CURRENT_STATE_ORACLE_ONLY = YES
FUTURE_INFORMATION_ALLOWED = NO
```

## 6. Exact first-service observation semantics

**FROZEN_SCIENTIFIC_DECISION**

The sole scientific observation boundary is:

```text
_C4SharedLogicalServer._start_next selects packet P
-> P becomes the in-service packet for the first time
-> snapshot causally available receiver state
-> _serve may then decrement the first service slice
```

Observation is one-time per packet. Cross-frame continuation of a packet that
already consumed service is not another observation point, and no
applicability recheck is authorized.

```text
SHADOW_OBSERVATION_POINT_STATUS = SAFE_WITH_LOCAL_SNAPSHOT
CAUSAL_SERVICE_START_ORACLE_VALID = CONDITIONAL
CAUSAL_VALIDITY_CONDITION = EVENT_LOCAL_SNAPSHOT_BEFORE_FIRST_BYTE_DECREMENT
CAUSAL_TIMING_P0 = CLOSED
SCIENTIFIC_DEFINITION_CHANGE_REQUIRED = NO
```

**MANDATORY_IMPLEMENTATION_QUALIFICATION**

A future implementation must mechanically distinguish a packet whose
`service_start_frame` is unset from an already partially served in-service
packet, and it must bind the snapshot to the one-time transition into first
service.

**NON_AUTHORIZATION**

End-of-frame reconstruction, post-`admit` reconstruction, later-stage state,
final-ledger reconstruction, post-feedback state, and any future state are
forbidden substitutes for the event-local snapshot.

## 7. Whole-packet current non-applicability predicate

**FROZEN_SCIENTIFIC_DECISION**

For an ID-State packet `P` observed at its true first-service decision time
`t`, define `WHOLE_PACKET_CURRENTLY_NON_APPLICABLE(P,t)` as follows.

### Gate 1 — frozen packet-level version rejection

If:

```text
P.source_state_version <= receiver._last_id_packet_version
```

then:

```text
WHOLE_PACKET_CURRENTLY_NON_APPLICABLE = YES
REASON = VERSION_REJECT
```

This is implementation-relative current applicability. It does not assert
semantic dominance by a newer packet.

### Gate 2 — remap effects

For each remap effect:

```text
(view_id, source_track_id) -> target_track_id
```

set `REMAP_CURRENTLY_APPLICABLE = NO` if either:

1. current receiver live rows for `view_id` do not contain
   `source_track_id`; or
2. current `_applied_id_map` contains the same
   `(view_id, source_track_id)` with a different target and the frozen
   consumer would reject the incoming remap as a conflict.

Otherwise conservatively set `REMAP_CURRENTLY_APPLICABLE = YES`.
Same-key/same-target is not automatically redundant while its source row is
live.

### Gate 3 — confirmed effects

For each `c` in `confirmed_ids`:

```text
CONFIRMED_CURRENTLY_APPLICABLE = YES
iff c is absent from current receiver confirmed state
```

If `c` is already present,
`CONFIRMED_CURRENTLY_APPLICABLE = NO`. No downstream counterfactual task-value
prediction is included.

### Whole-packet classification

If Gate 1 rejects, the whole packet is currently non-applicable. Otherwise:

```text
WHOLE_PACKET_CURRENTLY_NON_APPLICABLE = YES
iff
all remap effects are currently non-applicable
AND
all confirmed effects are currently non-applicable
```

If any audited task effect is potentially applicable, classification is `NO`.
A mixed-applicability packet is not an opportunity.

An empty task-effect packet (`remap_events = []`, `confirmed_ids = []`) is an
opportunity. A delayed matched-only packet with those two empty task-effect
sets is also an opportunity under this frozen implementation-relative
predicate.

## 8. ID-State effect semantics used by the predicate

**FROZEN_SCIENTIFIC_DECISION**

```text
SEMANTIC_APPLICABILITY_GRANULARITY = EFFECT_LEVEL
TRANSPORT_SERVICE_GRANULARITY = PACKET_LEVEL
AUDITED_DELAYED_CONSUMER_EFFECTS = REMAP_EVENTS_PLUS_CONFIRMED_IDS
```

The packet remains a heterogeneous, atomically served transport container.
The predicate evaluates its audited effects but classifies opportunity only at
whole-packet granularity. It does not authorize effect-level transmission.

Track-row numeric IDs and remap keys must be interpreted only as current
implementation state. The predicate must not infer immutable physical
identity, long-horizon lifecycle continuity, or supersession from those keys.

## 9. Frozen four-cell MVE

**FROZEN_SCIENTIFIC_DECISION**

| Role | Pair | Frozen C4 condition |
| --- | --- | --- |
| CONTROL | Pair23 | mild (`R_MILD` from frozen C4) |
| FRONTIER | Pair23 | strong (`R_STRONG` from frozen C4) |
| FRONTIER | Pair44 | moderate (`R_MODERATE` from frozen C4) |
| FRONTIER | Pair66 | mild (`R_MILD` from frozen C4) |

The frontier rule chooses, for each frozen workload tier, the mildest C4
service constraint where joint MDA degradation and IDSW worsening were already
observed. Pair23-mild is the no-pressure control.

```text
CELL_SELECTION = PRE_REGISTERED_FROM_FROZEN_C4_OUTCOMES
SHADOW_PREDICATE = FROZEN_BEFORE_SHADOW_RESULTS
SHADOW_MEASUREMENT = BLIND_TO_NEW_TRACKING_EVALUATION_OUTCOMES
CELL_SEARCH = NOT_AUTHORIZED
```

Dataset, split, frame range, detector, tracker, checkpoint, thresholds, packet
schema, service rates, seeds/determinism controls, and evaluator definitions
are inherited unchanged from each frozen C4 cell. Any new or replacement
value is `NOT FROZEN BY THIS CONTRACT` and requires a new Research Decision.

## 10. Shadow-only execution invariants

**FROZEN_SCIENTIFIC_DECISION**

```text
SHADOW_ONLY = TRUE
SAME_R = REQUIRED
SHADOW_TRAJECTORY_PARITY = MANDATORY
```

The observer must not skip, drop, reorder, cancel, preempt, resize, reserialize,
or repacketize traffic. It must not change `R`, packet schema, packet
generation, queue/service state, completion behavior, receiver state, tracking
state, or feedback. It records only the frozen label and descriptive evidence.

## 11. Primary opportunity metrics and denominators

**FROZEN_SCIENTIFIC_DECISION**

Primary metrics:

```text
checked_id_packet_count
whole_packet_non_applicable_count
whole_packet_non_applicable_ratio

checked_id_packet_wire_bytes
whole_packet_non_applicable_wire_bytes
whole_packet_non_applicable_wire_bytes_ratio
```

Denominators:

- packet ratio: ID-State packets that actually reach a true first-service
  decision;
- wire-byte ratio: wire bytes of those checked ID-State packets.

`whole_packet_non_applicable_wire_bytes` denotes baseline-trajectory
opportunity bytes. It does not denote realized service savings.

No new metric, significance test, arbitrary threshold, or majority gate is
frozen by this Contract.

## 12. Secondary descriptive mechanism evidence

**FROZEN_SCIENTIFIC_DECISION**

Permitted packet-level fields:

```text
version_reject_packet_count
empty_task_effect_packet_count
mixed_effect_packet_count
```

Permitted effect-level fields:

```text
remap_total
remap_applicable_count
remap_source_absent_count
remap_conflict_count
confirmed_total
confirmed_new_count
confirmed_already_present_count
```

Effect-level reason counts are not mutually exclusive packet categories. They
must not be summed or relabeled as a count of invalid packets.

## 13. Control interpretation

**FROZEN_SCIENTIFIC_DECISION**

Pair23-mild is a `NO_PRESSURE_NO_OP_CONTEXT_CONTROL`. Opportunity is not
required to be zero there. A control cell may contain currently
non-applicable work without queue/completion pressure.

The control separates opportunity occurrence from the separate question of
whether opportunity becomes consequential under finite service pressure.

## 14. Runs and progression rule

**NON_AUTHORIZATION**

```text
MINIMUM_VIABLE_EXECUTION = NOT_AUTHORIZED_BY_THIS_CONTRACT
FORMAL_EXECUTION = NOT_AUTHORIZED_BY_THIS_CONTRACT
COMPUTE_BUDGET = NOT_FROZEN_BY_THIS_CONTRACT
CHECKPOINT_RESUME_BEHAVIOR = NOT_FROZEN_BY_THIS_CONTRACT
```

**FROZEN_SCIENTIFIC_DECISION**

The only frozen first-stage matrix is the four-cell MVE in Section 9. Its
progression rule is:

- If all three frontier cells have zero
  `whole_packet_non_applicable_wire_bytes`, the exact conservative
  whole-packet intervention has no direct action opportunity on the frozen
  frontier cells and must not proceed unchanged automatically.
- If any frontier cell has non-zero
  `whole_packet_non_applicable_wire_bytes`, mark the Shadow Census complete and
  return evidence to the researcher for a new Research Decision.

Neither outcome authorizes closed-loop Oracle-FIFO. No `>5%`, `2/3`, majority,
or p-value progression rule is permitted.

## 15. Claim boundary

**CLAIM_BOUNDARY**

Permitted claims are limited to:

- existence or absence of whole-packet current non-applicability opportunities
  in the frozen cells;
- baseline-trajectory opportunity packet count and wire bytes;
- descriptive structure across the four frozen cells;
- mechanical reason breakdown.

Forbidden claims include actual service savings, queue relief, earlier
retained-packet completion, MDA or IDSW recovery, tracking benefit, deployable
validity policy, optimal communication policy, Supplement lifecycle,
all-channel applicability, and population-wide generalization.

## 16. Mandatory qualification gates

**MANDATORY_IMPLEMENTATION_QUALIFICATION**

All gates below must pass before any separately authorized Shadow Census run:

1. **Authority gate:** bind the implementation and inputs to the frozen C4
   authority and exact four-cell definitions.
2. **Event-local snapshot gate:** prove rows, confirmed state,
   `_applied_id_map`, and `_last_id_packet_version` are copied exactly at first
   service, before the first-byte decrement, once per checked packet.
3. **First-service denominator gate:** distinguish never-started packets from
   cross-frame continuations and count each checked ID-State packet once.
4. **Predicate consistency gate:** mechanically compare the read-only predicate
   with frozen delayed-consumer behavior on isolated/copied/synthetic state,
   without modifying authoritative state or running scientific tracking
   outcomes.
5. **Metric gate:** verify wire-byte accounting, denominators, packet/effect
   category separation, and absence of double-count interpretation.
6. **Shadow trajectory parity gate:** prove instrumentation does not alter the
   pre-existing scientific/runtime trajectory.

Parity evidence must canonically/mechanically cover pre-existing predictions,
packet generation, queue/service order and slices, completion behavior,
consumer consequences, feedback, and tracking trajectory. New shadow-only
metadata is permitted and need not make whole augmented files byte-identical
to old files. Exact artifact encodings and hash layouts are
`NOT FROZEN BY THIS CONTRACT`.

## 17. Leakage and post-hoc prohibitions

**NON_AUTHORIZATION**

The following invalidate the Census:

- future receiver or GT information;
- post-arrival outcome leakage;
- end-of-frame, post-admission, later-stage, post-feedback, or ledger-based
  reconstruction of first-service receiver state;
- selecting new cells from Shadow or new tracking/evaluation outcomes;
- changing the predicate after observing Shadow results;
- using future completion, termination, MDA, or IDSW in classification;
- treating newer version/time as semantic dominance;
- treating same-key/same-target as proven redundancy;
- converting effect reason counts into mutually exclusive packet totals.

## 18. Explicit non-authorization block

**NON_AUTHORIZATION**

This Contract does not authorize:

```text
SHADOW_CENSUS_IMPLEMENTATION
SHADOW_CENSUS_EXECUTION
CLOSED_LOOP_PACKET_SKIP_OR_DROP
CANCEL_OR_PREEMPTION
REPACKETIZATION_OR_EFFECT_LEVEL_TRANSMISSION
SUPPLEMENT_APPLICABILITY
TTL
SUPERSESSION_OR_LATEST_WINS
ACK_OR_RECEIVER_FEEDBACK_CHANNEL
PRIORITY_SCHEDULING_OR_EDF
OPTIMIZATION_OR_UTILITY_PREDICTION
BANDIT_OR_RL_OR_MARL
NEW_SCIENTIFIC_METRIC_OR_SIGNIFICANCE_THRESHOLD
NEW_CELL_SEARCH_OR_POPULATION_CLAIM
```

Each requires a new Research Decision and separate authorization.

## 19. Required artifacts and seals for a future implementation stage

**MANDATORY_IMPLEMENTATION_QUALIFICATION**

A future, separately authorized implementation stage must define and produce:

- implementation-authority and frozen-C4 input bindings;
- a machine-auditable record that each Shadow label was captured at the
  one-time first-service event;
- canonical/mechanical Shadow trajectory parity evidence for all pre-existing
  behavior;
- isolated predicate-versus-consumer consistency evidence;
- denominator, wire-byte, and reason-counter validation evidence;
- per-cell completeness and failure status for the four frozen cells;
- an immutable run-start/run-end status and qualification seal sufficient to
  prevent incomplete evidence from being interpreted.

Artifact filenames, schemas, hashing details, output directory, and resume
protocol are `NOT FROZEN BY THIS CONTRACT` and require independent
implementation review before execution authorization.

## 20. Stop conditions

**MANDATORY_IMPLEMENTATION_QUALIFICATION**

Stop without interpreting opportunity results if any of the following occurs:

- authority or frozen-cell binding fails;
- Shadow trajectory parity fails or cannot be established;
- event-local timing or one-time first-service identity cannot be proved;
- future/post-hoc state enters the predicate;
- predicate-versus-consumer consistency fails;
- denominator or byte-accounting validation fails;
- packet-level and effect-level counts cannot be separated;
- any required cell is incomplete;
- an unauthorized runtime, tracking, communication, evaluator, metric, cell,
  or predicate change is introduced.

**NON_AUTHORIZATION**

If either frontier outcome pattern is observed, stop at evidence return. Do not
self-authorize a closed-loop intervention.

## 21. Contract status block

```text
C5_SHADOW_CENSUS_CONTRACT_STATUS = DRAFT_COMPLETE

SCIENTIFIC_FREEZE_SOURCE =
C5_SHADOW_CENSUS_AUTHORITATIVE_DECISION_BLOCK_R1_R3

C5_SHADOW_SCOPE = ID_STATE_ONLY

CELL_SELECTION =
PRE_REGISTERED_FROM_FROZEN_C4_OUTCOMES

SHADOW_PREDICATE =
FROZEN_BEFORE_SHADOW_RESULTS

SHADOW_MEASUREMENT =
BLIND_TO_NEW_TRACKING_EVALUATION_OUTCOMES

SHADOW_TRAJECTORY_PARITY_REQUIRED = YES
CURRENT_STATE_ORACLE_ONLY = YES
FUTURE_INFORMATION_ALLOWED = NO
CAUSAL_SERVICE_START_BOUNDARY = CLOSED

CLOSED_LOOP_PACKET_SKIP_AUTHORIZED = NO
CLOSED_LOOP_ORACLE_PROBE_AUTHORIZED = NO
SUPPLEMENT_APPLICABILITY_AUTHORIZED = NO
TTL_AUTHORIZED = NO
SUPERSESSION_AUTHORIZED = NO
EDF_PRIORITY_AUTHORIZED = NO
RL_MARL_AUTHORIZED = NO

SHADOW_CENSUS_EXECUTION_AUTHORIZED = NO
C5_IMPLEMENTATION_AUTHORIZED = NO
IMPLEMENTATION_STARTED = NO
EXPERIMENT_EXECUTED = NO

P0_OPEN = 0
BLOCKERS = NONE

NEXT_AUTHORIZED_STAGE =
INDEPENDENT_CONTRACT_REVIEW
```
