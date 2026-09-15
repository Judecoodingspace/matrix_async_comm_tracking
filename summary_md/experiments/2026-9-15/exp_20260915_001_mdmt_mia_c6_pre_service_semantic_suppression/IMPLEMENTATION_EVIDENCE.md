# C6 bounded implementation evidence

**Status:** non-scientific implementation evidence only.

## Authority

```text
IMPLEMENTATION_BASE_SHA = 9a511c3ce300b5dedb1f2e970f131ddd2522b0c0
C5_PRODUCTION_BYTE_PROVENANCE_SHA = 846350036f4169b0715e4d33caaa54c947a5e8e7
CONTRACT_SHA = 989ee15285866b119a643f1f1ccdf52d2d02009f
CONTRACT_RAW_SHA256 = f89bb6d2f1c218b85fee7d77916a3f911d19687f34fbef9c51196b6e245de125
PLAN_SHA = 93f44de70c4540afa0f3044aa066a0ed894648e9
PLAN_RAW_SHA256 = 277b1426628c0eadfd93fabac2399137d96c4a7c30ca91ce4d0fe0fc93d95a7b
```

The C5 production runtime is byte-identical between `8463500...` and
`9a511c3...`; the latter additionally carries the validated cell-local Shadow
evidence-path corrections in the C5 runner/test path.

## Bounded implementation

TB-C6-DELTA-01 corrective revision: the baseline CLI now reads the frozen
Run004 filenames (`c5_shadow_records_*`, `c4_service_ledger_*`, and packet
census emissions/terminals), treats Shadow as classification authority without
requiring its absent `wire_digest`, and accepts classified packets as a subset
of census terminals. A real Run004 structural-only preflight passed; no
derivation, aggregate, or scientific result was computed.

- Added fail-closed `MIA_C6_SUPPRESSION_CONFIG` parsing.
- At `_C4SharedLogicalServer._start_next`, an enabled ID-State head is
  classified after `popleft()` and before normal `service_start` side effects.
- A suppressible packet receives `suppressed` / `SUPPRESSED`, zero served and
  remaining bytes, a suppressed-obligation byte partition, no completion path,
  and unchanged same-frame budget.
- The server owns a bounded suppressed-item drain. `PacketRuntime` drains it
  immediately after `admit()` and once per `begin_frame()`, writing exactly one
  packet-census `SUPPRESSED` terminal at the observed terminal transition.
- All non-suppressed work follows the common frozen service-start path.
- Added a read-only baseline-derivation CLI with canonical packet joins,
  reconciliation, exclusive output creation, and context/results/seal/report.
  It has not been pointed at Run004.
- Added strict authorization, packet-census and suppression-consequence gates,
  MVE validity/science schemas, Formal dry-run input separation, and run seal
  helpers. The Formal builder has no science-artifact argument.
- Added the deterministic tiny runtime fixture and the versioned suppression
  decision JSONL/seal writer.

## G2 and generated-source binding preparation

G2 independently loads candidate runtime source, hashes the bounded semantic
regions (including `_c5_context_provider`), compares them to the frozen base,
then executes the real provider plus predicate synthetic replay before it can
write `C6_G2_DEPENDENCY_MANIFEST_V2`. Caller-supplied hashes or PASS status are
not accepted. The manifest is a caller-selected exclusive path; MVE artifacts
are strictly `mve/C6_MVE_VALIDITY.json` and `mve/C6_MVE_SCIENCE.json` under an
authorized output root.

The identified future generated-source base root is:

```text
/mnt/data/yzm/experiments/mdmt_mia_official/variants/packetized_active_sync
demo/supplement_MIA.py SHA-256 = 21a4081097cf36711702096d87899afde3ab7b3d753994d80bfd1ac3ddb5b062
demo/utils/active_packet_runtime.py SHA-256 = ea7cf5e6a8f303b9484252a2749f6fa2017c29c39d401b214a9e1b90c70d4a12
```

No C6 generated variant was created. Generation, source binding qualification,
E2E, baseline derivation, MVE, and Formal remain separately unauthorized.

## Test evidence

```text
C6 focused tests cover immediate and queued/cross-frame census terminals,
current-state/decoy independence, true-first-service queue timing, sticky
service classification, byte reconciliation failures, G2 negative failures,
role metadata independence, disabled-path base parity, and suppression
consequence rejection. They do not claim an end-to-end qualification.

The exact corrective test counts are recorded only after this revision's
authorized test commands complete.
```

No real dataset, GPU scientific execution, Run004 output, tracking metric, or
tracking outcome was accessed.
