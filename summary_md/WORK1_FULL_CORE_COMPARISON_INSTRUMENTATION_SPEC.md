# Work 1 Passive Full-Core Comparison Instrumentation Specification

## Decision

```text
DYNAMIC_M2_COMPARISON_COVERAGE_BLOCKER_CLEARED_FOR_REVIEW
DYNAMIC_M2_EXECUTION_NOT_AUTHORIZED
```

## A/B/C architecture

```text
frozen parent (never edited in place)
  +-- isolated A traced derivative
  |     shared full-core recorder; no Work 1 treatment
  +-- isolated shared BC traced derivative
        shared full-core recorder
        +-- B: observer OFF
        +-- C: observer ON
```

`A_PARENT_REFERENCE` remains the immutable hash authority.
`A_TRACED_RUNTIME` is a comparison-only derivative. Before interpreting future
Dynamic M2, it must pass source/diff/passivity gates and future real parent vs
A-traced output parity. This design pass proves structural/synthetic parity but
does not claim real-runtime parity.

The runtime parity gate is now machine-implemented as exact byte-SHA comparison
of the two author prediction artifacts per pair. Any mismatch is
`A_PARENT_VS_A_TRACED_RUNTIME_PARITY_FAIL`.

## Exact canonicalization

Canonicalization produces UTF-8 JSON bytes from a type-tagged tree with sorted
mapping keys and no `repr`, Python `hash`, pickle, tolerance, or approximate
float comparison.

- arrays: defensive contiguous copy, exact dtype string, exact shape, ordered values;
- floats: exact hexadecimal finite representation; deterministic `nan/+inf/-inf` tokens;
- integers, floats and booleans remain type-distinct;
- list and tuple order is retained; sets are byte-sorted;
- tensors are detached and copied to CPU before canonicalization;
- `None`, empty arrays and non-contiguous views have explicit semantics;
- object-dtype arrays and cyclic graphs fail closed;
- aliases are traversed as values and never modified.

Equality is `EXACT_CANONICAL_EQUALITY`. Any dtype, shape, row-order, runtime-ID,
bbox, event-order, event-count, queue, counter, or payload difference is a diff.

## Ordered checkpoints

The checkpoint vocabulary and three ordered profiles
(`FRAME0_CHECKPOINT_PROFILE`, `STANDARD_FRAME_CHECKPOINT_PROFILE`, and
`FINAL_CHECKPOINT_PROFILE`) are literal constants in
`src/tracking/mdmt_mia_work1_core_comparison.py`. A/B/C use the same copied
recorder source and generated specification. A/B/C must have identical count
and order for the same pair/frame. Comparison never uses intersection-only
matching; the monotonically increasing `checkpoint_sequence` is also compared.

Before cross-run comparison, each trace is independently validated against the
exact JSON field set, role/observer treatment, contiguous sequence numbers,
expected pair, externally supplied full frame count, frame-0 profile, every
standard-frame profile, and the final profile. Empty traces, uniform omission,
uniform truncation, duplicate rows and schema drift fail closed even when A/B/C
are identically malformed.

## Trace and comparison

Each JSONL row follows `WORK1_FULL_CORE_COMPARISON_TRACE_SCHEMA.json`. Default
storage is digest plus structural metadata; full canonical payload is not
serialized. The strict comparator checks record count, checkpoint sequence,
pair/frame/view, type, shape, dtype, digest, event count, source region and
schema version.

```text
CORE_OUTPUT_DIFF = number of aligned trace positions with any exact inequality,
including missing, extra, or sequence-mismatched records.
```

The comparator reports only the first mismatch location and structural detail
needed for fail-closed diagnosis.

## Observer mutation metric

Observer guard checkpoints surround every Work 1 hook and contain every mutable
author object supplied to that hook. The closure epoch retains two independent
diagnostic counts:

```text
B_VS_C_CORE_DIFF_COUNT
OBSERVER_GUARD_CHANGE_COUNT
```

They are not added and a nonzero value is not described as an independent
mutation-event count. The gate requires both to be zero. It does not claim
impossible causal attribution beyond observed boundaries. Next-frame state and
final predictions are included in `B_VS_C_CORE_DIFF_COUNT`.

## Passivity

Every recorder call is statement-only; return values are ignored. Recorder
operations are copy/canonicalize/digest/append-to-private-ledger and return
`None`. It imports no detector/tracker/Supplement/packet/GT/XML algorithm and
calls no author method. Packet state is copied from fields without invoking
scheduler methods. Frozen helper/runtime files remain byte-identical.

Instrumentation runtime overhead is `UNGRADED`. Wall-clock overhead is not a
semantic metric. Any changed scheduling/state checkpoint is a comparison
failure rather than an allowed tolerance.

## Generation and future gates

The generator verifies frozen hashes, copies to new isolated roots, adds the
same recorder/version/checkpoint schema, writes a derivative manifest, and
re-verifies protected helpers. Persistent derivatives must only be generated
after a separate execution authorization.

Future runtime must produce A/B/C JSONL traces and
`WORK1_CORE_OUTPUT_COMPARISON.json`. None were generated in this task.

It must also produce a same-condition B repeat. Exact trace equality is required;
any mismatch is `EXACT_COMPARISON_DETERMINISM_BLOCKER`. The normalized launch
environment/argv audit is machine-enforced before launch.
