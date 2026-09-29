# V2-2 prospective dependency map — Team A registration candidate

Source corrective: `42118c0594523efa3823397fed054770549a827d`. Applicability anchor: the same exact SHA. This registration is prospective; it does not reclassify the historical `3430054ec32489116523644fc958ccb7ac29f4d3` → `5c59a2e51bb65dd9a59b6ba2801dc26292a9c2a4` introduction diff. Its exact-bound review remains in `candidate_evidence/V2_2_INTRODUCTION_UNKNOWN_SCOPE_REVIEW.json` and uses the historical map.

The long-lived map now adds three behavior-oriented units:

| Unit | Scope | Level | Dependency |
| --- | --- | --- | --- |
| `v2_2.execution_lifecycle` | Attempt namespace, process identity/session, mechanical terminal, detached launch and outcome-blind stdio in the execution module and thin CLI | L1 | None |
| `v2_2.qualification_protocol` | Non-scientific Q1/Q2/Q4/Q5 qualification orchestration and synthetic child protocol | L1 | `v2_2.execution_lifecycle` |
| `tests.v2_2_execution_qualification` | Test-only qualification source | L0 | None |

`V2_2_EXECUTION_RELIABILITY` is registered against the first two units with the `V2_2_EXECUTION_RELIABILITY_QUALIFICATION` gate. This is a dependency classification, not independent acceptance of Team A's Q3 or other V2-2 evidence. All pre-existing C6/C7 behavior units, edges, and evidence rows remain unchanged; no historical C7 evidence depends on V2-2. The C6 dynamic import boundary remains `UNMAPPED`. Supporting V2-2 documents and candidate evidence remain outside the long-lived behavior graph.

The map identity is `ff0a2b71bcb49da21dbdbb32f62e8c1d68191a601245817c1105a873194e267d`; its representation digest is `dcfbdfb73c59a327973064b1d13a1fb91ebb1ef5e1cb565a39df27d85cdd6ab0`. Both were recomputed by `make_mapping()`. `make_applicability()` binds the map to nine non-L0 source paths at the source corrective SHA.

Focused Governance v2 tests: 40 passed. Temporary Git commit fixtures show a future lifecycle or qualification-protocol change makes V2-2 evidence `NON_INHERITABLE` while unrelated C7 evidence remains `INHERITABLE`; a V2-2 test-only change has no protected scientific invariant impact. Independent review of this exact registration commit remains pending. `V2_2_CLOSED_PASS=NO` and `H_R_FORMAL_AUTHORIZED=NO`.
