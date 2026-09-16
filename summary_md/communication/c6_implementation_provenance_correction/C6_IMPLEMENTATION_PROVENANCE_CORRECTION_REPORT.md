# C6 Implementation Authority Provenance Correction Audit

Status: PASS. The defect is `A_METADATA_ONLY_PROVENANCE_DEFECT`.

## Verification

- Intended Git authority exists and is canonical: `1e440166554e04d219291b1c3c6a8a1f5f6b88ff`.
- The malformed 38-character manifest value does not resolve as a Git object.
- Generated `demo/utils/async_deadline_runtime.py` SHA-256 is
  `af03c1bbcce62b3cf774790634332c126b48d07cdd80b25c70193b0b4a15dc71`, exactly matching
  the intended Git source path. The generated tree, file count, and inventory bytes are unchanged.
- The pre-correction propagation scan found 36 malformed-string occurrences in 15 files.
  Twelve were direct downstream accepted E2E evidence files; eight E2E files were also
  transitively bound through the old manifest hash. Runtime-origin path strings were retained
  because they identify the unchanged on-disk generated tree, not a Git authority field.

## Correction and rebind

The old qualification directory remains immutable. A superseding generated-source context,
manifest, results, seal, report, and supersession mapping bind the canonical implementation
SHA. The manifest changed from
`281ab9efba2a5ee87214173a758881f5b431d6c933403115e59b84c0becd9986` to
`40c2209e34b39966ef5c3059f3d565bdce0cc6f274ba72b1617b117caf1b04da`; its qualification seal
changed from `e98c73a589fd44c1d373b1785da0d3d631bf632770ea624c41bfe0eb1cd5c7ae` to
`4e450083170193dc3fd3c1782e44a77cc68694eb2e61959ae5758ca23c73bceb`.

The accepted production launcher was re-bound and rerun only on the synthetic E2E fixture.
The child boundary, disk re-read, validator, B_avoided recomputation, 22 negative fail-close
checks, evidence inventory, seal, and `RUN_END` all passed. No MVE, Formal, scientific cell,
or tracking outcome was executed or read.

## Researcher Digest

Valid source bytes can coexist with invalid provenance because a metadata field can be mistyped
while the generated files remain byte-identical to the intended commit. A seal can faithfully
bind that wrong field: cryptographic integrity proves the record was not altered, not that the
record named the right authority. Once the manifest changes, every downstream identity binding
must be re-sealed; keeping the old E2E seal would claim validity for a superseded manifest. This
is serious for auditability and reproducibility, but it does not imply that C6 runtime semantics
were wrong—the independent runtime byte comparison passed. MVE remains blocked until Team B
reviews this correction and authorizes a fresh MVE preflight.
