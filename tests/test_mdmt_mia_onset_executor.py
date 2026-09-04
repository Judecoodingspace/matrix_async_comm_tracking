from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
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
    with pytest.raises(MvePreflightError): executor.execute_and_accept(
        spec, qualification_status=_qualification_status(tmp_path), launch=True, runner=lambda *a,**k: Ok())
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


def _qualification_status(tmp_path: Path):
    records = []
    for spec in executor.qualification_plan(tmp_path / 'package'):
        records.append({
            'classification': 'INSTRUMENTATION_QUALIFICATION',
            'pair': spec.pair,
            'qualification': spec.name,
            'gate': spec.gate,
            'passed': True,
            'baseline_artifact_digest': ['fixture'],
            'qualification_artifact_digest': ['fixture'],
        })
    path = tmp_path / 'instrumentation_qualification.json'
    assert executor.write_qualification_status(path, records)['state'] == 'INSTRUMENTATION_QUALIFICATION_PASS'
    return path


def _write_qualification_surface(spec, payload: str, prefixes=()):
    first, second = executor.prediction_paths(spec)
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_text(payload); second.write_text(payload)
    for prefix in prefixes:
        (first.parent / f'{prefix}{spec.pair}-1.jsonl').write_text('fixture trace\n')


def test_y00_parity_pass_is_retained_by_accepted_state(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: {})
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{}'); return type('Ok', (), {'returncode': 0})()
    executor.execute_and_accept(spec, reference=_reference(tmp_path, '53', '{}'),
                                qualification_status=_qualification_status(tmp_path), launch=True, runner=runner)
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
        executor.execute_and_accept(spec, reference=_reference(tmp_path, '53', '{"reference":true}'),
                                    qualification_status=_qualification_status(tmp_path), launch=True, runner=runner)
    state=json.loads((spec.output_root/'attempt_state.json').read_text())
    assert state['state']=='INVALID' and state['y00_reference_parity_pass'] is False


def test_y00_missing_reference_prevents_accepted(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: pytest.fail('must not evaluate without reference'))
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{}'); return type('Ok', (), {'returncode': 0})()
    with pytest.raises(MvePreflightError, match='Y00_REFERENCE_ARTIFACT_MISSING'):
        executor.execute_and_accept(spec, qualification_status=_qualification_status(tmp_path), launch=True, runner=runner)
    assert json.loads((spec.output_root/'attempt_state.json').read_text())['state']=='INVALID'


