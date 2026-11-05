from tools.browser_support import chromium_executable
"""Real Chromium interaction -> generated recipe -> actual API -> persisted RSS.

Only the source website HTTP response is mocked; web picker, extraction, app,
SQLite, and published RSS are production code.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock
import httpx
import pytest
from defusedxml import ElementTree as ET
from playwright.sync_api import sync_playwright
from openfeed.storage import Store
import openfeed.app as server

ROOT=Path(__file__).resolve().parents[1]
URL='https://research.example.org/insights'
HTML='''<html><head><title>Research Reports</title></head><body><main>
<article class="research-card"><h2><a href="/report/1">A detailed report about emerging markets</a></h2><time datetime="2026-10-18">October 18</time></article>
<article class="research-card"><h2><a href="/report/2">A detailed report about global inflation</a></h2><time datetime="2026-10-19">October 19</time></article>
<article class="research-card"><h2><a href="/report/3">A detailed report about fixed income</a></h2><time datetime="2026-10-20">October 20</time></article>
</main></body></html>'''


def select_in_browser():
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(executable_path=chromium_executable(),headless=True,args=['--no-sandbox'])
        page=browser.new_page()
        page.goto(URL,wait_until='domcontentloaded') if False else page.set_content(HTML)
        page.evaluate('''() => {window.__messages=[];window.chrome={runtime:{onMessage:{addListener(fn){window.__handler=fn}},sendMessage(m){window.__messages.push(m)}}}}''')
        page.add_script_tag(path=str(ROOT/'extension/picker.js'))
        page.add_script_tag(path=str(ROOT/'extension/content.js'))
        page.locator('article').first.click()
        for field,selector in [('title','h2'),('link','h2 a'),('date','time')]:
            page.evaluate('(field)=>window.__handler({type:"SET_FIELD",field},null,()=>{})',field)
            page.locator('article').first.locator(selector).click()
        picked=page.evaluate('window.__messages.at(-1).selection')
        assert picked['coverage']['total']==3
        browser.close()
        return picked


@pytest.mark.asyncio
async def test_browser_selected_recipe_publishes_stable_feed(tmp_path,monkeypatch):
    picked=await asyncio.to_thread(select_in_browser)
    db=Store(str(tmp_path/'picked.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','bridge-test-token')
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    monkeypatch.setattr(server,'fetch',AsyncMock(return_value=(URL,HTML.encode(),'utf-8')))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver') as client:
        headers={'X-Admin-Token':'bridge-test-token'}
        recipe={'mode':'css','item_selector':picked['item_selector'],'fields':picked['fields']}
        source={'title':'Research Reports','source_url':URL,'recipe':recipe}
        created=await client.post('/api/feeds',headers=headers,json=source)
        assert created.status_code==201,created.text
        feed_id=created.json()['id']
        initial=await client.post(f'/api/feeds/{feed_id}/run',headers=headers)
        assert initial.json()['inserted']==3,initial.text
        rss=await client.get(f'/rss/{feed_id}.xml')
        assert rss.status_code==200
        nodes=ET.fromstring(rss.content).findall('./channel/item')
        assert len(nodes)==3
        assert all(n.findtext('link').startswith('https://research.example.org/report/') for n in nodes)
        original_guids={n.findtext('guid') for n in nodes}
        repeated=await client.post(f'/api/feeds/{feed_id}/run',headers=headers)
        assert repeated.json()['inserted']==0
        assert {n.findtext('guid') for n in ET.fromstring((await client.get(f'/rss/{feed_id}.xml')).content).findall('./channel/item')}==original_guids
        monkeypatch.setattr(server,'fetch',AsyncMock(side_effect=ValueError('Temporary outage')))
        failed=await client.post(f'/api/feeds/{feed_id}/run',headers=headers)
        assert failed.json()['status']=='error'
        assert len(ET.fromstring((await client.get(f'/rss/{feed_id}.xml')).content).findall('./channel/item'))==3
    db.close()
