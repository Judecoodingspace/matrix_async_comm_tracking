"""Synthetic-only integration and the unchanged E023 cache hook fixtures."""
import ast
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tracking import mdmt_mia_onset_cache_seed as cache
from tracking import mdmt_mia_onset_executor as executor
from tracking.mdmt_mia_onset_mve import MvePreflightError


@pytest.fixture
def setup(monkeypatch, tmp_path):
    data, gt, variant = (tmp_path / n for n in ('data', 'gt', 'variant'))
    for pair in ('53', '66'):
        for view in ('1', '2'):
            folder = data / 'train' / view / (pair + '-' + view)
            folder.mkdir(parents=True)
            for name in ('00000201.jpg', '00000202.jpg'):
                (folder / name).write_bytes(b'synthetic-image-input')
            gt.mkdir(exist_ok=True)
            (gt / (pair + '-' + view + '.txt')).write_text('unused')
    (variant / 'demo').mkdir(parents=True)
    (variant / 'demo/supplement_MIA.py').write_text('frozen fixture entry')
    hook, checkpoint, config, wrapper = (tmp_path / n for n in ('hook', 'checkpoint', 'config.py', 'wrapper'))
    for path in (hook, checkpoint, config, wrapper):
        path.write_text('# fixture')
    monkeypatch.setattr(executor, 'DATASET', data)
    monkeypatch.setattr(executor, 'SOURCE_GT', gt)
    monkeypatch.setattr(executor, 'VARIANT', variant)
    monkeypatch.setattr(executor, 'REFERENCE_VARIANT', variant)
    monkeypatch.setattr(executor, 'AUTHOR_WRAPPER', wrapper)
    for name, value in [('HOOK', hook), ('CHECKPOINT', checkpoint), ('CONFIG', config)]:
        monkeypatch.setattr(cache, name, value)
    monkeypatch.setattr(cache, 'validate_package', lambda root: None)
    def output(argv, **kwargs):
        return '' if 'status' in argv else 'fixture-commit\n'
    monkeypatch.setattr(cache.subprocess, 'check_output', output)
    root = tmp_path / 'package'
    root.mkdir()
    (root / 'MVE_EXECUTION_PACKAGE_MANIFEST.json').write_text('{}')
    return root


def write_entries(root, pair):
    for name in cache.image_population(pair):
        np.savez_compressed(root / name, class_count=np.array([3], dtype=np.int32),
                            **{'class_%d' % i: np.zeros((0, 5), dtype=np.float32) for i in range(3)})


def good_runner(argv, **kwargs):
    assert argv[-2] == 'train'
    assert kwargs['env']['MIA_DETECTION_CACHE_MODE'] == 'write'
    assert kwargs['env']['MIA_CASCADE_EDGE_CUT'] == '0'
    assert kwargs['env']['MIA_CASCADE_SHADOW'] == '0'
    assert json.loads(kwargs['env']['MIA_ASYNC_CHANNEL_DELAYS']) == {
        'local': 0, 'homography': 0, 'id_state': 0, 'supplement': 0}
    write_entries(Path(kwargs['env']['MIA_DETECTION_CACHE_ROOT']), argv[-1])
    return SimpleNamespace(returncode=0)


def test_population_matches_resolved_path_key_and_includes_first_frame(setup):
    rows = cache.image_population('53')
    assert len(rows) == 4
    assert all(hashlib.sha256(str(p.resolve()).encode()).hexdigest() + '.npz' == key
               for key, p in rows.items())
    assert any(p.name == '00000201.jpg' for p in rows.values())
    with pytest.raises(MvePreflightError):
        cache.image_population('22')
    image = executor.DATASET / 'train/2/53-2/00000201.jpg'
    image.unlink()
    with pytest.raises(MvePreflightError, match='population mismatch'):
        cache.image_population('53')


def test_seed_preserves_scientific_and_reference_paths(setup):
    spec = cache.seed_spec('53', setup, setup / 'seed/attempt_001', setup / 'staging')
    assert spec['condition'] == 'detector_cache_seed'
    assert spec['classification'] == 'PRE_LAUNCH_ENGINEERING_PREPARATION'
    assert all(Path(spec['environment'][k]).is_absolute() for k in
               ('MIA_OUTPUT_ROOT', 'MIA_RUN_INPUT_ROOT', 'MIA_DETECTION_CACHE_ROOT'))
    assert len(executor.plan(setup)) == 22
    assert len(executor.qualification_plan(setup)) == 8
    for item in executor.plan(setup) + [q.execution for q in executor.qualification_plan(setup)]:
        assert item.env['MIA_DETECTION_CACHE_MODE'] == 'read'
        assert item.env['MIA_DETECTION_CACHE_ROOT'] == str(setup / 'detector_cache')
    reference = executor.resolve('53', 'Y00', setup, role='REFERENCE')
    assert not any(k.startswith('MIA_DETECTION_CACHE') for k in reference.env)


