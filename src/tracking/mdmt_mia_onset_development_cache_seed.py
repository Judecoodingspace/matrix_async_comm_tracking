"""Manual-only, pair-specific detector-cache preparation for development.

There is no live-detector fallback in a packetized development condition.  A
cache is published independently for each frozen development pair only after
its full image population has been written and validated.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from tracking.mdmt_mia_onset_mve import MvePreflightError, canonical_json
from tracking import mdmt_mia_onset_cache_seed as common
from tracking import mdmt_mia_onset_development_executor as development

REPO = Path(__file__).resolve().parents[2]


def image_population(pair: str) -> dict[str, Path]:
    if str(pair) not in development.DEVELOPMENT_PAIRS:
        raise MvePreflightError('cache seed permits frozen development pairs only')
    first = development.inherited.DATASET / 'train' / '1' / f'{pair}-1'
    second = development.inherited.DATASET / 'train' / '2' / f'{pair}-2'
    names = sorted((path.name for path in first.iterdir() if path.suffix.lower() in ('.jpg', '.png', '.jpeg')),
                   key=lambda name: int(Path(name).stem))
    if not names or {path.name for path in second.iterdir() if path.suffix.lower() in ('.jpg', '.png', '.jpeg')} != set(names):
        raise MvePreflightError('paired train image population mismatch')
    rows: dict[str, Path] = {}
    for name in names:
        for directory in (first, second):
            image = (directory / name).resolve(strict=True)
            key = hashlib.sha256(str(image).encode('utf-8')).hexdigest() + '.npz'
            if key in rows:
                raise MvePreflightError('cache input collision')
            rows[key] = image
    return rows


def _digest(path: Path) -> str:
    return common.sha256(path)


def package_manifest(root: Path) -> dict:
    path = root / 'DEVELOPMENT_EXECUTION_PACKAGE_MANIFEST.json'
    if not path.is_file():
        raise MvePreflightError('development execution package manifest missing')
    payload = json.loads(path.read_text())
    required = {'scientific_plan_sha256', 'condition_manifest_sha256', 'implementation_commit',
                'scientific_expected', 'qualification_expected', 'outcome_embargo'}
    if not required <= set(payload) or payload['scientific_expected'] != 255 or payload['qualification_expected'] != 0:
        raise MvePreflightError('development execution package manifest invalid')
    if _digest(root / 'DEVELOPMENT_EXECUTION_PLAN_MANIFEST.json') != payload['scientific_plan_sha256']:
        raise MvePreflightError('development scientific plan mismatch')
    if _digest(root / 'condition_manifest.json') != payload['condition_manifest_sha256']:
        raise MvePreflightError('development condition manifest mismatch')
    frozen = json.loads((root / 'DEVELOPMENT_EXECUTION_PLAN_MANIFEST.json').read_text())
    specs = development.plan(root)
    references = development.reference_plan(root)
    if frozen.get('specs') != [spec.as_dict() for spec in specs] or frozen.get('reference_parity_specs') != [spec.as_dict() for spec in references]:
        raise MvePreflightError('development execution mapping differs from frozen package')
    for spec in specs:
        if spec.env.get('MIA_DETECTION_CACHE_MODE') != 'read' or spec.env.get('MIA_DETECTION_CACHE_ROOT') != str(root / 'detector_cache' / spec.pair):
            raise MvePreflightError('pair-specific cache-read policy mismatch')
    if any('MIA_DETECTION_CACHE_ROOT' in spec.env for spec in references):
        raise MvePreflightError('reference must retain live detector role')
    return payload


def pair_identity(root: Path, pair: str) -> dict:
    return {'execution_package_sha256': _digest(root / 'DEVELOPMENT_EXECUTION_PACKAGE_MANIFEST.json'),
            'pair': pair, 'split': 'train', 'device': 'cuda:0', 'seed': 7,
            'detector_config': str(common.CONFIG), 'config_sha256': common.config_fingerprints(common.CONFIG),
            'checkpoint': str(common.CHECKPOINT), 'checkpoint_sha256': _digest(common.CHECKPOINT),
            'cache_hook_sha256': _digest(common.HOOK),
            'images': {name: {'path': str(path), 'sha256': _digest(path)}
                       for name, path in image_population(pair).items()}}


def seed_spec(pair: str, root: Path, attempt: Path, cache: Path) -> dict:
    base = development.resolve(pair, 'Y00', root)
    output = attempt / 'author_output'
    env = {**base.env, 'MIA_OUTPUT_ROOT': str(output), 'MIA_RUN_INPUT_ROOT': str(output / 'run_inputs'),
           'MIA_DETECTION_CACHE_ROOT': str(cache), 'MIA_DETECTION_CACHE_MODE': 'write',
           'PYTHONDONTWRITEBYTECODE': '1'}
    return {'classification': 'PRE_LAUNCH_ENGINEERING_PREPARATION', 'pair': pair,
            'condition': 'detector_cache_seed', 'argv': list(base.argv), 'environment': env}


def _write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(canonical_json(value))
    temporary.replace(path)


def _files(path: Path) -> dict[str, Path]:
    return {item.name: item for item in path.glob('*.npz') if item.is_file()}


def status(root: Path, *, verify: bool = False) -> dict:
    root = root.resolve()
    rows = {}
    missing = unexpected = 0
    for pair in development.DEVELOPMENT_PAIRS:
        expected = image_population(pair)
        cache = root / 'detector_cache' / pair
        files = _files(cache)
        manifest_path = cache / 'cache_manifest.json'
        complete = False
        if verify and manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text())
            complete = (manifest.get('state') == 'COMPLETE' and manifest.get('identity') == pair_identity(root, pair)
                        and set(files) == set(expected) and set(manifest.get('cache_sha256', {})) == set(expected))
            if complete:
                for name, path in files.items():
                    common.validate_npz(path)
                    if path.is_symlink() or _digest(path) != manifest['cache_sha256'][name]:
                        complete = False
                        break
        rows[pair] = {'expected': len(expected), 'actual': len(set(files) & set(expected)), 'complete': complete}
        missing += len(set(expected) - set(files)); unexpected += len(set(files) - set(expected))
    state_path = root / 'cache_seed/status.json'
    state = json.loads(state_path.read_text()) if state_path.is_file() else {'state': 'NOT_STARTED'}
    return {'state': state.get('state'), 'current_pair': state.get('current_pair'), 'pairs': rows,
            'missing': missing, 'unexpected': unexpected,
            'verification': 'PASS' if all(row['complete'] for row in rows.values()) else 'CACHE_PROVENANCE_OR_CONTENT_MISMATCH'}


def seed(root: Path, *, runner=subprocess.run) -> None:
    root = root.resolve(); package_manifest(root)
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).strip():
        raise MvePreflightError('worktree must be clean before manual seeding')
    existing = root / 'detector_cache'
    if existing.exists() and all(row['complete'] for row in status(root, verify=True)['pairs'].values()):
        print('DEVELOPMENT_DETECTOR_CACHE_ALREADY_VERIFIED'); return
    if existing.exists():
        raise MvePreflightError('existing development cache is incomplete; refusing overwrite')
    seed_root = root / 'cache_seed'; seed_root.mkdir(exist_ok=True)
    for ordinal, pair in enumerate(development.DEVELOPMENT_PAIRS, 1):
        attempt = seed_root / f'{pair}_attempt_001'
        attempt.mkdir(exist_ok=False); cache = attempt / 'detector_cache'; cache.mkdir()
        identity = pair_identity(root, pair)
        _write(seed_root / 'status.json', {'state': 'RUNNING', 'current_pair': pair, 'pair_index': ordinal})
        _write(attempt / 'seed_manifest.json', {'state': 'RUNNING', 'identity': identity})
        spec = seed_spec(pair, root, attempt, cache); _write(attempt / 'command.json', spec)
        env = {key: value for key, value in os.environ.items() if not key.startswith(('MIA_', 'MDMT_', 'PYTHON')) and key != 'DEVICE'}
        env.update(spec['environment'])
        with (attempt / 'author.log').open('xb') as log:
            result = runner(spec['argv'], cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        if result.returncode or set(_files(cache)) != set(identity['images']):
            _write(attempt / 'seed_manifest.json', {'state': 'FAILED', 'identity': identity})
            _write(seed_root / 'status.json', {'state': 'STOPPED', 'current_pair': pair, 'pair_index': ordinal})
            raise MvePreflightError('cache seed failed for pair ' + pair)
        for path in _files(cache).values():
            if path.is_symlink(): raise MvePreflightError('cache symlink forbidden')
            common.validate_npz(path)
        record = {'state': 'COMPLETE', 'identity': identity,
                  'cache_sha256': {name: _digest(path) for name, path in sorted(_files(cache).items())}}
        _write(cache / 'cache_manifest.json', record)
        for path in cache.iterdir(): path.chmod(0o444)
        target = root / 'detector_cache' / pair; target.parent.mkdir(exist_ok=True)
        cache.rename(target); target.chmod(0o555)
        _write(attempt / 'seed_manifest.json', record)
    _write(seed_root / 'status.json', {'state': 'COMPLETE', 'current_pair': None, 'pair_index': None})
