"""Real Uvicorn HTTP + Chromium UI + SQLite backup/restart acceptance.
Uses explicitly labelled synthetic stored articles; it does not prove live fetch.
"""
from __future__ import annotations
import argparse,hashlib,json,os,secrets,socket,sqlite3,subprocess,sys,tempfile,time
from pathlib import Path
import httpx
import feedparser
from playwright.sync_api import sync_playwright
from openfeed.storage import Store
from tools.restore_backup import restore
from tools.browser_support import chromium_executable
ROOT=Path(__file__).resolve().parents[1]

def run(out):
    out.mkdir(parents=True,exist_ok=True);checks=[]
    def check(name,passed,detail=''):
        checks.append({'check':name,'passed':bool(passed),'detail':detail})
        (out/'results.json').write_text(json.dumps({'scope':'Real local HTTP/UI/backup. Stored content is synthetic, zero claim of institutional fetch or Reader cloud ingestion.','checks':checks},ensure_ascii=False,indent=2))
        assert passed,(name,detail)
    with tempfile.TemporaryDirectory(prefix='openfeed-http-') as tmp:
        tmp=Path(tmp);dbpath=tmp/'app.sqlite3';db=Store(str(dbpath))
        source=db.create({'title':'合成测试源 · Financial research fixture','source_url':'https://example.org/research','enabled':False,'recipe':{'mode':'css','item_selector':'article','fields':{'title':'h2','link':'a@href'}}})
        ident=source['id']
        articles=[{'title':f'Synthetic financial report {i}','url':f'https://example.org/reports/{i}','summary':'Synthetic acceptance fixture; not a live institution report.','published_at':'2026-10-20T00:00:00+00:00'} for i in range(3)]
        db.finish(db.get(ident),articles,None,1);db.close()
        token=secrets.token_urlsafe(32)
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        base=f'http://127.0.0.1:{port}';headers={'X-Admin-Token':token}
        env={**os.environ,'OPENFEED_DB':str(dbpath),'OPENFEED_ADMIN_TOKEN':token,'OPENFEED_PUBLIC_URL':base,'OPENFEED_ENABLE_SCHEDULER':'0','OPENFEED_FETCH_TIMEOUT':'3'}
        logfile=(out/'server.log').open('w');proc=None
        def start(database):
            nonlocal proc
            env['OPENFEED_DB']=str(database)
            proc=subprocess.Popen([sys.executable,'-m','uvicorn','openfeed.app:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=logfile,stderr=logfile)
            for _ in range(100):
                if proc.poll() is not None:raise RuntimeError('Uvicorn exited; inspect server.log')
                try:
                    if httpx.get(base+'/api/health',timeout=1).status_code==200:return
                except httpx.HTTPError:pass
                time.sleep(.1)
            raise RuntimeError('Server did not become healthy')
        def stop():
            if proc and proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=12)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
        try:
            start(dbpath)
            with httpx.Client(base_url=base,timeout=12) as client:
                check('Unauthenticated management denied',client.get('/api/feeds').status_code==401)
                rss=client.get(f'/rss/{ident}.xml');parsed=feedparser.parse(rss.content)
                check('Independent RSS parse',not parsed.bozo and len(parsed.entries)==3,str(len(parsed.entries)))
                check('RSS stable unique GUIDs',len({x.id for x in parsed.entries})==3)
                etag=rss.headers['etag']
                check('RSS conditional GET',client.get(f'/rss/{ident}.xml',headers={'If-None-Match':etag}).status_code==304)
                head=client.head(f'/rss/{ident}.xml');check('RSS HEAD',not head.content and head.headers['content-length']==str(len(rss.content)))
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path=chromium_executable(),headless=True)
                    try:
                        page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                        page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
                        page.goto(base);page.locator('#auth-token').fill(token);page.locator('#auth-form button').click()
                        page.locator('.feed-row').wait_for();page.screenshot(path=str(out/'01-overview.png'),full_page=True)
                        page.locator('#feed-search').fill('not-a-source');check('UI search removes unmatched sources',page.locator('.feed-row').count()==0)
                        page.locator('#feed-search').fill('Financial');page.locator('.feed-row').click()
                        page.locator('.diag-item').first.wait_for();check('UI shows stored article history',page.locator('.diag-item').count()==3)
                        page.screenshot(path=str(out/'02-editor.png'),full_page=True)
                        page.locator('#toggle-btn').click()
                        page.wait_for_function("() => document.getElementById('toggle-btn').textContent==='Pause source'")
                        check('UI resume persists',client.get('/api/feeds/'+ident,headers=headers).json()['feed']['enabled'])
                        page.locator('#toggle-btn').click()
                        page.wait_for_function("() => document.getElementById('toggle-btn').textContent==='Resume source'")
                        check('UI pause persists',not client.get('/api/feeds/'+ident,headers=headers).json()['feed']['enabled'])
                        # Change the title via real HTTP, then restore from the UI.
                        changed=client.patch('/api/feeds/'+ident,headers=headers,json={'title':'Temporary fixture revision'})
                        check('HTTP rule revision saved',changed.status_code==200)
                        page.locator('#close-drawer').click();page.reload();page.locator('.feed-row').click()
                        page.locator('[data-restore="1"]').wait_for();page.locator('[data-restore="1"]').click()
                        page.wait_for_function("() => document.getElementById('feed-title').value.includes('Financial research')")
                        check('UI history restore preserves RSS path',client.get('/api/feeds/'+ident,headers=headers).json()['feed']['title']==source['title'])
                        page.locator('#close-drawer').click();page.locator('#nav-import').click()
                        page.locator('[data-export="database"]').wait_for();page.screenshot(path=str(out/'03-backup.png'),full_page=True)
                        with page.expect_download() as download:page.locator('[data-export="database"]').click()
                        backup=tmp/'download.sqlite3';download.value.save_as(backup)
                        check('UI database download is SQLite',backup.read_bytes().startswith(b'SQLite format 3'))
                        with sqlite3.connect(backup) as con:check('Downloaded backup integrity',con.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
                        page.locator('#migration-close').click();page.set_viewport_size({'width':390,'height':844});page.wait_for_function("() => document.querySelectorAll('.toast').length===0");page.screenshot(path=str(out/'04-mobile.png'),full_page=True)
                        check('Mobile metadata hidden',page.locator('.feed-row .meta-cell:visible').count()==0)
                        check('Mobile page fits viewport',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
                        check('No uncaught browser errors',not errors,str(errors))
                    finally:browser.close()
                saved=client.get(f'/rss/{ident}.xml').content
                (out/'synthetic-rss.xml').write_bytes(saved)
                opml=client.get('/api/export/opml',headers=headers);(out/'synthetic.opml').write_bytes(opml.content)
                check('OPML export includes stable RSS URL',f'/rss/{ident}.xml'.encode() in opml.content)
            stop()
            restored=tmp/'restored.sqlite3';report=restore(backup,restored)
            check('Offline restore preserves feeds and items',report['feeds']==1 and report['items']==3)
            start(restored)
            restored_rss=httpx.get(base+f'/rss/{ident}.xml').content
            check('HTTP RSS byte-identical after restored restart',saved==restored_rss,hashlib.sha256(saved).hexdigest())
        finally:stop();logfile.close()
    print(json.dumps({'passed':sum(x['passed'] for x in checks),'total':len(checks),'output':str(out)},ensure_ascii=False))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();run(Path(args.output).resolve())
