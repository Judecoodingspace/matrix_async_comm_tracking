from __future__ import annotations
import json
from pathlib import Path
import pytest
import tracking.mdmt_mia_onset_executor as executor
from tracking.mdmt_mia_onset_mve import MvePreflightError

def _roots(monkeypatch, tmp_path: Path):
    data=tmp_path/'data'; gt=tmp_path/'gt'; variant=tmp_path/'variant'
    for pair in ('53','66'):
        for view in ('1','2'):
            (data/'train'/view/f'{pair}-{view}').mkdir(parents=True)
            gt.mkdir(exist_ok=True); (gt/f'{pair}-{view}.txt').write_text('fixture\n')
    (variant/'demo').mkdir(parents=True); (variant/'demo'/'supplement_MIA.py').write_text('entry\n')
    monkeypatch.setattr(executor,'DATASET',data); monkeypatch.setattr(executor,'SOURCE_GT',gt); monkeypatch.setattr(executor,'VARIANT',variant)

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

def test_gate_violation_is_not_accepted(monkeypatch,tmp_path):
    _roots(monkeypatch,tmp_path); a,b=tmp_path/'a',tmp_path/'b'; a.write_text('{}'); b.write_text('{}')
    for stem,field in executor.GATE_ARTIFACTS.values(): (tmp_path/f'{stem}.json').write_text(json.dumps({field:0}))
    # Missing semantic fields are rejected; no boolean schema can promote it.
    with pytest.raises(MvePreflightError): executor.accept_attempt((a,b),tmp_path)
