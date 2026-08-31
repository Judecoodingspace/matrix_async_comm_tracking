# Work 1 Dynamic M2 Preexecution Gate Specification

## Scope

```text
WORK1_DYNAMIC_M2_PREEXECUTION_GATE
EXECUTION_VALIDITY_EVIDENCE_ONLY
```

These gates validate a future A/B/C non-interference attempt. They do not
create mechanism evidence, authorize execution, select inputs, grade GT, or
change author/Work 1 semantics.

## Frozen authority

| Field | Frozen value/scope |
| --- | --- |
| author entrypoint | `packetized_id_supplement_cascade_v8/demo/supplement_MIA.py` |
| author entrypoint SHA-256 | `4c8674425462dc8e14dc1f53eaaa62a83d93879e45b4cb46a05b38ea78008616` |
| XML reader source | complete frozen `demo/utils/common.py` containing `read_xml_r()` |
| XML reader source SHA-256 | `c87dfcf6d6a785e0042b4bf348fa87733b61de78e92d6c32c60c8c1cc31d3b93` |
| initialization region | frozen entrypoint lines 166-199, inclusive |
| initialization-code SHA-256 | `53773a70cf69e8ae434c04ecaa013818968d1b20549116477a85d81e2113d395` |
| initialization frame | `0` |

XML hashes are pair-specific preregistered inputs. This specification does not
read dataset/XML files and cannot generate their expected baseline.

## Gates

| Gate | Protects | Checked when | Required evidence | Failure label |
| --- | --- | --- | --- | --- |
| `G-XML1` | frozen initialization provenance | before launch | frozen expected record plus independently observed hashes/frame | `G_XML1_INITIALIZATION_PROVENANCE_FAIL` |
| `G-XML2` | exact A/B/C initialization identity | immediately after all three initializations | `ABC_INITIALIZATION_EQUALITY_AUDIT.json` | `G_XML2_ABC_INITIALIZATION_MISMATCH` |
| `G-XML3 STATIC` | direct Work 1 oracle interface | before launch | source AST, signatures, schemas, serialized keys, env/path interfaces | `G_XML3_WORK1_ORACLE_FIREWALL_FAIL` |
| `G-XML3 DYNAMIC` | runtime direct-oracle access | after A/B/C validity traces exist | `WORK1_RUNTIME_ORACLE_FIREWALL_AUDIT.json` with four zero counters | `G_XML3_WORK1_ORACLE_FIREWALL_FAIL` |
| `G-XML4` | initialization/Work 1 event ordering | after initialization, before interpretation | GT-read, passive marker, and first-E_pre sequence metadata | `G_XML4_INITIALIZATION_BOUNDARY_FAIL` |
| `G-XML5` | safety and claim scope | schema/template preflight and final reporting | ledger, aggregate, decision, report schemas/content | `G_XML5_CLAIM_BOUNDARY_FAIL` |

## G-XML1 record

Required exact fields:

```text
author_entrypoint_sha256
xml_reader_source_sha256
initialization_code_sha256
xml_view1_sha256
xml_view2_sha256
initialization_frame
```

Expected and observed records must match exactly. The expected authority must
contain the frozen code hashes above. The validator cannot update expected
values from observed values.

## G-XML2 schema

`ABC_INITIALIZATION_EQUALITY_AUDIT.json` has exactly conditions A/B/C, each
with:

```text
xml_view1_sha256
xml_view2_sha256
initialization_code_sha256
initialization_frame
initial_bbox_view1_digest
initial_id_view1_digest
initial_label_view1_digest
initial_bbox_view2_digest
initial_id_view2_digest
initial_label_view2_digest
post_initialization_tracker_state_digest
```

Every field requires exact `A == B == C`; tolerance-based equality is
forbidden. The schema file in `summary_md/` is structural only and contains no
runtime or dataset result.

## G-XML3 records

The static layer rejects forbidden imports, unbounded `**kwargs`, raw GT/XML
path/field interfaces, and serialized oracle fields in Work 1 scientific
components.

The future dynamic audit is produced by `ACTUAL_WORK1_ACCESS_OBSERVATION`, not
by zero-initialized constants. It records an observation ledger and the frozen
observability boundary. Within that boundary it requires exactly zero:

```text
xml_open_count_by_work1
gt_file_open_count_by_work1
gt_field_access_count_by_work1
gt_serialized_field_count
```

The boundary covers registered Work 1 file/path calls, constructor/runtime
interfaces and token/ledger serialization, together with the static source
gate. It does not claim arbitrary hidden-reflection interception. Frozen author initialization access is accounted separately and never charged
to Work 1, provided it remains inside the frozen initialization boundary.

## G-XML4 marker

One shared passive sequence is advanced only by the actual last `read_xml_r`
completion, the actual initialization-complete hook and the actual first E_pre
hook. Hard-coded/post-hoc sequence values are forbidden. The passive marker schema is:

```text
frame_id
author_initialization_complete = true
initialization_state_digest
marker_sequence_number
```

It receives author state only to compute a digest; raw values are not retained.
Its return is ignored. The validator requires:

```text
last_author_gt_read_sequence_number
< marker_sequence_number
< first_work1_e_pre_sequence_number
```

The marker is written only into a separate execution-validity audit. It cannot
enter an eligibility/opportunity mechanism metric.

## G-XML5 forbidden outputs

Reject fields or positive claims for GT correctness, candidate/association
truth, true/false association, false/safe write-in, MDA, IDF1, MOTA, IDSW,
deployment readiness, GT-free runtime, XML-free MIA, or GT-free initialization.
`GT_SAFETY_UNGRADED` is allowed and required.

## Gate order and stop behavior

```text
M2_SYNTHETIC_PARITY_PASS
-> G-XML1 PASS
-> G-XML3 STATIC PASS
-> SOURCE / DERIVATIVE HASH PASS
-> authorization review
-> future A/B/C launch
-> G-XML2 PASS
-> G-XML4 PASS
-> G-XML3 DYNAMIC PASS
-> CORE_OUTPUT_DIFF == 0
-> B_VS_C_CORE_DIFF_COUNT == 0
-> OBSERVER_GUARD_CHANGE_COUNT == 0
-> G-XML5 final artifact/report PASS
```

- Prelaunch failure: do not start A/B/C.
- Post-launch G-XML2/3/4/5 failure: mark attempt invalid and stop before
  non-interference interpretation.
- No gate can be rescued by approximate equality, regenerated expected hashes,
  input replacement, or mechanism outcome.

## Machine-checkable implementation

- Validators: `src/tracking/mdmt_mia_work1_xml_governance.py`
- CLI: `scripts/audit_mdmt_mia_work1_xml_governance.py`
- Tests: `tests/test_mdmt_mia_work1_xml_governance.py`
- Passive derivative marker: generated only by
  `scripts/prepare_mdmt_mia_work1_eligibility_variant.py`; frozen parent remains
  immutable.
- Material/input/structured launch validator:
  `scripts/audit_mdmt_mia_work1_preexecution.py`.
- G-XML5 is mandatory both before launch for output schemas/templates and after
  runtime for every final artifact/report.

No real `ABC_INITIALIZATION_EQUALITY_AUDIT.json` or runtime firewall audit is
generated in this documentation/gate-freeze pass.
