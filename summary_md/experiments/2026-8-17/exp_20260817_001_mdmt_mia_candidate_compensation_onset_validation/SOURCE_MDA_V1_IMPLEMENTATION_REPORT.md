# SOURCE_MDA_V1_IMPLEMENTATION_REPORT

## Scope

This implementation creates `MDMT_SOURCE_ANNOTATION_MDA_V1`, an independently
defined source-annotation evaluation protocol for internal mechanism
replication. It is not an official-test exporter reproduction and must not be
called official-equivalent non-test GT.

The implementation is isolated from the historical official-export converter:

```text
src/datasets/mdmt_source_annotation_mda_v1.py
scripts/run_mdmt_source_annotation_mda_v1_preflight.py
tests/test_mdmt_source_annotation_mda_v1.py
```

It imports no tracker, detector, prediction or evaluator module, does not open
image pixels, and exposes no tracking or MVE command.

## Frozen conversion semantics

| Field | Source-MDA-v1 rule |
| --- | --- |
| Frame | `evaluation_frame = XML_frame + 1` |
| Identity | `evaluation_id = XML_track_id + 1` |
| BBox | `x=xtl`, `y=ytl`, `width=xbr-xtl`, `height=ybr-ytl` |
| Numeric type | `Decimal` parsing and `Decimal` arithmetic only |
| Serialization | canonical deterministic Decimal spelling |
| `outside=1` | excluded only with an immutable provenance record and `outside=1` reason |
| `occluded=1` | retained; never an exclusion by itself |
| Duplicate `(frame, identity)` | preserved; it is not a uniqueness key |
| Provenance | `xml_relative_path|track:<track_index>|box:<box_index>` |
| Label | provenance only; never used for identity or retention repair |

One source row creates exactly one converted row unless it is the frozen
`outside=1` exclusion. No clipping, rounding, image inspection, manual repair,
or official-export filtering is implemented.

## Test evidence

```text
PYTHONPATH=src python -m py_compile \
  src/datasets/mdmt_source_annotation_mda_v1.py \
  scripts/run_mdmt_source_annotation_mda_v1_preflight.py
PYTHONPATH=src pytest -q tests/test_mdmt_source_annotation_mda_v1.py

7 passed
```

Fixtures cover frame/ID `+1`, Decimal bbox arithmetic, deterministic spelling,
outside and occluded handling, duplicate source multiplicity, unique
provenance, fail-closed negative geometry, deterministic seed-7 cohort creation
and absence of a tracking/MVE execution interface.

## Frozen source hashes

```text
converter: bb4201f8d39165ad29c87380d9b4d5acc4f9041be0bc8c8c3c8049f2faf64c5a
preflight command: 1ba8d5d9315e8f54ef76ebee613a81dc52de07d2ec9515aaed450bd4db81e2e3
tests: 9a7182e7c4fae6f8834d816bcd5df77577bee4ab908fc58788fc911159e29b4c
```

## Boundary retained

`OFFICIAL_EXPORT_FILTER_POLICY = UNKNOWN`. The historical `5/28` exact-file,
`23/28` mismatch and `347` source-only-row fingerprint was not read, classified
or used by this implementation.
