import pytest
from openfeed.storage import Store
from openfeed.app import Recipe

def test_job_lifecycle_requires_two_complete_observations(tmp_path):
    db=Store(str(tmp_path/'jobs.db'))
    a='https://jobs.example/123'; b='https://jobs.example/456'
    record=db.create({'title':'Company Jobs','source_url':'https://jobs.example/','kind':'web','recipe':{'content_type':'jobs','complete_inventory':True},'interval_minutes':60})
    def put(urls):
        return db.finish(db.get(record['id']),[{'title':u,'url':u,'published_at':None} for u in urls],None,12)
    put([a,b]);put([a]); row=next(x for x in db.item_lifecycle(record['id']) if x['url']==b)
    assert (row['availability'],row['missing_count'])==('missing_once',1)
    put([a]); row=next(x for x in db.item_lifecycle(record['id']) if x['url']==b)
    assert (row['availability'],row['missing_count'])==('possibly_closed',2)
    put([a,b]); row=next(x for x in db.item_lifecycle(record['id']) if x['url']==b)
    assert (row['availability'],row['missing_count'])==('observed',0)
    db.close()

def test_incomplete_job_inventory_does_not_mark_closures(tmp_path):
    db=Store(str(tmp_path/'jobs.db'))
    feed=db.create({'title':'Jobs','source_url':'https://jobs.example/','recipe':{'content_type':'jobs','complete_inventory':False}})
    db.finish(db.get(feed['id']),[{'title':'A','url':'https://jobs.example/a'}],None,1)
    db.finish(db.get(feed['id']),[{'title':'B','url':'https://jobs.example/b'}],None,1)
    assert all(x['availability']=='observed' for x in db.item_lifecycle(feed['id']))
    db.close()

def test_job_config_validation():
    assert Recipe(content_type='jobs',complete_inventory=True).complete_inventory

@pytest.mark.asyncio
async def test_truncated_job_inventory_cannot_age_missing_positions(monkeypatch):
    import openfeed.app as server
    source={'id':'job-guard-test','source_url':'https://jobs.example/jobs','kind':'web',
            'interval_minutes':60,'recipe':{'content_type':'jobs','complete_inventory':True}}
    failures=[]
    monkeypatch.setattr(server.store,'get',lambda _:source)
    monkeypatch.setattr(server.store,'finish',lambda *args: failures.append(args[2]) or {'status':'error'})
    async def fake_collector(*args,**kwargs):
        return ([{'title':'A','url':'https://jobs.example/a','published_at':None}],
                {'pages_fetched':1,'items_found':1,'limit_reached':True})
    monkeypatch.setattr(server,'collect_pages',fake_collector)
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    server._last_domain.clear()
    result=await server.run_feed('job-guard-test')
    assert result['status']=='error'
    assert 'not provably complete' in failures[-1]
