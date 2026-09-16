# C6 Failed MVE Mechanical-Validity Audit

The preserved attempt is a failed mechanical canary, not an accepted MVE. The author workload completed 700/700 frames with exit 0; the wrapper returned 1 because the pre-correction path contract retained the literal `train_{}` component. Communication evidence is present at `train_23/results/mia_train_23`, and post-failure validation is PASS, but this does not upgrade the attempt.

- Preserved root: `/tmp/c6_mve_primary_p23_fifo_strong_failed_mechanical_20260916`
- Inventory SHA-256: `88a933ec38bab88cfb3bc056c085a7ce8f90c4a5c5d9d2b196131c3ba8486efb`
- Parent/wrapper/author exits: `1 / 1 / 0`
- Author progress: `700/700`
- Failure: `scripts/run_mdmt_mia_c6_real_child.py:_run:116`, old source line 77
- Classification: `A = WRAPPER_PATH_CONTRACT_BUG`
- Synthetic corrected-path and fail-close tests: PASS
- New MVE authorization: NO; second real attempt: NO

Forensic quantities are quarantined (`scientific_use_allowed=false`) and were not used for adaptation or downstream progression.
