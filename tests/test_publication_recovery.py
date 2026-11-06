import json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
import pytest
from openfeed.storage import Store
sys.path.insert(0,str(Path(__file__).parents[1]/'ops'))
import cloud_publish as p
NOW=datetime(2026,11,6,0,5,tzinfo=timezone.utc)
def state(tmp_path):
 s=tmp_path/'state';s.mkdir();store=Store(str(s/'openfeed.sqlite3'));feed=store.create({'title':'A','source_url':'https://example.com/list','recipe':{}});store.finish(feed,[{'title':'First','url':'https://example.com/first'}],None,1);store.close();(s/'runtime-control.json').write_text(json.dumps({'mode':'production','publish_enabled':True,'mac_writer_stopped':True,'final_mac_snapshot_sha256':'a'*64}));return s,feed

def public_repo(tmp_path):
 bare=tmp_path/'origin.git';repo=tmp_path/'public'
 def call(*args):return subprocess.run(['git',*map(str,args)],check=True,capture_output=True,text=True).stdout.strip()
 call('init','--bare','--initial-branch=main',bare);call('init','--initial-branch=main',repo);call('-C',repo,'config','user.name','Test');call('-C',repo,'config','user.email','test@example.com');(repo/'README.md').write_text('Static only');call('-C',repo,'add','.');call('-C',repo,'commit','-m','Initial');call('-C',repo,'remote','add','origin',bare);call('-C',repo,'push','-u','origin','main');return repo,bare,call

@pytest.mark.parametrize('fault',['pages_failure','push_reply_lost'])
def test_retry_frozen_snapshot_never_adds_second_rss_commit(tmp_path,monkeypatch,fault):
 s,feed=state(tmp_path);intent=p.freeze_publication(s,p.publication_intent(s,NOW));frozen=intent['candidate_sha256'];repo,bare,call=public_repo(tmp_path);original=p.git;once=[False];builds=[]
 def git(repo,*args):
  if args==('remote','get-url','origin'):return p.REMOTE
  value=original(repo,*args)
  if fault=='push_reply_lost' and args[0]=='push' and not once[0]:once[0]=True;raise subprocess.CalledProcessError(1,args)
  return value
 def build(commit):
  builds.append(commit)
  if fault=='pages_failure' and not once[0]:once[0]=True;raise TimeoutError('Page build response lost')
  return {'status':'built','commit':commit}
 monkeypatch.setattr(p,'git',git);monkeypatch.setattr(p,'build_published_commit',build);monkeypatch.setenv('OPENFEED_PAGES_TOKEN','test-only-token')
 with pytest.raises((TimeoutError,subprocess.CalledProcessError)):p.publish_committed_state(s,repo)
 store=Store(str(s/'openfeed.sqlite3'));store.finish(feed,[{'title':'Later','url':'https://example.com/later'}],None,1);store.close()
 retry=p.freeze_publication(s,p.publication_intent(s,NOW));assert retry['candidate_sha256']==frozen
 done=p.publish_committed_state(s,repo);p.complete_publication(s,done);assert p.publication_intent(s,NOW) is None
 assert call('--git-dir',bare,'rev-list','--count','main')=='2'
 raw=call('--git-dir',bare,'show','main:rss/'+feed['id']+'.xml');assert 'First' in raw and 'Later' not in raw
 assert all(commit==done['commit'] for commit in builds)

def test_pending_retries_next_allowed_hour_and_rejects_tampered_candidate(tmp_path):
 s,feed=state(tmp_path);first=p.freeze_publication(s,p.publication_intent(s,NOW));later=datetime(2026,11,6,1,5,tzinfo=timezone.utc);retry=p.publication_intent(s,later);assert retry['reuse_candidate'] and retry['slot']!=first['slot']
 assert p.publication_intent(s,datetime(2026,11,6,14,1,tzinfo=timezone.utc)) is None
 (s/'publication-candidate.sqlite3').write_bytes(b'changed')
 with pytest.raises(ValueError,match='missing or changed'):p.freeze_publication(s,retry)
