# Pair53/66 train detector cache seed integration

READY_TO_SEED_CACHE = YES (implementation readiness; cache not generated).

`PAIR53_PAIR66_DETECTOR_CACHE_SEED_PATH_READY`

This is manual pre-launch engineering preparation, following the accepted
`KEEP_PACKETIZED_SHARED_CACHE_REFERENCE_MAY_RUN_LIVE` authority. No real author
process was launched during implementation. The script reuses the unchanged
E023 ByteTrack cache-write hook via the existing author wrapper with `mia train
53` / `mia train 66`, all-zero delays and no shadow/edge-cut. Like the E023
seed, the future manual preparation traverses the author pipeline and may
produce incidental prediction/runtime files in its isolated preparation root;
none is evaluated, accepted, or used as a scientific/qualification result.

## Identity and evidence

- Branch: `exp/20260903-001-mdmt-mia-p39-homography-fallback-successor-census`.
- Worktree: `/mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census`.
- HEAD before integration: `c721533abfc833627793e05e7b2de8ec74964a3d`.
- Implementation commit: the commit adding this document and
  `scripts/seed_mdmt_mia_onset_detector_cache.py`; use `git log -1 --format=%H -- scripts/seed_mdmt_mia_onset_detector_cache.py`.
- Existing execution-package SHA-256 remains
  `2d1037acc2a0e42bf5b744b8676e1af465949db7738b44245ec4ed30eb3a44a8`.
  Package artifacts and their historical implementation commit are unchanged.
- Detector config: `/mnt/data/yzm/experiments/mdmt_mia_official/run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py`;
  SHA-256 `6f472813987fdfecd4751d0ff5729c264c4595430745a43f75b32f891e7f288a`.
  The adapter also checks the three recursively declared base-config hashes.
- Checkpoint: `/mnt/data/yzm/datasets/Multi-Drone-Multi-Object-Detection-and-Tracking/checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth`;
  SHA-256 `f50882a6814b08d8f9ee2db278825258b52d16463fff6fb45ff45484df7d9e96`.
- Device: `cuda:0`; inherited seed environment: `PYTHONHASHSEED=7`.
  No additional RNG policy is introduced.
- Unchanged cache-hook SHA-256:
  `14536aaf1e60f5be03fadf3ad6e8da8b4620294e2973ad54c34d588900d6b165`.
- Both pairs use the existing physical canonical root:
  `/mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census/outputs/20260904_mdmt_mia_pair53_66_mve_execution_7d52da2/detector_cache`.
  Their disjoint namespaces are the SHA-256 of resolved train image paths.
  Introducing pair subdirectories would change existing consumer paths, so none
  were added.

## Coverage and publication

The actual author sorts view-1 `.jpg/.png/.jpeg` filenames numerically, maps
view 2 by directory/sequence replacement, and calls `inference_mot` for both
views at every index including frame zero. The unchanged cache key is
`sha256(str(Path(image_filename).resolve())) + '.npz'`.

| Pair | Files per view | Source filenames | Expected entries | Actual before seed |
| --- | ---: | --- | ---: | ---: |
| 53 | 500 | `00000201.jpg` through `00000700.jpg` | 1000 | 0 |
| 66 | 300 | `00000401.jpg` through `00000700.jpg` | 600 | 0 |

`MISSING_CACHE_ENTRIES = 1600` before manual seeding. Completeness is not claimed.
The adapter checks both view populations, source image hashes, config/base
hashes, checkpoint, wrapper, author entry and cache-hook identity. Each new
seed attempt uses `cache_seed/attempt_NNN/`, outside scientific/qualification
roots. After both author exits succeed, exact expected filenames and NPZ schema
must match; input fingerprints must remain unchanged. Only then is the whole
directory atomically renamed to `detector_cache`, with a completion/provenance
record and per-file hashes. Files are made read-only. No incomplete cache is
published, and an existing unbound or altered cache is never overwritten.

Incomplete attempt roots are preserved; invoking seed again uses a new attempt.
A verified published cache is reused without inference. A partially populated
canonical root or provenance mismatch requires inspection; no automatic repair.
The exclusive seed lock prevents simultaneous writers.

REFERENCE still has no cache environment or hook. All 22 packetized conditions
and eight qualification specifications retain the original `read` environment
and root. Missing entries still raise in the original hook. Future strict
REFERENCE/Y00 dual-view prediction parity remains unchanged.

## Focused verification

```bash
PYTHONPATH=src:scripts python -m pytest -q tests/test_mdmt_mia_onset_cache_seed.py tests/test_mdmt_mia_onset_executor.py
```

