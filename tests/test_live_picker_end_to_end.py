from tools.browser_support import chromium_executable
"""Chromium end-to-end test of live page selection and import to Studio.
The Chrome API is emulated at the extension boundary; this does not assert that
Chrome installs/starts a Manifest V3 service worker successfully.
"""
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def test_live_picker_to_studio_import():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=chromium_executable(), args=['--no-sandbox'])
        page = browser.new_page()
        page.set_content('''<html><head><title>Test Research</title></head><body><main>
          <article class="research-card"><h2><a href="/one">Report number one with details</a></h2><time datetime="2026-10-20">20 Oct</time></article>
          <article class="research-card"><h2><a href="/two">Report number two with details</a></h2><time datetime="2026-10-19">19 Oct</time></article>
          <article class="research-card"><h2><a href="/three">Report number three with details</a></h2><time datetime="2026-10-18">18 Oct</time></article>
          </main></body></html>''')
        page.evaluate('''() => {
          window.__messages=[];
          window.chrome={runtime:{onMessage:{addListener(fn){window.__listener=fn}},sendMessage(msg){window.__messages.push(msg)}}};
        }''')
        page.add_script_tag(path=str(ROOT / 'extension/picker.js'))
        page.add_script_tag(path=str(ROOT / 'extension/content.js'))
        page.locator('article').first.click()
        for field, selector in [('title','h2'),('link','h2 a'),('date','time')]:
            page.evaluate('(f) => window.__listener({type:"SET_FIELD",field:f},null,()=>{})', field)
            page.locator('article').first.locator(selector).click()
        selection=page.evaluate('window.__messages.at(-1).selection')
        assert selection['coverage']['total']==3
        assert selection['coverage']['fields']=={'title':3,'link':3,'date':3}
        assert selection['fields']['link'].endswith('@href')
        assert selection['fields']['date'].endswith('@datetime')
        assert page.locator('.of-match').count()==3
        assert page.locator('.of-field-match').count()>=3
        studio = browser.new_page()
        import json
        selection['url']='https://research.example.com/insights'
        studio.set_content((ROOT / 'static/index.html').read_text())
        studio.evaluate('(hash) => location.hash = hash', '#import-picker=' + quote(json.dumps(selection), safe=''))
        studio.evaluate("""() => { const store={};Object.defineProperty(window,'sessionStorage',{configurable:true,value:{getItem:k=>store[k]||null,setItem:(k,v)=>store[k]=v,removeItem:k=>delete store[k]}}); }""")
        studio.add_script_tag(path=str(ROOT / 'static/picker.js'))
        studio.add_script_tag(path=str(ROOT / 'static/app.js'))
        studio.wait_for_timeout(150)
        assert studio.locator('#src-url').input_value() == selection['url']
        assert studio.locator('#item-selector').input_value() == selection['item_selector']
        assert studio.locator('#title-selector').input_value() == selection['fields']['title']
        assert studio.locator('#link-selector').input_value() == selection['fields']['link']
        assert studio.locator('#date-selector').input_value() == selection['fields']['date']
        browser.close()
