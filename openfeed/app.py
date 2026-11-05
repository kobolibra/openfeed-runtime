"""OpenFeed Studio 0.4 -- self-hosted Web-to-RSS engineering prototype."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import secrets
import time
import tempfile
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from typing import Literal
from defusedxml import ElementTree as SafeET

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, FileResponse
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from .security import check_url, fetch, UnsafeURL, UpstreamHTTPError, retry_after_seconds, validate_json_request, public_request_options
from .extract import discover, extract_articles, parse_native, safe_preview, render_rss, infer_candidates, response_html, confirmed_empty_native
from .storage import Store, source_identity_changed
from .batch_jobs import BatchJobs
from .browser import browser_fetch
from .pagination import collect_pages
from .quality import validate_items

ROOT=Path(__file__).resolve().parent.parent
TOKEN=os.getenv('OPENFEED_ADMIN_TOKEN','')
BASE=os.getenv('OPENFEED_PUBLIC_URL','http://localhost:8765').rstrip('/')
store=Store(os.getenv('OPENFEED_DB',str(ROOT/'openfeed.sqlite3')))
batch_jobs=BatchJobs(os.getenv('OPENFEED_DB',str(ROOT/'openfeed.sqlite3')))
active=set()
locks:dict[str,asyncio.Lock]={}
_last_domain:dict[str,float]={}
_scheduled_tasks:set[asyncio.Task]=set()
fetch_slots=asyncio.Semaphore(4)

def admin(request:Request):
    if not TOKEN:
        raise HTTPException(503,'OPENFEED_ADMIN_TOKEN not configured')
    sent=request.headers.get('X-Admin-Token','')
    if not secrets.compare_digest(sent,TOKEN):
        raise HTTPException(401,'Enter administrator access token')
    return True

class Recipe(BaseModel):
    mode: Literal['css','xpath','pattern','json','pdf']='css'
    fetch_mode: Literal['http','browser']='http'
    fetch_url: str=Field(default='',max_length=2048)
    request_method: Literal['GET','POST']='GET'
    request_data: dict[str,str]=Field(default_factory=dict)
    request_json: dict | None=None
    json_contract: dict=Field(default_factory=dict)
    json_filters: dict[str,str]=Field(default_factory=dict)
    json_offset_field: str=Field(default='',max_length=80)
    json_offset_response_path: str=Field(default='',max_length=300)
    json_page_step: int=Field(default=6,ge=1,le=100)
    empty_json_path: str=Field(default='',max_length=300)
    public_api_key: str=Field(default='',max_length=500,pattern=r'^[!-~]*$')
    date_format: Literal['auto','unix_seconds','unix_milliseconds','embedded_calendar']='auto'
    keep_fragments: bool=False
    sort_newest: bool=False
    link_template: str=Field(default='',max_length=2048)
    direct_link_field: str=Field(default='',max_length=300)
    direct_link_base: str=Field(default='',max_length=2048)
    response_html_path: str=Field(default='',max_length=300)
    allow_empty_native: bool=False
    required_selectors: list[str]=Field(default_factory=list,max_length=10)
    empty_selector: str=Field(default='',max_length=500)
    empty_text: str=Field(default='',max_length=300)
    content_type: Literal['articles','jobs']='articles'
    complete_inventory: bool=False
    wait_selector: str=Field(default='',max_length=180)
    item_selector: str=Field(default='',max_length=500)
    global_pattern: str=Field(default='',max_length=500)
    next_selector: str=Field(default='',max_length=400)
    max_pages: int=Field(default=1,ge=1,le=3)
    min_items: int=Field(default=0,ge=0,le=300)
    min_dated_pct: int=Field(default=0,ge=0,le=100)
    fields: dict[str,str]=Field(default_factory=dict)
    @model_validator(mode='after')
    def bounded_request(self):
        if self.json_filters:
            if self.mode!='json' or self.content_type!='articles' or len(self.json_filters)>10:
                raise ValueError('JSON record filters require articles JSON mode and at most ten fields')
            if any(not k or len(k)>300 or not v or len(v)>500 for k,v in self.json_filters.items()):
                raise ValueError('Invalid JSON record filter')
        if self.json_offset_field:
            offset=(self.request_json or {}).get(self.json_offset_field)
            if (self.mode!='json' or self.fetch_mode!='http' or self.request_method!='POST'
                or not self.json_offset_response_path or not self.json_contract or self.next_selector
                or type(offset) is not int or offset<0):
                raise ValueError('JSON offset pagination requires a bounded JSON POST offset, response echo and contract')
        elif self.json_offset_response_path:
            raise ValueError('Offset response path requires an offset field')
        if self.json_contract:
            if self.mode!='json' or len(self.json_contract)>10:raise ValueError('JSON contracts require JSON mode and at most ten paths')
            validate_json_request({str(i):v for i,v in enumerate(self.json_contract.values())})
            if any(not isinstance(k,str) or not k or len(k)>300 for k in self.json_contract):raise ValueError('Invalid JSON contract path')
        if self.empty_json_path and (self.mode!='json' or self.empty_json_path!=self.item_selector or not self.json_contract or self.max_pages!=1):
            raise ValueError('Empty JSON requires matching item path, response contract and single page')
        if self.request_json is not None:
            validate_json_request(self.request_json)
            if self.request_method!='POST' or self.request_data:raise ValueError('JSON body requires POST without form data')
        if any(not x or len(x)>500 for x in self.required_selectors):
            raise ValueError('Required source selectors must be nonempty and bounded')
        if bool(self.empty_selector)!=bool(self.empty_text):
            raise ValueError('Empty listing requires both a specific selector and exact text')
        if (self.empty_selector or self.required_selectors) and (self.mode=='json' or self.max_pages!=1):
            raise ValueError('HTML page contracts require a single HTML response')
        if len(self.request_data)>20 or any(len(k)>80 or len(v)>500 for k,v in self.request_data.items()):
            raise ValueError('Public API request data is too large')
        if self.request_method=='POST' and ((self.mode!='json' and not self.response_html_path) or self.fetch_mode!='http' or (self.max_pages!=1 and not self.json_offset_field)):
            raise ValueError('POST requires a single public JSON API response or explicit wrapped HTML path')
        return self
    @field_validator('fetch_url')
    @classmethod
    def valid_fetch_url(cls,value):return check_url(value,resolve=False) if value else value
    @field_validator('fields')
    @classmethod
    def limited(cls,v):
        if len(v)>8 or any(len(k)>30 or len(val)>500 for k,val in v.items()):
            raise ValueError('Too many/too long field selectors')
        return v

class Source(BaseModel):
    title: str=Field(min_length=1,max_length=180)
    source_url: str=Field(max_length=2048)
    description: str=Field(default='',max_length=500)
    kind: Literal['web','native']='web'
    recipe: Recipe=Field(default_factory=Recipe)
    interval_minutes: int=Field(default=720,ge=15,le=10080)
    enabled: bool=True
    @field_validator('source_url')
    @classmethod
    def valid_url(cls,v): return check_url(v,resolve=False)

class Update(BaseModel):
    title: str|None=Field(default=None,min_length=1,max_length=180)
    source_url: str|None=Field(default=None,max_length=2048)
    description: str|None=Field(default=None,max_length=500)
    kind: Literal['web','native']|None=None
    recipe: Recipe|None=None
    interval_minutes: int|None=Field(default=None,ge=15,le=10080)
    enabled: bool|None=None
    @model_validator(mode='before')
    @classmethod
    def reject_explicit_null(cls, value):
        # Omission leaves a field unchanged; null cannot represent a stored rule.
        if isinstance(value, dict) and any(v is None for k,v in value.items() if k in cls.model_fields):
            raise ValueError('Update fields may be omitted but must not be null')
        return value
    @field_validator('source_url')
    @classmethod
    def valid_url(cls,v): return check_url(v,resolve=False) if v else v

class Inspect(BaseModel):
    url: str=Field(max_length=2048)
    recipe: Recipe=Field(default_factory=Recipe)
    @field_validator('url')
    @classmethod
    def valid_url(cls,v): return check_url(v,resolve=False)

async def run_feed(ident:str):
    lock=locks.setdefault(ident,asyncio.Lock())
    if lock.locked():
        return {'status':'busy','message':'Source is already being refreshed'}
    async with lock:
        f=store.get(ident)
        if not f: raise HTTPException(404,'Feed not found')
        domain=urlsplit(f['recipe'].get('fetch_url') or f['source_url']).hostname or ''
        cooldown=store.domain_delay(domain)
        if cooldown:
            store.defer(ident,cooldown)
            return {'status':'rate_limited','retry_after':cooldown,'reason':'domain_cooldown'}
        min_gap=int(os.getenv('OPENFEED_MIN_DOMAIN_INTERVAL','60'))
        elapsed=time.monotonic()-_last_domain.get(domain,-1e9)
        if elapsed < min_gap:
            delay=max(1,int(min_gap-elapsed)+1)
            store.defer(ident,delay)
            return {'status':'rate_limited','retry_after':delay}
        _last_domain[domain]=time.monotonic()
        t0=time.monotonic(); items=[]; err=None; metrics=None
        diagnostic='';empty_confirmed=False;upstream_delay=0
        try:
            async with fetch_slots:
                if f['kind']=='native':
                    resolved,body,enc=await fetch(f['source_url'])
                    items=parse_native(body,resolved)
                    empty_confirmed=not items and f['recipe'].get('allow_empty_native',False) and confirmed_empty_native(body)
                else:
                    items,metrics=await collect_pages(f['source_url'],f['recipe'],fetch,browser_fetch)
                    empty_confirmed=not items and metrics.get('empty_confirmed',False)
                    diagnostic=f"{metrics['pages_fetched']} page(s), {metrics['items_found']} unique item(s)"
                    if metrics['limit_reached']:
                        diagnostic+='; extraction limit reached'
            # A truncated or capped extraction is not a complete job inventory.
            # Reject the refresh instead of falsely aging absent job postings.
            cfg=f.get('recipe') or {}
            if (cfg.get('content_type')=='jobs' and cfg.get('complete_inventory') is True
                    and (f['kind']=='native' or (metrics and metrics.get('limit_reached')))):
                raise ValueError('Job inventory is not provably complete; existing statuses preserved')
            items, quality = validate_items(items)
            if cfg.get('content_type')=='jobs' and cfg.get('complete_inventory') is True and quality['rejected']:
                raise ValueError('Complete job inventory contains rejected items; existing statuses preserved')
            if quality['rejected']:
                diagnostic += '; rejected=' + str(quality['rejected'])
            if quality['date_missing']:
                diagnostic += '; unknown_dates=' + str(quality['date_missing'])
            if not items and not empty_confirmed: raise ValueError('No valid items extracted; existing RSS was preserved')
            if empty_confirmed:diagnostic+='; official empty listing confirmed; existing RSS retained'
            # Per-source quality contracts are opt-in: a truncated list or a
            # broken date selector cannot silently pass as a healthy refresh.
            cfg=f.get('recipe') or {}
            minimum=int(cfg.get('min_items') or 0)
            if minimum and len(items)<minimum:
                raise ValueError(f'Quality gate: extracted {len(items)} items, minimum is {minimum}; existing RSS preserved')
            date_minimum=int(cfg.get('min_dated_pct') or 0)
            dated=sum(bool(x.get('published_at')) for x in items)
            if date_minimum and dated*100<len(items)*date_minimum:
                raise ValueError(f'Quality gate: dated items {dated}/{len(items)} below {date_minimum}%; existing RSS preserved')
        except Exception as exc:
            err=str(exc)
            if isinstance(exc,UpstreamHTTPError) and exc.status in (429,503):
                upstream_delay=retry_after_seconds(exc.retry_after) or (900 if exc.status==429 else 0)
                if upstream_delay:store.cool_domain(domain,upstream_delay)
        result=store.finish(f,items,err,int((time.monotonic()-t0)*1000),diagnostic)
        if upstream_delay and result.get('status')=='error':
            current=store.get(ident)
            scheduled=datetime.fromisoformat(current['next_run']) if current and current.get('next_run') else datetime.now(timezone.utc)
            if (scheduled-datetime.now(timezone.utc)).total_seconds()<upstream_delay:store.defer(ident,upstream_delay)
            result['retry_after']=upstream_delay
        return result

async def process_batch(job_id: str, max_items: int | None = None):
    if not batch_jobs.claim(job_id):
        return
    processed = 0
    try:
        record = batch_jobs.get(job_id)
        for identifier in record['feed_ids'][record['next_index']:]:
            if batch_jobs.get(job_id)['status'] != 'running':
                break
            try:
                outcome = await run_feed(identifier)
                result = {'feed_id': identifier, 'result': outcome}
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                result = {'feed_id': identifier, 'error': str(exc)[:500]}
            if not batch_jobs.finish_one(job_id, identifier, result):
                break
            processed += 1
            if max_items is not None and processed >= max_items:
                batch_jobs.yield_pending(job_id)
                break
    finally:
        # Cancellation, shutdown, and unexpected failures must not leave a
        # permanently "running" job until the next process restart.
        batch_jobs.interrupt(job_id)

async def batch_scheduler():
    while True:
        for ident in batch_jobs.pending():
            await process_batch(ident, max_items=1)
        await asyncio.sleep(2)

def choose_scheduled_feed(feeds,active_ids,domain_last,now,min_domain_gap=300):
    for f in feeds:
        host=urlsplit(f['recipe'].get('fetch_url') or f['source_url']).hostname or ''
        if f['id'] not in active_ids and now-domain_last.get(host,-1e9)>=min_domain_gap:return f
    return None

async def scheduler():
    domain_last={};last_start=-1e9
    while True:
        await asyncio.sleep(5)
        now=time.monotonic()
        if len(active)>=3 or now-last_start<60:continue
        f=choose_scheduled_feed(store.due(200),active,domain_last,now)
        if f is None:continue
        host=urlsplit(f['recipe'].get('fetch_url') or f['source_url']).hostname or ''
        domain_last[host]=now;last_start=now;active.add(f['id'])
        async def execute(identifier):
            try:await run_feed(identifier)
            except Exception:pass
            finally:active.discard(identifier)
        job=asyncio.create_task(execute(f['id']))
        _scheduled_tasks.add(job);job.add_done_callback(_scheduled_tasks.discard)

@asynccontextmanager
async def lifespan(app):
    batch_task=asyncio.create_task(batch_scheduler())
    task=None
    if os.getenv('OPENFEED_ENABLE_SCHEDULER','1')=='1':
        task=asyncio.create_task(scheduler())
    yield
    batch_task.cancel()
    try: await batch_task
    except asyncio.CancelledError: pass
    if task:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
    # Finish or cancel outstanding scheduler jobs before closing SQLite.
    if _scheduled_tasks:
        done,pending=await asyncio.wait(_scheduled_tasks,timeout=8)
        for job in pending: job.cancel()
        if pending: await asyncio.gather(*pending,return_exceptions=True)
    batch_jobs.close()
    store.close()

VERSION='0.10.0-dev'
app=FastAPI(title='OpenFeed Studio',version=VERSION,lifespan=lifespan,docs_url=None,redoc_url=None)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

@app.get('/')
def home():
    return FileResponse(ROOT/'static'/'index.html',headers={'Cache-Control':'no-cache','Content-Security-Policy':"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-src 'self'"})

@app.get('/api/status')
def status(_:bool=Depends(admin)):
    from .diagnostics import failure_summary
    return {'stats':store.stats(),'runs':store.runs(limit=25),'version':VERSION,'public_url':BASE,'diagnostics':failure_summary(store.list()),'domain_cooldowns':store.cooldowns(),'recoveries':store.recoveries(),'scheduling':{'timezone':'Asia/Shanghai','automatic_start_gap_seconds':60,'automatic_domain_gap_seconds':300,'max_automatic_inflight':3,'spread_feeds':sum(f.get('schedule_phase_seconds') is not None for f in store.list())}}

@app.post('/api/schedule/spread')
def spread_schedule(_:bool=Depends(admin)):
    return store.spread_schedule()

@app.get('/api/monitor')
def monitor(_:bool=Depends(admin)):
    return store.monitor()

@app.get('/api/feeds')
def feeds(_:bool=Depends(admin)):
    return store.list()

@app.post('/api/feeds',status_code=201)
def create(data:Source,_:bool=Depends(admin)):
    return store.create(data.model_dump())

@app.get('/api/feeds/{feed_id}')
def feed_detail(feed_id:str,_:bool=Depends(admin)):
    f=store.get(feed_id)
    if not f: raise HTTPException(404,'Feed not found')
    return {'feed':f,'items':store.entries(feed_id,30),'runs':store.runs(feed_id,30)}

@app.get('/api/feeds/{feed_id}/events')
def feed_events(feed_id:str,_:bool=Depends(admin)):
    if not store.get(feed_id): raise HTTPException(404,'Feed not found')
    return {'feed_id':feed_id,'events':store.item_events(feed_id)}

@app.get('/api/feeds/{feed_id}/lifecycle')
def lifecycle(feed_id:str,_:bool=Depends(admin)):
    if not store.get(feed_id): raise HTTPException(404,'Feed not found')
    return {'feed_id':feed_id,'items':store.item_lifecycle(feed_id)}

@app.get('/api/feeds/{feed_id}/revisions')
def list_revisions(feed_id:str,_:bool=Depends(admin)):
    if not store.get(feed_id): raise HTTPException(404,'Feed not found')
    return store.revisions(feed_id)

@app.post('/api/feeds/{feed_id}/restore/{revision}')
def restore_revision(feed_id:str,revision:int,_:bool=Depends(admin)):
    if not store.get(feed_id): raise HTTPException(404,'Feed not found')
    if revision < 1: raise HTTPException(422,'Revision must be positive')
    try:
        snapshot=store.restore_revision(feed_id,revision)
        return {'feed':snapshot,'restored_from':revision}
    except ValueError as exc:
        raise HTTPException(409,str(exc))

@app.patch('/api/feeds/{feed_id}')
def patch(feed_id:str,data:Update,_:bool=Depends(admin)):
    current=store.get(feed_id)
    if not current: raise HTTPException(404,'Feed not found')
    if current['item_count'] and source_identity_changed(current,{**current,**data.model_dump(exclude_unset=True)}):
        raise HTTPException(409,'Changing a populated source URL could mix unrelated articles. Create a new feed instead.')
    return store.update(feed_id,data.model_dump(exclude_unset=True))

@app.delete('/api/feeds/{feed_id}')
def remove(feed_id:str,_:bool=Depends(admin)):
    if not store.get(feed_id): raise HTTPException(404,'Feed not found')
    store.delete(feed_id)
    return {'deleted':True}

class BulkRefresh(BaseModel):
    feed_ids: list[str]=Field(min_length=1,max_length=30)
    @field_validator('feed_ids')
    @classmethod
    def unique_ids(cls, values):
        if any(not isinstance(x,str) or not x or len(x)>100 for x in values):
            raise ValueError('Invalid feed ID')
        if len(values)!=len(set(values)):
            raise ValueError('Duplicate feed IDs')
        return values

@app.post('/api/feeds/batch-jobs',status_code=202)
def enqueue_batch(payload: BulkRefresh, _:bool=Depends(admin)):
    missing=[identifier for identifier in payload.feed_ids if store.get(identifier) is None]
    if missing:raise HTTPException(404,detail={'missing_feed_ids':missing})
    try:return batch_jobs.create(payload.feed_ids)
    except ValueError as exc:raise HTTPException(429,str(exc))

@app.get('/api/feeds/batch-jobs/{job_id}')
def batch_progress(job_id:str, _:bool=Depends(admin)):
    result=batch_jobs.get(job_id)
    if result is None:raise HTTPException(404,'Batch not found')
    return result

@app.post('/api/feeds/batch-jobs/{job_id}/cancel')
def cancel_batch(job_id: str, _: bool = Depends(admin)):
    job = batch_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, 'Batch not found')
    if not batch_jobs.cancel(job_id):
        raise HTTPException(409, 'Batch is already completed or cancelled')
    return batch_jobs.get(job_id)


@app.post('/api/feeds/batch-jobs/{job_id}/resume')
def resume_batch(job_id:str, _:bool=Depends(admin)):
    result=batch_jobs.get(job_id)
    if result is None:raise HTTPException(404,'Batch not found')
    if not batch_jobs.resume(job_id):raise HTTPException(409,'Only interrupted batches can resume')
    return batch_jobs.get(job_id)

@app.post('/api/feeds/bulk-refresh')
async def bulk_refresh(payload: BulkRefresh, _:bool=Depends(admin)):
    # Validate every ID before invoking any side effects.
    missing=[identifier for identifier in payload.feed_ids if store.get(identifier) is None]
    if missing:
        raise HTTPException(404,detail={'missing_feed_ids':missing})
    # Bounded fan-out also respects run_feed's existing per-source lock,
    # network slot semaphore and per-domain request pacing.
    limit=asyncio.Semaphore(3)
    async def execute(identifier:str):
        async with limit:
            try:
                outcome=await run_feed(identifier)
                return {'feed_id':identifier,'result':outcome}
            except Exception as exc:
                return {'feed_id':identifier,'error':str(exc)}
    results=await asyncio.gather(*(execute(i) for i in payload.feed_ids))
    return {'requested':len(payload.feed_ids),'results':results}

@app.post('/api/feeds/{feed_id}/run')
async def run(feed_id:str,_:bool=Depends(admin)):
    return await run_feed(feed_id)

@app.post('/api/inspect')
async def inspect(data:Inspect,_:bool=Depends(admin)):
    try:
        recipe=data.recipe.model_dump()
        target=data.recipe.fetch_url or data.url
        url,body,enc=await (browser_fetch(target,data.recipe.wait_selector) if data.recipe.fetch_mode=='browser' else fetch(target,**public_request_options(recipe)))
        content=response_html(body.decode(enc,errors='replace'),recipe)
        recipe={**recipe,'response_html_path':''}
        if not data.recipe.response_html_path and data.recipe.mode not in ('json','pdf') and (body.lstrip().startswith((b'<?xml', b'{', b'[')) or '<rss' in content[:300] or '<feed' in content[:300]):
            native=parse_native(body,url)
            return {'url':url,'discovered':[],'preview_items':native[:20],'selector':'native feed','snapshot':None,'candidates':[]}
        found=[] if data.recipe.mode=='json' else discover(content,url)
        try:
            items,sel=extract_articles(content,url,recipe)
            error=None
        except Exception as e:
            items=[];sel='';error=str(e)
        candidates=[] if data.recipe.mode=='json' else infer_candidates(content)
        warnings=[]
        if candidates and any(c['count']>100 for c in candidates):
            warnings.append('More than 100 matching cards: only the first 100 extracted items are retained per refresh. Use an explicit same-origin next-page selector to retrieve additional pages (up to 3).')
        if items and all(not x.get('published_at') for x in items):
            warnings.append('Publication dates could not be parsed. Articles retain the first-seen timestamp, not a fabricated publication date.')
        if data.recipe.max_pages > 1:
            warnings.append('Preview shows only page one. Saved refreshes will fetch at most '+str(data.recipe.max_pages)+' same-origin pages with source pacing.')
        if found:
            warnings.append('An existing feed was discovered. Prefer the original feed to avoid HTML scraping when it covers the desired topic.')
        return {'url':url,'discovered':found,'preview_items':items[:30], 'selector':sel, 'error':error, 'snapshot':None if data.recipe.mode=='json' else safe_preview(content), 'candidates':candidates,'warnings':warnings}
    except (ValueError,UnsafeURL) as e:
        raise HTTPException(422,str(e))
    except Exception as e:
        raise HTTPException(502,f'Unable to fetch source: {str(e)[:250]}')

@app.post('/api/feeds/{feed_id}/diagnose')
async def diagnose(feed_id:str,_:bool=Depends(admin)):
    # Read-only selector health check. Never rewrites the user's Recipe.
    feed=store.get(feed_id)
    if not feed:raise HTTPException(404,'Feed not found')
    if feed['kind']=='native':
        return {'feed_id':feed_id,'mode':'native','message':'Native RSS does not use article selectors','suggestions':[]}
    recipe=feed['recipe']
    try:
        target=recipe.get('fetch_url') or feed['source_url']
        url,body,enc=await (browser_fetch(target,recipe.get('wait_selector',''))
            if recipe.get('fetch_mode')=='browser' else fetch(target,**public_request_options(recipe)))
        content=response_html(body.decode(enc,errors='replace'),recipe)
        recipe={**recipe,'response_html_path':''}
        error=None
        try:current,_=extract_articles(content,url,recipe)
        except Exception as exc:current=[];error=str(exc)[:200]
        suggestions=[]
        if recipe.get('mode','css')=='css':
            for candidate in infer_candidates(content,limit=8):
                alternative=dict(recipe)
                alternative['item_selector']=candidate['selector']
                alternative['fields']={}
                try:rows,_=extract_articles(content,url,alternative)
                except Exception:continue
                if not rows:continue
                suggestions.append({'selector':candidate['selector'],'valid_items':len(rows),
                    'sample_titles':[x['title'] for x in rows[:3]],
                    'dated':sum(bool(x.get('published_at')) for x in rows)})
            suggestions.sort(key=lambda x:(x['valid_items'],x['dated']),reverse=True)
        return {'feed_id':feed_id,'mode':recipe.get('mode','css'),
            'current_items':len(current),'stored_items':feed.get('item_count',0),
            'current_error':error,'suggestions':suggestions[:5],
            'message':'Suggestions are read-only; test before saving. DOM changes may also require field updates.'}
    except Exception as exc:
        raise HTTPException(502,'Diagnosis failed: '+str(exc)[:200])

@app.api_route('/rss/{feed_id}.xml', methods=['GET', 'HEAD'])
def public_rss(feed_id:str, request:Request):
    f=store.get(feed_id)
    if not f: raise HTTPException(404,'Feed not found')
    entries=store.entries(feed_id,100)
    data=render_rss(f,entries,BASE+f'/rss/{feed_id}.xml')
    etag='"'+sha256(data).hexdigest()+'"'
    headers={'ETag':etag,'Cache-Control':'public, max-age=300', 'X-Content-Type-Options':'nosniff'}
    # Conditional requests may contain multiple opaque validators. Weak matches
    # are acceptable for GET/HEAD, but never for write preconditions.
    supplied=[value.strip() for value in request.headers.get('if-none-match','').split(',')]
    if '*' in supplied or etag in supplied or 'W/'+etag in supplied:
        return Response(status_code=304, headers=headers)
    headers['Content-Length']=str(len(data))
    return Response(content=b'' if request.method=='HEAD' else data,
                    media_type='application/rss+xml; charset=utf-8', headers=headers)

@app.get('/api/export/recipes')
def export_recipes(_:bool=Depends(admin)):
    rows=store.list()
    data={'format':'openfeed-recipes','version':2,'feeds':[{k:f[k] for k in ('id','title','source_url','description','kind','interval_minutes','recipe','enabled')} for f in rows]}
    return Response(json.dumps(data,indent=2,ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':'attachment; filename="openfeed-recipes.json"'})

@app.get('/api/export/database')
def export_database(_:bool=Depends(admin)):
    """Online SQLite backup: includes history and preserves all feed IDs."""
    tmp = tempfile.NamedTemporaryFile(prefix='openfeed-backup-', suffix='.sqlite3', delete=False)
    tmp.close()
    try:
        store.backup_to(tmp.name)
    except Exception:
        os.unlink(tmp.name)
        raise
    return FileResponse(tmp.name, media_type='application/octet-stream',
        filename='openfeed-backup.sqlite3', background=BackgroundTask(os.unlink,tmp.name),
        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.get('/api/export/opml')
def export_opml(_:bool=Depends(admin)):
    root=ET.Element('opml',version='2.0'); head=ET.SubElement(root,'head'); ET.SubElement(head,'title').text='OpenFeed Studio'
    body=ET.SubElement(root,'body')
    for f in store.list():
        ET.SubElement(body,'outline',{'type':'rss','text':f['title'],'title':f['title'],'xmlUrl':BASE+f'/rss/{f["id"]}.xml','htmlUrl':f['source_url']})
    return Response(ET.tostring(root,encoding='utf-8',xml_declaration=True),media_type='application/xml',headers={'Content-Disposition':'attachment; filename="openfeed.opml"'})

@app.get('/api/health')
def health():return {'ok':True,'version':VERSION}

@app.post('/api/import/recipes')
async def import_recipes(request:Request,_:bool=Depends(admin)):
    body=await request.body()
    if len(body)>1_000_000: raise HTTPException(413,'Recipe import exceeds 1MB limit')
    try:
        data=json.loads(body)
        if data.get('format')!='openfeed-recipes' or data.get('version') not in (1,2) or not isinstance(data.get('feeds'),list):
            raise ValueError('Expected OpenFeed Recipe Bundle version 1 or 2')
        if len(data['feeds'])>300: raise ValueError('Maximum 300 feeds per import')
        validated=[]
        for row in data['feeds']:
            parsed=Source.model_validate(row).model_dump()
            if data['version']==2 and 'id' in row:
                identifier=row['id']
                if not isinstance(identifier,str) or len(identifier)!=28 or any(c not in '0123456789abcdef' for c in identifier):
                    raise ValueError('Invalid feed ID in backup')
                parsed['id']=identifier
            validated.append(parsed)
    except Exception as e: raise HTTPException(422,str(e)[:300])
    try:
        count,skipped=store.create_many(validated)
    except Exception as e:
        raise HTTPException(422,'Import failed: '+str(e)[:200])
    return {'imported':count,'skipped':skipped,'note':'Version 2 preserves feed IDs on an empty installation; back up the SQLite database to retain item history.'}

@app.post('/api/import/opml')
async def import_opml(request:Request,_:bool=Depends(admin)):
    body=await request.body()
    if len(body)>1_000_000:raise HTTPException(413,'OPML import exceeds 1MB limit')
    try:
        root=SafeET.fromstring(body)
        if root.tag!='opml':raise ValueError('Expected an OPML document')
        nodes=root.findall('.//outline')
        if len(nodes)>300:raise ValueError('Maximum 300 OPML entries per import')
        feeds=[]
        for node in nodes:
            src=node.attrib.get('xmlUrl','')
            if src:
                feeds.append(Source.model_validate({'title':node.attrib.get('title') or node.attrib.get('text') or 'Imported feed', 'source_url':src,'kind':'native'}).model_dump())
    except Exception as e:raise HTTPException(422,str(e)[:300])
    try:
        count,skipped=store.create_many(feeds)
    except Exception as e:
        raise HTTPException(422,'OPML import failed: '+str(e)[:200])
    return {'imported':count,'skipped':skipped,'note':'OPML imports existing RSS URLs; it does not migrate the original website extraction rules.'}
