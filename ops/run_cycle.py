"""One bounded SHADOW cycle. Never writes the input DB or publishes files.

Run as a fresh CLI process; app has module-global Store state. This is not yet
an authoritative cloud runner: every invocation uses a new isolated snapshot.
"""
import argparse,asyncio,hashlib,json,os,sqlite3,sys,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def prepare(source,output):
    source=source.resolve(strict=True);output=output.resolve()
    if output.exists():raise ValueError('Output must be a NEW directory; no overwrite/resume')
    output.mkdir(mode=0o700,parents=True)
    dest=output/'shadow.sqlite3'
    read=sqlite3.connect('file:'+source.as_posix()+'?mode=ro',uri=True)
    try:
        write=sqlite3.connect(dest)
        try:read.backup(write)
        finally:write.close()
    finally:read.close()
    dest.chmod(0o600)
    return dest

async def cycle(db,output,mode,max_feeds,budget,fixtures,feed_ids,wait_for_start=False,public_base="https://kobolibra.github.io/openfeed-feeds"):
    if 'openfeed.app' in sys.modules:raise RuntimeError('Use a fresh CLI process, app already imported')
    os.environ['OPENFEED_DB']=str(db);os.environ['OPENFEED_ENABLE_SCHEDULER']='0'
    os.environ['OPENFEED_PUBLIC_URL']=public_base.rstrip('/')
    import openfeed.app as app
    started=time.monotonic();result=[]
    try:
        if mode=='fixtures':
            mapping=json.loads(fixtures.read_text())
            async def captured(url,**options):
                # Exact fixture keys include POST bodies: cannot silently reuse page 1.
                key=json.dumps({'url':url,'options':options},sort_keys=True)
                row=mapping.get(key)
                if row is None:raise ValueError('No exact captured request; no live fallback')
                if row.get('error'):
                    from openfeed.security import UpstreamHTTPError
                    raise UpstreamHTTPError(row['error'],url,row.get('retry_after',''))
                path=(fixtures.parent/row['path']).resolve();data=path.read_bytes()
                if len(data)>8_000_000:raise ValueError('Fixture exceeds fetch limit')
                return row.get('final_url',url),data,row.get('encoding','utf-8')
            async def browser_capture(url,wait_selector=''):
                return await captured(url,wait_selector=wait_selector)
            app.fetch=captured;app.browser_fetch=browser_capture
        all_feeds=app.store.list();known={f['id'] for f in all_feeds}
        if set(feed_ids)-known:raise ValueError('Unknown explicit source ID')
        # Explicit IDs are a deliberate fixture/manual shadow check only;
        # normal cycles use due() including persisted recovery candidates.
        candidates=[f for f in all_feeds if f['id'] in feed_ids and f['enabled']] if feed_ids else app.store.due(10000)
        if wait_for_start and mode!='plan':
            # Give distinct hosts their first turn before waiting for a sibling.
            seen=set();first=[];siblings=[]
            for candidate in candidates:
                host=urlsplit(candidate['recipe'].get('fetch_url') or candidate['source_url']).hostname
                (siblings if host in seen else first).append(candidate);seen.add(host)
            candidates=first+siblings
        report={'mode':mode,'shadow_only':True,'published':False,'selected':[],'results':result,'deferred':[]}
        # Persist starts in the shadow DB so a subsequent cycle based on this
        # checkpoint cannot evade spacing by restarting the Python process.
        app.store.db.execute('CREATE TABLE IF NOT EXISTS shadow_cycle_starts (host TEXT PRIMARY KEY, started REAL NOT NULL)')
        used=set()
        for f in candidates:
            if len(result)>=max_feeds:
                report['deferred'].append({'id':f['id'],'reason':'max_feeds'});continue
            host=urlsplit(f['recipe'].get('fetch_url') or f['source_url']).hostname
            if host in used and (not wait_for_start or mode=='plan'):
                report['deferred'].append({'id':f['id'],'reason':'same_host'});continue
            remaining=budget-(time.monotonic()-started)
            if remaining<=0:
                report['deferred'].append({'id':f['id'],'reason':'cycle_deadline'});continue
            if mode!='plan':
                now=time.time()
                last=app.store.db.execute('SELECT MAX(started) FROM shadow_cycle_starts').fetchone()[0]
                row=app.store.db.execute('SELECT started FROM shadow_cycle_starts WHERE host=?',(host,)).fetchone()
                global_delay=max(0,60-(now-last)) if last is not None else 0
                domain_delay=max(0,300-(now-row[0])) if row else 0
                delay=max(global_delay,domain_delay)
                reason='domain_start_gap' if domain_delay>global_delay else 'global_start_gap'
                if delay:
                    # Wait only when the unchanged persisted gap fits the budget.
                    if not wait_for_start or delay+1>=remaining:
                        report['deferred'].append({'id':f['id'],'reason':reason});continue
                    await asyncio.sleep(delay)
                    now=time.time()
                    remaining=budget-(time.monotonic()-started)
                with app.store.db:
                    app.store.db.execute('INSERT INTO shadow_cycle_starts VALUES (?,?) ON CONFLICT(host) DO UPDATE SET started=excluded.started',(host,now))
            used.add(host)
            report['selected'].append(f['id'])
            if mode=='plan':outcome={'status':'planned'}
            else:
                try:
                    async with asyncio.timeout(remaining):outcome=await app.run_feed(f['id'])
                except TimeoutError:outcome={'status':'cycle_deadline','history_preserved':True}
                except Exception as exc:outcome={'status':'exception','type':type(exc).__name__}
            result.append({'id':f['id'],'result':outcome})
        if mode!='plan':
            from openfeed.extract import render_rss
            folder=output/'rss';folder.mkdir()
            manifest={}
            for f in app.store.list():
                data=render_rss(f,app.store.entries(f['id'],100),app.BASE+'/rss/'+f['id']+'.xml')
                (folder/(f['id']+'.xml')).write_bytes(data)
                manifest[f['id']]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
            (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
        report['next_schedule']=[{'id':f['id'],'next_run':f['next_run'],'schedule_phase_seconds':f.get('schedule_phase_seconds')} for f in app.store.list()]
        report['recoveries']=app.store.recoveries()
        report['cooldowns']=app.store.cooldowns()
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        return report
    finally:app.batch_jobs.close();app.store.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--input-db',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=['plan','fixtures','shadow-live'],default='plan');p.add_argument('--fixtures',type=Path);p.add_argument('--feed-id',action='append',default=[])
    p.add_argument('--wait-for-start',action='store_true');p.add_argument('--max-feeds',type=int,default=3);p.add_argument('--budget-seconds',type=float,default=120);a=p.parse_args()
    if not 1<=a.max_feeds<=100 or not 0<a.budget_seconds<=3600:p.error('Invalid bounded cycle limits')
    if a.mode=='fixtures' and not a.fixtures:p.error('--fixtures required')
    os.umask(0o077);source=a.input_db.resolve(strict=True);before=digest(source);db=prepare(source,a.output)
    report=asyncio.run(cycle(db,a.output.resolve(),a.mode,a.max_feeds,a.budget_seconds,a.fixtures.resolve() if a.fixtures else None,a.feed_id,a.wait_for_start))
    report['input_db_unchanged']=before==digest(source);report['input_sha256']=before;report['shadow_sha256']=digest(db)
    (a.output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if not report['input_db_unchanged']:raise RuntimeError('Input changed externally; do not use this run as preservation evidence')
    print(json.dumps({'shadow_only':True,'published':False,'results':report['results'],'input_db_unchanged':True}))
if __name__=='__main__':main()
