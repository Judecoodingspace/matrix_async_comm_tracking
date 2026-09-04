# MDMT Source Annotation Protocol R1/R2 Authority Audit

Status: `SOURCE_ANNOTATION_PROTOCOL_R1_R2_AUTHORITY_PASS`

Scope: `MDMT_SOURCE_ANNOTATION_MDA_V1`, an internal source-annotation
evaluation protocol for mechanism replication only. This audit does **not**
claim that train/val evaluation reproduces official-test export semantics.

## Scope and method

This is a source/XML and official-test/TXT audit only. It did not run a
tracker, detector, MIA, E023, compensation-onset experiment, or any new MDA
evaluation. No source XML or official TXT was modified. The 347 source-only
rows were counted only as the previously frozen fingerprint; their cause was
not inspected and no filtering rule was inferred.

Audited inputs:

- MDMT source root:
  `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking`;
- 28 test XML files under `new_xml/{1,2}/` (split resolved from the paired
  image directories);
- 28 author-distributed official-test TXT files under
  `/mnt/data/yzm/experiments/mdmt_mia_official/upstream/demo/eval/test/`;
- author repository commit `551f90d998087ea2d02df75700e3c7739c4ecbe1`,
  especially `demo/eval/mango_eval.py`.

All XML numerical attributes and TXT numerical fields were parsed as exact
`Decimal` values. The shared-row comparison preserved multiplicity. An
independent anchor analysis first grouped rows only by the exact numeric bbox;
it used an anchor only when that bbox occurred once in the XML and once in the
corresponding TXT file. It did not use IoU, tolerance, image inspection, row
deletion, or manual matching.

## R1 Cross-view identity

### FACT

- The official MDMT README describes the task as associating identities across
  drones and MDA as a cross-view association measure, but it does **not** state
  whether XML `track_id` values use a shared paired-view namespace. The
  documentation therefore establishes task intent only, not the requested XML
  field semantic. See the [official README](https://github.com/VisDrone/Multi-Drone-Multi-Object-Detection-and-Tracking)
  and local lines 7-12.
- The author evaluator reads the second TXT field directly as `GTTarget.ID`
  (local `mango_eval.py:54-64`) and declares a GT cross-view association when
  `gtA.ID == gtB.ID` (`mango_eval.py:144-149`). The inspected evaluator has no
  view-local-to-global remap, mapping table, or per-camera namespace
  conversion between those operations.
- Across the 28 files, 600,923 official TXT rows had an exact XML shared row.
  The shared rows yielded zero contradictions:

  | Check | Count |
  | --- | ---: |
  | XML `(sequence, view, track_id)` mapping to more than one TXT identity | 0 |
  | TXT `(sequence, view, identity)` mapping to more than one XML track ID | 0 |
  | XML `track_id`s observed in both views and checked | 1,374 |
  | Those paired-view IDs mapping to different TXT identities | 0 |

- The 501,614 unambiguous numeric-bbox anchors independently yielded only
  `(official_frame - xml_frame, official_id - xml_track_id) = (1, 1)`.

### INFERENCE

The author evaluator's direct cross-view equality semantics and the complete
contradiction-free test shared-row mapping are independent, mutually
consistent evidence that, for a paired MDMT view pair, equal XML `track_id`
denotes the shared cross-view identity used by the source-annotation protocol.

### UNKNOWN

No located official README or annotation specification explicitly defines the
XML `track_id` namespace. This audit does not elevate that missing documentary
statement into a fact, and it does not claim any unknown official export
filtering policy.

### Decision

`R1_CROSS_VIEW_IDENTITY_AUTHORITY_PASS`

The verified semantic is limited to the source-annotation protocol: identical
paired-view XML `track_id` is the same cross-view identity. It is not evidence
that every XML row must be exported by the official-test TXT release.

## R2 Frame mapping

### FACT

For all 600,923 shared rows, the only observed mapping is:

```text
official_frame = XML_frame + 1
```

| Measure | Count |
| --- | ---: |
| Total official TXT rows / shared rows | 600,923 |
| Supporting rows | 600,923 |
| Contradiction rows | 0 |
| Other offset among 501,614 independent anchors | 0 |

### Decision

`R2_FRAME_MAPPING_AUTHORITY_PASS`

## R2 Identity indexing

### FACT

For all 600,923 shared rows, the only observed indexing convention is:

```text
official_identity = XML_track_id + 1
```

| Measure | Count |
| --- | ---: |
| Total official TXT rows / shared rows | 600,923 |
| Supporting rows | 600,923 |
| Contradiction rows | 0 |
| Other offset among 501,614 independent anchors | 0 |

This is an indexing convention. It is deliberately separate from R1's claim
about the cross-view meaning of an equal source identity.

### Decision

`R2_IDENTITY_INDEXING_AUTHORITY_PASS`

## R2 BBox mapping

### FACT

For all 600,923 shared rows, exact numeric and textual fields support:

```text
x      = xtl
y      = ytl
width  = xbr - xtl
height = ybr - ytl
```

| Check | Result |
| --- | ---: |
| Numeric-equivalent shared rows | 600,923 |
| Textually identical projected first six fields | 600,923 |
| Textual difference rows | 0 |
| `width = xbr - xtl + 1`, `height = ybr - ytl + 1` shared matches | 0 |
| Source test rows with non-integral coordinate values | 0 |

Thus no inclusive-coordinate convention is supported. The test source
coordinates are integral, so they cannot empirically distinguish a rounding,
truncation, or integer-cast implementation that happens to be a no-op on
these inputs. The frozen protocol consequently specifies exact `Decimal`
parsing and arithmetic rather than inferring an unobserved rounding rule.
There is no evidence of clipping on shared rows; this is not a claim that the
unknown official exporter never applies a conditional filter or clipping rule
to non-shared rows.

### TEXTUAL_EQUIVALENCE and NUMERIC_EQUIVALENCE

Both hold for the six compared fields in this test corpus. Future protocol
validation must report them separately: a formatting difference may still be
numerically equivalent, but it must never be called byte or textual equality.

### Decision

`R2_BBOX_MAPPING_AUTHORITY_PASS`

## Official export filtering

`OFFICIAL_EXPORT_FILTER_POLICY = UNKNOWN`.

The frozen fingerprint remains:

```text
official test files: 28
exact files:         5
mismatching files:  23
missing rows:        0
source-only rows:  347
```

The 347 rows were not classified, filtered, compared by visual similarity, or
used to alter frame, identity, or bbox mapping. This fingerprint means only
that the source protocol is not an official-test export-equivalent protocol.

## Final contract decision

The evidence supports freezing the following **source-annotation** semantics:

```text
paired-view equal XML track_id -> shared cross-view identity
evaluation frame              = XML frame + 1
evaluation ID                 = XML track_id + 1
(x, y, width, height)         = (xtl, ytl, xbr - xtl, ybr - ytl)
```

The contract must retain all of these boundaries:

- `MDMT_SOURCE_ANNOTATION_MDA_V1` supports internal mechanism replication only;
- it must not be described as official-test export equivalence;
- source rows are not manually repaired and no filter is inferred from the
  347-row discrepancy;
- a separately authorized implementation and fresh G1-G7 source-protocol
  audit are still required before any non-test tracking or scientific result.

```text
SOURCE_ANNOTATION_PROTOCOL_R1_R2_AUTHORITY_PASS
READY_FOR_SOURCE_PROTOCOL_IMPLEMENTATION_AND_G1_G7_AUDIT
```
