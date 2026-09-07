# Paper Artifact Registry

Artifact registration is not paper acceptance.  `READY` is not final paper
inclusion, and `NEEDS_HOLDOUT` is not confirmed evidence.  This registry is a
paper-specific provenance layer and does not replace scientific authority.

## Schema

Every artifact record contains the following fields.  If a value is not
established by existing authority, it is written as `UNKNOWN`; it is never
inferred here.

| Field | Meaning |
| --- | --- |
| `ARTIFACT_ID` | Stable paper-asset identifier |
| `TYPE` | `FIGURE` or `TABLE` |
| `PAPER_SECTION` | Intended paper section, or `UNPLANNED` |
| `SCIENTIFIC_QUESTION` | Source scientific question |
| `CLAIM` | Candidate paper message, bounded by the source protocol |
| `CLAIM_STATUS` | Evidence readiness: `READY`, `NEEDS_HOLDOUT`, `DEVELOPMENT_ONLY`, `DIAGNOSTIC_ONLY`, `NEGATIVE_EVIDENCE`, `SUPERSEDED`, or `UNKNOWN` |
| `SOURCE_EXPERIMENT_ID` | Authoritative experiment identifier |
| `SOURCE_PROTOCOL` | Measurement/protocol boundary |
| `SOURCE_BRANCH` | Source branch, or `UNKNOWN` |
| `SOURCE_COMMIT` | Frozen execution/analysis commit, or `UNKNOWN` |
| `SOURCE_PACKAGE` | Authoritative output package/root, or `UNKNOWN` |
| `SOURCE_PACKAGE_DIGEST` | Package digest, or `UNKNOWN` |
| `SOURCE_ANALYSIS_REPORT` | Tracked report authority |
| `SOURCE_ANALYSIS_MANIFEST` | Manifest path and digest, or `UNKNOWN` |
| `SOURCE_DATA` | Minimal derived data path; `UNPLANNED` until extracted |
| `GENERATION_SCRIPT` | Deterministic generator; `UNPLANNED` until authorized |
| `OUTPUT_FILE` | Intended generated file; `UNPLANNED` until authorized |
| `CAPTION_STATUS` | Caption drafting state |
| `REPRODUCIBLE` | Whether source-data and a generator exist |
| `REVIEW_STATUS` | Paper/reviewer readiness state |
| `PROTOCOL_BOUNDARY` | Explicit limits on interpretation and reuse |

## Registered candidates — no assets generated in Phase 4A

### F-E023-01

```text
ARTIFACT_ID = F-E023-01
TYPE = FIGURE
PAPER_SECTION = UNPLANNED
SCIENTIFIC_QUESTION = Does delayed ID state create a candidate/Supplement compensation path?
CLAIM = ID-state delay harm and candidate/Supplement compensation under E023 official-test formal evaluation.
CLAIM_STATUS = READY
SOURCE_EXPERIMENT_ID = exp_20260808_001_mdmt_mia_id_supplement_cascade
SOURCE_PROTOCOL = E023 formal official-test MDA evaluation; Y00/Y10/Y01/Y11/Yec; paired bootstrap.
SOURCE_BRANCH = UNKNOWN
SOURCE_COMMIT = 7fcea6808bff2e17e435b39e3f44c00d73d92488
SOURCE_PACKAGE = outputs/20260813_mdmt_mia_id_supplement_cascade_formal_v8/
SOURCE_PACKAGE_DIGEST = UNKNOWN
SOURCE_ANALYSIS_REPORT = summary_md/experiments/2026-8-8/exp_20260808_001_mdmt_mia_id_supplement_joint_transaction/FORMAL_ANALYSIS_REPORT.md
SOURCE_ANALYSIS_MANIFEST = UNKNOWN
SOURCE_DATA = UNPLANNED; no data extracted in Phase 4A
GENERATION_SCRIPT = UNPLANNED
OUTPUT_FILE = UNPLANNED
CAPTION_STATUS = UNWRITTEN
REPRODUCIBLE = NOT_YET
REVIEW_STATUS = UNREVIEWED
PROTOCOL_BOUNDARY = Formal official-test mechanism evidence; scope-limited; not non-test replication; not deployable-policy evidence.
```

### F-DEV-01

