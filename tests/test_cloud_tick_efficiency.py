import hashlib,json,shutil,sqlite3,subprocess,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import pytest
from openfeed.storage import Store
from openfeed.scheduling import publication_slot
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ops'))
import cloud_tick as tick

def git(path,*args):return subprocess.run(['git','-C',str(path),*args],check=True,capture_output=True,text=True).stdout.strip()
@pytest.fixture
def setup(tmp_path,monkeypatch):
 state=tmp_path/'private-state';state.mkdir();git(state,'init','--initial-branch=shadow-state');git(state,'config','user.name','Test');git(state,'config','user.email','test@example.com')
 origin=tmp_path/'origin.git';subprocess.run(['git','init','--bare',str(origin)],check=True,capture_output=True);git(state,'remote','add','origin',str(origin))
 s=Store(str(state/'openfeed.sqlite3'));f=s.create({'title':'A','source_url':'https://example.org/','recipe':{}});s.finish(f,[{'title':'Old','url':'https://example.org/old'}],None,1);s.db.execute('update feeds set next_run=?',((datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),));s.close()
 (state/'checkpoint.json').write_text(json.dumps({'database_sha256':hashlib.sha256((state/'openfeed.sqlite3').read_bytes()).hexdigest()}));(state/'runtime-control.json').write_text(json.dumps({'mode':'production','publish_enabled':False,'mac_writer_stopped':True,'final_mac_snapshot_sha256':'a'*64}));(state/'coverage.json').write_text(json.dumps({'sources':{f['id']:{'status':'not_tested'}}}));git(state,'add','.');git(state,'commit','-m','Initial');git(state,'push','origin','HEAD:shadow-state');monkeypatch.setattr(tick,'ROOT',tmp_path);calls=[]
 def run(*args,cwd=None):
  calls.append(args)
  if args[0]=='sudo':return ''
  if args[0]=='docker':
   if 'run' in args:
    cycle=tmp_path/'cloud-io/cycle';cycle.mkdir();input=tmp_path/'cloud-io/input.sqlite3';shutil.copyfile(input,cycle/'shadow.sqlite3');s=Store(str(cycle/'shadow.sqlite3'));feed=s.get(f['id']);result=s.finish(feed,[{'title':'New','url':'https://example.org/new'}],None,1);s.close();(cycle/'report.json').write_text(json.dumps({'shadow_only':True,'input_db_unchanged':True,'input_sha256':hashlib.sha256(input.read_bytes()).hexdigest(),'shadow_sha256':hashlib.sha256((cycle/'shadow.sqlite3').read_bytes()).hexdigest(),'results':[{'id':f['id'],'result':result}]}));(cycle/'manifest.json').write_text(json.dumps({f['id']:{'sha256':'fixture'}}))
   return ''
  if args==('git','rev-parse','HEAD') and cwd is None:return 'source-under-test'
  return git(cwd or tmp_path,*args[1:])
 monkeypatch.setattr(tick,'run',run);return tmp_path,state,f,calls

def reseal(state):
 (state/'checkpoint.json').write_text(json.dumps({'database_sha256':hashlib.sha256((state/'openfeed.sqlite3').read_bytes()).hexdigest()}));git(state,'add','.');git(state,'commit','-m','Configure test');git(state,'push','origin','HEAD:shadow-state')
def test_idle_tick_does_not_build_commit_or_modify_database(setup):
 root,state,f,calls=setup;before=(state/'openfeed.sqlite3').read_bytes();head=git(state,'rev-parse','HEAD');result=tick.tick('idle');assert result['reason']=='idle' and result['state_written'] is False;assert git(state,'rev-parse','HEAD')==head;assert (state/'openfeed.sqlite3').read_bytes()==before;assert not any(c[0]=='docker' for c in calls)
@pytest.mark.parametrize('browser',[False,True])
def test_fetch_tick_starts_browser_only_when_required_and_keeps_history(setup,browser):
 root,state,f,calls=setup;c=sqlite3.connect(state/'openfeed.sqlite3');c.execute('update feeds set next_run=?,recipe=?',((datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),json.dumps({'fetch_mode':'browser'} if browser else {})));c.commit();c.close();reseal(state);before=tick.identities(state/'openfeed.sqlite3');result=tick.tick('fetch');assert result['processed']==1 and result['browser_started']==browser;assert any(c[0]=='docker' and 'up' in c for c in calls)==browser;after=tick.identities(state/'openfeed.sqlite3');assert before[0]==after[0] and before[1].issubset(after[1]);assert len(after[1])==2;assert git(state,'status','--porcelain')==''
def test_publication_only_tick_uses_durable_candidate_without_docker(setup,monkeypatch):
 root,state,f,calls=setup;control=json.loads((state/'runtime-control.json').read_text());control['publish_enabled']=True;(state/'runtime-control.json').write_text(json.dumps(control));reseal(state)
 # Fix an in-window slot without altering process/global time.
 import cloud_publish
 now=datetime(2026,11,6,9,30,tzinfo=timezone.utc);monkeypatch.setattr(tick,'plan',lambda path,**kw:__import__('cloud_plan').plan(path,now));monkeypatch.setattr(tick,'publication_intent',lambda path:cloud_publish.publication_intent(path,now))
 before=(state/'openfeed.sqlite3').read_bytes()
 def publish(path,public):
  assert git(path,'status','--porcelain')==''
  assert 'publication-candidate.sqlite3' in git(path,'ls-tree','--name-only','HEAD');return {'result':'unchanged','commit':'verified-public-head','pages':{'status':'built','commit':'verified-public-head'}}
 monkeypatch.setattr(tick,'publish_committed_state',publish);result=tick.tick('publication',root/'public');assert result['processed']==0;assert not any(c[0]=='docker' for c in calls);assert (state/'openfeed.sqlite3').read_bytes()==before;assert json.loads((state/'publication-state.json').read_text())['result']=='complete'
