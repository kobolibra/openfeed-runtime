"""Bounded live-source evidence capture using the application's real HTTP client.
Honors robots rules; stops at login, challenge or investor qualification gates.
Produces candidates only, never declares unattended production readiness.
"""
from __future__ import annotations
import argparse,asyncio,hashlib,json,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from openfeed.security import fetch,USER_AGENT
from openfeed.extract import extract_articles,infer_candidates,discover
from openfeed.quality import validate_items
SOURCES=[('oaktree','https://www.oaktreecapital.com/Insights/memos'),('bofa','https://institute.bankofamerica.com/transformation.html'),('gold','https://www.gold.org/industry-insights'),('kkr','https://www.kkr.com/insights'),('morgan-stanley','https://www.morganstanley.com/insights'),('capital-group','https://www.capitalgroup.com/institutional/insights.html'),('cepr','https://cepr.org/voxeu/columns?title=China'),('citi','https://jobs.citi.com/search-jobs/China/287/2/1814991/35/105/50/2'),('liepin','https://www.liepin.com/company-jobs/8652522/')]
async def one(name,url,out):
    record={'name':name,'url':url,'started_at':datetime.now(timezone.utc).isoformat(),'status':'unverified'}
    started=time.monotonic()
    try:
        origin=f'{urlsplit(url).scheme}://{urlsplit(url).netloc}'
        try:
            _,raw,enc=await fetch(origin+'/robots.txt')
            (out/f'{name}-robots.txt').write_bytes(raw)
            robots=RobotFileParser();robots.parse(raw.decode(enc,errors='replace').splitlines())
            record['robots_allowed']=robots.can_fetch(USER_AGENT,url)
            if not record['robots_allowed']:
                record['status']='robots_disallowed';return record
        except Exception as exc:
            record['robots_error']=str(exc)
            if 'HTTP 404' not in str(exc):
                record['status']='robots_unavailable';return record
        final,body,enc=await fetch(url)
        record.update(resolved_url=final,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
        html=body.decode(enc,errors='replace'); (out/f'{name}.html').write_bytes(body)
        lower=html.lower()
        if ('safe.liepin.com' in final or any(x in lower for x in ('verify you are human','access denied','captcha/dispatch','checking your browser'))):
            record['status']='access_challenge';return record
        if name=='capital-group':
            record['status']='investor_qualification_required';return record
        candidates=infer_candidates(html,limit=5);record['candidates']=candidates
        record['discovered_feeds']=discover(html,final)
        try:
            items,selector=extract_articles(html,final,{'mode':'css'})
            items,quality=validate_items(items)
            record.update(status='candidate_requires_review' if items else 'no_items',selector=selector,items=items,quality=quality)
        except Exception as exc:record.update(status='needs_rule_or_dynamic_render',error=str(exc))
    except Exception as exc:record.update(status='fetch_failed',error=f'{type(exc).__name__}: {exc}')
    finally:
        record['elapsed_ms']=round((time.monotonic()-started)*1000)
    return record
async def run(out):
    out.mkdir(parents=True,exist_ok=True)
    results=[]
    for name,url in SOURCES:
        result=await one(name,url,out);results.append(result)
        print(name,result['status'],flush=True)
        (out/'results.json').write_text(json.dumps({'generated_at':datetime.now(timezone.utc).isoformat(),'note':'Real HTTP-client evidence; candidate extraction does not establish complete/stable RSS or Reader ingestion.','results':results},ensure_ascii=False,indent=2))
    return results
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();asyncio.run(run(Path(a.output)))
