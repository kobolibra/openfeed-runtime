import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from defusedxml import ElementTree as ET
from openfeed.extract import extract_articles, discover, parse_native, render_rss, safe_preview
from openfeed.security import check_url, UnsafeURL
from openfeed.storage import Store
import openfeed.app as server

ARTICLE_HTML = '''<!DOCTYPE html><html><head><title>Research</title>
<link rel="alternate" type="application/rss+xml" title="Native RSS" href="/feeds/official.xml"></head><body>
<main><article class="memo"><h2><a href="/articles/first">The first research memo</a></h2><time datetime="2026-10-18">18 Oct 2026</time><p>A useful overview of global markets</p></article>
<article class="memo"><h2><a href="/articles/second">The second research memo</a></h2><time datetime="2026-10-20">20 Oct 2026</time><p>Some detail on inflation and interest rates</p></article></main>
<script>alert('do-not-run')</script><iframe src="https://evil.example/"></iframe><img src="https://evil.example/track.png"></body></html>'''
ATOM = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>New research finding</title><link href="https://www.example.org/one"/><updated>2026-10-20T10:00:00Z</updated></entry></feed>'''


def test_css_xpath_and_dates():
    items,selector=extract_articles(ARTICLE_HTML,'https://www.example.org/insights',{})
    assert selector=='main article' and len(items)==2
    assert items[0]['url']=='https://www.example.org/articles/first'
    assert items[1]['published_at'].startswith('2026-10-20')
    xp={'mode':'xpath','item_selector':'//article','fields':{'title':'(.//h2/a/text())[1]','link':'(.//h2/a/@href)[1]','date':'(.//time/@datetime)[1]'}}
    got,_=extract_articles(ARTICLE_HTML,'https://www.example.org/insights',xp)
    assert len(got)==2 and got[0]['title']==items[0]['title']


def test_discovery_native_and_snapshot():
    feeds=discover(ARTICLE_HTML,'https://www.example.org/insights')
    assert feeds[0]['url']=='https://www.example.org/feeds/official.xml'
    assert parse_native(ATOM,'https://www.example.org/feed')[0]['title']=='New research finding'
    preview=safe_preview(ARTICLE_HTML)
    assert 'do-not-run' not in preview and 'evil.example' not in preview
    assert '<script' not in preview

@pytest.mark.parametrize('url',[
 'http://localhost/admin','http://127.0.0.1','http://169.254.169.254/latest/meta-data','http://10.0.0.1',
 'http://192.168.1.1','http://[::1]/','file:///etc/passwd','http://user:pass@example.com','http://example.com:8080'
])
def test_ssrf(url):
    with pytest.raises(UnsafeURL): check_url(url)


def test_transaction_and_stable_guid(tmp_path):
    db=Store(str(tmp_path/'db.sqlite'))
    f=db.create({'title':'Testing','source_url':'https://www.example.org/insights','recipe':{}})
    item,_=extract_articles(ARTICLE_HTML,f['source_url'],{})
    a=db.finish(f,item,None,123)
    b=db.finish(f,item,None,90)
    assert a['inserted']==2 and b['inserted']==0
    rows=db.entries(f['id'])
    ids=[x['guid'] for x in rows]
    db.finish(f,[],"HTTP 503",80)
    assert db.get(f['id'])['status']=='error'
    assert [x['guid'] for x in db.entries(f['id'])]==ids
    xml=render_rss(db.get(f['id']),rows,'https://feeds.example.org/rss/a.xml')
    assert len(ET.fromstring(xml).findall('./channel/item'))==2
    db.close()

@pytest.mark.asyncio
async def test_full_api_with_mocked_external_fetch(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'api.sqlite'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','unit-test-token')
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    monkeypatch.setattr(server,'fetch',AsyncMock(return_value=('https://www.example.org/insights',ARTICLE_HTML.encode(),'utf-8')))
    transport=httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport,base_url='http://testserver') as c:
        headers={'X-Admin-Token':'unit-test-token'}
        assert (await c.get('/api/feeds')).status_code==401
        create=await c.post('/api/feeds',headers=headers,json={'title':'Test Research','source_url':'https://www.example.org/insights','interval_minutes':60})
        assert create.status_code==201,create.text
        ident=create.json()['id']
        prev=await c.post('/api/inspect',headers=headers,json={'url':'https://www.example.org/insights'})
        assert prev.status_code==200 and len(prev.json()['preview_items'])==2
        assert prev.json()['discovered'][0]['title']=='Native RSS'
        first=(await c.post('/api/feeds/'+ident+'/run',headers=headers)).json()
        assert first['status']=='success' and first['inserted']==2
        second=(await c.post('/api/feeds/'+ident+'/run',headers=headers)).json()
        assert second['inserted']==0
        rss=await c.get('/rss/'+ident+'.xml')
        assert rss.status_code==200 and rss.headers['content-type'].startswith('application/rss+xml')
        assert len(ET.fromstring(rss.content).findall('./channel/item'))==2
        assert 'The first research memo' in rss.text
        opml=await c.get('/api/export/opml',headers=headers)
        assert ident in opml.text and ET.fromstring(opml.content).tag=='opml'
        recipe=await c.get('/api/export/recipes',headers=headers)
        assert recipe.json()['feeds'][0]['title']=='Test Research'
        monkeypatch.setattr(server,'fetch',AsyncMock(side_effect=ValueError('Upstream temporarily down')))
        run=(await c.post('/api/feeds/'+ident+'/run',headers=headers)).json()
        assert run['status']=='error'
        assert len(ET.fromstring((await c.get('/rss/'+ident+'.xml')).content).findall('./channel/item'))==2
        assert (await c.delete('/api/feeds/'+ident,headers=headers)).status_code==200
        assert (await c.get('/rss/'+ident+'.xml')).status_code==404
    db.close()

def test_feed43_capture_engine():
    html='''<div class="post"><a href="/a">Article Alpha</a>posted <time>2026-10-10</time></div>
