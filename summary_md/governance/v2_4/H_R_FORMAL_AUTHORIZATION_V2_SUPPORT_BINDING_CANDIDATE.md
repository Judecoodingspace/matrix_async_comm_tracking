# H_R Formal authorization V2: prospective support binding candidate

Status: `CANDIDATE_FOR_INDEPENDENT_REVIEW`
Production base: `4de4e5a00abbd6c5b4205364738751a73c53c9f7`
Formal002 scientific design: `8cec5529214b64d14528c04f6063ca28427c13cd`

This candidate adds `H_R_FORMAL_AUTHORIZATION_V2` for future Formal attempts. It does not issue an authorization, run qualification or Formal002, consume support evidence, or read scientific outcomes. The accepted three-frame qualification, C7 cell, FIFO service, C6 suppression and PacketRuntime behavior are unchanged.

## V2 authorization boundary

V2 retains the V1 Formal fields and adds two required fields:

| Field | Meaning |
| --- | --- |
| `formal_support_qualification_attempt_id` | The qualification attempt selected by this authorization. |
| `formal_support_evidence_node_id` | The authoritative evidence node selected by this authorization. |

The existing required `formal_support_consumer_record_path` and `formal_support_consumer_record_sha256` select one exact record and its bytes. The authorization hash covers all four bindings. The V2 issuer takes the qualification and node identities as explicit arguments; it does not search for a latest record.

At issuance and at Formal admission, V2 requires the named record bytes, exact SHA-256, matching attempt and node in both the record and its anchor, `REUSE_ADMISSIBLE`, `CONTENT` verification, six passing checks, current RAW/NORMALIZED lineage ownership, and a fresh read-only V2-1 applicability recomputation matching C4's CIM and independent attestation identities. All existing source, selected-cell, configuration, attempt and output checks remain in the shared authorization loader. The real child applies the existing Formal effective-config reconciliation to V2 as it does to V1.

V1's schema and record validator remain historical. The Formal launch entry admits V1 only for `v2_4_hr_formal_001`; prospective attempts use V2. The V2 loader refuses the already-consumed Formal001 attempt ID. The historical fixed `qual_002` consumer identity is not consulted by V2.

## Verification and scope

Focused tests create only synthetic temporary authorizations and support records. The positive test uses readable tracked V2-1 CIM and attestation bytes; negative tests cover wrong SHA, qualification attempt, evidence node, missing record, refused decision, historical fallback, omitted bindings, invalid V2-1 applicability, runtime/config mismatch and schema downgrade. No real Formal002 support record exists yet; independent review is required before this candidate can be accepted as an execution source.
