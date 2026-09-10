# P13 runtime-evidence adapter corrective revision

## Scope

This narrow revision closes only the outcome-blind `pending_at_end_count`
evidence gap found after the completed Formal Val run. It does not alter the
frozen runtime, execution package, cache, inputs, predictions, evaluator, or
scientific analysis path.

## Root cause and correction

The frozen runtime records terminal queued packets as `packet_action =
"pending_at_end"` events in its immutable packet trace, while the locked-d1
validity gate previously expected `pending_at_end_count` to be present directly
in the runtime manifest set.

The validity layer now accepts a distinct `runtime_packet_trace` input. It:

- admits only a regular file contained by the accepted attempt root;
- mechanically counts only `packet_action == "pending_at_end"`;
- rejects malformed rows, non-string actions, symlinks, and forbidden scientific
  fields;
- rejects a conflict if a runtime manifest also declares a different count;
- binds the trace identifier, current SHA-256, byte count, and derived count in
  `RUNTIME_GATES_CHECKED.json`;
- reopens and re-derives the current trace during acceptance sealing and every
  later acceptance-seal verification.

The request CLI exposes the same `runtime_packet_trace` input for both artifact
validation and runtime-gate production.

An end-to-end rehearsal also found that the validity parity producer still
looked for reference attempts under `attempts/`, while the sealed P13 execution
plan correctly writes them under the isolated `references/` root. The producer
and its later seal verifier now enforce that exact sealed reference layout.

## Verification

```text
Focused validity/analysis tests: 20 passed
Locked-d1 regression: 55 passed
Full repository regression: 397 passed, 2 skipped
Existing Formal Val runtime-evidence rehearsal: 25/25 gates passed
```

The rehearsal read only runtime manifests and the predefined `packet_action`
field from packet traces. Prediction files, metrics, scientific outcomes, Train
outputs, evaluator, analyzer, and unblinding were not accessed.

Independent Team B delta audit remains required before regenerating acceptance
evidence or sealing Formal Val measurement validity.
