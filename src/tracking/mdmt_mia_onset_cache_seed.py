"""Train Pair53/66 adapter for the frozen E023 cache-write author path.

No evaluator or scientific acceptance is called. Both pairs are prepared in a
fresh staging directory; the shared cache is published only when both complete.
The existing absolute, resolved-image-path cache key and NPZ bytes are retained.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
from pathlib import Path

import numpy as np

from tracking import mdmt_mia_onset_executor as executor
from tracking.mdmt_mia_onset_mve import MvePreflightError, canonical_json

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / 'outputs/20260904_mdmt_mia_pair53_66_mve_execution_7d52da2'
CONFIG = executor.AUTHOR_ROOT / 'run_configs/one_carafe_bytetrack_full_mdmt_reproduction.py'
CHECKPOINT = executor.DATASET / 'checkpoints/work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt/epoch_12.pth'
HOOK = executor.VARIANT / 'mmtrack/models/mot/byte_track.py'
HOOK_SHA256 = '14536aaf1e60f5be03fadf3ad6e8da8b4620294e2973ad54c34d588900d6b165'
CHECKPOINT_SHA256 = 'f50882a6814b08d8f9ee2db278825258b52d16463fff6fb45ff45484df7d9e96'
CONFIG_SHA256 = {
    str(CONFIG): '6f472813987fdfecd4751d0ff5729c264c4595430745a43f75b32f891e7f288a',
    str(executor.AUTHOR_ROOT / 'upstream/configs/_base_/models/new_faster_rcnn_r50_fpn.py'):
        '8a62bb8d993640f13ba9218d844955b9b0d04510dfe905567b77fd1617b566b1',
    str(executor.AUTHOR_ROOT / 'upstream/configs/_base_/datasets/test_challenge.py'):
        'f05b77f867e7a27ae072006e5aa1a50a7445c539e74e834c7fd9099d5d8889ba',
    str(executor.AUTHOR_ROOT / 'upstream/configs/_base_/default_runtime.py'):
        'be4151073d5053562b18651294b6b109d8220bcebff7f437fc0f506785201ecf',
}


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def image_population(pair: str) -> dict[str, Path]:
    """Mirror supplement_MIA image enumeration and the frozen cache filename.

    The author enumerates view 1, replaces /1/ and -1 for view 2, and calls
    inference_mot for both even at i=0. No annotation or prediction is read.
    """
    if pair not in executor.MVE_PAIRS:
        raise MvePreflightError('cache seed permits train Pair53/66 only')
    first = executor.DATASET / 'train/1' / (pair + '-1')
    second = executor.DATASET / 'train/2' / (pair + '-2')
    names = sorted((p.name for p in first.iterdir()
                    if p.name.endswith(('.jpg', '.png', '.jpeg'))),
                   key=lambda name: int(name.split('.')[0]))
    other = {p.name for p in second.iterdir() if p.name.endswith(('.jpg', '.png', '.jpeg'))}
    if not names or set(names) != other:
        raise MvePreflightError('paired train image population mismatch')
    entries = {}
    for name in names:
        for directory in (first, second):
            image = (directory / name).resolve(strict=True)
            key = hashlib.sha256(str(image).encode('utf-8')).hexdigest() + '.npz'
            if not image.is_file() or key in entries:
                raise MvePreflightError('cache input collision or non-file')
            entries[key] = image
    return entries


def config_fingerprints(path: Path, seen=None) -> dict[str, str]:
    """Hash the actual config and recursively declared MMConfig bases, no exec."""
    seen = {} if seen is None else seen
    path = path.resolve(strict=True)
    if str(path) in seen:
        return seen
    seen[str(path)] = sha256(path)
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_base_'
                                               for t in node.targets):
            bases = ast.literal_eval(node.value)
            for base in ([bases] if isinstance(bases, str) else bases):
                config_fingerprints(path.parent / base, seen)
    return seen


def validate_package(root: Path = PACKAGE) -> None:
    """Check a rendered, self-consistent immutable execution package."""
    root = root.resolve()
    if Path.cwd().resolve() != REPO:
        raise MvePreflightError('run from the authoritative worktree')
    manifest_path = root / 'MVE_EXECUTION_PACKAGE_MANIFEST.json'
    manifest = json.loads(manifest_path.read_text())
    required = {'scientific_plan_sha256', 'qualification_plan_sha256',
                'condition_manifest_sha256', 'implementation_commit'}
    if not required <= set(manifest):
        raise MvePreflightError('execution package manifest is incomplete')
    for name, key in [('MVE_EXECUTION_PLAN_MANIFEST.json', 'scientific_plan_sha256'),
                      ('AUXILIARY_QUALIFICATION_PLAN.json', 'qualification_plan_sha256'),
                      ('condition_manifest.json', 'condition_manifest_sha256')]:
        if sha256(root / name) != manifest[key]:
            raise MvePreflightError('frozen package artifact mismatch: ' + name)
    frozen = json.loads((root / 'MVE_EXECUTION_PLAN_MANIFEST.json').read_text())
    scientific = executor.plan(root)
    references = [executor.resolve(p, 'Y00', root, role='REFERENCE') for p in executor.MVE_PAIRS]
    qualifications = executor.qualification_plan(root)
    if ([s.as_dict() for s in scientific] != frozen['specs'] or
            [s.as_dict() for s in references] != frozen['reference_parity_specs'] or
            [s.as_dict() for s in qualifications] != json.loads(
                (root / 'AUXILIARY_QUALIFICATION_PLAN.json').read_text())['specs']):
        raise MvePreflightError('execution mapping differs from frozen package')
    for spec in scientific + [q.execution for q in qualifications]:
        if (spec.env.get('MIA_DETECTION_CACHE_MODE') != 'read' or
                spec.env.get('MIA_DETECTION_CACHE_ROOT') != str(root / 'detector_cache')):
            raise MvePreflightError('packetized cache-read policy mismatch')
    if any('MIA_DETECTION_CACHE_MODE' in s.env or 'MIA_DETECTION_CACHE_ROOT' in s.env
           for s in references):
        raise MvePreflightError('reference must retain live detector role')
    if sha256(HOOK) != HOOK_SHA256 or sha256(CHECKPOINT) != CHECKPOINT_SHA256:
        raise MvePreflightError('frozen detector hook/checkpoint mismatch')
    if config_fingerprints(CONFIG) != CONFIG_SHA256:
        raise MvePreflightError('frozen detector config/base mismatch')


def identity(root: Path) -> dict:
    populations = {pair: image_population(pair) for pair in executor.MVE_PAIRS}
    return {
        'classification': 'PRE_LAUNCH_ENGINEERING_PREPARATION',
        'execution_package_sha256': sha256(root / 'MVE_EXECUTION_PACKAGE_MANIFEST.json'),
        'detector_config': str(CONFIG), 'config_sha256': config_fingerprints(CONFIG),
        'checkpoint': str(CHECKPOINT), 'checkpoint_sha256': sha256(CHECKPOINT),
        'cache_hook_sha256': sha256(HOOK),
        'author_entry_sha256': sha256(executor.VARIANT / 'demo/supplement_MIA.py'),
        'author_wrapper_sha256': sha256(executor.AUTHOR_WRAPPER),
        'device': 'cuda:0', 'seed': 7, 'split': 'train',
        'images': {pair: {key: {'path': str(path), 'sha256': sha256(path)}
                          for key, path in rows.items()} for pair, rows in populations.items()},
    }


def seed_spec(pair: str, root: Path, attempt: Path, cache: Path) -> dict:
    """Adapt E023 zero-delay, no-shadow seed to train and a separate attempt."""
    base = executor.resolve(pair, 'Y00', root)
    output = attempt / pair
    env = {**base.env, 'MIA_OUTPUT_ROOT': str(output),
           'MIA_RUN_INPUT_ROOT': str(output / 'run_inputs'),
           'MIA_DETECTION_CACHE_ROOT': str(cache), 'MIA_DETECTION_CACHE_MODE': 'write',
           'PYTHONDONTWRITEBYTECODE': '1'}
    return {'pair': pair, 'classification': 'PRE_LAUNCH_ENGINEERING_PREPARATION',
            'condition': 'detector_cache_seed', 'argv': list(base.argv), 'environment': env}


def cache_files(root: Path) -> dict[str, Path]:
    return {p.name: p for p in root.glob('*.npz') if p.is_file()}


def validate_npz(path: Path) -> None:
    # Preserve E023 schema and values; this only checks readability and shape.
    with np.load(str(path), allow_pickle=False) as archive:
        count = archive['class_count']
        if count.shape != (1,) or count.dtype != np.dtype('int32') or int(count[0]) != 3:
            raise MvePreflightError('invalid frozen CARAFE class_count')
        if set(archive.files) != {'class_count', 'class_0', 'class_1', 'class_2'}:
            raise MvePreflightError('invalid frozen CARAFE NPZ schema')
        for i in range(3):
            boxes = archive['class_' + str(i)]
            if boxes.ndim != 2 or boxes.shape[1] != 5 or not np.isfinite(boxes).all():
                raise MvePreflightError('unreadable detector array')


def _write(path: Path, payload: dict) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(canonical_json(payload))
    temporary.replace(path)


def status(root: Path = PACKAGE, *, verify: bool = False) -> dict:
    """Read cache counts/status only. Full verify rechecks inputs and NPZ hashes."""
    canonical = root / 'detector_cache'
    state_path = root / 'cache_seed/status.json'
    state = json.loads(state_path.read_text()) if state_path.is_file() else {'state': 'NOT_STARTED'}
    cache = canonical
    if not canonical.exists() and state.get('attempt'):
        cache = root / 'cache_seed' / state['attempt'] / 'detector_cache'
    files = cache_files(cache)
    populations = {p: image_population(p) for p in executor.MVE_PAIRS}
    expected = set().union(*(set(rows) for rows in populations.values()))
    complete = False
    reason = 'CACHE_NOT_PUBLISHED'
    manifest_path = canonical / 'cache_manifest.json'
    if verify and manifest_path.is_file():
        validate_package(root)
        manifest = json.loads(manifest_path.read_text())
        complete = (not canonical.is_symlink() and manifest.get('state') == 'COMPLETE'
                    and manifest.get('identity') == identity(root)
                    and set(files) == expected and set(manifest.get('cache_sha256', {})) == expected)
        if complete:
            for name, path in files.items():
                validate_npz(path)
                if path.is_symlink() or sha256(path) != manifest['cache_sha256'][name]:
                    complete = False
                    break
        reason = 'PASS' if complete else 'CACHE_PROVENANCE_OR_CONTENT_MISMATCH'
    return {'state': state['state'], 'current_pair': state.get('current_pair'),
            'attempt': state.get('attempt'), 'published': manifest_path.is_file(),
            'cache_root': str(cache), 'verified': verify,
            'pairs': {pair: {'expected': len(rows), 'actual': len(set(rows) & set(files)),
                             'complete': complete} for pair, rows in populations.items()},
            'missing': len(expected - set(files)), 'unexpected': len(set(files) - expected),
            'verification': reason}


def seed(root: Path = PACKAGE, *, runner=subprocess.run) -> None:
    validate_package(root)
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).strip():
        raise MvePreflightError('worktree must be clean before manual seeding')
    canonical = root / 'detector_cache'
    if canonical.exists():
        if all(p['complete'] for p in status(root, verify=True)['pairs'].values()):
            print('DETECTOR_CACHE_ALREADY_VERIFIED')
            return
        raise MvePreflightError('existing cache is incomplete/unbound; refusing overwrite')
    preparation = root / 'cache_seed'
    preparation.mkdir(exist_ok=True)
    # Cross-process exclusive lock, released automatically on interruption.
    import fcntl
    with (preparation / 'seed.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        number = 1
        while (preparation / ('attempt_%03d' % number)).exists():
            number += 1
        attempt = preparation / ('attempt_%03d' % number)
        attempt.mkdir()
        cache = attempt / 'detector_cache'
        cache.mkdir()
        before = identity(root)
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
        record = {'state': 'RUNNING', 'attempt': attempt.name,
                  'classification': 'PRE_LAUNCH_ENGINEERING_PREPARATION',
                  'implementation_commit': commit, 'identity': before}
        _write(attempt / 'seed_manifest.json', record)
        try:
            expected = set()
            for pair in executor.MVE_PAIRS:
                _write(preparation / 'status.json', {'state': 'RUNNING', 'attempt': attempt.name,
                                                     'current_pair': pair})
                spec = seed_spec(pair, root, attempt, cache)
                _write(attempt / ('command_' + pair + '.json'), spec)
                # Do not inherit MIA_CONFIG, cache-mode, or runtime overrides.
                env = {k: v for k, v in os.environ.items()
                       if not k.startswith(('MIA_', 'MDMT_', 'PYTHON')) and k != 'DEVICE'}
                env.update(spec['environment'])
                with (attempt / ('author_' + pair + '.log')).open('xb') as log:
                    result = runner(spec['argv'], cwd=REPO, env=env,
                                    stdout=log, stderr=subprocess.STDOUT, check=False)
                if result.returncode:
                    raise MvePreflightError('cache seed author failed for pair ' + pair)
                expected.update(before['images'][pair])
                if set(cache_files(cache)) != expected:
                    raise MvePreflightError('cache seed image coverage mismatch for pair ' + pair)
                print('PAIR%s_CACHE_WRITTEN = %s' % (pair, len(before['images'][pair])), flush=True)
            if identity(root) != before:
                raise MvePreflightError('detector inputs changed during seeding')
            for path in cache_files(cache).values():
                if path.is_symlink():
                    raise MvePreflightError('cache symlink forbidden')
                validate_npz(path)
            record.update(state='COMPLETE', cache_sha256={key: sha256(path)
                          for key, path in sorted(cache_files(cache).items())})
            _write(cache / 'cache_manifest.json', record)
            # Read-only cache for future consumers; no per-condition writers.
            for path in cache.iterdir():
                path.chmod(0o444)
            if canonical.exists():
                raise MvePreflightError('canonical cache appeared during seeding')
            cache.rename(canonical)
            canonical.chmod(0o555)
            _write(attempt / 'seed_manifest.json', record)
            _write(preparation / 'status.json', {'state': 'COMPLETE', 'attempt': attempt.name,
                                                 'current_pair': None})
        except BaseException:
            record['state'] = 'FAILED'
            _write(attempt / 'seed_manifest.json', record)
            _write(preparation / 'status.json', {'state': 'STOPPED', 'attempt': attempt.name,
                                                 'current_pair': pair if 'pair' in locals() else None})
            raise


def render(root: Path = PACKAGE) -> dict:
    root = root.resolve()
    validate_package(root)
    attempt = root / 'cache_seed/attempt_001'
    return {'execution_package_sha256': sha256(root / 'MVE_EXECUTION_PACKAGE_MANIFEST.json'),
            'expected': {pair: len(image_population(pair)) for pair in executor.MVE_PAIRS},
            'commands': [seed_spec(pair, root, attempt, attempt / 'detector_cache')
                         for pair in executor.MVE_PAIRS],
            'canonical_cache_root': str(root / 'detector_cache')}
