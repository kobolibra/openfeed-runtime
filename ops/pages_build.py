"""Explicitly build the fixed legacy Pages site after a production Git push."""
import os,time
import httpx
API='https://api.github.com/repos/kobolibra/openfeed-feeds'

def ensure_build(client,commit,clock=time.monotonic,sleep=time.sleep,budget=120):
    site=client.get(API+'/pages');site.raise_for_status();site=site.json()
    if site.get('build_type')!='legacy' or site.get('source')!={'branch':'main','path':'/'}:
        raise ValueError('Unexpected Pages publication source')
    latest=client.get(API+'/pages/builds/latest')
    if latest.status_code!=404:latest.raise_for_status()
    state=latest.json() if latest.status_code!=404 else {}
    if state.get('commit')!=commit or state.get('status') not in ('built','building','queued'):
        response=client.post(API+'/pages/builds');response.raise_for_status()
        state=response.json()
    end=clock()+budget
    while True:
        if state.get('commit')==commit:
            if state.get('status')=='built':return {'status':'built','commit':commit}
            if state.get('status')=='errored':raise RuntimeError('Pages build failed for expected commit')
        if clock()>=end:raise TimeoutError('Expected Pages commit was not built within the publication budget')
        sleep(min(5,max(0,end-clock())))
        response=client.get(API+'/pages/builds/latest');response.raise_for_status();state=response.json()

def build_published_commit(commit):
    token=os.environ.get('OPENFEED_PAGES_TOKEN')
    if not token:raise ValueError('Production publication requires an explicit Pages API token')
    with httpx.Client(trust_env=False,timeout=15,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'}) as client:
        return ensure_build(client,commit)
