from __future__ import annotations
import json
from pathlib import Path
import pytest
import tracking.mdmt_mia_onset_executor as executor
from tracking.mdmt_mia_onset_mve import MvePreflightError

def _roots(monkeypatch, tmp_path: Path):
    data=tmp_path/'data'; gt=tmp_path/'gt'; variant=tmp_path/'variant'; reference=tmp_path/'reference'
    for pair in ('53','66'):
        for view in ('1','2'):
            (data/'train'/view/f'{pair}-{view}').mkdir(parents=True)
            gt.mkdir(exist_ok=True); (gt/f'{pair}-{view}.txt').write_text('fixture\n')
    (variant/'demo').mkdir(parents=True); (variant/'demo'/'supplement_MIA.py').write_text('entry\n')
    (reference/'demo').mkdir(parents=True); (reference/'demo'/'supplement_MIA.py').write_text('legacy entry\n')
    monkeypatch.setattr(executor,'DATASET',data); monkeypatch.setattr(executor,'SOURCE_GT',gt); monkeypatch.setattr(executor,'VARIANT',variant); monkeypatch.setattr(executor,'REFERENCE_VARIANT',reference)

def test_22_real_dry_run_specs_are_train_only(monkeypatch, tmp_path):
    _roots(monkeypatch,tmp_path); specs=executor.plan(tmp_path/'out')
    assert len(specs)==22 and len({(s.pair,s.logical) for s in specs})==22
    y01=[s for s in specs if s.logical=='Y01']; assert [s.physical for s in y01]==['Y01_d1','Y01_d1']
    target=next(s for s in specs if s.pair=='53' and s.logical=='Y10_d3')
    assert target.argv[-2:]==('train','53') and target.env['MIA_ASYNC_CHANNEL_DELAYS']=='{"homography": 0, "id_state": 3, "local": 0, "supplement": 0}'

