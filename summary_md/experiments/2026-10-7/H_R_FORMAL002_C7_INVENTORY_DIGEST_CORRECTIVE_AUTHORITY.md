# H_R Formal002 C7 inventory digest corrective authority

Date: 2026-10-07 Asia/Shanghai. Status: candidate for focused independent review.
Prospective scope: `FORMAL002_C7_COMPARABILITY_PRECHECK` only, before any Formal002
authorization, baseline endpoint derivation, or treatment outcome access.

## Original and corrected identities

- Original frozen Formal002 scientific design commit:
  `8cec5529214b64d14528c04f6063ca28427c13cd`.
- Original frozen design path:
  `summary_md/experiments/2026-10-6/exp_20261006_002_mdmt_mia_hr_formal002_paired_redistribution/FORMAL002_TREATMENT_ONLY_C7_CONTROL_SUPERSESSION.md`.
- Original design Git blob: `c228ed328cbf93a370702912c17b2ecc1acff29d`.
  The original file remains unchanged and auditable.
- Original recorded `C7_CELL_INVENTORY_DIGEST`:
  `205aafad0d21237207cd46c6e07998d9459b436849e7660b1a6f14031a7cdb85ef4`
  (67 hex characters).
- Correct internal inventory SHA-256:
  `205aafad0d21237207cd46c6e07998d9459b436849e7660b6ae138d03efd0f6c`
  (64 hex characters).

This is a `CLERICAL_DERIVED_DIGEST_DEFECT`: the original recorded value has an
invalid SHA-256 encoded length. It also differs from the independently
recomputed value embedded in the already sealed C7 cell. The original design
explicitly requires equality with `cell_seal.json`'s
`sealed_payload.inventory_sha256` before derivation; the prior fail-close was
correct. This correction substitutes only that recorded derived digest for the
named Formal002 precheck. It does not rewrite historical C7 authority.

## Deterministic derivation and source identities

The authoritative inventory is
`census/exp_20260925_001_c7_full_21_cell_census/cells/P66__P20/cell_inventory.json`,
raw file SHA-256
`69c8e1c9543c3cdbaa9db70ecf8fc8735701d5889e996c6ee59573e7efac4f2b`.
Its schema is `C7_CELL_INVENTORY_V1`. The C7 package and validator build its
`files` list from the five lexically sorted cell files `cell_aggregate.json`,
`cell_manifest.json`, `cell_qualification.json`, `cell_validation.json`, and
`windows.jsonl`. Each entry has `path`, raw file `sha256`, and `byte_count`.
The internal digest is SHA-256 of the inventory object's canonical UTF-8 JSON:
`json.dumps(object, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`.
The expected encoded length is 64 lowercase hex characters. The reconstructed
object equals the stored inventory; its canonical digest equals the corrected
value above.

| Frozen C7 artifact, under `census/exp_20260925_001_c7_full_21_cell_census/` | Frozen and observed raw SHA-256 |
| --- | --- |
| `cells/P66__P20/windows.jsonl` | `dba4f926ed16eefa1fcf7a2660fc07dade63d2952693c8f6c58eee890ab09c74` |
| `operational/child/P66__P20/author_outputs/mia/train_66/results/mia_train_66/c4_service_ledger_66-1.jsonl` | `1e81c4008efc9745442662f20bd9b4dece6b2598963ae39bb956502c24866c30` |
| `cells/P66__P20/cell_inventory.json` | `69c8e1c9543c3cdbaa9db70ecf8fc8735701d5889e996c6ee59573e7efac4f2b` |
| `cells/P66__P20/cell_seal.json` | `430a13969eee7a72d1b36179a0f143f6338d1edd34e99da4dbc0b1eea30c5f1b` |

The sealed payload binds run
`exp_20260925_001_c7_full_21_cell_census`, cell `P66__P20`, the raw
`cell_manifest.json` SHA-256, the corrected internal inventory digest, and
`VALIDATED` status. Its canonical SHA-256 is
`596a0d7b61edfe379309c2d1635e03f5ad493ac7b3b05ebf0059deb7ae13bd5e`.
The `CELL_COMMITTED.json` marker repeats the inventory and seal digests and
has `COMMITTED` status. Both reproduce exactly from the stored file identities.

## Scope and validation

THIS CORRECTION CHANGES ONLY THE DERIVED C7 INTERNAL INVENTORY DIGEST IDENTITY.

IT DOES NOT CHANGE C7 artifact bytes, C7 file SHA identities, the sealed C7
result, `P66__P20`, capacity `16649`, control selection, treatment definition,
metrics, denominators, comparison rule, scientific hypothesis, or the
Formal002 treatment-only design. `SCIENTIFIC_DESIGN_CHANGED = NO`;
`C7_EVIDENCE_CHANGED = NO`; `COMPARISON_RULE_CHANGED = NO`;
`DERIVED_IDENTITY_CORRECTED = YES`.

The prospective derivation gate in `scripts/analyze_mdmt_mia_hr_formal002.py`
rehashes the four frozen files, rebuilds the five-file inventory, requires this
digest and the exact seal/commit chain, then binds this authority's SHA-256 in
the implementation record before any endpoint read. Focused checks require the
corrected digest with the same exact inventory to pass and the malformed
original digest, an altered C7 file identity, inventory, or seal to fail.
No latest, search, or fallback authority selection is permitted.

`SCIENTIFIC_OUTCOMES_READ = NO`. Formal002 authorization and execution remain
absent; `v2_4_hr_formal_002` is unused. Existing qualification
`v2_4_hr_qual_005` / `initial` and its support consumer are unchanged.

Next action after focused independent acceptance: publish the exact candidate
SHA, then resume at Formal002 V2 authorization using existing qualification and
support evidence. No C7 or qualification rerun is required.
