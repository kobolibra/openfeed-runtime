"""Verify reviewed recipes online twice, then incrementally save and run via API.
No database replacement, cached network body, or speculative placeholder import.
"""
from __future__ import annotations
import asyncio,argparse,json,hashlib,time
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit
import httpx,feedparser
from bs4 import BeautifulSoup
from openfeed.security import fetch
from openfeed.extract import extract_articles,parse_native,canonical_link,render_rss,guid_for,response_html
from openfeed.quality import validate_items

async def run(profiles,research,out,token_file):
 out.mkdir(parents=True,exist_ok=True);locks={};last={};slots=asyncio.Semaphore(4)
 token=token_file.read_text().strip(); api_domain_locks={}
 async def run_saved(api,ident,url):
  async with api_domain_locks.setdefault(urlsplit(url).netloc,asyncio.Lock()):
   for attempt in range(5):
    reply=await api.post(f"/api/feeds/{ident}/run");reply.raise_for_status();outcome=reply.json()
    if outcome.get("status")!="rate_limited":return outcome
    await asyncio.sleep(outcome.get("retry_after",61)+1)
   raise ValueError("Saved refresh still rate limited after retries")
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8765',headers={'X-Admin-Token':token},timeout=90,trust_env=False) as api:
  current=(await api.get('/api/feeds'));current.raise_for_status();existing=current.json(); save_lock=asyncio.Lock()
  async def save_profile(p,payload):
   async with save_lock:
    reply=await api.get('/api/feeds');reply.raise_for_status();latest=reply.json()
    matches=[f for f in latest if f['source_url'] in (payload['source_url'],p['original_url']) or f.get('id')==p.get('existing_id','')]
    if len(matches)>1:raise ValueError('Ambiguous existing source, refusing duplicate')
    if matches:reply=await api.patch('/api/feeds/'+matches[0]['id'],json=payload)
    else:reply=await api.post('/api/feeds',json=payload)
    reply.raise_for_status();return reply.json()['id']
  async def paced(url,recipe,gap=2):
   host=urlsplit(url).netloc
   async with locks.setdefault(host,asyncio.Lock()):
    await asyncio.sleep(max(0,gap-(time.monotonic()-last.get(host,-1e9))))
    last[host]=time.monotonic();return await fetch(url,**{**({'method':'POST','data':recipe.get('request_data',{})} if recipe.get('request_method')=='POST' else {}),**({'public_api_key':recipe['public_api_key']} if recipe.get('public_api_key') else {})})
  async def one(p):
   n=p['index'];path=out/f'{n:03d}';path.mkdir(exist_ok=True)
   if (path/'result.json').exists():
    old=json.loads((path/'result.json').read_text())
    if old.get('status')=='passed' and old.get('profile')==p:return old
   record={'index':n,'original_url':p['original_url'],'profile':p,'started_at':datetime.now(timezone.utc).isoformat(),'fetches':[]}
   async with slots:
    try:
     source=json.loads((research/f'{n:03d}/record.json').read_text())
     if source['status']!='captured_requires_review':raise ValueError('Original URL has no reviewed successful public capture')
     url=p.get('source_url',p['original_url']);recipe=p['recipe'];all_items=[]
     for turn in (1,2):
      final,raw,enc=await paced(url,recipe,p.get('crawl_delay_seconds',2));(path/f'fetch-{turn}.body').write_bytes(raw)
      text=raw.decode(enc,errors='replace')
      items=parse_native(raw,final) if p.get('kind')=='native' else extract_articles(text,final,recipe)[0]
      items,quality=validate_items(items)
      if not items or quality['rejected']:raise ValueError('Empty or rejected records: '+str(quality))
      if len(items)<p.get('minimum',1):raise ValueError('Below reviewed minimum')
      prefixes=p.get('article_prefixes',[])
      if prefixes and not all(any(x['url'].startswith(prefix) for prefix in prefixes) for x in items):raise ValueError('Article URL left reviewed scope')
      if p.get('kind')!='native' and recipe.get('mode')!='json':
       doc=BeautifulSoup(response_html(text,recipe),'lxml');anchors={canonical_link(a['href'],final,keep_fragment=bool(recipe.get('keep_fragments'))) for a in doc.select('a[href]')}
       if recipe.get('keep_fragments'):
        anchors.update(final.split('#')[0]+'#'+str(el['id']) for el in doc.select('[id]'))
       if not all(x['url'] in anchors for x in items):raise ValueError('Extracted URL not backed by source anchor')
      xml=render_rss({'title':p['title'],'source_url':url,'description':p.get('scope','')},[{**x,'guid':guid_for(x['url'])} for x in items],'http://localhost:8765/verification.xml')
      parsed=feedparser.parse(xml)
      if parsed.bozo or {e.link for e in parsed.entries}!={x['url'] for x in items}:raise ValueError('Independent RSS parse failed')
      (path/f'fetch-{turn}.xml').write_bytes(xml)
      record['fetches'].append({'at':datetime.now(timezone.utc).isoformat(),'final_url':final,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'items':len(items),'dated':sum(bool(x.get('published_at')) for x in items),'quality':quality,'samples':items[:5],'rss_parse_valid':True})
      all_items.append(items)
      if turn==1:await asyncio.sleep(3)
     first={x['url'] for x in all_items[0]};second={x['url'] for x in all_items[1]}
     record['repeat_overlap']=len(first&second);record['repeat_same_urls']=first==second
     if not first&second:raise ValueError('No article identity overlap in independent captures')
     matches=[f for f in existing if f['source_url'] in (url,p['original_url']) or f.get('id')==p.get('existing_id','')]
     if len(matches)>1:raise ValueError('Ambiguous existing source, refusing duplicate')
     cfg={**recipe,'min_items':max(1,p.get('minimum',1))}
     payload={'title':p['title'],'source_url':url,'description':p.get('scope','')[:500],'kind':p.get('kind','web'),'recipe':cfg,'interval_minutes':p.get('interval_minutes',360),'enabled':False}
     ident=await save_profile(p,payload);record['feed_id']=ident
     if p.get('crawl_delay_seconds'):await asyncio.sleep(p['crawl_delay_seconds'])
     outcome=await run_saved(api,ident,url)
     record['saved_refresh']=outcome
     detail=(await api.get('/api/feeds/'+ident)).json();record['saved_status']=detail['feed']['status']
     if detail['feed']['last_error'] or not detail['items']:raise ValueError('Saved real refresh failed: '+str(detail['feed']['last_error']))
     rss=await api.get(f'/rss/{ident}.xml');rss.raise_for_status();(path/'saved-rss.xml').write_bytes(rss.content)
     parsed=feedparser.parse(rss.content)
     if parsed.bozo or not parsed.entries:raise ValueError('Saved HTTP RSS invalid')
     record['saved_rss']={'entries':len(parsed.entries),'valid':True,'url':f'http://localhost:8765/rss/{ident}.xml'}
     enabled=await api.patch('/api/feeds/'+ident,json={'enabled':True});enabled.raise_for_status()
     record['status']='passed';record['enabled']=True
    except Exception as e:record.update(status='failed',error=f'{type(e).__name__}: {e}')
   record['finished_at']=datetime.now(timezone.utc).isoformat();(path/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
   print(n,record['status'],p['title'],record.get('error',''),flush=True);return record
  rows=await asyncio.gather(*(one(p) for p in json.loads(profiles.read_text())))
  (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--profiles',type=Path,required=True);p.add_argument('--research',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--token-file',type=Path,required=True);a=p.parse_args();asyncio.run(run(a.profiles,a.research,a.output,a.token_file))