Result: **25 passed**. Synthetic-only checks cover exact resolved-image keys,
first-frame coverage, split rejection, pair-view mismatch, unchanged consumer
mapping, two-pair atomic publication, missing/foreign entries, process failure,
preserved attempts, changed source/cache rejection and the actual frozen hook's
write/read fixture (AST-extracted functions only, no detector/tracker imports).
`py_compile` and `git diff --check` passed. A read-only real-input plan render
resolved expected populations to 1000/600; it launched no author process.
A transient indentation error introduced in the final edit was caught during
collection, corrected, and the same 25 focused tests and compilation passed.
No real data execution was attempted during that engineering retry.

## Terminal A: pre-launch check

This checks the implementation commit, clean worktree and the existing package
through the real adapter. The final chat handoff also supplies the exact HEAD.

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census
(
  set -eu
  git branch --show-current
  git rev-parse HEAD
  git status --short
  test "$(git branch --show-current)" = exp/20260903-001-mdmt-mia-p39-homography-fallback-successor-census
  test "$(git rev-parse HEAD)" = "$(git log -1 --format=%H -- scripts/seed_mdmt_mia_onset_detector_cache.py)"
  test -z "$(git status --porcelain)"
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /mnt/data/deeplearning_env/anaconda3/bin/python scripts/seed_mdmt_mia_onset_detector_cache.py plan
) || { echo 'DO NOT LAUNCH'; false; }
```

## Terminal A: seed both pairs (researcher executes)

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /mnt/data/deeplearning_env/anaconda3/bin/python scripts/seed_mdmt_mia_onset_detector_cache.py seed
```

The orchestration Python above is the environment used by the focused tests;
the existing wrapper invokes the author environment at
`/mnt/data/yzm/experiments/mdmt_mia_official/.conda-env/bin/python`.
Seeding writes logs to `cache_seed/attempt_NNN/author_53.log` and `author_66.log`.
Use the structured count monitor below, which does not read these logs or any
prediction/metric output.

## Terminal B: cache live progress

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census
while true; do
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /mnt/data/deeplearning_env/anaconda3/bin/python scripts/seed_mdmt_mia_onset_detector_cache.py status
  sleep 5
done
```

Counts display entries in the active staging root until publication, then the
canonical root. Counts alone do not establish completeness; verify below does.

## Terminal A: verify cache (read-only)

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /mnt/data/deeplearning_env/anaconda3/bin/python scripts/seed_mdmt_mia_onset_detector_cache.py verify
```

Required result: `PAIR53_CACHE_COMPLETE = YES`, `PAIR66_CACHE_COMPLETE = YES`,
`MISSING_CACHE_ENTRIES = 0`, `UNEXPECTED_CACHE_ENTRIES = 0`, exit status zero.
It rechecks provenance, real source fingerprints, every expected NPZ and hash.

## Terminal A: existing MVE API invocation, only after cache verification

`SINGLE_PACKAGE_LAUNCH_NOT_SUPPORTED`: the tracked onset CLI is preflight-only.
The following explicit Python session calls the existing executor APIs. It
does not add an executor or alter qualification/acceptance logic. It has no
resume option: any pre-existing execution root blocks a new launch.

There is an ordering constraint in the existing executor: `Y00` acceptance
requires qualification PASS, whereas the `Y10_d5/Yec_d5` baselines may run
before qualification. Therefore this real command executes those four baseline
conditions, eight qualification runs, then live REFERENCE and remaining
conditions (including strict Y00 parity). Putting accepted Y00 before
qualification would contradict the current executor and is not implemented
by this cache integration.

The public console contains only status/counts. Author console is redirected
to a separate local log; no scientific values are printed by the session.
No claim of compensation/onset or final research review follows from reaching
22 accepted attempts.

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src /mnt/data/deeplearning_env/anaconda3/bin/python -u - <<'PY'
import json, os, subprocess
from pathlib import Path
from tracking import mdmt_mia_onset_executor as e
from tracking.mdmt_mia_onset_cache_seed import PACKAGE, REPO, status, validate_package

validate_package()
if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
    raise SystemExit('DO NOT LAUNCH: worktree dirty')
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
implementation = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--',
    'scripts/seed_mdmt_mia_onset_detector_cache.py'], text=True).strip()
if head != implementation:
    raise SystemExit('DO NOT LAUNCH: implementation identity mismatch')
if not all(row['complete'] for row in status(verify=True)['pairs'].values()):
    raise SystemExit('DO NOT LAUNCH: detector cache incomplete')
scientific = e.plan(PACKAGE)
qualifications = e.qualification_plan(PACKAGE)
references = {pair: e.resolve(pair, 'Y00', PACKAGE, role='REFERENCE') for pair in e.MVE_PAIRS}
roots = [s.output_root for s in scientific] + [q.execution.output_root for q in qualifications]
roots += [r.output_root for r in references.values()]
if any(p.exists() for p in roots):
    raise SystemExit('DO NOT LAUNCH: existing attempt; no automatic overwrite/resume')