def test_launch_and_acceptance_fail_closed(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    with pytest.raises(MvePreflightError): executor.run(spec)
    with pytest.raises(MvePreflightError): executor.accept_attempt((tmp_path/'a',tmp_path/'b'),tmp_path)
    with pytest.raises(MvePreflightError): executor.verify_y00_parity((tmp_path/'a',tmp_path/'b'),(tmp_path/'a',tmp_path/'missing'))
    (tmp_path/'a').write_text('{}'); (tmp_path/'b').write_text('{}')
    with pytest.raises(MvePreflightError): executor.accept_attempt((tmp_path/'a',tmp_path/'b'),tmp_path)


def test_reference_role_uses_distinct_legacy_variant_without_packet_env(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path)
    reference=executor.resolve('53','Y00',tmp_path/'out',role='REFERENCE')
    y00=executor.resolve('53','Y00',tmp_path/'out')
    assert reference.variant != y00.variant
    assert reference.argv != () and y00.argv != () and reference.env['MIA_SOURCE_ROOT'] != y00.env['MIA_SOURCE_ROOT']
    assert 'MIA_ACTIVE_PACKET_STAGES' not in reference.env
    assert 'MIA_ASYNC_CHANNEL_DELAYS' not in reference.env
    assert y00.env['MIA_ASYNC_CHANNEL_DELAYS'] == '{"homography": 0, "id_state": 0, "local": 0, "supplement": 0}'
    with pytest.raises(MvePreflightError): executor.resolve('53','Y10_d1',tmp_path/'out',role='REFERENCE')

def test_gate_violation_is_not_accepted(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); a,b=tmp_path/'a',tmp_path/'b'; a.write_text('{}'); b.write_text('{}')
    for stem,field in executor.GATE_ARTIFACTS.values(): (tmp_path/f'{stem}.json').write_text(json.dumps({field:0}))
    # Missing semantic fields are rejected; no boolean schema can promote it.
    with pytest.raises(MvePreflightError): executor.accept_attempt((a,b),tmp_path)

def test_real_state_machine_rejects_process_success_without_artifacts(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    class Ok: returncode=0
    with pytest.raises(MvePreflightError): executor.execute_and_accept(spec,launch=True,runner=lambda *a,**k: Ok())
    assert json.loads((spec.output_root/'attempt_state.json').read_text())['state']=='INVALID'


def _complete_packetized_attempt(spec, payload: str):
    prediction1, prediction2 = executor.prediction_paths(spec)
    prediction1.parent.mkdir(parents=True)
    prediction1.write_text(payload); prediction2.write_text(payload)
    evidence = {}
    for stem, field in executor.GATE_ARTIFACTS.values():
        value = 1 if field == 'logger_read_only' else 0
        evidence.setdefault(stem, {})[field] = value
        if field == 'packet_emission_count': evidence[stem]['packet_consumption_count'] = 0
    for stem, fields in evidence.items():
        (prediction1.parent / f'{stem}_fixture.json').write_text(json.dumps(fields))
    (prediction1.parent / 'async_packet_trace_fixture.jsonl').write_text('')


def _reference(tmp_path: Path, pair: str, payload: str, attempt: str = 'reference_attempt_001'):
    view1, view2 = tmp_path / 'reference-1.json', tmp_path / 'reference-2.json'
    view1.write_text(payload); view2.write_text(payload)
    return executor.ReferenceArtifacts(pair, attempt, view1, view2)


def test_y00_parity_pass_is_retained_by_accepted_state(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: {})
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{}'); return type('Ok', (), {'returncode': 0})()
    executor.execute_and_accept(spec, reference=_reference(tmp_path, '53', '{}'), launch=True, runner=runner)
    state=json.loads((spec.output_root/'attempt_state.json').read_text())
    assert state['state']=='ACCEPTED'
    assert state['y00_reference_parity_checked'] is True
    assert state['y00_reference_parity_pass'] is True
    assert state['y00_reference_attempt_identity']=='reference_attempt_001'


def test_y00_parity_failure_prevents_accepted(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: pytest.fail('must not evaluate after parity failure'))
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{"packetized":true}'); return type('Ok', (), {'returncode': 0})()
    with pytest.raises(MvePreflightError, match='y00 prediction parity mismatch'):
        executor.execute_and_accept(spec, reference=_reference(tmp_path, '53', '{"reference":true}'), launch=True, runner=runner)
    state=json.loads((spec.output_root/'attempt_state.json').read_text())
    assert state['state']=='INVALID' and state['y00_reference_parity_pass'] is False


def test_y00_missing_reference_prevents_accepted(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: pytest.fail('must not evaluate without reference'))
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{}'); return type('Ok', (), {'returncode': 0})()
    with pytest.raises(MvePreflightError, match='Y00_REFERENCE_ARTIFACT_MISSING'):
        executor.execute_and_accept(spec, launch=True, runner=runner)
    assert json.loads((spec.output_root/'attempt_state.json').read_text())['state']=='INVALID'


def test_y00_missing_reference_view_prevents_accepted(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: pytest.fail('must not evaluate without both reference views'))
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{}'); return type('Ok', (), {'returncode': 0})()
    reference=executor.ReferenceArtifacts('53', 'reference_attempt_001', tmp_path/'missing-1.json', tmp_path/'missing-2.json')
    with pytest.raises(MvePreflightError, match='Y00_REFERENCE_ARTIFACT_MISSING'):
        executor.execute_and_accept(spec, reference=reference, launch=True, runner=runner)
    assert json.loads((spec.output_root/'attempt_state.json').read_text())['state']=='INVALID'


def test_non_y00_does_not_require_reference_parity(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y10_d1',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: {})
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{}'); return type('Ok', (), {'returncode': 0})()
    executor.execute_and_accept(spec, launch=True, runner=runner)
    state=json.loads((spec.output_root/'attempt_state.json').read_text())
    assert state['state']=='ACCEPTED' and 'y00_reference_parity_checked' not in state
