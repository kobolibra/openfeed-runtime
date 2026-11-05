"""One private shadow tick, invoked by an owner-controlled public thin workflow.

All application output stays in the ephemeral runner's private log. No public
RSS publishing or production cutover occurs in this command.
"""
import argparse,hashlib,json,os,shutil,sqlite3,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
from shadow_checkpoint import promote
ROOT=Path(__file__).resolve().parents[1]

def run(*args,cwd=ROOT):
    return subprocess.run(args,cwd=cwd,check=True,text=True,capture_output=True).stdout.strip()

def identities(path):
    c=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    try:
        if c.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid state integrity')
        return (set(c.execute('SELECT id,schedule_phase_seconds FROM feeds')),
                set(c.execute('SELECT feed_id,guid,first_seen_at FROM items')))
    finally:c.close()

def tick(run_id):
    state=ROOT/'private-state';db=state/'openfeed.sqlite3'
    if not (state/'.git').exists():raise ValueError('Expected dedicated private state checkout')
    if run('git','status','--porcelain',cwd=state):raise ValueError('State checkout is dirty')
    checkpoint=json.loads((state/'checkpoint.json').read_text())
    if hashlib.sha256(db.read_bytes()).hexdigest()!=checkpoint['database_sha256']:raise ValueError('Checkpoint DB hash mismatch')
    previous=run('git','rev-parse','HEAD',cwd=state)
    before=identities(db)
    io=ROOT/'cloud-io';io.mkdir(mode=0o700);shutil.copyfile(db,io/'input.sqlite3')
    run('sudo','chown','-R','10001:10001',str(io))
    compose=['docker','compose','-f',str(ROOT/'compose.cloud.yaml')]
    try:
        run(*compose,'run','--build','--rm','cycle','--input-db','/cloud-io/input.sqlite3','--output','/cloud-io/cycle','--mode','shadow-live','--max-feeds','4','--budget-seconds','330','--wait-for-start')
    finally:
        run(*compose,'down','--volumes')
        run('sudo','chown','-R',str(os.getuid())+':'+str(os.getgid()),str(io))
    cycle=io/'cycle';after=identities(cycle/'shadow.sqlite3')
    if before[0]!=after[0] or not before[1].issubset(after[1]):raise ValueError('Source/phase/history identity changed')
    report=json.loads((cycle/'report.json').read_text())
    manifest=json.loads((cycle/'manifest.json').read_text())
    if set(manifest)!={ident for ident,phase in before[0]}:raise ValueError('Incomplete RSS export')
    meta=promote(db,cycle,run_id)
    meta.update(source_sha=run('git','rev-parse','HEAD'),previous_state_commit=previous,
                rss_manifest_sha256=hashlib.sha256((cycle/'manifest.json').read_bytes()).hexdigest(),
                source_identity_preserved=True,scope='private scheduled shadow only; Mac remains production')
    (state/'checkpoint.json').write_text(json.dumps(meta,indent=2))
    shutil.copyfile(cycle/'report.json',state/'last-report.json')
    shutil.copyfile(cycle/'manifest.json',state/'rss-manifest.json')
    matrix_path=state/'coverage.json'
    matrix=json.loads(matrix_path.read_text()) if matrix_path.exists() else {'sources':{}}
    at=datetime.now(timezone.utc).isoformat()
    for ident,phase in before[0]:matrix['sources'].setdefault(ident,{'status':'not_tested'})
    for row in report['results']:
        matrix['sources'][row['id']]={'checked_at':at,'run_id':str(run_id),'result':row['result'],'identity_preserved':True,'scope':'single cloud observation, not long-term acceptance'}
    matrix_path.write_text(json.dumps(matrix,indent=2))
    run('git','config','user.name','OpenFeed Cloud Shadow',cwd=state)
    run('git','config','user.email','openfeed-shadow@users.noreply.github.com',cwd=state)
    run('git','add','--','openfeed.sqlite3','checkpoint.json','last-report.json','rss-manifest.json','coverage.json',cwd=state)
    run('git','commit','-m','Private shadow tick '+str(run_id),cwd=state)
    run('git','push','origin','HEAD:shadow-state',cwd=state)
    return {'shadow_only':True,'published':False,'processed':len(report['results'])}

def main():
    p=argparse.ArgumentParser();p.add_argument('--run-id',required=True);a=p.parse_args()
    print(json.dumps(tick(a.run_id)))
if __name__=='__main__':main()