def test_y00_missing_reference_view_prevents_accepted(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y00',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: pytest.fail('must not evaluate without both reference views'))
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{}'); return type('Ok', (), {'returncode': 0})()
    reference=executor.ReferenceArtifacts('53', 'reference_attempt_001', tmp_path/'missing-1.json', tmp_path/'missing-2.json')
    with pytest.raises(MvePreflightError, match='Y00_REFERENCE_ARTIFACT_MISSING'):
        executor.execute_and_accept(spec, reference=reference,
                                    qualification_status=_qualification_status(tmp_path), launch=True, runner=runner)
    assert json.loads((spec.output_root/'attempt_state.json').read_text())['state']=='INVALID'


def test_non_y00_does_not_require_reference_parity(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); spec=executor.resolve('53','Y10_d1',tmp_path/'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: {})
    def runner(*args, **kwargs): _complete_packetized_attempt(spec, '{}'); return type('Ok', (), {'returncode': 0})()
    executor.execute_and_accept(spec, qualification_status=_qualification_status(tmp_path), launch=True, runner=runner)
    state=json.loads((spec.output_root/'attempt_state.json').read_text())
    assert state['state']=='ACCEPTED' and 'y00_reference_parity_checked' not in state


def test_exact_eight_qualification_specs_are_isolated_from_scientific_matrix(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    scientific = executor.plan(tmp_path / 'out')
    qualifications = executor.qualification_plan(tmp_path / 'out')
    assert len(scientific) == 22
    assert len(qualifications) == 8
    assert [(q.pair, q.name) for q in qualifications] == [
        ('53', 'Y10_d5_logging_off'), ('53', 'Yec_d5_logging_off'),
        ('53', 'Y10_d5_shadow_off'), ('53', 'Yec_d5_repeat'),
        ('66', 'Y10_d5_logging_off'), ('66', 'Yec_d5_logging_off'),
        ('66', 'Y10_d5_shadow_off'), ('66', 'Yec_d5_repeat'),
    ]
    assert all(q.execution.output_root.parts[-3] == 'qualification' for q in qualifications)
    assert all(q.execution.output_root.is_absolute() for q in qualifications)
    assert all(q.name not in {spec.logical for spec in scientific} for q in qualifications)
    logger = next(q for q in qualifications if q.name == 'Y10_d5_logging_off')
    shadow = next(q for q in qualifications if q.name == 'Y10_d5_shadow_off')
    repeat = next(q for q in qualifications if q.name == 'Yec_d5_repeat')
    assert logger.execution.env['MIA_CASCADE_LOGGING'] == '0'
    assert shadow.execution.env['MIA_CASCADE_SHADOW'] == '0'
    assert repeat.execution.env['MIA_CASCADE_LOGGING'] == '1'
    assert repeat.execution.env['MIA_CASCADE_SHADOW'] == '1'
    standard = next(spec for spec in scientific if spec.pair == '53' and spec.logical == 'Y10_d5')
    assert standard.output_root.is_absolute()
    assert standard.output_root != logger.execution.output_root


def test_logger_and_shadow_qualification_parity_fail_closed(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    baseline = executor.resolve('53', 'Y10_d5', tmp_path / 'out')
    _write_qualification_surface(baseline, '{}', ('async_packet_trace_',))
    qualifications = executor.qualification_plan(tmp_path / 'out')
    for name in ('Y10_d5_logging_off', 'Y10_d5_shadow_off'):
        qualification = next(q for q in qualifications if q.pair == '53' and q.name == name)
        def equal_runner(*args, **kwargs):
            _write_qualification_surface(qualification.execution, '{}', qualification.state_trace_prefixes)
            return type('Ok', (), {'returncode': 0})()
        record = executor.execute_qualification(qualification, baseline, launch=True, runner=equal_runner)
        assert record['passed'] is True

    failed = next(q for q in qualifications if q.pair == '66' and q.name == 'Y10_d5_logging_off')
    baseline66 = executor.resolve('66', 'Y10_d5', tmp_path / 'out')
    _write_qualification_surface(baseline66, '{}', ('async_packet_trace_',))
    def mismatched_runner(*args, **kwargs):
        _write_qualification_surface(failed.execution, '{"different":true}', failed.state_trace_prefixes)
        return type('Ok', (), {'returncode': 0})()
    with pytest.raises(MvePreflightError, match='qualification prediction/state parity mismatch'):
        executor.execute_qualification(failed, baseline66, launch=True, runner=mismatched_runner)
    assert json.loads((failed.execution.output_root / 'qualification_state.json').read_text())['state'] == 'INVALID'


def test_repeat_failure_blocks_package_progression(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    baseline = executor.resolve('53', 'Yec_d5', tmp_path / 'out')
    repeat = next(q for q in executor.qualification_plan(tmp_path / 'out')
                  if q.pair == '53' and q.name == 'Yec_d5_repeat')
    _write_qualification_surface(baseline, '{}', repeat.state_trace_prefixes)
    def mismatched_runner(*args, **kwargs):
        _write_qualification_surface(repeat.execution, '{}', repeat.state_trace_prefixes)
        trace = executor.evidence_root(repeat.execution) / 'cascade_edge_trace_53-1.jsonl'
        trace.write_text('different trace\n')
        return type('Ok', (), {'returncode': 0})()
    with pytest.raises(MvePreflightError, match='qualification prediction/state parity mismatch'):
        executor.execute_qualification(repeat, baseline, launch=True, runner=mismatched_runner)
    failed_status = tmp_path / 'failed-qualification.json'
    assert executor.write_qualification_status(failed_status, [])['state'] == 'INSTRUMENTATION_QUALIFICATION_FAIL'
    blocked = executor.resolve('53', 'Y10_d1', tmp_path / 'out')
    with pytest.raises(MvePreflightError, match='INSTRUMENTATION_QUALIFICATION_REQUIRED'):
        executor.execute_and_accept(blocked, qualification_status=failed_status, launch=True,
                                    runner=lambda *args, **kwargs: pytest.fail('must not launch'))


def test_only_d5_qualification_baselines_may_start_before_package_pass(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    baseline = executor.resolve('53', 'Y10_d5', tmp_path / 'out')
    monkeypatch.setattr(executor, 'evaluate_private', lambda *args: {})
    def runner(*args, **kwargs):
        _complete_packetized_attempt(baseline, '{}')
        return type('Ok', (), {'returncode': 0})()
    executor.execute_and_accept(baseline, launch=True, runner=runner)
    assert json.loads((baseline.output_root / 'attempt_state.json').read_text())['state'] == 'ACCEPTED'


def test_package_status_is_the_gate_and_exposes_no_scientific_values(monkeypatch, tmp_path):
    _roots(monkeypatch, tmp_path)
    status = _qualification_status(tmp_path)
    executor.require_qualification_pass(status)
    payload = json.loads(status.read_text())
    rendered = json.dumps(payload).lower()
    assert 'private_metric' not in rendered and 'r_edge' not in rendered and 'c_comp' not in rendered
    payload['qualification_records'][0]['private_metric'] = 1.0
    invalid = tmp_path / 'invalid-qualification.json'
    invalid.write_text(json.dumps(payload))
    with pytest.raises(MvePreflightError, match='INSTRUMENTATION_QUALIFICATION_REQUIRED'):
        executor.require_qualification_pass(invalid)


def test_shell_author_write_path_matches_executor_lookup_after_cd(tmp_path):
    """A fake author confirms that the wrapper passes an absolute result root."""
    mia = tmp_path / 'mia'; source = tmp_path / 'source'; dataset = tmp_path / 'dataset'
    fake_python = mia / '.conda-env' / 'bin' / 'python'
    fake_python.parent.mkdir(parents=True)
    fake_python.write_text("""#!/usr/bin/env bash
set -euo pipefail
result=''; method=''
while [[ $# -gt 0 ]]; do
  case "$1" in
    --result_dir) result="$2"; shift 2 ;;
    --method) method="$2"; shift 2 ;;
    *) shift ;;
  esac
done
mkdir -p "$result/$method"
printf '{}' > "$result/$method/53-1.json"
printf '{}' > "$result/$method/53-2.json"
printf '%s' "$result" > "$FAKE_RESULT_CAPTURE"
""")
    fake_python.chmod(0o755)
    (mia / 'run_configs').mkdir(parents=True)
    (mia / 'run_configs' / 'one_carafe_bytetrack_full_mdmt_reproduction.py').write_text('fixture')
    (source / 'demo').mkdir(parents=True)
    for view in ('1', '2'):
        (dataset / 'train' / view / f'53-{view}').mkdir(parents=True)
        (dataset / 'new_xml' / view).mkdir(parents=True)
        (dataset / 'new_xml' / view / f'53-{view}.xml').write_text('<xml/>')
    checkpoint = dataset / 'checkpoints' / 'work_dirsfaster_rcnn_r50_fpn_carafe_1x_full_mdmt'
    checkpoint.mkdir(parents=True); (checkpoint / 'epoch_12.pth').write_text('fixture')
    capture = tmp_path / 'result-root.txt'
    env = {**os.environ, 'MIA_ROOT': str(mia), 'MIA_SOURCE_ROOT': str(source),
           'MDMT_ROOT': str(dataset), 'MIA_OUTPUT_ROOT': 'output', 'MIA_RUN_INPUT_ROOT': 'inputs',
           'FAKE_RESULT_CAPTURE': str(capture)}
    wrapper = Path(__file__).resolve().parents[1] / 'scripts' / 'run_mdmt_mia_author_sync.sh'
    subprocess.run(['bash', str(wrapper), 'mia', 'train', '53'], cwd=tmp_path, env=env, check=True)
    output_root = (tmp_path / 'output').resolve()
    spec = executor.ExecutionSpec('53', 'Y10_d5', 'Y10_d5', 5, 'PACKETIZED', source,
                                  output_root, tmp_path / 'g1', tmp_path / 'g2', (), {})
    expected = executor.prediction_paths(spec)
    assert Path(capture.read_text()) / 'mia_train_53' == expected[0].parent
    assert all(path.is_file() for path in expected)
    assert not (expected[0].parent / 'output').exists()
