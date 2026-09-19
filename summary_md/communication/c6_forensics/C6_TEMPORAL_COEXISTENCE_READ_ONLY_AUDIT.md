# C6 Temporal Coexistence Read-Only Audit

```text
POST_HOC / READ_ONLY / EXISTING_ATTEMPT4_EVIDENCE_ONLY
```

## 1. Scope and governance

This audit parses only the sealed C6 Attempt4 treatment service and suppression
ledgers for `P23/FIFO-strong`, `P23/FIFO-mild`, `P44/FIFO-moderate`, and
`P66/FIFO-mild`.  It does not execute runtime code, alter an Attempt4 artifact,
read tracking outcomes, or reinterpret the frozen C6 result.

```text
RISK_CLASS = GREEN
AFFECTED_AUTHORITY = NONE; existing C6 authorities are read-only inputs
AFFECTED_INVARIANTS = evidence immutability; tracking-outcome embargo; three-layer authority model
REQUIRED_GATES = sealed-evidence provenance; service-accounting reconciliation; explicit observability limits
PROHIBITED_EXTRA_GATES = Formal readiness; platform requalification; Formal authorization; unsupported new governance gate
PLATFORM_REQUALIFICATION_REQUIRED = NO
EXACT_REHEARSAL_REQUIRED = NO
FORMAL_AUTHORIZATION_REQUIRED = NO
```

The planned report/CSV-only delta was independently classified as `GREEN`,
`STATIC_DELTA_REVIEW`, with no Science Authority, Platform Authority, or
qualification-evidence impact.  No new Gate is introduced: the accounting and
observability checks protect against the documented threat of treating
frame-level aggregates as simultaneous serviceable work.

## 2. Evidence availability

| Field / concept | Source | Status | Grain / coverage | Limitation |
| --- | --- | --- | --- | --- |
| Service epoch and event order | `c4_service_ledger_<pair>-1.jsonl` | Direct | event ordinal, every frame, all cells | Event, not wall-clock, order |
| Frame service budget and final unused budget | service ledger `frame_summary` | Direct | every frame, all cells | Final frame residual, not a counterfactual credit |
| ID-State offered and suppressed obligation | service ledger `packet_summary`; `c6_first_service_decisions_*.jsonl` | Direct | packet/event, all cells | No payload/snapshot for independent re-evaluation of non-empty predicate cases |
| ID-State serviced work | service ledger `service_start` / `service_slice` | Direct | event, all cells | No ID-State service event occurs |
| Supplement offered, serviced, and waiting delay | service ledger enqueue/start/slice/terminal | Direct | event, all cells | Start backlog represents the selected packet; queue length is already zero |
| Total queued bytes / packets | service-ledger `queue_backlog_bytes`, `queue_length` | Direct | every event | Not channel-specific after an event |
| Serviceable ID-State backlog | decision Boolean plus post-decision queue state | Derived | each first-service decision, all cells | Predicate Boolean is sealed evidence; non-empty effects cannot be independently recomputed from persisted payload/state |
| Idle capacity | `frame_unused_budget` and service slices | Direct/derived | every frame, all cells | It is the end-of-frame residual |

`SERVICEABLE_ID_BACKLOG_OBSERVABILITY = DERIVED`: the ledger directly records
all ID-State packets as suppressed at their first decision and records no
post-decision queue or ID-State service start.  The conclusion is limited to
the sealed logical-service trajectory; it is not an independent replay of each
non-empty predicate effect.

## 3. Definitions and temporal grain

The highest available fidelity is ledger event order within a frame.  A
suppression epoch is an `id_state` `suppression` event.  For a suppression
event `e`:

- `released_capacity_e` is the `suppressed_service_obligation_bytes` of its
  matching ID-State packet summary.  It is a logical avoided obligation, not
  automatically final idle capacity in that frame.
- `total_id_backlog_e` is the recorded queue state after the predicate decision.
- `serviceable_id_backlog_e` is positive only if a surviving, non-suppressed
  ID-State packet is recorded as queued or service-starting after its applicable
  first-service decision.
- `supplement_backlog_e` is positive only for already queued/pending Supplement
  work at that event.  A later same-frame enqueue is reported separately, not
  back-dated to the suppression event.
- `idle_capacity_t` is final `frame_unused_budget` after all events in frame
  `t`; per-frame conservation checks it against actual service slices.

This distinction prevents a same-frame aggregate from being misreported as
simultaneous recipient backlog and idle capacity.

## 4. Conservation and event-order checks

For every cell, every frame satisfies:

