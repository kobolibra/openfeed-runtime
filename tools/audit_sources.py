"""Read-only, bounded production-source audit. Does NOT create/alter feeds.

Usage: PYTHONPATH=. python tools/audit_sources.py --input tools/pilot-sources.csv \
         --output /tmp/openfeed-source-audit.json --limit 20

Statuses distinguish connectivity, valid native-feed discovery, usable article
extraction and unresolved requirements; no automatic claim of RSS readiness.
"""
from __future__ import annotations
import argparse
import asyncio
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from openfeed.security import fetch
from openfeed.extract import discover, extract_articles, infer_candidates, parse_native
from openfeed.quality import validate_items

async def audit_one(row:dict, fetcher=fetch)->dict:
    start=time.monotonic()
    result={'name':row.get('name',''), 'url':row['source_url'],
            'kind':row.get('type',''), 'strategy':row.get('proposed_strategy',''),
            'status':'unverified', 'valid_items':0, 'candidates':[], 'discovered_feeds':[], 'warnings':[]}
    try:
        target,body,encoding=await fetcher(row['source_url'])
        result['resolved_url']=target
        content=body.decode(encoding,errors='replace')
        if body.lstrip().startswith((b'<?xml',b'{')) or '<rss' in content[:500] or '<feed' in content[:500]:
            items=parse_native(body,target)
            valid,report=validate_items(items)
            result.update(status='native_feed' if valid else 'empty_native_feed', valid_items=len(valid),quality=report)
        else:
            result['discovered_feeds']=discover(content,target)
            result['candidates']=infer_candidates(content,limit=3)
            try:
                items,selector=extract_articles(content,target,{'mode':'css'})
                valid,report=validate_items(items)
                result.update(valid_items=len(valid),proposed_selector=selector,quality=report)
                result['status']='candidate_requires_review' if valid else 'no_items'
                if valid and all(not item.get('published_at') for item in valid):
                    result['warnings'].append('publication_dates_not_found')
            except Exception as e:
                result['status']='needs_manual_or_dynamic_inspection'
                result['warnings'].append(type(e).__name__+': '+str(e)[:180])
            if result['discovered_feeds']:
                result['warnings'].append('check_native_feed_before_creating_custom_rule')
    except Exception as e:
        result['status']='fetch_failed'
        result['warnings'].append(type(e).__name__+': '+str(e)[:180])
    result['elapsed_ms']=int((time.monotonic()-start)*1000)
    return result

async def run(rows:list[dict], concurrency:int=2)->list[dict]:
    sem=asyncio.Semaphore(max(1,min(concurrency,3)))
    async def wrapped(row):
        async with sem:
            return await audit_one(row)
    return list(await asyncio.gather(*(wrapped(r) for r in rows)))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',default='tools/pilot-sources.csv')
    p.add_argument('--output',default='source-audit.json')
    p.add_argument('--limit',type=int,default=20)
    args=p.parse_args()
    with open(args.input,encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))[:max(1,min(args.limit,300))]
    results=asyncio.run(run(rows))
    payload={'generated_utc':datetime.now(timezone.utc).isoformat(),
             'verified_live':sum(r['status'] not in ('fetch_failed','unverified') for r in results),
             'complete_rss_feeds_proven':0,
             'note':'Candidate extraction is not proof of stable RSS: review each site and run recurring tests.',
             'results':results}
    Path(args.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'checked':len(results),'connected':payload['verified_live'],
                      'failed':sum(r['status']=='fetch_failed' for r in results),
                      'output':args.output},ensure_ascii=False))

if __name__=='__main__': main()
