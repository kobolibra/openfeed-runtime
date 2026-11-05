import asyncio
import httpx
import pytest
from openfeed.batch_jobs import BatchJobs
import openfeed.app as server
from openfeed.storage import Store


def test_durable_interrupted_resume_and_exactly_once_progress(tmp_path):
    path=str(tmp_path/'queue.sqlite')
    jobs=BatchJobs(path)
    record=jobs.create(['a','b','c'])
    assert jobs.claim(record['id'])
    assert jobs.finish_one(record['id'],'a',{'feed_id':'a','result':{'status':'success'}})
    assert not jobs.finish_one(record['id'],'a',{'feed_id':'a'})
    jobs.close()
    restored=BatchJobs(path)
    assert restored.get(record['id'])['status']=='interrupted'
    assert restored.get(record['id'])['completed']==1
    assert restored.resume(record['id'])
    assert restored.claim(record['id'])
    assert restored.finish_one(record['id'],'b',{'feed_id':'b','error':'offline'})
    assert restored.finish_one(record['id'],'c',{'feed_id':'c','result':{'status':'success'}})
    final=restored.get(record['id'])
    assert final['status']=='completed' and final['completed']==3
    assert [r['feed_id'] for r in final['results']]==['a','b','c']
    restored.close()

@pytest.mark.asyncio
async def test_batch_api_progress_and_failure_isolation(monkeypatch,tmp_path):
    path=str(tmp_path/'live.sqlite')
    db=Store(path); jobs=BatchJobs(path)
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'batch_jobs',jobs)
    monkeypatch.setattr(server,'TOKEN','batch-admin')
    ids=[db.create({'title':f'Feed {n}','source_url':f'https://test{n}.org/feed',
                    'description':'','kind':'web','recipe':{'mode':'css'},
                    'interval_minutes':60,'enabled':True})['id'] for n in range(3)]
    async def fake_run(feed):
        if feed==ids[1]: raise ValueError('Source temporarily broken')
        return {'status':'success'}
    monkeypatch.setattr(server,'run_feed',fake_run)
    transport=httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport,base_url='http://local') as client:
        endpoint='/api/feeds/batch-jobs'
        assert (await client.post(endpoint,json={'feed_ids':ids})).status_code==401
        headers={'X-Admin-Token':'batch-admin'}
        response=await client.post(endpoint,json={'feed_ids':ids},headers=headers)
        assert response.status_code==202
        record=response.json()
        assert record['status']=='pending' and record['total']==3
        await server.process_batch(record['id'])
        progress=await client.get(endpoint+'/'+record['id'],headers=headers)
        assert progress.status_code==200
        data=progress.json()
        assert data['completed']==3 and data['status']=='completed'
        assert 'temporarily broken' in data['results'][1]['error']
        assert (await client.post(endpoint+'/'+record['id']+'/resume',headers=headers)).status_code==409
    jobs.close();db.close()

@pytest.mark.asyncio
async def test_batch_cancellation_can_resume_without_restart(monkeypatch,tmp_path):
    path=str(tmp_path/'cancel.sqlite')
    db=Store(path); jobs=BatchJobs(path)
    monkeypatch.setattr(server,'batch_jobs',jobs)
    first=asyncio.Event()
    calls=[]
    async def stalled(identifier):
        calls.append(identifier)
        first.set()
        await asyncio.Event().wait()
    monkeypatch.setattr(server,'run_feed',stalled)
    ident=jobs.create(['alpha','beta'])['id']
    worker=asyncio.create_task(server.process_batch(ident))
    await asyncio.wait_for(first.wait(),1)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert jobs.get(ident)['status']=='interrupted'
    assert jobs.get(ident)['completed']==0
    assert jobs.resume(ident)
    async def done(identifier): return {'status':'success'}
    monkeypatch.setattr(server,'run_feed',done)
    await server.process_batch(ident)
    assert jobs.get(ident)['status']=='completed'
    assert jobs.get(ident)['completed']==2
    jobs.close();db.close()

@pytest.mark.asyncio
async def test_batch_fairness_requeues_unfinished_feeds(monkeypatch,tmp_path):
    path=str(tmp_path/'fair.sqlite')
    jobs=BatchJobs(path)
    monkeypatch.setattr(server,'batch_jobs',jobs)
    executed=[]
    async def fake_run(feed):
        executed.append(feed)
        return {'status':'success'}
    monkeypatch.setattr(server,'run_feed',fake_run)
    a=jobs.create(['a1','a2','a3'])['id']
    b=jobs.create(['b1'])['id']
    for job in jobs.pending():
        await server.process_batch(job,max_items=1)
    assert executed==['a1','b1']
    assert jobs.get(a)['status']=='pending'
    assert jobs.get(b)['status']=='completed'
    assert jobs.get(a)['completed']==1
    await server.process_batch(a,max_items=1)
    await server.process_batch(a,max_items=1)
    assert jobs.get(a)['status']=='completed'
    jobs.close()