```text
frame_service_budget = sum(service_slice.bytes_served) + frame_unused_budget
ID-State offered = ID-State suppressed + ID-State serviced + ID-State remaining
Supplement offered = Supplement serviced + Supplement remaining
```

All cells have `byte_conservation=1`, `frame_budget_conservation=1`,
`terminal_conservation=1`, and `work_conserving=1` where the field is emitted.
All frame summaries end with queue bytes and queue length equal to zero.

At every active frame, event order is:

```text
ID-State enqueue → ID-State suppression (queue becomes zero)
→ Supplement enqueue → Supplement service start/slice/terminal
→ frame summary with positive unused budget
```

The Supplement starts have `waiting_delay=0` and `queue_length=0`: their
positive `queue_backlog_bytes` is the just-selected packet, not a surviving
waiting queue.  Thus Supplement work is present and served later in the same
frame, but is not queued at the preceding suppression event and does not remain
queued at final idle capacity.

## 5. Per-cell temporal coexistence

See `C6_TEMPORAL_COEXISTENCE_SUMMARY.csv` for exact counts and bytes.

| Cell | Suppression epochs | Strict suppression epochs with post-decision ID backlog | with serviceable ID backlog | with already-pending Supplement backlog | with final frame idle | Temporal verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| P23 strong | 699 | 0 | 0 | 0 | 699 | `NO_RECIPIENT_COEXISTENCE_OBSERVED` |
| P23 mild | 699 | 0 | 0 | 0 | 699 | `NO_RECIPIENT_COEXISTENCE_OBSERVED` |
| P44 moderate | 359 | 0 | 0 | 0 | 359 | `NO_RECIPIENT_COEXISTENCE_OBSERVED` |
| P66 mild | 299 | 0 | 0 | 0 | 299 | `NO_RECIPIENT_COEXISTENCE_OBSERVED` |

For every cell, the first and last suppression frames are `1` and the final
sequence frame (`699`, `699`, `359`, `299`).  Supplement service starts occupy
the same active-frame interval, but strictly follow suppression; final idle
capacity is positive from frame `0` through the final frame.  No ID-State
`service_start` is recorded in any cell.

At frame resolution only, every suppression frame also contains later
Supplement service and final residual capacity.  That is a frame-level
co-occurrence proxy, not a simultaneous recipient backlog: the event ledger
shows zero waiting delay, zero queue length, and no remaining queue before the
frame becomes idle.

## 6. Counterexample search

The search covered every Attempt4 suppression event and every subsequent
ledger event in its frame.  No event satisfied either strict counterexample:

```text
suppression + positive serviceable ID-State backlog + idle capacity
suppression + positive already-pending Supplement backlog + idle capacity
```

No ID-State service start exists; all post-suppression queue values are zero.
Supplement packets arrive after suppression, are served immediately, and are
absent at the final idle observation.  Therefore the sealed evidence contains
no strict missed-reuse candidate.  This does not prove that redistribution is
impossible under a different trajectory or scheduling policy.

## 7. Interpretation boundary

```text
ALL_CELL_TEMPORAL_INTERPRETATION =
STRUCTURAL_NON_TEST_STRENGTHENED_FOR_THE_SEALED_C6_LOGICAL_SERVICE_TRAJECTORY

MISSED_REUSE_CANDIDATE_OBSERVED = NO
H_R_CAPACITY_REDISTRIBUTION = NOT_SUPPORTED (unchanged)
H_R_FROZEN_VERDICT_CHANGED = NO
RD_C7_01_FROZEN = NO
```

The audit strengthens a narrow statement: when C6 removed each recorded
ID-State obligation, no surviving serviceable ID-State recipient was recorded
at that exact service event.  Supplement traffic did exist later in each active
frame and was served, but the ledger cannot attribute those bytes
counterfactually to suppression and it does not show a waiting Supplement queue
coexisting with final idle capacity.  Persisted predicate evidence remains
partially explanatory for non-empty effects; this report does not elevate that
limitation into a challenge to the frozen result.

## 8. Evidence for a future eligibility rule

Any later, separately reviewed redistribution test must guarantee, without
choosing thresholds here:

- nonzero stale/suppressible work;
- nonzero surviving, demonstrably serviceable recipient work;
- event-ordered temporal overlap between released logical capacity and that
  recipient backlog;
- sufficient volume beyond one-packet regimes; and
- accounting that can distinguish actual service from final unused capacity.

No C7 treatment, threshold, scheduler, queue-time policy, or authorization is
created by this audit.
