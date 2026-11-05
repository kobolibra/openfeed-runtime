from tools.browser_support import chromium_executable
"""v0.3 engineering regression: selector quality, atomic migration and browser UI."""
import os
import shutil
import sqlite3
import socket
import threading
import time
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import uvicorn
from openfeed.extract import infer_candidates, extract_articles
from openfeed.storage import Store
from openfeed.browser import browser_fetch
import openfeed.app as server

CONTENT = '''<!doctype html><html><head><title>Research archive</title></head><body>
<nav><ul><li><a href="/home">Home and company overview corporate</a></li><li><a href="/about">About us and our company culture</a></li></ul></nav>
<main><div class="research-list">'''+''.join(f'''<article class="research-card"><h2><a href="/research/{i}">Macro research report number {i} — inflation and monetary policy</a></h2><time datetime="2026-10-2{i}">Oct 2{i}</time><p>Original research in global finance and economies.</p></article>''' for i in range(1,5))+'''</div></main><script>window.x=1</script></body></html>'''


def test_repeated_container_ranking_and_extraction():
    options=infer_candidates(CONTENT)
    assert options and options[0]['selector']=='main article.research-card'
    assert options[0]['count']==4
    items,_=extract_articles(CONTENT,'https://example.com/research',{'mode':'css','item_selector':options[0]['selector'],'fields':{'title':'h2 a','link':'a@href','date':'time'}})
    assert len(items)==4
    assert items[0]['published_at'].startswith('2026-10-21')


def test_atomic_bundle_and_online_backup(tmp_path):
    db=Store(str(tmp_path/'db.sqlite3'))
    one={'title':'Real research','source_url':'https://example.com/research','recipe':{}}
    two={'title':'Bad ID','source_url':'https://example.org/research','recipe':{},'id':'INVALID'}
    with pytest.raises(ValueError): db.create_many([one,two])
    assert not db.list(), 'Import must roll back earlier rows on an error'
    n,skip=db.create_many([one,one])
    assert (n,skip)==(1,1)
    f=db.list()[0]
    db.finish(f,[{'title':'Original article','url':'https://example.com/research/1','summary':'text','published_at':None}],None,11)
    backup=tmp_path/'backup.sqlite3'
    db.backup_to(str(backup))
    with sqlite3.connect(backup) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert con.execute('SELECT COUNT(*) FROM items').fetchone()[0]==1
    db.close()


@pytest.mark.asyncio
async def test_database_export_and_browser_gating(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'e2e.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','secret-key')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://test') as client:
        assert (await client.get('/api/export/database')).status_code==401
        result=await client.get('/api/export/database',headers={'X-Admin-Token':'secret-key'})
        assert result.status_code==200 and result.content.startswith(b'SQLite format 3')
    monkeypatch.delenv('OPENFEED_EXPERIMENTAL_BROWSER',raising=False)
    with pytest.raises(ValueError,match='disabled'):
        await browser_fetch('https://example.com')
    db.close()


def test_chromium_picker_real_dom(tmp_path):
    if not chromium_executable():
        pytest.skip('Chromium not installed')
    playwright = pytest.importorskip('playwright.sync_api')
    with playwright.sync_playwright() as p:
        browser=p.chromium.launch(executable_path=chromium_executable(),args=['--no-sandbox'],headless=True)
        page=browser.new_page()
        page.set_content(CONTENT)
        page.add_script_tag(path=str(Path(__file__).parents[1]/'static'/'picker.js'))
        r=page.evaluate('''() => {
            const doc=document, title=doc.querySelector('article h2 a');
            const item=OpenFeedPicker.chooseItem(title,doc);
            return {selector:item.selector,count:item.count,
               title:OpenFeedPicker.chooseField(title,'title',item.selector,doc),
               link:OpenFeedPicker.chooseField(title,'link',item.selector,doc),
               date:OpenFeedPicker.chooseField(doc.querySelector('article time'),'date',item.selector,doc)};
        }''')
        assert r['selector']=='main article.research-card'
        assert r['count']==4 and r['link']['selector'].endswith('@href')
        assert r['date']['count']==4
        browser.close()


