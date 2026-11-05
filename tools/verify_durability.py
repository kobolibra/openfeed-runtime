"""Timed local storage soak and abrupt-process recovery; synthetic data only."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from openfeed.storage import Store
from openfeed.batch_jobs import BatchJobs

def run(seconds,out):
 out.mkdir(parents=True,exist_ok=True);started=time.monotonic();cycles=0;operations=0;errors=0
 with tempfile.TemporaryDirectory(prefix='openfeed-soak-') as tmp:
  path=Path(tmp)/'soak.sqlite';db=Store(str(path));ids=[]
  for i in range(150):ids.append(db.create({'title':f'Synthetic source {i}','source_url':f'https://source-{i}.example.org','recipe':{}})['id'])
  job=BatchJobs(str(path));batch=job.create(ids[:30]);job.claim(batch['id']);job.close()
  # Persistent intent survives an abrupt process exit; uncommitted writes do not.
  program="import os,sqlite3,sys;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');c.execute(\"UPDATE feeds SET title='UNCOMMITTED'\");os._exit(17)"
  child=subprocess.run([sys.executable,'-c',program,str(path)])
  assert child.returncode==17 and db.get(ids[0])['title']=='Synthetic source 0'
  reopened=BatchJobs(str(path));assert reopened.get(batch['id'])['status']=='interrupted';reopened.close()
  while time.monotonic()-started<seconds:
   for i,ident in enumerate(ids):
    records=[{'title':f'Synthetic report {j}','url':f'https://source-{i}.example.org/report/{j}'} for j in range(4)]
    failure='Injected upstream outage' if (i+cycles)%19==0 else None
    result=db.finish(db.get(ident),records,failure,1);operations+=1
    if failure:
     errors+=1;assert result['status']=='error'
    else:assert result['status']=='success'
   cycles+=1
   if cycles%5==0:
    backup=Path(tmp)/'backup.sqlite';db.backup_to(str(backup))
   assert db.db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
   # This pacing exercises a timed run instead of an unbounded CPU loop.
   time.sleep(.2)
  integrity=db.db.execute('PRAGMA integrity_check').fetchone()[0]
  assert integrity=='ok'
  assert all(len(db.entries(i))==4 for i in ids)
  db.close()
 result={'scope':'Local synthetic SQLite only; not network/browser/24x7 production stability','duration_seconds':round(time.monotonic()-started,2),'feeds':150,'cycles':cycles,'refresh_operations':operations,'injected_fetch_failures':errors,'uncommitted_crash_rollback':True,'running_batch_becomes_interrupted':True,'integrity_check':integrity,'all_feed_items_preserved':True}
 (out/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=120);p.add_argument('--output',required=True);a=p.parse_args();run(min(600,max(2,a.seconds)),Path(a.output).resolve())
