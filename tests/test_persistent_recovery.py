from datetime import datetime,timezone,timedelta
import pytest
from openfeed.storage import Store
ERR='Upstream connection failed: timeout (TimeoutError)'

def feed(s):return s.create({'title':'A','source_url':'https://example.com/a','recipe':{},'interval_minutes':720})

def test_recovery_survives_restart_is_bounded_and_preserves_phase(tmp_path):
 p=str(tmp_path/'db');s=Store(p);f=feed(s);s.finish(f,[{'title':'Old','url':'https://example.com/old'}],None,1);f=s.get(f['id']);phase=f['schedule_phase_seconds'];old=s.entries(f['id'])
 s.finish(f,[],ERR,1);job=s.recoveries()[0];normal=s.get(f['id'])['next_run'];s.close();s=Store(p)
 assert s.recoveries()[0]==job and s.entries(f['id'])==old
 s.db.execute('update recoveries set not_before=?',(datetime.now(timezone.utc).isoformat(),))
 assert s.due()[0]['id']==f['id'] and s.get(f['id'])['next_run']==normal
 s.finish(s.get(f['id']),[],ERR,1);assert s.recoveries()[0]['failures']==2
 s.finish(s.get(f['id']),[],ERR,1);assert s.recoveries()==[]
 assert s.get(f['id'])['schedule_phase_seconds']==phase;s.close()

@pytest.mark.parametrize('error',['Upstream HTTP 403','Upstream HTTP 429','Quality gate: extracted 0','Upstream connection failed: tls_certificate'])
def test_permanent_or_policy_failure_never_schedules_recovery(tmp_path,error):
 s=Store(str(tmp_path/'db'));f=feed(s);s.finish(f,[],error,1);assert not s.recoveries();s.close()

def test_post_and_changed_recipe_never_replay_old_recovery(tmp_path):
 s=Store(str(tmp_path/'db'));f=feed(s);s.finish(f,[],ERR,1);assert s.recoveries()
 s.update(f['id'],{'recipe':{'request_method':'POST'}});assert not s.recoveries()
 s.finish(s.get(f['id']),[],ERR,1);assert not s.recoveries();s.close()

def test_success_clears_recovery_and_cooldown_delays_it(tmp_path):
 s=Store(str(tmp_path/'db'));f=feed(s);s.finish(f,[],ERR,1);s.defer(f['id'],7200)
 assert s.recoveries()[0]['not_before']>=s.get(f['id'])['next_run']
 s.finish(s.get(f['id']),[{'title':'A','url':'https://example.com/a'}],None,1);assert not s.recoveries();s.close()
