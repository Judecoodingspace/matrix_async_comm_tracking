# Q3 real SSH / VSCode Remote disconnect procedure

Status: the operator completed the real abrupt-disconnect attempt `q3-real-20260928-001`; Team A Q3 evidence is `PASS` in `candidate_evidence/Q3_REAL_SESSION_EVIDENCE.json`. No intermediate post-disconnect `RUNNING` snapshot was captured. The procedure below records the qualification path for review; it does not request a second attempt. Do not run scientific H_R or C7 Formal work.

1. On the target host, record `hostname`, `cat /proc/sys/kernel/random/boot_id`, `who`, `loginctl list-sessions` where available, `loginctl show-user "$USER" -p Linger` where available, and effective `KillUserProcesses` from `/etc/systemd/logind.conf` plus drop-ins. Close any other active login/session for the same user that could mask a disconnect result. Record the actual launch path (SSH or VSCode Remote) and time.
2. In that real SSH or VSCode Remote terminal, use this worktree and a fresh attempt ID. Example commands:

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/governance_v2_2_execution_reliability
PYTHONDONTWRITEBYTECODE=1 python3 scripts/governance_v2_execution.py launch --attempts-root /tmp/v2_2_q3_real_session --attempt-id q3-real-20260928-001 -- /mnt/data/deeplearning_env/anaconda3/bin/python3 /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/governance_v2_2_execution_reliability/scripts/qualify_governance_v2_2.py _child --mode sleep --duration 300
```

The launch command prints attempt-local launch identity and returns while the child keeps running. Its output root is `/tmp/v2_2_q3_real_session/q3-real-20260928-001/output`. Use a new ID if that namespace already exists; never clear or reuse it.

3. Immediately sever the actual operator connection abruptly: close or kill the SSH client, drop its network connection, or close the VSCode Remote session/window. Do not use a clean shell `exit`. Keep all same-user alternate sessions absent for at least 60 seconds so an immediate reconnect cannot mask failure.
4. Reconnect through a fresh real session while the 300-second fixture is still expected to run. Inspect only mechanical state and identity:

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/governance_v2_2_execution_reliability
PYTHONDONTWRITEBYTECODE=1 python3 scripts/governance_v2_execution.py inspect --attempts-root /tmp/v2_2_q3_real_session --attempt-id q3-real-20260928-001
```

Expect `RUNNING` with live non-zombie attempt-session PID(s), the original launch identity, and wrapper process-instance match if the wrapper remains live. After the child duration, inspect again and require a valid identity-consistent `COMPLETED` terminal. Do not tail runtime logs as operational observability.

5. Record actual disconnect/reconnect times, session inventory, host/session settings, inspected states, and exact attempt path as Team A evidence. If the attempt fails to survive, record `NOHUP_BASELINE_FALSIFIED = YES`, stop, and return correction required; do not substitute a supervisor.

Team A records Q3 `PASS` for the bounded claim that the same attempt survived real operator-session loss and later had an identity-consistent `COMPLETED` terminal. Team B independent review remains pending; this is not V2-2 qualification closure or H_R authorization.
