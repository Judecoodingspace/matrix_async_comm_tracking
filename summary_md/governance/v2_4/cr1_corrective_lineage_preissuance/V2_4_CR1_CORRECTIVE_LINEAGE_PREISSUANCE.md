# V2-4 CR1 validator corrective-lineage pre-issuance

Status: Team A candidate for independent review. No V2-3 corrective node or accepted Platform Authority has been issued.

## Verified parent and authority

- Attempt 001 remains V2-2 FAILED and has no V2-3 finalization.
- The user authorized one replacement three-frame non-scientific attempt in the exact local session record at line 6241; the minimal hash-bound record is [REPLACEMENT_ATTEMPT_002_AUTHORITY_EVIDENCE.json](REPLACEMENT_ATTEMPT_002_AUTHORITY_EVIDENCE.json).
- Attempt 002 is V2-2 COMPLETED and V2-3 FINALIZED. Its RAW, NORMALIZED, effective config, manifest, finalization receipt, and Git/blob provenance resolve at CONTENT depth. CR1 read-only validator replay passes all seven runtime FIFO gate fields. See [V2_4_CR1_RAW_REUSE_ASSESSMENT.json](V2_4_CR1_RAW_REUSE_ASSESSMENT.json).
- The old post-finalization report remains inside the parent attempt. It is not a manifest reference and did not alter any referenced content. It must not be moved or deleted.
- Old 002 source SHA is `b027d50e56b7ee200604308bcf664a2ace102c0b`; it does not directly qualify CR1 `66affc8f0dbcb794ddf9a47ed97be867a14394f5`.

## Proposed V2-3 correction

The defect class is VALIDATOR: CR1 adds the omitted runtime FIFO finalization gate and moves the report to stdout. The exact code delta changes no PacketRuntime, C7 FIFO, C6 suppression, selection, effective runtime config, or H_R real-child composition. Scientific impact on the existing protected graph is NONE.

Use `affected_layers=["NORMALIZED_EVIDENCE"]` and `purposes=["H_R_PRODUCTION_PROOF", "H_R_FORMAL_PREISSUANCE"]`. The RAW bytes are inherited by exact parent manifest/finalization/hash reference. CR1 rederivation produced byte-identical NORMALIZED and effective-config content, but V2-3 `_lineage()` selects a new head only for an affected layer, and `check_reuse()` requires that layer's content owner to be the head. The future child must therefore materialize its own NORMALIZED file, even when bytes match, with CR1 validator Git/blob provenance. This declares a changed validation/provenance layer, not changed communication bytes. The effective/config files must also be child-local NODE_FILE refs; V2-3 INHERITED is defined only for RAW/NORMALIZED evidence.

The exact old validator Git blob at `b027d50e56b7ee200604308bcf664a2ace102c0b` is proposed defect evidence, route `VALIDATOR_FIFO_FINALIZATION_GATE_OMITTED`. The CR1 Git blob at `66affc8f0dbcb794ddf9a47ed97be867a14394f5` is the proposed new validator. The non-executable [V2_4_CR1_CORRECTIVE_DECLARATION_DRAFT.json](V2_4_CR1_CORRECTIVE_DECLARATION_DRAFT.json) contains the schema-shaped plan with null attestation and accepted-authority references.

## V2-1 route and unissued fields

The authoritative first-introduction diff is `415d9c7132d8203c7970e45a70b77981fc41fc3b → 66affc8f0dbcb794ddf9a47ed97be867a14394f5`, raw diff SHA256 `5757d466ac3b277b3e6e953a939b3f1cc17c4de1143d9c6a7ff0013e2aa518a9`. All ten changed paths are additions relative to that base. The [exact hunk scope review](V2_4_CR1_V2_1_UNKNOWN_SCOPE_REVIEW.json) uses `INTRODUCTION_ZERO_EXISTING_PROTECTED_IMPACT` solely for the old mapped graph. The [candidate CIM](V2_4_CR1_V2_1_CHANGE_IMPACT_MANIFEST.json) is `CANDIDATE_REVIEWABLE_TEAM_B_PENDING`, with map applicability `APPLICABLE_TO_BASE` and `INDEPENDENT_DEPENDENCY_CLOSURE_REVIEW` outstanding. It is evidence, not acceptance of the new H_R path.

The narrower `b027d50e56b7ee200604308bcf664a2ace102c0b → 66affc8f0dbcb794ddf9a47ed97be867a14394f5` diff modifies already-existing unmapped H_R paths. V2-1 accepts the introduction semantic only for added paths, so that delta cannot provide the required candidate closure before prospective registration. No map registration is performed here.

The old map still marks `C6_HARNESS_DYNAMIC_BOUNDARY` UNMAPPED. H_R statically imports its C7-derived child boundary and does not traverse `run_harness_v2.py`; the future attestation must name only evidence actually relied on and must not claim that dynamic boundary closed.

The current H_R `preissue_check` hard-codes `node_id="initial"` and parent manifest/provenance. The proposed purpose set makes that stale parent fail closed after correction; it does not itself redirect the consumer. A separately reviewed future integration must pin the accepted corrective child before Formal-support consumption. This is outside the present package and no source is changed.

The future `correction.v2_1_change_impact` cannot contain an issued `attestation_path/sha256` before Team B independently accepts the CIM and scope review. The future `correction.accepted_authority` cannot contain a `decision=ACCEPT` Platform record before that review and separate authority issuance. Both remain null in this draft. The [Platform Authority pre-issuance proposal](V2_4_CR1_PLATFORM_AUTHORITY_PREISSUANCE.json) is `PENDING_INDEPENDENT_REVIEW`, not a V2-3 accepted authority.

No `create_correction()`, `finalize()`, Formal-support `check_reuse()`, real qualification, C7 rerun, prospective map registration, or Formal H_R execution was performed.