<div class="post"><a href="/b">Article Beta</a>posted <time>2026-10-11</time></div>'''
    recipe={'mode':'pattern','item_selector':'<a href="{%}">{%}</a>posted <time>{%}</time>','fields':{'title':'2','link':'1','date':'3'}}
    items,_=extract_articles(html,'https://www.example.org/news',recipe)
    assert [x['title'] for x in items]==['Article Alpha','Article Beta']
    assert items[0]['url']=='https://www.example.org/a'
    with pytest.raises(ValueError): extract_articles(html,'https://www.example.org',{'mode':'pattern','item_selector':'not-a-pattern'})

@pytest.mark.asyncio
async def test_recipe_import_and_conditional_http(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'another.sqlite'))
    monkeypatch.setattr(server,'store',db);monkeypatch.setattr(server,'TOKEN','test-import');monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    client=httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver')
    h={'X-Admin-Token':'test-import'}
    async with client as c:
        bundle={'format':'openfeed-recipes','version':1,'feeds':[{'title':'Oaktree','source_url':'https://www.example.org/memos','recipe':{'mode':'css','item_selector':'main article'}}]}
        res=await c.post('/api/import/recipes',headers=h,json=bundle)
        assert res.status_code==200 and res.json()['imported']==1
        assert (await c.post('/api/import/recipes',headers=h,json=bundle)).json()['skipped']==1
        opml=b'''<?xml version="1.0"?><opml version="2.0"><body><outline type="rss" title="Original feed" xmlUrl="https://www.example.org/rss.xml"/></body></opml>'''
        res=await c.post('/api/import/opml',headers=h,content=opml)
        assert res.json()['imported']==1
        feeds=(await c.get('/api/feeds',headers=h)).json()
        assert next(f for f in feeds if f['kind']=='native')['title']=='Original feed'
        f=next(f for f in feeds if f['title']=='Oaktree')
        storeitems,_=extract_articles(ARTICLE_HTML,'https://www.example.org/insights',{})
        db.finish(f,storeitems,None,20)
        rss=await c.get('/rss/'+f['id']+'.xml')
        assert rss.status_code==200 and rss.headers.get('etag')
        cached=await c.get('/rss/'+f['id']+'.xml',headers={'If-None-Match':rss.headers['etag']})
        assert cached.status_code==304 and not cached.content
    db.close()
