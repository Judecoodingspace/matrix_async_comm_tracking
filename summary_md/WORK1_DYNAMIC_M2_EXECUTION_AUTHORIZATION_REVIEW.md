# Work 1 Dynamic M2 Execution Authorization Review

## Review status

```text
DYNAMIC_M2_COMPARISON_COVERAGE_BLOCKER
```

This is a `PREEXECUTION_REVIEW_ONLY` record. No A/B/C, detector, tracker,
dataset, MVE, Formal, held-out, or GT safety-grading execution occurred.

## Frozen inputs and provenance

- Pair set: train `23,25,27,28,29`, both views, full available sequences.
- Delay: `local=0,homography=0,id_state=5,supplement=0`.
- Parent entrypoint, XML reader, first-frame initialization region, XML files,
  and wrapper construction are frozen in
  `WORK1_DYNAMIC_M2_XML_INPUT_MANIFEST.json`.
- XML was handled only as file identity: existence, realpath, metadata and
  SHA-256. No XML scientific field was parsed.
- Parent and provenance authority hashes match the frozen values. The focused
  parity/governance suite passed (`24 passed`), and G-XML3 static passed.

## Frozen future launch semantics

```text
A = frozen v8 parent; observer absent
B = one persistent isolated derivative; MIA_WORK1_OBSERVER=0
C = the same persistent isolated derivative; MIA_WORK1_OBSERVER=1
```

The derivative must be generated only after a separate execution authorization,
then structurally audited and hashed before any process launch. Its manifest,
entrypoint, and observer hashes are therefore not runtime facts yet.

The exact non-executed command templates and their permitted differences are
in `WORK1_DYNAMIC_M2_EXECUTION_SPEC.json`.

## Gate order

```text
M2_SYNTHETIC_PARITY_PASS
  -> G-XML1 frozen provenance
  -> G-XML3 STATIC
  -> frozen parent hash audit
  -> authorized persistent-derivative generation
  -> derivative structure/hash audit
  -> A/B/C launch-command diff audit
  -> A/B/C launch
  -> G-XML2 initialization equality
  -> G-XML4 initialization-boundary ordering
  -> G-XML3 DYNAMIC
  -> complete core-output comparison
  -> observer-mutation audit
  -> Dynamic M2 decision
```

## Pre-launch versus runtime gates

| Gate | Can be checked before launch? | Requires runtime? | Failure action |
| --- | --- | --- | --- |
| M2 synthetic parity | Yes; PASS | No | `DO_NOT_LAUNCH` |
| G-XML1 provenance | Yes | No | `DO_NOT_LAUNCH` |
| G-XML3 static | Yes; PASS | No | `DO_NOT_LAUNCH` |
| Frozen parent hash | Yes; PASS | No | `DO_NOT_LAUNCH` |
| Derivative structure/hash | Only after authorized generation | No | `DO_NOT_LAUNCH` |
| Pair/XML manifest | Yes; PASS | No | `DO_NOT_LAUNCH` |
| A/B/C launch diff | Not fully satisfiable | No | `DO_NOT_LAUNCH` |
| G-XML2 initialization equality | No | Yes | invalid attempt; stop |
| G-XML4 marker ordering | No | Yes | invalid attempt; stop |
| G-XML3 dynamic | No | Yes | invalid attempt; stop |
| `CORE_OUTPUT_DIFF` | No | Yes | `DYNAMIC_M2_NON_INTERFERENCE_FAIL` |
| observer mutation count | No | Yes | `DYNAMIC_M2_NON_INTERFERENCE_FAIL` |

## Required runtime artifacts

The future attempt must produce, rather than pre-create:

- `WORK1_DYNAMIC_M2_EXECUTION_MANIFEST.json`
- `ABC_LAUNCH_ARGUMENT_DIFF_AUDIT.json`
- `ABC_INITIALIZATION_EQUALITY_AUDIT.json`
- `AUTHOR_INITIALIZATION_BOUNDARY_AUDIT.json`
- `WORK1_RUNTIME_ORACLE_FIREWALL_AUDIT.json`
- `WORK1_PARENT_DERIVATIVE_HASH_AUDIT.json`
- `WORK1_CORE_OUTPUT_COMPARISON.json`
- `WORK1_OBSERVER_MUTATION_AUDIT.json`
- `WORK1_DYNAMIC_M2_DECISION.md`

The preexecution XML manifest, execution spec, stop matrix, and evidence
availability matrix are the only artifacts created in this review.

## Decisive blocker

`DYNAMIC_M2_COMPARISON_COVERAGE_BLOCKER` is established from source:

1. The parent A emits no Work 1 comparison trace.
2. The derivative B with observer OFF instantiates no observer and emits no
   comparison trace.
3. The derivative C records only an author High-score digest and a terminal
   digest subset; it does not emit the frozen comparison scope: detector rows,
   tracker rows/order, all three ID-state stage outputs, low-score inputs and
   outputs, NMS, feedback/next-frame state, final predictions, and packet
   accounting.
4. `scripts/run_mdmt_mia_work1_eligibility_mve.py` only hashes three already
   supplied artifacts; it cannot collect or verify the required scope.
5. The present A/B/C templates also do not have a resolved launch-diff policy:
   B/C require isolated ordinary output roots for retained artifacts, while the
   frozen rule authorizes only observer enablement and observer-output path.

Thus the current implementation cannot measure the required full
`CORE_OUTPUT_DIFF` or substantiate
`TRACKER_MUTATION_COUNT_FROM_OBSERVER=0`. Runtime-required evidence is not
misreported as prelaunch PASS; the blocker is missing measurement coverage,
not the mere absence of a runtime result.

## Fail-closed policy

The exact stop matrix is in `WORK1_DYNAMIC_M2_STOP_MATRIX.json`. Any failed
attempt must stop without repair-and-continue, pair/XML replacement, parameter
change, gate relaxation, digest regeneration, or comparison-scope reduction.

## Authorization recommendation

```text
DO_NOT_AUTHORIZE_DYNAMIC_M2_EXECUTION
```

This review does not authorize A/B/C, MVE, Formal, held-out access, GT safety
grading, tracker write-in, or Route A.
