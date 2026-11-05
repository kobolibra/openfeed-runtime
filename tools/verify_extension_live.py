"""Interactive MV3 fixture acceptance. Use the real Chromium toolbar action and
click article/fields; this waits for actual chrome.tabs.create handoff to Studio.
The source page is a labelled synthetic route, not a live institutional source.
"""
from __future__ import annotations
import argparse,json,os,secrets,socket,subprocess,sys,tempfile,time
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright
from tools.browser_support import chromium_executable
ROOT=Path(__file__).resolve().parents[1]
HTML='''<!doctype html><html><head><title>Synthetic OpenFeed Extension Acceptance</title><style>body{font:20px system-ui;padding:70px}article{padding:15px;border:1px solid #aaa;margin:20px}h2{font-size:24px}a{color:#165e46}time{font-size:18px}</style></head><body><h1>Synthetic extension fixture · 非真实站点</h1><p>Click an article, then Title, URL and Date using the extension.</p>'''+''.join(f'<article class="research-card"><h2><a href="/report/{i}">Synthetic research report {i}</a></h2><time datetime="2026-10-20">20 October 2026</time><p>Fixture summary {i}.</p></article>' for i in range(1,4))+'''</body></html>'''
def main(out):
 out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='openfeed-mv3-') as tmp:
  tmp=Path(tmp);token=secrets.token_urlsafe(32)
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  base=f'http://127.0.0.1:{port}'
  env={**os.environ,'OPENFEED_DB':str(tmp/'app.sqlite3'),'OPENFEED_ADMIN_TOKEN':token,'OPENFEED_PUBLIC_URL':base,'OPENFEED_ENABLE_SCHEDULER':'0'}
  log=(out/'server.log').open('w');server=subprocess.Popen([sys.executable,'-m','uvicorn','openfeed.app:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
  try:
   for _ in range(100):
    try:
     if httpx.get(base+'/api/health',timeout=1).status_code==200:break
    except httpx.HTTPError:pass
    time.sleep(.1)
   with sync_playwright() as p:
    context=p.chromium.launch_persistent_context(str(tmp/'profile'),executable_path=chromium_executable(),headless=False,viewport={'width':1280,'height':850},args=[f'--disable-extensions-except={ROOT/"extension"}',f'--load-extension={ROOT/"extension"}'])
    try:
     sw=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
     studio=context.new_page();studio.goto(base);studio.locator('#auth-token').fill(token);studio.locator('#auth-form button').click();studio.locator('#auth-overlay').wait_for(state='hidden')
     fixture=context.new_page();fixture.route('https://openfeed-fixture.example/**',lambda route:route.fulfill(status=200,content_type='text/html',body=HTML));fixture.goto('https://openfeed-fixture.example/insights');fixture.bring_to_front()
     # Set destination only; selection, activeTab grant and handoff remain real.
     sw.evaluate('(url)=>chrome.storage.local.set({studioUrl:url})',base)
     (out/'ready.json').write_text(json.dumps({'status':'ready_for_toolbar','studio':base,'extension':sw.url,'source_fixture':'synthetic routed HTML; no institutional request'},indent=2))
     print('READY: activate OpenFeed extension from Chromium toolbar, select card/title/link/date, then Open in Studio',flush=True)
     deadline=time.monotonic()+240
     while time.monotonic()<deadline:
      for page in context.pages:
       if page.url.startswith(base+'/#import-picker=') or (page!=studio and page.url.startswith(base)):
        page.locator('#item-selector').wait_for(timeout=15000)
        page.wait_for_function("() => document.getElementById('item-selector').value.length>0")
        fields={k:page.locator('#'+v).input_value() for k,v in [('url','src-url'),('item','item-selector'),('title','title-selector'),('link','link-selector'),('date','date-selector')]}
        assert all(fields.values()),fields
        assert fields['url']=='https://openfeed-fixture.example/insights'
        selection=sw.evaluate('async()=> (await chrome.storage.session.get("lastSelection")).lastSelection')
        assert selection['coverage']['total']==3
        assert selection['coverage']['fields']=={'title':3,'link':3,'date':3}
        page.screenshot(path=str(out/'studio-import.png'),full_page=True)
        fixture.screenshot(path=str(out/'selected-fixture.png'),full_page=True)
        result={'status':'passed','scope':'Installed real MV3, actual activeTab toolbar activation, content clicks, runtime messaging, storage, tabs.create and real HTTP Studio import; synthetic source HTML only.','selection':selection,'imported_fields':fields}
        (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('PASS: real MV3 selection and handoff',flush=True);return
      fixture.wait_for_timeout(300)
     raise TimeoutError('No completed extension handoff in 240 seconds')
    finally:context.close()
  finally:
   server.terminate()
   try:server.wait(timeout=10)
   except subprocess.TimeoutExpired:server.kill();server.wait()
   log.close()
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();main(Path(args.output).resolve())
