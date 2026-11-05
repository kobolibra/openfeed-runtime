import json
import pytest
from openfeed.extract import extract_articles
from openfeed.app import Recipe

def test_public_listing_html_wrapper_extracts_real_cards():
    cfg={'mode':'css','request_method':'POST','response_html_path':'data.content','item_selector':'article','fields':{'title':'h2','link':'a@href'}}
    Recipe.model_validate(cfg)
    rows,_=extract_articles(json.dumps({'success':True,'data':{'content':'<article><h2>Economic outlook</h2><a href="/perspectives/outlook">Read</a></article>'}}),'https://example.org/api',cfg)
    assert rows[0]['title']=='Economic outlook' and rows[0]['url']=='https://example.org/perspectives/outlook'

@pytest.mark.parametrize('body',['not json','{"data":{"content":[]}}','{"success":false,"data":{}}'])
def test_changed_api_contract_fails_instead_of_extracting_navigation(body):
    with pytest.raises(ValueError):extract_articles(body,'https://example.org/api',{'mode':'css','response_html_path':'data.content'})

@pytest.mark.asyncio
async def test_wrapped_listing_preview_and_diagnosis(monkeypatch,tmp_path):
    import httpx
    from unittest.mock import AsyncMock
    import openfeed.app as server
    from openfeed.storage import Store
    db=Store(str(tmp_path/'wrapped.sqlite'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','wrapped-test')
    cfg={'mode':'css','request_method':'POST','request_data':{'action':'load_listing_results'},'response_html_path':'data.content','item_selector':'article','fields':{'title':'h2','link':'a@href'}}
    body=json.dumps({'data':{'content':'<article><h2>Economic outlook</h2><a href="/perspectives/outlook">Read</a></article><script>alert(1)</script>'}}).encode()
    mocked=AsyncMock(return_value=('https://example.org/api',body,'utf-8'))
    monkeypatch.setattr(server,'fetch',mocked)
    feed=db.create({'title':'Public listing','source_url':'https://example.org/api','recipe':cfg})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver',headers={'X-Admin-Token':'wrapped-test'}) as client:
        preview=await client.post('/api/inspect',json={'url':'https://example.org/api','recipe':cfg})
        assert preview.status_code==200,preview.text
        assert preview.json()['preview_items'][0]['title']=='Economic outlook'
        assert '<script' not in preview.json()['snapshot']
        diagnosis=await client.post('/api/feeds/'+feed['id']+'/diagnose')
        assert diagnosis.status_code==200 and diagnosis.json()['current_items']==1
    assert db.get(feed['id'])['recipe']==cfg
    assert mocked.call_args.kwargs=={'method':'POST','data':cfg['request_data']}
    db.close()
