# H_R Formal002 analyzer packet identity mapping correction

Date: 2026-10-07 Asia/Shanghai. Status: candidate for focused independent
review. Prospective scope: the packet identity validation and joins in the
Formal002 analyzer only. The frozen treatment-only scientific design remains
commit `8cec5529214b64d14528c04f6063ca28427c13cd`; the accepted inventory
correction remains commit `8af235863663c96407a0ef3a229e713959e1c64e`.

## Evidence for two source schemas

The accepted `PacketRuntime` service `_packet_id(census_emission,
packet_sequence)` copies `census_emission["packet_id"]` when an emission exists;
otherwise it constructs exactly `{sequence_name, packet_sequence}`. Its Census
sidecar constructs exactly `{census_run_id, sequence_name,
runtime_instance_id, emission_ordinal}` when enabled.

The frozen C7 cell `P66__P20` uses the normalized two-field packet ID. A
read-only scan of all 300 frozen windows examined 3,646 packet-bearing observer
events and 3,646 observer items; a read-only scan of the frozen C4 service
ledger examined 6,020 packet-bearing events. Every inspected packet ID had
exactly `{sequence_name, packet_sequence}`, with `sequence_name == "66-1"`,
positive integer `packet_sequence`, and matching containing event sequence
where present. Each packet-bearing event retained run
`exp_20260925_001_c7_full_21_cell_census`, pair `P66`, condition
`FIFO_strong`, and frame budget `16649`. The four raw C7 SHA-256 identities,
inventory, seal and commit marker are unchanged. No baseline endpoint was
calculated by the schema scan.

The accepted H_R real child sets `MIA_PACKET_CENSUS_RUN_ID = auth.run_id` and
enables the C7 finite FIFO service. The runtime's `_wire()` always calls the
enabled Census sidecar's `emission()`; `_send()` passes that emission to the C4
server, which copies its four-field packet ID. Thus a valid Formal002
treatment observer and ledger are expected to use the exact four-field Census
schema. The prospective analyzer requires its `census_run_id` to equal the
Formal002 run, `sequence_name == "66-1"`, a nonempty runtime instance matching
the containing event, and positive integer `emission_ordinal`. It never
equates `packet_sequence` to `emission_ordinal`.

## Explicit mapping and namespace

The analyzer calls the same byte accounting with one required source mode:

- Frozen C7 observed baseline: `C7_BASELINE_NORMALIZED_TWO_FIELD`.
- Prospective Formal002 treatment: `FORMAL_TREATMENT_CENSUS_FOUR_FIELD`.

Each source joins its own raw canonical packet ID with `wire_digest` and
`channel`. No ID fields are synthesized or translated between sources. No
schema auto-detection, union, latest selection or fallback is allowed.
`SERVICEABLE`, `SUPPRESSIBLE_STALE`, first-service classification, positive
service-slice summation, partial-service conservation and frame reconciliation
are unchanged. The primary metric remains
`serviceable_id_state_serviced_bytes`, for `P66__P20`, capacity `16649`,
frames `0..299`, denominator `NONE`.

The previous failed baseline attempt wrote only
`formal_evidence/analysis/v2_4_hr_formal_002/C7_BASELINE_IMPLEMENTATION_BINDING.json`,
raw SHA-256 `09c702eeb0181410ec5a291d1d1f28267f8fb4d3bdf7fa71db1c27e82c11030e`.
It is retained untouched. The prospective fixed analysis namespace is
`formal_evidence/analysis/v2_4_hr_formal_002__packet_schema_v2/`. There is no
existing formal corrective-lineage mechanism for analysis artifacts in this
tracked analyzer. Its baseline binding will identify the frozen design,
accepted inventory corrective authority, this mapping authority's file SHA,
the exact analyzer SHA/commit, the explicit modes, and the fixed namespace.
The comparison reads the baseline seal from that same fixed namespace.

Synthetic checks exercise exact two-field and four-field acceptance,
wrong-schema and provenance rejection, and equal byte accounting for the same
service history under separately keyed source identities. Existing slice and
frame reconciliation negatives remain in force. No C7 baseline total,
treatment endpoint, delta or scientific verdict was read or computed during
this correction.

After focused independent acceptance, publish the exact candidate SHA, seal
the C7 baseline in this prospective namespace, and resume Formal002 V2
authorization with the existing qual_005 and support consumer. No C7,
qualification or support-consumption rerun is required.
