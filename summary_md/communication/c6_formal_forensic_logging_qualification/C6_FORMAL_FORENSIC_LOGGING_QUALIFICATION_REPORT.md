# C6 Formal Forensic Logging Qualification

Status: PASS (mechanical only).

## Scope

The real C6 child now persists the captured stdout and stderr of the nested
author-wrapper process as:

- `cells/<cell>/C6_AUTHOR_WORKLOAD_STDOUT.txt`
- `cells/<cell>/C6_AUTHOR_WORKLOAD_STDERR.txt`

This changes only failure observability. It does not change the author command,
generated source, dataset, service condition/rate, packet semantics, baseline,
metrics, tracking-result embargo, or Formal cell matrix.

The previously failed Formal `attempt1` remains quarantined and was not edited,
rerun, or used as scientific evidence.

## Verification

- Focused failure-path regression:
  `python -m pytest -q tests/test_mdmt_mia_c6_failed_mve_retry.py` ->
  `25 passed`.
- The new regression injects a non-zero author exit and verifies exact stdout
  and stderr persistence while retaining fail-closed status `FAIL`.
- Official four-cell no-data Formal qualification, with a temporary
  `candidate(False)` authorization and an isolated `/tmp` root ->
  `FORMAL_RUN_END`, all four cells `VALID`, `tracking_outcome_read=false`, and
  `synthetic_non_scientific=true`.

Qualified real-child SHA-256:
`1f5aa228ad66059407444ea7dcc5f0212171ef7e86507fc566b63cc610c366c4`.

## Boundary

No real author workload or Formal cell was launched during this qualification.
The existing live authorization remains a live-policy artifact only; any new
Formal attempt still requires the prescribed fresh authorization because the
previous attempt root is quarantined.
