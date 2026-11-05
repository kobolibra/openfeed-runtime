"""Feed discovery and caching behavior for standards-based RSS clients."""
import pytest
import httpx
from openfeed.storage import Store
import openfeed.app as server

@pytest.mark.asyncio
async def test_rss_head_and_conditional_client_requests(tmp_path, monkeypatch):
    db=Store(str(tmp_path/'client.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','integration-secret')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver') as c:
        created=await c.post('/api/feeds',headers={'X-Admin-Token':'integration-secret'},json={
            'title':'Reader compatibility','source_url':'https://example.com/news',
            'recipe':{'mode':'css','item_selector':'article'}})
        assert created.status_code==201,created.text
        identifier=created.json()['id']; path=f'/rss/{identifier}.xml'
        initial=await c.get(path)
        assert initial.status_code==200
        assert initial.headers['content-type'].startswith('application/rss+xml')
        etag=initial.headers['etag']
        assert etag.startswith('"')
        head=await c.head(path)
        assert head.status_code==200 and head.content==b''
        assert head.headers['etag']==etag
        assert head.headers['content-length']==str(len(initial.content))
        assert (await c.get(path,headers={'If-None-Match':etag})).status_code==304
        assert (await c.head(path,headers={'If-None-Match':'"none", W/'+etag})).status_code==304
        assert (await c.get(path,headers={'If-None-Match':'*'})).status_code==304
        assert (await c.get(path,headers={'If-None-Match':'"other"'})).status_code==200
        assert (await c.get('/rss/nonexistent.xml')).status_code==404
    db.close()