```text
ARTIFACT_ID = F-DEV-01
TYPE = FIGURE
PAPER_SECTION = UNPLANNED
SCIENTIFIC_QUESTION = How does D_ID vary across preregistered d1-d5 in the frozen development cohort?
CLAIM = D_ID across preregistered d1-d5 in the frozen 15-pair train development cohort.
CLAIM_STATUS = NEEDS_HOLDOUT
SOURCE_EXPERIMENT_ID = exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation
SOURCE_PROTOCOL = MDMT_SOURCE_ANNOTATION_MDA_V1; frozen 15-pair train development cohort; pair bootstrap with 10,000 resamples and default_rng(7).
SOURCE_BRANCH = exp/20260903-001-mdmt-mia-p39-homography-fallback-successor-census
SOURCE_COMMIT = 47ce0fd35f1d9e7c10465297f5dcaf6b69117fab
SOURCE_PACKAGE = outputs/20260905_mdmt_mia_frozen_15_pair_development_v5/
SOURCE_PACKAGE_DIGEST = 649a73d36d8b0f1a49627d7b69585e91280e3232260ee401a390b44c373ef05d
SOURCE_ANALYSIS_REPORT = summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/FROZEN_15_PAIR_DEVELOPMENT_SCIENTIFIC_ANALYSIS.md
SOURCE_ANALYSIS_MANIFEST = outputs/20260906_mdmt_mia_frozen_15_pair_development_analysis_v1/DEVELOPMENT_ANALYSIS_MANIFEST.json; SHA-256 22b3cd7449314603662b39df0a10cac250244180322e549e32a41b1d15f9b891
SOURCE_DATA = UNPLANNED; no data extracted in Phase 4A
GENERATION_SCRIPT = UNPLANNED
OUTPUT_FILE = UNPLANNED
CAPTION_STATUS = UNWRITTEN
REPRODUCIBLE = NOT_YET
REVIEW_STATUS = UNREVIEWED
PROTOCOL_BOUNDARY = Development evidence only; Source-MDA-v1; not official train GT; not confirmatory until locked holdout.
```

### F-DEV-02

```text
ARTIFACT_ID = F-DEV-02
TYPE = FIGURE
PAPER_SECTION = UNPLANNED
SCIENTIFIC_QUESTION = How do R_edge and C_comp vary across preregistered d1-d5 with registered gate interpretation?
CLAIM = R_edge and C_comp across preregistered d1-d5 with pair-level uncertainty and registered gate interpretation.
CLAIM_STATUS = NEEDS_HOLDOUT
SOURCE_EXPERIMENT_ID = exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation
SOURCE_PROTOCOL = MDMT_SOURCE_ANNOTATION_MDA_V1; frozen 15-pair train development cohort; pair bootstrap with 10,000 resamples and default_rng(7).
SOURCE_BRANCH = exp/20260903-001-mdmt-mia-p39-homography-fallback-successor-census
SOURCE_COMMIT = 47ce0fd35f1d9e7c10465297f5dcaf6b69117fab
SOURCE_PACKAGE = outputs/20260905_mdmt_mia_frozen_15_pair_development_v5/
SOURCE_PACKAGE_DIGEST = 649a73d36d8b0f1a49627d7b69585e91280e3232260ee401a390b44c373ef05d
SOURCE_ANALYSIS_REPORT = summary_md/experiments/2026-8-17/exp_20260817_001_mdmt_mia_candidate_compensation_onset_validation/FROZEN_15_PAIR_DEVELOPMENT_SCIENTIFIC_ANALYSIS.md
SOURCE_ANALYSIS_MANIFEST = outputs/20260906_mdmt_mia_frozen_15_pair_development_analysis_v1/DEVELOPMENT_ANALYSIS_MANIFEST.json; SHA-256 22b3cd7449314603662b39df0a10cac250244180322e549e32a41b1d15f9b891
SOURCE_DATA = UNPLANNED; no data extracted in Phase 4A
GENERATION_SCRIPT = UNPLANNED
OUTPUT_FILE = UNPLANNED
CAPTION_STATUS = UNWRITTEN
REPRODUCIBLE = NOT_YET
REVIEW_STATUS = UNREVIEWED
PROTOCOL_BOUNDARY = Development evidence only; Source-MDA-v1; not official train GT; R_edge/C_comp remain registered development analysis until locked holdout confirmation.
```

No optional candidates are registered in Phase 4A.  No source-data, script,
figure, table, numeric extract, or caption is created by this registry.
