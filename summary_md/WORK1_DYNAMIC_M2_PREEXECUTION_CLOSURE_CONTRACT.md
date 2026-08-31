# Work 1 Dynamic M2 Preexecution Closure Contract

## Status

```text
PREEXECUTION_SCOPE_CLOSED
DYNAMIC_M2_EXECUTION = NOT_AUTHORIZED
MVE = NOT_RUN
FORMAL = NOT_RUN
HELDOUT = NOT_ACCESSED
GT_SAFETY = UNGRADED
```

The sole estimand remains whether Work 1 observer instrumentation preserves
frozen original-MIA runtime behavior. A/B/C success still requires exact core
equality and two independent zero gates:

```text
CORE_OUTPUT_DIFF = 0
B_VS_C_CORE_DIFF_COUNT = 0
OBSERVER_GUARD_CHANGE_COUNT = 0
```

Nonzero counts are diagnostic positions, not independent causal mutation-event
counts and are never added together.

## Closed closure list

| ID | Frozen repair | Required evidence |
| --- | --- | --- |
| C1 | material launch provenance | exact resolved wrapper/config/checkpoint/Python paths and hashes; dataset/XML roots and runtime identity |
| C2 | executable G-XML1 observed producer | bytes independently hashed from resolved runtime paths; no XML parsing |
| C3 | exact ten-unit input manifest | five pairs, both directions, exact filename/count/set/content identity; frame count manifest-derived |
| C4 | real-event G-XML4 chain | one passive monotonic source advanced at actual last read, initialization completion and first E_pre hooks |
| C5 | actual-access G-XML3 evidence | registered Work 1 path/interface/serialization observations plus static rejection of unregistered forbidden interfaces |
| C6 | G-XML5 execution integration | prelaunch schema/template and final artifact/report gates |
| C7 | pair provenance | structured launch injects non-null pair/role; ledgers, lifecycle and traces retain pair/view attribution |

No other repair may be introduced in this closure epoch.

## Blocker admission criteria

A newly found issue blocks only if it demonstrates at least one:

- `B1_FALSE_PASS_RISK`
- `B2_SCIENTIFIC_SEMANTIC_DRIFT`
- `B3_ABC_TREATMENT_CONTAMINATION`
- `B4_ORACLE_LEAKAGE`
- `B5_REPRODUCIBILITY_AUTHORITY_FAILURE`
- `B6_REQUIRED_EVIDENCE_IMPOSSIBLE_TO_PRODUCE`

The final audit must identify the criterion, a reproducible counterexample and
the material consequence. Additional logging, redundant hashes, presentation,
performance-overhead measurement, naming and debug detail are not blockers.

## Severity semantics

- P0: only future/oracle leakage, hidden treatment contamination, or destructive
  author-state mutation; blocks.
- P1: only a demonstrated B1-B6 issue; blocks.
- P2: important limitation without B1-B6 consequence; non-blocking warning.
- P3: metadata/readability/cleanup; non-blocking cleanup.

## G-XML3 observability boundary

Dynamic evidence covers actual calls at registered Work 1-owned file/path
interfaces, observer constructor/runtime inputs and token/ledger serialization.
Static AST/source-hash gates reject unregistered forbidden imports, parameters,
environment/schema fields and serialized keys. Arbitrary hidden Python
reflection is explicitly not claimed. Frozen author first-frame XML access is
separate execution-validity provenance and never a Work 1 scientific input.

## Frozen final-audit scope

The next audit may check only C1-C7, regression of previously closed blockers,
clean/frozen Git provenance, executable prelaunch gates and a new issue meeting
B1-B6. If all pass and no admitted blocker exists, it must return
`AUTHORIZE_DYNAMIC_M2_EXECUTION`. This contract does not itself authorize or
execute Dynamic M2.
