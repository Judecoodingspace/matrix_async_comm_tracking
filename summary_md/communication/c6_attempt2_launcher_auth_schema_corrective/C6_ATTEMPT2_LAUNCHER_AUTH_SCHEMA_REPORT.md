# C6 Attempt 2 Launcher Authorization-Schema Corrective

This narrow correction resolves the pre-launch Attempt 2 block without touching the scientific runtime or generated source. The C6 MVE authorization and launch specification now bind `attempt = 2` and the accepted wrapper-status-contract authority `47d20389363582e62676e547483547582c4d820c` exactly.

The Attempt 2 run ID and logical output root are deterministically derived from the attempt identity. Attempt 1 naming, the quarantined failed `/tmp` root, schema/type deviations, stale authority values, root collisions, and authorization/spec attempt mismatches fail before child execution. A stubbed parent boundary test reaches the production child invocation point without launching a child or author workload.

Verification: `PYTHONPATH=src pytest -q tests/test_mdmt_mia_c6_*.py` — 48 passed. No real authorization artifact, real MVE, tracking read, Formal execution, or science adaptation occurred. This evidence supports only Team B's narrow launcher/auth-schema delta review.
