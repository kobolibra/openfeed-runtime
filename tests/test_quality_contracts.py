import pytest
from openfeed.app import Recipe, run_feed
from openfeed import app as application

def test_quality_fields_validate_bounds():
    assert Recipe(min_items=12, min_dated_pct=80).min_items == 12
    with pytest.raises(ValueError): Recipe(min_items=301)
    with pytest.raises(ValueError): Recipe(min_dated_pct=101)

@pytest.mark.asyncio
async def test_quality_gate_prevents_partial_feed_overwrite(monkeypatch):
    source={'id':'feed-test', 'source_url':'https://research.example/list',
       'kind':'native', 'interval_minutes':60, 'recipe':{'min_items':3, 'min_dated_pct':0}}
    outcomes=[]
    monkeypatch.setattr(application.store,'get',lambda ident:source)
    monkeypatch.setattr(application.store,'finish',lambda *args: outcomes.append(args) or {'status':'error' if args[2] else 'success'})
    monkeypatch.setattr(application,'fetch',lambda *args:None)
    async def fake_fetch(url):return url,b'<rss></rss>','utf-8'
    monkeypatch.setattr(application,'fetch',fake_fetch)
    monkeypatch.setattr(application,'parse_native',lambda *args:[{'title':'A','url':'https://research.example/a','published_at':'2026-10-01'}])
    application._last_domain.clear()
    result=await run_feed('feed-test')
    assert result['status']=='error'
    assert 'minimum is 3' in outcomes[-1][2]

@pytest.mark.asyncio
async def test_date_coverage_gate(monkeypatch):
    source={'id':'feed-test2','source_url':'https://dates.example/list','kind':'native',
            'interval_minutes':60,'recipe':{'min_items':0,'min_dated_pct':80}}
    results=[]
    monkeypatch.setattr(application.store,'get',lambda ident:source)
    monkeypatch.setattr(application.store,'finish',lambda *args:results.append(args) or {'status':'error' if args[2] else 'success'})
    async def fake_fetch(url):return url,b'<rss></rss>','utf-8'
    monkeypatch.setattr(application,'fetch',fake_fetch)
    monkeypatch.setattr(application,'parse_native',lambda *args:[
        {'title':'A','url':'https://dates.example/a','published_at':None},
        {'title':'B','url':'https://dates.example/b','published_at':'2026-10-01'}])
    application._last_domain.clear()
    result=await run_feed('feed-test2')
    assert result['status']=='error'
    assert 'dated items 1/2' in results[-1][2]
