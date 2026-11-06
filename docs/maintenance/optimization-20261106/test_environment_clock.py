import sys,datetime,pytest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));from production_relay_logic import claim
from environment_clock_logic import release_time,reserve
NOW=1793959800
PARENT={'created_at':datetime.datetime.fromtimestamp(NOW-600,datetime.timezone.utc).isoformat()}
ENV={'protection_rules':[{'type':'wait_timer','wait_timer':10}]}
def test_release_requires_native_wait_and_full_interval():
 assert release_time(ENV,PARENT,NOW)==NOW
 assert release_time(ENV,PARENT,NOW+70)==NOW+70
 with pytest.raises(ValueError,match='early'):release_time(ENV,PARENT,NOW-1)
@pytest.mark.parametrize('value',[{}, {'protection_rules':[]},{'protection_rules':[{'type':'wait_timer','wait_timer':0}]},{'protection_rules':[{'type':'wait_timer','wait_timer':5}]}])
def test_removed_or_reduced_timer_cannot_start_a_run_storm(value):
 with pytest.raises(ValueError):release_time(value,PARENT,NOW)
def test_bad_parent_timestamp_rejected():
 with pytest.raises(ValueError):release_time(ENV,{'created_at':'2026-11-06T00:00:00'},NOW)
def test_claim_rebases_only_unaccepted_local_metadata_on_admin_race(tmp_path,monkeypatch):
 import subprocess,json
 monkeypatch.chdir(tmp_path);calls=[];state={'head':'base','push':0}
 def git(*args):
  calls.append(args)
  if args==('rev-parse','HEAD'):return state['head']
  if args[0]=='commit':state['head']='claim'+str(state['push'])
  if args[0]=='push':
   state['push']+=1
   if state['push']==1:raise subprocess.CalledProcessError(1,args)
  if args[0]=='ls-remote':return 'admin-new-head\trefs/heads/shadow-state'
  if args[0]=='reset':state['head']='admin-new-head';Path('relay-cursor.json').unlink(missing_ok=True)
  return ''
 assert reserve(git,claim,'123',0,'123',NOW)
 assert ('fetch','origin','shadow-state') in calls
 assert not any('--force' in c for c in calls)
 assert state['push']==2