def test_both_pairs_publish_atomically_and_verify_without_acceptance(setup, monkeypatch):
    monkeypatch.setenv('MIA_CONFIG', '/wrong/config')
    monkeypatch.setenv('MIA_DETECTION_CACHE_MODE', 'auto')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *a: pytest.fail('no evaluator'))
    monkeypatch.setattr(executor, 'execute_and_accept', lambda *a: pytest.fail('no acceptance'))
    calls = []
    def runner(argv, **kwargs):
        assert 'MIA_CONFIG' not in kwargs['env']
        assert not (setup / 'detector_cache').exists()
        calls.append(argv[-1])
        return good_runner(argv, **kwargs)
    cache.seed(setup, runner=runner)
    result = cache.status(setup, verify=True)
    assert calls == ['53', '66']
    assert result['missing'] == result['unexpected'] == 0
    assert all(row['complete'] for row in result['pairs'].values())
    manifest = json.loads((setup / 'detector_cache/cache_manifest.json').read_text())
    assert manifest['identity']['split'] == 'train'
    assert len(manifest['cache_sha256']) == 8
    assert not list(setup.rglob('attempt_state.json'))
    assert not list(setup.rglob('qualification_state.json'))
    cache.seed(setup, runner=lambda *a, **k: pytest.fail('must reuse verified immutable cache'))


@pytest.mark.parametrize('failure', ['incomplete', 'foreign', 'process'])
def test_failed_seed_never_publishes_and_clean_retry_preserves_attempt(setup, failure):
    def runner(argv, **kwargs):
        result = good_runner(argv, **kwargs)
        root = Path(kwargs['env']['MIA_DETECTION_CACHE_ROOT'])
        if argv[-1] == '66':
            if failure == 'incomplete':
                (root / next(iter(cache.image_population('66')))).unlink()
            elif failure == 'foreign':
                (root / 'historical-test.npz').write_bytes(b'foreign')
            else:
                result.returncode = 1
        return result
    with pytest.raises(MvePreflightError):
        cache.seed(setup, runner=runner)
    assert not (setup / 'detector_cache').exists()
    first = setup / 'cache_seed/attempt_001/seed_manifest.json'
    original = first.read_bytes()
    assert json.loads(original)['state'] == 'FAILED'
    cache.seed(setup, runner=good_runner)
    assert first.read_bytes() == original
    assert cache.status(setup, verify=True)['verification'] == 'PASS'


def test_changed_input_or_cache_cannot_verify(setup):
    cache.seed(setup, runner=good_runner)
    image = next(iter(cache.image_population('53').values()))
    original = image.read_bytes()
    image.write_bytes(b'changed')
    assert not cache.status(setup, verify=True)['pairs']['53']['complete']
    image.write_bytes(original)
    entry = next(iter(cache.cache_files(setup / 'detector_cache').values()))
    entry.chmod(0o644)
    np.savez_compressed(entry, class_count=np.array([3], dtype=np.int32),
                        **{'class_%d' % i: np.ones((1, 5), dtype=np.float32) for i in range(3)})
    assert not cache.status(setup, verify=True)['pairs']['53']['complete']


def test_unbound_cache_blocks_no_live_fallback(setup):
    (setup / 'detector_cache').mkdir()
    with pytest.raises(MvePreflightError, match='refusing overwrite'):
        cache.seed(setup, runner=lambda *a, **k: pytest.fail('must not launch'))


def test_frozen_e023_hook_write_read_roundtrip_and_missing_fails(monkeypatch, tmp_path):
    # Extract ONLY these two source functions; no torch/model/tracker import.
    source = executor.AUTHOR_ROOT / 'variants/packetized_candidate_compensation_onset_mve_v1/mmtrack/models/mot/byte_track.py'
    assert cache.sha256(source) == cache.HOOK_SHA256
    nodes = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef)
             and n.name in ('_mdmt_cache_filename', '_load_or_compute_mdmt_detections')]
    namespace = dict(os=os, Path=Path, hashlib=hashlib, np=np)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
    function = namespace['_load_or_compute_mdmt_detections']
    image = tmp_path / 'image.jpg'
    image.write_bytes(b'fixture')
    meta = [{'filename': str(image)}]
    detector = SimpleNamespace(simple_test=lambda *a, **k: [[np.zeros((0, 5)) for _ in range(3)]])
    monkeypatch.setenv('MIA_DETECTION_CACHE_ROOT', str(tmp_path / 'cache'))
    monkeypatch.setenv('MIA_DETECTION_CACHE_MODE', 'write')
    original = function(detector, None, meta, True)
    detector.simple_test = lambda *a, **k: pytest.fail('live inference in read mode')
    monkeypatch.setenv('MIA_DETECTION_CACHE_MODE', 'read')
    loaded = function(detector, None, meta, True)
    assert all(np.array_equal(a, b) for a, b in zip(original, loaded))
    for p in (tmp_path / 'cache').glob('*.npz'):
        cache.validate_npz(p)
        p.unlink()
    with pytest.raises(FileNotFoundError):
        function(detector, None, meta, True)
