# C6 to C7 Decision Inputs

```text
POST_HOC
READ_ONLY
NON_PREREGISTERED_EXPLANATORY_ANALYSIS
C7_EXECUTION_AUTHORIZED = NO
```

This document records factual branches only. It does not design, select, or authorize C7.

## Supported factual branches

### Branch A — Part of the 100% suppression pattern is directly supported

The empty-effect branch is independently supported by the decision flag and Census effect counts for 1,076 decisions in each P23 cell, 837 in P44, and 592 in P66. These counts reconcile with the frozen predicate's `all([])` behavior.

### Branch B — Predicate explanatory persistence is incomplete

For 1,021 decisions in each P23 cell, 240 in P44, and 305 in P66, the suppressed Boolean is persisted with an empty reason list. Frozen source semantics identify these as non-empty, all-non-applicable results, but Attempt4 does not persist the treatment receiver snapshot or per-effect results needed for independent verification.

### Branch D — Observable C5/C6 trajectory divergence exists

C5 and C6 have the same ID-State emission counts per cell, but exact wire contents diverge from frame 6 in P23, frame 3 in P44, and frame 8 in P66. P66 also contains two exact same-wire examples whose C6 first service occurs one or two frames earlier and whose C5 and C6 applicability classifications differ.

### Branch E — The full P44/P66 classification divergence remains unresolved

Only 7 P44 and 21 P66 first-service packets have exact unique wire-digest correspondence. C6 does not persist the predicate state needed to explain the remaining all-suppressed decisions. P44 and P66 are therefore only partially explained, not reconciled packet-by-packet.

## Service-budget facts

- All treatment ID-State obligation is suppressed; treatment serviceable ID-State serviced bytes and remaining bytes are both zero.
- Supplement service is observed and fully accounted on each treatment trajectory.
- Frame-unused logical capacity is directly derivable and positive in every cell.
- Existing evidence does not establish that suppression caused the observed Supplement service.
- `H_R_CAPACITY_REDISTRIBUTION = NOT_SUPPORTED` remains frozen.

## Exactly one next Research Decision

```text
NEXT_RESEARCH_DECISION_ID = RD-C7-01

QUESTION =
Should the next separately authorized study first close the missing treatment-path predicate-state evidence for non-empty suppressed packets, or accept the present partial explanation and instead test redistribution only in a regime that retains serviceable ID-State work?

WHY_THIS_DECISION_IS_NOW_REQUIRED =
Attempt4 validly establishes positive suppression and no serviceable-ID redistribution, but 100% of treatment ID-State decisions were suppressed; 1,021/1,021/240/305 decisions per cell lack independently reproducible predicate-state evidence, and P44/P66 C5-to-C6 divergence is only partially localized.

OPTION_A =
Authorize a separate evidence-completeness study whose scientific purpose is to make the existing predicate decision independently auditable for non-empty effects.

OPTION_B =
Treat the current partial predicate explanation as the stopping boundary for C6 and discuss a separate redistribution study whose eligibility requires nonzero serviceable ID-State work.

WHAT_INFORMATION_EACH_OPTION_ALLOWS =
Option A can determine whether the all-non-applicable treatment decisions are independently reproducible from persisted packet and receiver state. Option B can determine whether redistribution is observable when the treatment trajectory contains eligible serviceable ID-State work, but it would not retrospectively resolve Attempt4's missing predicate-state evidence.

SCIENTIFIC_INVARIANT_AT_STAKE =
Measurement-validity evidence must remain separate from a new redistribution hypothesis; neither option may redefine H_R post hoc, use tracking outcomes to explain communication behavior, or convert the C6 conditional review into C7 authorization.
```

```text
NEXT_STAGE = HUMAN_RESEARCH_DECISION_DISCUSSION
```
