import pytest
from unittest.mock import AsyncMock
import httpx
from openfeed.storage import Store
import openfeed.app as server

HTML='''<main><div class="memo-card"><h2><a href="/memo/1">Global macro memo one</a></h2><time datetime="2026-10-21">Today</time></div><div class="memo-card"><h2><a href="/memo/2">Global macro memo two</a></h2><time datetime="2026-10-20">Yesterday</time></div></main>'''

@pytest.mark.asyncio
async def test_diagnose_suggests_non_destructive_rule_repair(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'db.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','diagnostics-secret')
    url='https://research.example.com/insights'
    monkeypatch.setattr(server,'fetch',AsyncMock(return_value=(url,HTML.encode(),'utf-8')))
    feed=db.create({'title':'Research','source_url':url,'recipe':{'mode':'css','item_selector':'.obsolete'}})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver') as client:
        endpoint='/api/feeds/'+feed['id']+'/diagnose'
        assert (await client.post(endpoint)).status_code==401
        resp=await client.post(endpoint,headers={'X-Admin-Token':'diagnostics-secret'})
        assert resp.status_code==200,resp.text
        result=resp.json()
        assert result['current_items']==0
        assert result['suggestions']
        assert any(x['valid_items']>=2 for x in result['suggestions'])
        assert db.get(feed['id'])['recipe']['item_selector']=='.obsolete'
    db.close()