@pytest.mark.asyncio
async def test_web_ui_full_browser_flow(monkeypatch,tmp_path):
    """Real Chromium UI bridged to real FastAPI ASGI in offline environment."""
    if not chromium_executable():
        pytest.skip('Chromium not installed')
    pytest.importorskip('playwright.async_api')
    from playwright.async_api import async_playwright
    db=Store(str(tmp_path/'web.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','browser-e2e-key')
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    monkeypatch.setattr(server,'fetch',AsyncMock(return_value=('https://example.com/research',CONTENT.encode(),'utf-8')))
    html=(Path(__file__).parents[1]/'static'/'index.html').read_text()
    # Chromium cannot navigate even localhost in this restricted execution environment.
    # Use the REAL UI code in Chromium and a transparent ASGI transport bridge.
    html=html.replace('<link rel="stylesheet" href="/static/styles.css">','').replace('<script defer src="/static/picker.js"></script>','').replace('<script defer src="/static/app.js"></script>','')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://example.test') as client:
        async def request_bridge(path,options):
            response=await client.request(options.get('method','GET'),path,headers=options.get('headers',{}),content=options.get('body'))
            return {'status':response.status_code,'body':response.text,'headers':dict(response.headers)}
        async with async_playwright() as p:
            browser=await p.chromium.launch(executable_path=chromium_executable(),args=['--no-sandbox'],headless=True)
            page=await browser.new_page(viewport={'width':1440,'height':950})
            errors=[]
            page.on('pageerror',lambda error: errors.append(str(error)))
            await page.expose_function('asgiBridge',request_bridge)
            await page.set_content(html)
            await page.add_style_tag(path=str(Path(__file__).parents[1]/'static'/'styles.css'))
            await page.evaluate('''() => {
              window.fetch = async (path, options={}) => {
                const result=await window.asgiBridge(path,options);
                return new Response(result.body,{status:result.status,headers:result.headers});
              };
            }''')
            await page.add_script_tag(path=str(Path(__file__).parents[1]/'static'/'picker.js'))
            app_js=(Path(__file__).parents[1]/'static'/'app.js').read_text().replace("storage.getItem('openfeed-token') || ''","'browser-e2e-key'")
            await page.add_script_tag(content=app_js)
            await page.locator('[data-action="create"]').first.click()
            await page.locator('#src-url').fill('https://example.com/research')
            await page.locator('#feed-title').fill('Institutional Research Monitor')
            await page.locator('#test-btn').click()
            await page.locator('.preview-item').first.wait_for(timeout=9000)
            assert await page.locator('.preview-item').count()==4
            assert await page.locator('.candidate-choice').count()>=1
            await page.locator('#visual-btn').click()
            frame=page.frame_locator('#snapshot')
            await frame.locator('article h2 a').first.click()
            assert await page.locator('#item-selector').input_value()=='main article.research-card'
            await page.locator('[data-field="link"]').click()
            await frame.locator('article h2 a').first.click()
            assert (await page.locator('#link-selector').input_value()).endswith('@href')
            await page.locator('#inspector-close').click()
            await page.locator('#next-selector').fill('.pagination-next')
            await page.locator('#max-pages').select_option('2')
            await page.locator('#save-btn').click()
            await page.locator('#publish-result:not(.hidden)').wait_for(timeout=9000)
            assert 'rss/' in await page.locator('#created-link').input_value()
            assert db.list()[0]['recipe']['max_pages']==2
            await page.locator('[data-restore="1"]').wait_for(timeout=9000)
            # A bad saved selector remains recoverable from the UI revision timeline.
            await page.locator('#title-selector').fill('h1')
            await page.locator('#save-btn').click()
            await page.locator('[data-restore="1"]:not([disabled])').wait_for(timeout=9000)
            page.once('dialog',lambda dialog: dialog.accept())
            await page.locator('[data-restore="1"]').click()
            await page.wait_for_function('''() => document.querySelector('#title-selector')?.value === '' ''')
            assert db.list()[0]['recipe']['fields'].get('title') is None
            assert len(db.entries(db.list()[0]['id']))==4
            await page.screenshot(path=str(tmp_path/'openfeed-web-e2e.png'),full_page=True)
            assert not errors,errors
            await browser.close()
    assert db.stats()['items']==4
    db.close()


def test_playwright_executes_dynamic_dom_with_offline_fixture():
    """Chromium renders scripted content; no claim of external-site connectivity."""
    if not chromium_executable():
        pytest.skip('Chromium not installed')
    playwright = pytest.importorskip('playwright.sync_api')
    source='''<html><main id="results"></main><script>
    document.querySelector('#results').innerHTML = Array.from({length:3},(_,i)=>
    `<article><h2><a href="/dynamic/${i}">Dynamic institutional report ${i}</a></h2><p>Analysis of interest rates and economic outlook</p></article>`).join('')
    </script></html>'''
    with pytest.raises(ValueError):
        extract_articles(source,'https://example.com/dynamic',{})
    with playwright.sync_playwright() as p:
        browser=p.chromium.launch(executable_path=chromium_executable(),args=['--no-sandbox'])
        page=browser.new_page()
        page.set_content(source)
        page.locator('article').first.wait_for()
        dynamic,_=extract_articles(page.content(),'https://example.com/dynamic',{})
        assert len(dynamic)==3
        assert dynamic[1]['url']=='https://example.com/dynamic/1'
        browser.close()


def test_generic_card_auto_detection_not_only_article_tags():
    html='<main><div class="list">'+''.join(
        f'<div class="insight-card"><h3><a href="/insights/{i}">Investment perspective on global inflation and the dollar {i}</a></h3><p>Macro and asset allocation strategy</p></div>'
        for i in range(6))+'</div></main>'
    items, selector=extract_articles(html,'https://example.com/insights',{})
    assert selector=='main div.insight-card'
    assert len(items)==6


def test_selector_inference_bounded_on_large_static_dom():
    import time
    html='<main><div class="list">'+''.join(
        f'<div class="card"><h3><a href="/r/{i}">Institutional research outlook with inflation and rates {i}</a></h3></div>'
        for i in range(250))+'</div></main>'
    t0=time.monotonic()
    result=infer_candidates(html)
    elapsed=time.monotonic()-t0
    assert result and result[0]['selector']=='main div.card'
    assert elapsed<10, 'Selector analysis should not explode on larger DOMs'
