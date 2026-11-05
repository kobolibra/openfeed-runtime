import json
import pytest
from openfeed.extract import extract_articles
from openfeed.app import Recipe

BASE='https://research.example.com/api/posts'

def test_nested_json_records_and_duplicates():
    body=json.dumps({'payload': {'entries': [
        {'headline':'New macro outlook','permalink':'/research/macro','published': '2026-10-21','abstract':'Markets'},
        {'headline':'Repeat','permalink':'/research/macro','published':'2026-10-21'},
        {'headline':'Rates note','permalink':'https://research.example.com/rates','published':'2026-10-20'}
    ]}})
    cfg={'mode':'json','item_selector':'payload.entries','fields':{'title':'headline','link':'permalink','date':'published','summary':'abstract'}}
    items,path=extract_articles(body,BASE,cfg)
    assert path=='payload.entries' and len(items)==2
    assert items[0]['url']=='https://research.example.com/research/macro'
    assert items[0]['published_at'].startswith('2026-10-21')
    assert items[1]['title']=='Rates note'

def test_json_validation_and_safe_paths():
    assert Recipe(mode='json',item_selector='data.rows').mode=='json'
    with pytest.raises(ValueError,match='array'):
        extract_articles('{"data":{"rows":1}}',BASE,{'mode':'json','item_selector':'data.rows'})
    with pytest.raises(ValueError,match='Invalid JSON field'):
        extract_articles('{"data":[]}',BASE,{'mode':'json','item_selector':'__class__'})
    with pytest.raises(ValueError,match='valid JSON'):
        extract_articles('<html>nope</html>',BASE,{'mode':'json','item_selector':'items'})
    with pytest.raises(ValueError,match='500'):
        extract_articles(json.dumps({'items':[{'title':'x'}]*501}),BASE,{'mode':'json'})

def test_json_numeric_paths_and_dangerous_links():
    body=json.dumps({'groups':[{'posts':[
        {'title':'Fine','url':'https://example.org/news/1'},
        {'title':'Bad','url':'javascript:alert(1)'},
        {'title':'Missing URL'},
    ]}]})
    items,_=extract_articles(body, BASE, {'mode':'json','item_selector':'groups.0.posts'})
    assert len(items)==1
    assert items[0]['url']=='https://example.org/news/1'

@pytest.mark.asyncio
async def test_json_mode_api_preview_publish_and_dedup(monkeypatch,tmp_path):
    from unittest.mock import AsyncMock
    import httpx
    from defusedxml import ElementTree as ET
    from openfeed.storage import Store
    import openfeed.app as server
    db=Store(str(tmp_path/'json-api.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','json-mode-test')
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    json_data=json.dumps({'data':{'reports':[
        {'headline':'China market note','permalink':'/notes/china','date':'2026-10-21'},
        {'headline':'Global macro outlook','permalink':'/notes/global','date':'2026-10-20'}]}}).encode()
    monkeypatch.setattr(server,'fetch',AsyncMock(return_value=(BASE,json_data,'utf-8')))
    recipe={'mode':'json','item_selector':'data.reports',
            'fields':{'title':'headline','link':'permalink','date':'date'}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver') as c:
        auth={'X-Admin-Token':'json-mode-test'}
        preview=await c.post('/api/inspect',headers=auth,json={'url':BASE,'recipe':recipe})
        assert preview.status_code==200,preview.text
        assert len(preview.json()['preview_items'])==2
        assert preview.json()['snapshot'] is None
        create=await c.post('/api/feeds',headers=auth,json={
            'title':'JSON Research Feed','source_url':BASE,'recipe':recipe})
        assert create.status_code==201,create.text
        feed_id=create.json()['id']
        first=(await c.post(f'/api/feeds/{feed_id}/run',headers=auth)).json()
        second=(await c.post(f'/api/feeds/{feed_id}/run',headers=auth)).json()
        assert first['status']=='success' and first['inserted']==2
        assert second['inserted']==0
        rss=await c.get(f'/rss/{feed_id}.xml')
        assert len(ET.fromstring(rss.content).findall('./channel/item'))==2
    db.close()
