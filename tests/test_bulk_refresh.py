import pytest
import httpx
from openfeed.storage import Store
import openfeed.app as server

@pytest.mark.asyncio
async def test_bulk_refresh_authenticated_bounded_and_ordered(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'bulk.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','bulk-token')
    ids=[]
    for n in range(4):
        record=db.create({'title':f'Source {n}','source_url':f'https://example{n}.org/notes',
                         'description':'','kind':'web','recipe':{'mode':'css'},'interval_minutes':60,'enabled':True})
        ids.append(record['id'])
    active=0
    peak=0
    async def fake_run(identifier):
        nonlocal active,peak
        import asyncio
        active+=1
        peak=max(peak,active)
        await asyncio.sleep(0.01)
        active-=1
        return {'status':'success','id':identifier}
    monkeypatch.setattr(server,'run_feed',fake_run)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),
                                base_url='http://testserver') as client:
        url='/api/feeds/bulk-refresh'
        assert (await client.post(url,json={'feed_ids':ids})).status_code==401
        headers={'X-Admin-Token':'bulk-token'}
        bad=await client.post(url,json={'feed_ids':ids+['missing']},headers=headers)
        assert bad.status_code==404
        dup=await client.post(url,json={'feed_ids':[ids[0],ids[0]]},headers=headers)
        assert dup.status_code==422
        ok=await client.post(url,json={'feed_ids':ids},headers=headers)
        assert ok.status_code==200,ok.text
        assert [x['feed_id'] for x in ok.json()['results']]==ids
        assert peak<=3
        assert all(x['result']['status']=='success' for x in ok.json()['results'])
    db.close()

@pytest.mark.asyncio
async def test_bulk_refresh_failure_is_isolated(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'failure.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','bulk-token')
    ids=[db.create({'title':f'T{n}','source_url':f'https://sample{n}.org/',
                    'description':'','kind':'web','recipe':{'mode':'css'},'interval_minutes':60,'enabled':True})['id'] for n in range(3)]
    async def sometimes_fails(identifier):
        if identifier==ids[1]: raise RuntimeError('Temporary source failure')
        return {'status':'success'}
    monkeypatch.setattr(server,'run_feed',sometimes_fails)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver') as client:
        response=await client.post('/api/feeds/bulk-refresh',
                                   headers={'X-Admin-Token':'bulk-token'},json={'feed_ids':ids})
        assert response.status_code==200
        results=response.json()['results']
        assert results[0]['result']['status']=='success'
        assert results[1]['feed_id']==ids[1] and 'Temporary source failure' in results[1]['error']
        assert results[2]['result']['status']=='success'
    db.close()
