"""Serve the real-capture SQLite snapshot through Uvicorn and validate each RSS."""
from __future__ import annotations
import argparse,json,os,secrets,shutil,socket,subprocess,sys,tempfile,time
from pathlib import Path
import httpx,feedparser
ROOT=Path(__file__).resolve().parents[1]
def run(snapshot,out):
 out.mkdir(parents=True,exist_ok=True);checks=[]
 with tempfile.TemporaryDirectory(prefix='of-actual-rss-') as tmp:
  db=Path(tmp)/'app.sqlite3';shutil.copyfile(snapshot,db)
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  base=f'http://127.0.0.1:{port}';token=secrets.token_urlsafe(32)
  env={**os.environ,'OPENFEED_DB':str(db),'OPENFEED_ADMIN_TOKEN':token,'OPENFEED_PUBLIC_URL':base,'OPENFEED_ENABLE_SCHEDULER':'0'}
  with (out/'server.log').open('w') as log:
   process=subprocess.Popen([sys.executable,'-m','uvicorn','openfeed.app:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=log)
   try:
    for _ in range(100):
     try:
      if httpx.get(base+'/api/health',timeout=1).status_code==200:break
     except httpx.HTTPError:pass
     time.sleep(.1)
    with httpx.Client(base_url=base) as c:
     feeds=c.get('/api/feeds',headers={'X-Admin-Token':token}).json()
     assert len(feeds)==6
     for f in feeds:
      r=c.get('/rss/'+f['id']+'.xml');parsed=feedparser.parse(r.content)
      assert r.status_code==200 and not parsed.bozo and len(parsed.entries)==f['item_count']
      assert len({e.id for e in parsed.entries})==f['item_count']
      assert c.get('/rss/'+f['id']+'.xml',headers={'If-None-Match':r.headers['etag']}).status_code==304
      checks.append({'title':f['title'],'items':len(parsed.entries),'rss_http_200':True,'independent_parser_ok':True,'unique_guids':True,'etag_304':True,'paused':not f['enabled']})
     assert sum(x['items'] for x in checks)==111
   finally:
    process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill();process.wait()
 (out/'results.json').write_text(json.dumps({'scope':'Real page captures -> original extraction/store -> actual Uvicorn HTTP RSS; no claim of default protected live refresh or Readwise cloud ingest.','feeds':checks,'total_items':111},ensure_ascii=False,indent=2));print('PASS: six real-capture feeds, 111 items, actual HTTP RSS/unique GUIDs/ETag')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(Path(a.snapshot),Path(a.output))
