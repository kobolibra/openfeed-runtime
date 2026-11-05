import pytest
from openfeed.extract import extract_articles
from openfeed.app import Recipe

HTML='''<aside><a href="/junk">Ignore</a></aside>
<main class="reports">
<a href="/a">Alpha</a>posted <time>2026-10-01</time>
<a href="/b">Beta</a>posted <time>2026-10-02</time>
</main><footer><a href="/c">Outside</a>posted <time>2026-10-03</time></footer>'''


def test_global_scope_and_numbered_output_templates():
    recipe={'mode':'pattern','global_pattern':'<main class="reports">{%}</main>',
        'item_selector':'<a href="{%}">{%}</a>posted <time>{%}</time>',
        'fields':{'title':'Research: {%2}', 'link':'{%1}','date':'{%3}','summary':'Source item: {%2}'}}
    items,_=extract_articles(HTML,'https://research.example/',recipe)
    assert [x['title'] for x in items] == ['Research: Alpha','Research: Beta']
    assert [x['url'] for x in items] == ['https://research.example/a','https://research.example/b']
    assert '2026-10-02' in items[1]['published_at']
    assert items[1]['summary']=='Source item: Beta'


def test_invalid_global_search_is_rejected():
    with pytest.raises(ValueError, match='global search'):
        extract_articles(HTML,'https://research.example/',{'mode':'pattern','global_pattern':'<missing>{%}</missing>',
          'item_selector':'<a href="{%}">{%}</a>'})


def test_pattern_rule_length_bounds():
    with pytest.raises(ValueError):Recipe(global_pattern='a'*501)


def test_invalid_captures_cannot_inject_unbounded_text():
    html='<main>'+('x'*50000)+'</main>'
    rows,_=extract_articles(html,'https://research.example/',{'mode':'pattern','global_pattern':'<main>{%}</main>',
           'item_selector':'x{%}y'})
    assert rows == []

@pytest.mark.asyncio
async def test_feed43_preview_save_refresh_and_rss(monkeypatch, tmp_path):
    import httpx
    from unittest.mock import AsyncMock
    from defusedxml import ElementTree as ET
    from openfeed.storage import Store
    import openfeed.app as server
    store=Store(str(tmp_path/'feed43-api.sqlite3'))
    monkeypatch.setattr(server,'store',store)
    monkeypatch.setattr(server,'TOKEN','feed43-integration-secret')
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    url='https://research.example/reports'
    monkeypatch.setattr(server,'fetch',AsyncMock(return_value=(url,HTML.encode(),'utf-8')))
    recipe={'mode':'pattern','global_pattern':'<main class="reports">{%}</main>',
        'item_selector':'<a href="{%}">{%}</a>posted <time>{%}</time>',
        'fields':{'title':'Research: {%2}','link':'{%1}','date':'{%3}'}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver') as client:
        auth={'X-Admin-Token':'feed43-integration-secret'}
        preview=await client.post('/api/inspect',headers=auth,json={'url':url,'recipe':recipe})
        assert preview.status_code==200,preview.text
        assert [x['title'] for x in preview.json()['preview_items']]==['Research: Alpha','Research: Beta']
        created=await client.post('/api/feeds',headers=auth,json={'title':'Research','source_url':url,'recipe':recipe})
        ident=created.json()['id']
        first=await client.post(f'/api/feeds/{ident}/run',headers=auth)
        assert first.json()['inserted']==2
        second=await client.post(f'/api/feeds/{ident}/run',headers=auth)
        assert second.json()['inserted']==0
        rss=await client.get(f'/rss/{ident}.xml')
        titles=[x.text for x in ET.fromstring(rss.content).findall('./channel/item/title')]
        assert set(titles)=={'Research: Alpha','Research: Beta'}
    store.close()

def test_feed43_global_region_can_span_large_research_archive():
    body='<main>'+(' ' * 10000)+'<a href="/paper">Long archive item</a>'+('</main>')
    recipe={'mode':'pattern','global_pattern':'<main>{%}</main>',
        'item_selector':'<a href="{%}">{%}</a>',
        'fields':{'title':'{%2}','link':'{%1}'}}
    rows,_=extract_articles(body,'https://research.example/',recipe)
    assert len(rows)==1 and rows[0]['title']=='Long archive item'
