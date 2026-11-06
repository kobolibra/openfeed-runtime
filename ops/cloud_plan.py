"""Read-only, standard-library preflight before dependency installation or Docker."""
import argparse,hashlib,json,sqlite3,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openfeed.scheduling import publication_slot

def stamp(value):
    if not value:return None
    result=datetime.fromisoformat(value)
    if result.tzinfo is None:raise ValueError('State timestamps must include timezone')
    return result

def plan(state,now=None,targets=(),browser_horizon_seconds=900):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Planning requires timezone')
    db=state/'openfeed.sqlite3';checkpoint=json.loads((state/'checkpoint.json').read_text())
    if hashlib.sha256(db.read_bytes()).hexdigest()!=checkpoint['database_sha256']:raise ValueError('Checkpoint DB hash mismatch')
    control=json.loads((state/'runtime-control.json').read_text())
    production=control.get('mode')=='production'
    if production and (control.get('mac_writer_stopped') is not True or len(control.get('final_mac_snapshot_sha256',''))!=64):raise ValueError('Production requires stopped Mac writer evidence')
    if not production and control.get('shadow_until') and now>=stamp(control['shadow_until']):
        return {'work_needed':False,'due_count':0,'browser_needed':False,'publication_due':False,'reason':'validation_deadline_reached'}
    publication=False
    slot=publication_slot(now)
    if production and control.get('publish_enabled') is True and slot:
        path=state/'publication-state.json';previous=json.loads(path.read_text()) if path.exists() else {}
        publication=previous.get('result')=='attempt_reserved' or previous.get('slot')!=slot
    con=sqlite3.connect(db.resolve().as_uri()+'?mode=ro&immutable=1',uri=True);con.row_factory=sqlite3.Row
    try:
        recoveries={r['feed_id']:dict(r) for r in con.execute('select * from recoveries')}
        feeds=[dict(r) for r in con.execute('select id,enabled,kind,recipe,next_run from feeds')]
    finally:con.close()
    known={f['id'] for f in feeds}
    if set(targets)-known:raise ValueError('Unknown explicit source ID')
    def due(feed,at):
        if not feed['enabled']:return False
        if targets:return feed['id'] in targets
        normal=stamp(feed['next_run']);r=recoveries.get(feed['id']);retry=False
        if r:
            start=stamp(r.get('not_before'));end=stamp(r.get('expires_at'))
            retry=bool(start and end and start<=at<end)
        return bool(normal and normal<=at) or retry
    due_feeds=[f for f in feeds if due(f,now)]
    # Docker preparation can cross another source's due time. Conservatively
    # include every browser source that might become due within this bounded job.
    horizon=now+timedelta(seconds=browser_horizon_seconds)
    browser=any(f['kind']!='native' and json.loads(f['recipe']).get('fetch_mode','http')=='browser' and (due(f,now) or due(f,horizon)) for f in feeds)
    return {'work_needed':bool(due_feeds or publication),'due_count':len(due_feeds),'browser_needed':browser if due_feeds else False,'publication_due':bool(publication),'reason':'due_work' if due_feeds else 'publication_only' if publication else 'idle'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('--github-output',type=Path);a=p.parse_args();value=plan(a.state)
    if a.github_output:
        with a.github_output.open('a') as f:f.write('work_needed='+str(value['work_needed']).lower()+'\n')
    print(json.dumps(value))
if __name__=='__main__':main()