for name in tuple(os.environ):
    if name.startswith(('MIA_', 'MDMT_')):
        del os.environ[name]
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
public = (PACKAGE / 'manual_mve_progress.log').open('x', buffering=1)
author = (PACKAGE / 'manual_mve_author_console.log').open('xb')
qualification_status = PACKAGE / 'instrumentation_qualification.json'
records = []
def emit(state, pair='-', condition='-', attempt='-'):
    accepted = sum((s.output_root / 'attempt_state.json').is_file() and
        json.loads((s.output_root / 'attempt_state.json').read_text()).get('state') == 'ACCEPTED'
        for s in scientific)
    line = 'package=%s qualification=%d/8 scientific_accepted=%d/22 pair=%s condition=%s attempt=%s embargo=ACTIVE' % (
        state, len(records), accepted, pair, condition, attempt)
    print(line, flush=True)
    public.write(line + '\n')
def runner(argv, **kwargs):
    return subprocess.run(argv, **kwargs, stdout=author, stderr=subprocess.STDOUT)
pair, condition = '-', '-'
try:
    for spec in scientific:
        if spec.logical in e.QUALIFICATION_BASELINES:
            pair, condition = spec.pair, spec.logical
            emit('RUNNING', pair, condition, 'RUNNING')
            e.execute_and_accept(spec, launch=True, runner=runner)
            emit('RUNNING', pair, condition, 'ACCEPTED')
    for q in qualifications:
        pair, condition = q.pair, q.name
        emit('RUNNING', pair, condition, 'RUNNING')
        baseline = next(s for s in scientific if s.pair == q.pair and s.logical == q.source_logical)
        records.append(e.execute_qualification(q, baseline, launch=True, runner=runner))
        emit('RUNNING', pair, condition, 'QUALIFICATION_PASSED')
    e.write_qualification_status(qualification_status, records)
    e.require_qualification_pass(qualification_status)
    for pair in e.MVE_PAIRS:
        ref = references[pair]
        condition = 'REFERENCE'
        emit('RUNNING', pair, condition, 'RUNNING')
        e.run(ref, launch=True, runner=runner)
        first, second = e.prediction_paths(ref)
        reference = e.ReferenceArtifacts(pair, str(ref.output_root), first, second)
        for spec in scientific:
            if spec.pair == pair and spec.logical not in e.QUALIFICATION_BASELINES:
                condition = spec.logical
                emit('RUNNING', pair, condition, 'RUNNING')
                e.execute_and_accept(spec, reference=reference if condition == 'Y00' else None,
                    qualification_status=qualification_status, launch=True, runner=runner)
                emit('RUNNING', pair, condition, 'ACCEPTED')
    emit('COMPLETE', attempt='EXECUTION_COMPLETE')
except BaseException:
    emit('STOPPED', pair, condition, 'FAILED_OR_INTERRUPTED')
    raise SystemExit('MVE STOPPED; inspect execution failure before any retry')
finally:
    public.close()
    author.close()
PY
```

## Terminal B: MVE live progress / snapshot

This follows only the allowlisted public lines generated above. It never reads
the author log, prediction JSON, numeric metrics or contrasts.

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census
tail -n 20 -F outputs/20260904_mdmt_mia_pair53_66_mve_execution_7d52da2/manual_mve_progress.log
```

For a one-shot read-only snapshot, replace `-F` with no follow flag:

```bash
cd /mnt/data/yzm/experiments/matrix_async_pose_comm_tracking/.worktrees/p39_homography_fallback_successor_census
tail -n 1 outputs/20260904_mdmt_mia_pair53_66_mve_execution_7d52da2/manual_mve_progress.log
```

Status advances on actual API completions. A long-running author process leaves
its last `RUNNING` entry until completion. `STOPPED` requires inspection. A hard
kill/host failure can leave a stale RUNNING line; it is not proof the process
is still alive. No unattended resume or automatic Git repair is supplied.

## Final boundary

```text
REFERENCE_LIVE_DETECTOR_AUTHORITY_PRESERVED = YES
PACKETIZED_SHARED_CACHE_POLICY_PRESERVED = YES
CODEX_AUTOMATIC_CACHE_SEED = NO
CODEX_AUTOMATIC_MVE_LAUNCH = NO
PAIR53_TRACKING_EXECUTED_BY_CODEX = NO
PAIR66_TRACKING_EXECUTED_BY_CODEX = NO
PAIR53_CACHE_SEEDED_BY_CODEX = NO
PAIR66_CACHE_SEEDED_BY_CODEX = NO
REAL_QUALIFICATION_RUNS = 0/8
REAL_ACCEPTED_RUNS = 0/22
SCIENTIFIC_OUTCOMES_READ = NO
```
