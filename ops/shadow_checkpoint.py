"""Promote a completed shadow state inside a PRIVATE validation branch only."""
import argparse,hashlib,json,os,sqlite3,tempfile
from pathlib import Path

def promote(state,cycle,run_id):
    report=json.loads((cycle/'report.json').read_text())
    if report.get('shadow_only') is not True or not report.get('input_db_unchanged'):raise ValueError('Incomplete shadow cycle')
    expected=report['input_sha256']
    if hashlib.sha256(state.read_bytes()).hexdigest()!=expected:raise ValueError('State changed; refusing stale checkpoint')
    shadow=cycle/'shadow.sqlite3'
    actual=hashlib.sha256(shadow.read_bytes()).hexdigest()
    if report.get('shadow_sha256')!=actual:raise ValueError('Candidate hash does not match completed cycle')
    conn=sqlite3.connect('file:'+str(shadow.resolve())+'?mode=ro',uri=True)
    try:
        if conn.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid candidate SQLite')
        with tempfile.NamedTemporaryFile(dir=state.parent,delete=False) as h:temp=Path(h.name)
        out=sqlite3.connect(temp)
        try:conn.backup(out)
        finally:out.close()
    finally:conn.close()
    try:
        # Caller holds single-writer workflow concurrency; compare again before rename.
        if hashlib.sha256(state.read_bytes()).hexdigest()!=expected:raise ValueError('Concurrent state change')
        os.replace(temp,state)
    finally:temp.unlink(missing_ok=True)
    meta={'run_id':str(run_id),'previous_sha256':expected,'database_sha256':hashlib.sha256(state.read_bytes()).hexdigest(),'scope':'private shadow validation only; no production cutover'}
    (state.parent/'checkpoint.json').write_text(json.dumps(meta,indent=2))
    return meta

def main():
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('--cycle',type=Path,required=True);p.add_argument('--run-id',required=True);a=p.parse_args();print(json.dumps(promote(a.state,a.cycle,a.run_id)))
if __name__=='__main__':main()
