import asyncio
import httpx
import pytest
from openfeed.batch_jobs import BatchJobs
from openfeed.storage import Store
from openfeed.pagination import collect_pages
import openfeed.app as server

@pytest.mark.asyncio
async def test_cancel_stops_remaining_source_fetches(monkeypatch,tmp_path):
    jobs=BatchJobs(str(tmp_path/'jobs.sqlite')); monkeypatch.setattr(server,'batch_jobs',jobs)
    ident=jobs.create(['first','must-not-fetch'])['id'];calls=[]
    async def fetch(feed):
        calls.append(feed)
        jobs.cancel(ident)
        return {'status':'success'}
    monkeypatch.setattr(server,'run_feed',fetch)
    await server.process_batch(ident)
    assert calls==['first']
    jobs.close()

@pytest.mark.asyncio
async def test_per_page_item_cap_marks_inventory_incomplete():
    html=''.join(f'<article><h2><a href="/jobs/{i}">Research analyst role {i}</a></h2></article>' for i in range(130))
    async def fetch(url):return url,html.encode(),'utf-8'
    items,meta=await collect_pages('https://example.com/jobs',{'mode':'css','item_selector':'article'},fetch,None)
    assert len(items)==100
    assert meta['limit_reached'] is True

@pytest.mark.asyncio
@pytest.mark.parametrize('payload',[{'enabled':None},{'title':None},{'recipe':None},{'source_url':None}])
async def test_null_patch_rejected_without_server_error(payload,monkeypatch,tmp_path):
    store=Store(str(tmp_path/'api.sqlite'));monkeypatch.setattr(server,'store',store);monkeypatch.setattr(server,'TOKEN','test-token')
    feed=store.create({'title':'Research','source_url':'https://example.org','recipe':{}})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app,raise_app_exceptions=False),base_url='http://test') as c:
        r=await c.patch('/api/feeds/'+feed['id'],headers={'X-Admin-Token':'test-token'},json=payload)
        assert r.status_code==422,r.text
        assert store.get(feed['id'])['title']=='Research'
    store.close()

@pytest.mark.parametrize('module,function',[('openfeed.browser_ipc','read_regular_result'),('openfeed.sandbox_worker','read_job_safely')])
def test_ipc_fifo_cannot_block_process(tmp_path,module,function):
    import os,subprocess,sys
    path=tmp_path/'fifo';os.mkfifo(path)
    code=f'from pathlib import Path;from {module} import {function};{function}(Path({str(path)!r}))'
    try:
        p=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=2)
    except subprocess.TimeoutExpired:
        pytest.fail('IPC open blocked on a FIFO before validating file type')
    assert p.returncode!=0
    assert 'Invalid browser' in p.stderr

@pytest.mark.asyncio
async def test_complete_job_inventory_rejects_dropped_invalid_items(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'inventory.sqlite'));monkeypatch.setattr(server,'store',db)
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    feed=db.create({'title':'Jobs','source_url':'https://jobs.example.org','recipe':{'mode':'css','item_selector':'article','content_type':'jobs','complete_inventory':True}})
    db.finish(db.get(feed['id']),[{'title':'Valid research vacancy','url':'https://jobs.example.org/one'},{'title':'Previously visible vacancy','url':'https://jobs.example.org/two'}],None,1)
    html=b'<article><h2><a href="/one">Valid research vacancy</a></h2></article><article><h2><a href="http://127.0.0.1/private">Invalid private vacancy</a></h2></article>'
    async def fetch(url):return url,html,'utf-8'
    monkeypatch.setattr(server,'fetch',fetch)
    result=await server.run_feed(feed['id'])
    assert result['status']=='error'
    assert all(x['missing_count']==0 for x in db.item_lifecycle(feed['id']))
    db.close()
