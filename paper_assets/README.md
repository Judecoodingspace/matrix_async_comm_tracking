# Paper Asset Infrastructure

## Purpose

`paper_assets/` is a traceable derived layer from authoritative scientific
evidence to paper figures and tables.  It is not a new scientific authority.

Scientific authority remains with frozen experiment contracts, manifests,
scientific reports, and authoritative output packages.  In case of a conflict,
those sources prevail over anything in this directory.

## Provenance chain

```text
authoritative experiment
  -> frozen analysis
  -> minimal source-data
  -> generation script
  -> figure/table
  -> registry entry
```

Every intended paper asset must have a corresponding entry in
[`registry/PAPER_ARTIFACT_REGISTRY.md`](registry/PAPER_ARTIFACT_REGISTRY.md).
The entry records its source experiment, protocol boundary, source package,
digest, analysis authority, derived source data, generation script, and review
state.

## Immutability and regeneration

- A figure or table must never modify its scientific source, contract,
  manifest, analysis report, or authoritative output package.
- Where practical, a figure or table must be deterministically regenerable
  from tracked minimal source-data and a tracked generation script.
- The numeric authority must not be a long-lived manually copied Markdown
  value or manually edited spreadsheet.  Manual final-layout adjustments are
  permitted only after the underlying scientific values are sourced from the
  registered source-data.

## Source-data policy

`source_data/` may contain only the minimal derived aggregate needed to
regenerate a paper figure or table: small CSV, TSV, JSON, compact table source,
or plotting metadata.

It must not contain prediction JSON dumps, detector caches, raw images, author
runtime trees, checkpoints, full logs, traces, complete experiment packages, or
the 174 GB development output.

```text
TARGET: individual file in KB or low-MB range
SOFT LIMIT: individual file < 10 MB
TOTAL TARGET: all repository paper source-data < 50 MB
OVER LIMIT: STOP_AND_REVIEW; do not add Git LFS automatically
```

`paper_assets/` is not a storage-archival solution.  Outputs, prediction
artifacts, detector caches, raw traces, runtime variants, datasets, and
checkpoints remain in their server/archive locations and are never copied here
merely for paper preparation.

## Directory roles

| Directory | Role |
| --- | --- |
| `registry/` | candidate and produced-asset provenance records |
| `source_data/` | small, derived, tracked numerical inputs only |
| `scripts/` | deterministic figure/table generators when authorized |
| `figures/` | generated paper figures only |
| `tables/` | generated paper tables only |

Phase 4A establishes this infrastructure only.  It creates no source-data,
scripts, figures, or tables.
