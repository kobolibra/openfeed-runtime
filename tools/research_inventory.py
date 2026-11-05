"""Capture each inventory URL through OpenFeed's protected transport.
Per-origin pacing and robots checking; resumable per-URL evidence, no DB writes.
Heuristic recipes are research suggestions and require explicit review.
"""
from __future__ import annotations
import asyncio,hashlib,json,time,argparse
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from openfeed.security import fetch,USER_AGENT,UpstreamHTTPError
from openfeed.extract import discover,infer_candidates,extract_articles,parse_native
from openfeed.quality import validate_items

async def run(inventory:Path,out:Path,retry_failed=False):
 out.mkdir(parents=True,exist_ok=True)
 limits=asyncio.Semaphore(6); locks={};robots={};last={};delays={}
 async def polite(url):
  origin=f'{urlsplit(url).scheme}://{urlsplit(url).netloc}'
  lock=locks.setdefault(origin,asyncio.Lock())
  async with lock:
   await asyncio.sleep(max(0,delays.get(origin,2)-(time.monotonic()-last.get(origin,-1e9))))
   last[origin]=time.monotonic()
   return await fetch(url)
 async def allowed(url):
  origin=f'{urlsplit(url).scheme}://{urlsplit(url).netloc}'
  if origin not in robots:
   async def get():
    try:
     final,raw,enc=await polite(origin+'/robots.txt')
     parser=RobotFileParser();parser.parse(raw.decode(enc,errors='replace').splitlines())
     delays[origin]=max(2,parser.crawl_delay(USER_AGENT) or parser.crawl_delay('*') or 0)
     fn=hashlib.sha256(origin.encode()).hexdigest()[:16]+'-robots.txt';(out/fn).write_bytes(raw)
     return parser,{'policy':'rules_available','url':origin+'/robots.txt','evidence':fn,'sha256':hashlib.sha256(raw).hexdigest()}
    except UpstreamHTTPError as e:
     # RFC 9309 2.3.1.3: a 4xx robots response means unavailable,
     # not a Disallow rule. 429 remains a temporary stop to respect limits.
     allowed=400<=e.status<500 and e.status!=429
     return None,{'error':str(e),'http_status':e.status,'policy':'unavailable_no_rules' if allowed else 'temporarily_unreachable','allow_without_file':allowed}
    except Exception as e:
     return None,{'error':str(e),'policy':'unreachable','allow_without_file':False}
   robots[origin]=asyncio.create_task(get())
  parser,record=await robots[origin]
  return parser.can_fetch(USER_AGENT,url) if parser else record.get('allow_without_file',False),record
 async def one(row):
  n=row['index'];p=out/f'{n:03d}';p.mkdir(exist_ok=True)
  if (p/'record.json').exists():
   previous=json.loads((p/'record.json').read_text())
   if not retry_failed or previous.get('status') not in ('fetch_failed','robots_disallowed_or_unavailable','robots_disallowed','robots_unreachable'):
    return previous
   (p/'record.json').rename(p/('prior-attempt-'+str(time.time_ns())+'.json'))
  result={**row,'started_at':datetime.now(timezone.utc).isoformat(),'transport':'OpenFeed protected fetch; secure DNS; TLS verification; vetted socket IP'}
  async with limits:
   try:
    ok,result['robots']=await allowed(row['normalized_url'])
    if not ok:
     result['status']='robots_disallowed' if result['robots'].get('policy')=='rules_available' else 'robots_unreachable'
    else:
     final,raw,enc=await polite(row['normalized_url']);(p/'source.html').write_bytes(raw)
     result.update(final_url=final,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),encoding=enc)
     text=raw.decode(enc,errors='replace');doc=BeautifulSoup(text,'lxml')
     result['page_title']=doc.title.get_text(' ',strip=True) if doc.title else ''
     result['heading_samples']=[x.get_text(' ',strip=True)[:180] for x in doc.select('main h1,main h2,main h3')[:15]]
     lower=text.lower()
     if any(x in lower for x in ('verify you are human','captcha/dispatch','checking your browser','access to this page has been denied')) or 'safe.liepin.com' in final:
      result['status']='access_challenge'
     else:
      result['discovered_feeds']=discover(text,final)
      try:
       native=parse_native(raw,final)
       if native:result['native_items']=native
      except Exception:pass
      candidates=infer_candidates(text,limit=5);result['candidates']=candidates
      for candidate in candidates:
       cfg={'mode':'css','item_selector':candidate['selector'],'fields':candidate['fields']}
       try:
        items,_=extract_articles(text,final,cfg);items,q=validate_items(items)
        candidate.update(recipe=cfg,items=items,quality=q)
       except Exception as e:candidate['error']=str(e)
      result['status']='captured_requires_review'
   except Exception as e:result.update(status='fetch_failed',error=f'{type(e).__name__}: {e}',http_status=getattr(e,'status',None))
  result['finished_at']=datetime.now(timezone.utc).isoformat()
  (p/'record.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
  print(n,result['status'],result.get('page_title','')[:70],result.get('error',''),flush=True)
  return result
 rows=await asyncio.gather(*(one(row) for row in json.loads(inventory.read_text())['urls']))
 (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inventory',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--retry-failed',action='store_true');a=p.parse_args();asyncio.run(run(a.inventory,a.output,a.retry_failed))
