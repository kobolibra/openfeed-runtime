import pytest
from openfeed.extract import extract_articles
from openfeed.app import Recipe

PAGE='''<main><section class="publications">
 <article class="report"><a href="/pdf/china-outlook.pdf">China Outlook</a><time datetime="2026-10-01">October 1</time></article>
 <article class="report"><a href="https://research.example/pdf/markets.PDF?download=1">Markets Review</a><time datetime="2026-09-29">29 Sep</time></article>
 <article class="report"><a href="/pdf/china-outlook.pdf">Duplicate</a></article>
 <article class="report"><a href="/research/overview">HTML page</a></article>
</section><footer><a href="/files/terms.pdf">Terms</a></footer></main>'''

def test_pdf_scoped_cards_dates_dedupe():
    recipe={'mode':'pdf','item_selector':'article.report'}
    items,sel=extract_articles(PAGE,'https://research.example/insights',recipe)
    assert sel=='article.report' and len(items)==2
    assert items[0]['title']=='China Outlook'
    assert items[0]['published_at'].startswith('2026-10-01')
    assert items[1]['url']=='https://research.example/pdf/markets.PDF?download=1'

def test_pdf_document_links_not_footer_if_scoped():
    items,_=extract_articles(PAGE,'https://research.example/',{'mode':'pdf','item_selector':'section.publications a'})
    assert len(items)==2
    assert all('terms.pdf' not in x['url'] for x in items)

def test_pdf_rejects_invalid_selector():
    with pytest.raises(ValueError, match='Invalid PDF CSS selector'):
        extract_articles(PAGE,'https://research.example/',{'mode':'pdf','item_selector':'div['})

def test_recipe_accepts_pdf_mode():
    assert Recipe(mode='pdf').mode == 'pdf'

@pytest.mark.asyncio
async def test_pdf_full_http_feed_workflow(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    import httpx
    from defusedxml import ElementTree as ET
    from openfeed.storage import Store
    import openfeed.app as server

    db = Store(str(tmp_path / 'pdf-feed.sqlite'))
    monkeypatch.setattr(server, 'store', db)
    monkeypatch.setattr(server, 'TOKEN', 'pdf-test-key')
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL', '0')
    fetch = AsyncMock(return_value=('https://research.example/insights', PAGE.encode(), 'utf-8'))
    monkeypatch.setattr(server, 'fetch', fetch)
    headers={'X-Admin-Token': 'pdf-test-key'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url='http://testserver') as client:
        sample=await client.post('/api/inspect',headers=headers,json={
            'url':'https://research.example/insights', 'recipe':{'mode':'pdf','item_selector':'article.report'}})
        assert sample.status_code == 200, sample.text
        assert len(sample.json()['preview_items']) == 2
        response=await client.post('/api/feeds',headers=headers,json={
            'title':'Research PDFs','source_url':'https://research.example/insights',
            'recipe':{'mode':'pdf','item_selector':'article.report'}})
        assert response.status_code == 201, response.text
        ident=response.json()['id']
        first=await client.post(f'/api/feeds/{ident}/run',headers=headers)
        assert first.json()['inserted']==2, first.text
        second=await client.post(f'/api/feeds/{ident}/run',headers=headers)
        assert second.json()['inserted']==0
        rss=await client.get(f'/rss/{ident}.xml')
        links=[i.findtext('link') for i in ET.fromstring(rss.content).findall('./channel/item')]
        assert len(links)==2 and all('.pdf' in x.lower() for x in links)
        monkeypatch.setattr(server, 'fetch', AsyncMock(side_effect=ValueError('network outage')))
        fail=await client.post(f'/api/feeds/{ident}/run',headers=headers)
        assert fail.json()['status']=='error'
        assert (await client.get(f'/rss/{ident}.xml')).content==rss.content or len(ET.fromstring((await client.get(f'/rss/{ident}.xml')).content).findall('./channel/item'))==2
    db.close()

def test_pdf_mime_declared_endpoint_without_dot_pdf_path():
    from openfeed.extract import extract_articles
    html='<main><a href="/download?id=42" type="application/pdf">Fiscal research (PDF)</a><a href="/download?id=43">Unknown file</a></main>'
    rows,_=extract_articles(html,'https://research.example/reports',{'mode':'pdf','item_selector':'main a'})
    assert len(rows)==1
    assert rows[0]['url']=='https://research.example/download?id=42'
