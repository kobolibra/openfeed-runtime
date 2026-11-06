import sys
from pathlib import Path
import httpx,pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'ops'))
from pages_build import ensure_build

def client_for(handler):return httpx.Client(transport=httpx.MockTransport(handler))
def test_builds_the_expected_commit_and_waits_for_it():
 calls=[];states=iter([{'commit':'old','status':'built'},{'commit':'new','status':'building'},{'commit':'new','status':'built'}])
 def handler(r):
  calls.append((r.method,r.url.path))
  if r.url.path.endswith('/pages'):return httpx.Response(200,json={'build_type':'legacy','source':{'branch':'main','path':'/'}})
  if r.method=='POST':return httpx.Response(201,json={'commit':'new','status':'queued'})
  return httpx.Response(200,json=next(states))
 with client_for(handler) as c:assert ensure_build(c,'new',sleep=lambda _:None)['commit']=='new'
 assert sum(m=='POST' for m,p in calls)==1

def test_same_commit_already_built_needs_no_new_build():
 def handler(r):
  assert r.method=='GET'
  return httpx.Response(200,json={'build_type':'legacy','source':{'branch':'main','path':'/'}} if r.url.path.endswith('/pages') else {'commit':'new','status':'built'})
 with client_for(handler) as c:assert ensure_build(c,'new')['status']=='built'

@pytest.mark.parametrize('kind',['wrong_source','failed_build','stale_build'])
def test_refuses_wrong_source_failed_build_or_stale_commit(kind):
 def handler(r):
  if r.url.path.endswith('/pages'):return httpx.Response(200,json={'build_type':'workflow' if kind=='wrong_source' else 'legacy','source':{'branch':'main','path':'/'}})
  return httpx.Response(200,json={'commit':'old' if kind=='stale_build' else 'new','status':'built' if kind=='stale_build' else 'errored'})
 with client_for(handler) as c:
  with pytest.raises((ValueError,RuntimeError,TimeoutError)):ensure_build(c,'new',budget=0)
