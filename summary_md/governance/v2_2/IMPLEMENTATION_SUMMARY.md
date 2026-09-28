# Governance v2 V2-2 execution reliability — Team A candidate

Base authority: `3430054ec32489116523644fc958ccb7ac29f4d3`. Dedicated branch: `impl/20260928-governance-v2-2-execution-reliability`. Pre-implementation worktree was clean. V2-1 history, existing C6/C7 science code, and historical Formal artifacts remain unchanged.

The implementation adds `src/tracking/governance_v2_execution.py`, `scripts/governance_v2_execution.py`, and a synthetic non-scientific qualification runner. The operator CLI atomically creates `attempts/<attempt_id>` with `mkdir` and launches `nohup` in the background with all wrapper stdio redirected locally. The Python wrapper establishes its own session with `setsid()`, atomically records boot ID/PID/start-time plus exact argv/cwd before starting a directly waited child, and routes child stdio into the attempt. Inspection compares live wrapper process-instance fields, scans non-zombie members of the recorded session, and reads terminal → liveness → terminal. The wrapper writes only mechanical `COMPLETED` or `FAILED` by same-directory fsync and atomic rename. Hard disappearance derives `INCOMPLETE`; no such terminal is persisted. Exit-zero completion waits for all other non-zombie session members to leave.

The child receives `V2_2_OUTPUT_ROOT` inside its fresh attempt namespace and runs with that root as cwd. The local qualification fixture obeys the no-detach child contract. Production child compliance and exact production-path proof belong to V2-4; this candidate does not integrate with C6/C7 Formal runtime. The new wrapper uses only the Python standard library and imports no scientific runtime module.

Local non-scientific Q1, Q2-A, Q2-B, Q4-A, Q4-B, Q5-A, Q5-B and the stray-process check passed in `candidate_evidence/LOCAL_QUALIFICATION_SUMMARY.json`. Host/session settings are recorded there. Q3 remains `OPERATOR_ACTION_REQUIRED`; exact real-session steps are in `Q3_REAL_SESSION_PROCEDURE.md`. No scripted stand-in or scientific Formal run was used.

G1/G2 supersession is recorded in `G1_G2_SCOPE.md`. Optional progress was omitted. No supervisor, daemon, watchdog, heartbeat, telemetry database, artifact registry, or new authority layer was added.

This is Team A implementation evidence only. V2-1 change-impact classification of the final candidate remains required; new infrastructure paths are expected to be unmapped under the selected V2-1 map and must fail closed for inheritance. Team B qualification and Q3 real-session evidence remain necessary before V2-2 closure or H_R readiness.
