from __future__ import annotations

import json
from pathlib import Path

import pytest

from tracking.mdmt_mia_onset_mve import MvePreflightError
from tracking import mdmt_mia_onset_development_executor as development
from tracking import mdmt_mia_onset_development_cache_seed as development_cache


def _roots(monkeypatch, tmp_path: Path):
    data, gt, variant, reference = (tmp_path / name for name in ('data', 'gt', 'variant', 'reference'))
    for pair in development.DEVELOPMENT_PAIRS:
        for view in ('1', '2'):
            (data / 'train' / view / f'{pair}-{view}').mkdir(parents=True)
            gt.mkdir(exist_ok=True); (gt / f'{pair}-{view}.txt').write_text('fixture\n')
    for source in (variant, reference):
        (source / 'demo').mkdir(parents=True); (source / 'demo' / 'supplement_MIA.py').write_text('entry\n')
    monkeypatch.setattr(development.inherited, 'DATASET', data)
    monkeypatch.setattr(development.inherited, 'SOURCE_GT', gt)
    monkeypatch.setattr(development.inherited, 'VARIANT', variant)
    monkeypatch.setattr(development.inherited, 'REFERENCE_VARIANT', reference)


def test_frozen_255_matrix_and_y01_singleton(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    specs = development.plan(tmp_path / 'package')
    assert len(specs) == 255
    assert [spec.pair for spec in specs[::17]] == list(development.DEVELOPMENT_PAIRS)
    assert all(sum(spec.pair == pair and spec.logical == 'Y00' for spec in specs) == 1 for pair in development.DEVELOPMENT_PAIRS)
    assert all(sum(spec.pair == pair and spec.logical == 'Y01' and spec.physical == 'Y01_d1' for spec in specs) == 1 for pair in development.DEVELOPMENT_PAIRS)
    assert not any(spec.physical in ('Y01_d2', 'Y01_d3', 'Y01_d4', 'Y01_d5') for spec in specs)
    assert all(sum(spec.pair == pair and spec.logical.startswith(f'Y{kind}_') for spec in specs) == 5
               for pair in development.DEVELOPMENT_PAIRS for kind in ('10', '11', 'ec'))


def test_roles_cache_paths_and_delays_are_frozen(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    root = tmp_path / 'package'
    y11 = development.resolve('53', 'Y11_d2', root)
    assert json.loads(y11.env['MIA_ASYNC_CHANNEL_DELAYS']) == {'local': 0, 'homography': 0, 'id_state': 2, 'supplement': 2}
    assert y11.env['MIA_DETECTION_CACHE_ROOT'] == str(root.resolve() / 'detector_cache' / '53')
    reference = development.resolve('53', 'Y00', root, role='REFERENCE')
    assert reference.env['MIA_IMPORT_VARIANT_MMTRACK'] == '0'
    assert not any(key.startswith('MIA_DETECTION_CACHE') or key.startswith('MIA_ASYNC') for key in reference.env)
    assert len(development.reference_plan(root)) == 15


def test_progress_is_outcome_embargoed(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    root = tmp_path / 'package'
    first = development.plan(root)[0]
    first.output_root.mkdir(parents=True)
    (first.output_root / 'attempt_state.json').write_text(json.dumps({'state': 'ACCEPTED', 'private_metric': 99.0}))
    progress = development.public_progress(root)
    assert progress['scientific_accepted'] == 1 and progress['scientific_expected'] == 255
    assert progress['embargo'] == 'ACTIVE'
    assert 'private_metric' not in json.dumps(progress)


def test_development_y00_fails_closed_and_non_y00_skips_parity(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    root = tmp_path / 'package'; y00 = development.resolve('53', 'Y00', root)
    monkeypatch.setattr(development.inherited, 'evaluate_private', lambda *args: {})
    def complete(spec, payload):
        paths = development.inherited.prediction_paths(spec); paths[0].parent.mkdir(parents=True)
        paths[0].write_text(payload); paths[1].write_text(payload)
        values = {}
        for stem, field in development.inherited.GATE_ARTIFACTS.values():
            values.setdefault(stem, {})[field] = 1 if field == 'logger_read_only' else 0
            if field == 'packet_emission_count': values[stem]['packet_consumption_count'] = 0
        for stem, row in values.items(): (paths[0].parent / f'{stem}_fixture.json').write_text(json.dumps(row))
        (paths[0].parent / 'async_packet_trace_fixture.jsonl').write_text('')
    def runner(*args, **kwargs): complete(y00, '{}'); return type('Ok', (), {'returncode': 0})()
    with pytest.raises(MvePreflightError, match='Y00_REFERENCE_ARTIFACT_MISSING'):
        development.execute_and_accept(y00, launch=True, runner=runner)
    assert json.loads((y00.output_root / 'attempt_state.json').read_text())['state'] == 'INVALID'
    y10 = development.resolve('53', 'Y10_d2', root)
    def runner2(*args, **kwargs): complete(y10, '{}'); return type('Ok', (), {'returncode': 0})()
    development.execute_and_accept(y10, launch=True, runner=runner2)
    assert json.loads((y10.output_root / 'attempt_state.json').read_text())['state'] == 'ACCEPTED'


def test_pair_specific_cache_seed_spec_preserves_y00_scientific_semantics(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    first = development.inherited.DATASET / 'train' / '1' / '53-1'
    second = development.inherited.DATASET / 'train' / '2' / '53-2'
    for directory in (first, second):
        (directory / '00000001.jpg').write_bytes(b'fixture')
    rows = development_cache.image_population('53')
    assert len(rows) == 2
    spec = development_cache.seed_spec('53', tmp_path / 'package', tmp_path / 'seed', tmp_path / 'cache')
    assert spec['environment']['MIA_DETECTION_CACHE_MODE'] == 'write'
    assert spec['environment']['MIA_ASYNC_CHANNEL_DELAYS'] == '{"homography": 0, "id_state": 0, "local": 0, "supplement": 0}'
    with pytest.raises(MvePreflightError): development_cache.image_population('22')
