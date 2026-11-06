import hashlib,json,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from openfeed.storage import Store
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ops'))
from cloud_plan import plan
NOW=datetime(2026,11,6,9,30,tzinfo=timezone.utc)
@pytest.fixture
def state(tmp_path):
 s=Store(str(tmp_path/'openfeed.sqlite3'));a=s.create({'title':'A','source_url':'https://example.org/','recipe':{}});b=s.create({'title':'Browser','source_url':'https://other.example/','recipe':{'fetch_mode':'browser'}})
 s.db.execute('update feeds set next_run=?',((NOW+timedelta(hours=2)).isoformat(),));s.close()
 (tmp_path/'runtime-control.json').write_text(json.dumps({'mode':'production','publish_enabled':True,'mac_writer_stopped':True,'final_mac_snapshot_sha256':'a'*64}))
 (tmp_path/'publication-state.json').write_text(json.dumps({'slot':'2026-11-06T17','result':'complete'}))
 reseal(tmp_path);return tmp_path,a['id'],b['id']
def reseal(state):
 (state/'checkpoint.json').write_text(json.dumps({'database_sha256':hashlib.sha256((state/'openfeed.sqlite3').read_bytes()).hexdigest()}))
def update(state,sql,args=()):
 import sqlite3
 c=sqlite3.connect(state/'openfeed.sqlite3');c.execute(sql,args);c.commit();c.close();reseal(state)
def test_idle_preflight_is_readonly_and_does_not_need_dependencies(state):
 p,a,b=state;before={x.name:x.read_bytes() for x in p.iterdir()};r=plan(p,NOW);assert not r['work_needed'];assert {x.name:x.read_bytes() for x in p.iterdir()}==before
 assert r['reason']=='idle'
def test_http_only_due_skips_browser_but_near_due_browser_is_prepared(state):
 p,a,b=state;update(p,'update feeds set next_run=? where id=?',(NOW.isoformat(),a));r=plan(p,NOW);assert r['work_needed'] and r['due_count']==1 and not r['browser_needed']
 update(p,'update feeds set next_run=? where id=?',((NOW+timedelta(minutes=8)).isoformat(),b));assert plan(p,NOW)['browser_needed']
def test_browser_due_and_native_feed_do_not_mix_modes(state):
 p,a,b=state;update(p,'update feeds set next_run=? where id=?',(NOW.isoformat(),b));assert plan(p,NOW)['browser_needed']
 update(p,"update feeds set kind='native' where id=?",(b,));assert not plan(p,NOW)['browser_needed']
def test_publication_only_and_pending_retry_respect_window(state):
 p,a,b=state;(p/'publication-state.json').unlink();r=plan(p,NOW);assert r['publication_due'] and r['reason']=='publication_only' and not r['browser_needed']
 (p/'publication-state.json').write_text(json.dumps({'slot':'2026-11-06T17','result':'attempt_reserved'}));assert plan(p,NOW)['publication_due']
 assert not plan(p,datetime(2026,11,6,14,1,tzinfo=timezone.utc))['publication_due']
def test_persisted_recovery_is_not_missed(state):
 p,a,b=state;update(p,'insert into recoveries values (?,?,?,?,?)',(a,1,1,(NOW-timedelta(minutes=1)).isoformat(),(NOW+timedelta(minutes=5)).isoformat()));assert plan(p,NOW)['due_count']==1
 update(p,'update recoveries set expires_at=?',((NOW-timedelta(seconds=1)).isoformat(),));assert plan(p,NOW)['due_count']==0
def test_disabled_source_ignored_and_checkpoint_tampering_fails(state):
 p,a,b=state;update(p,'update feeds set enabled=0,next_run=?',(NOW.isoformat(),));assert plan(p,NOW)['due_count']==0
 (p/'openfeed.sqlite3').write_bytes(b'bad')
 with pytest.raises(ValueError,match='hash mismatch'):plan(p,NOW)
def test_no_production_or_target_permission_is_inferred(state):
 p,a,b=state;control=p/'runtime-control.json';d=json.loads(control.read_text());d['mac_writer_stopped']=False;control.write_text(json.dumps(d))
 with pytest.raises(ValueError,match='stopped Mac'):plan(p,NOW)
 d.update(mode='shadow',shadow_until=(NOW-timedelta(seconds=1)).isoformat());control.write_text(json.dumps(d));assert not plan(p,NOW)['work_needed']
 d['shadow_until']=(NOW+timedelta(hours=1)).isoformat();control.write_text(json.dumps(d))
 with pytest.raises(ValueError,match='Unknown'):plan(p,NOW,targets=['unknown'])
