"""Local-only bridge. Config edits wait for the current cloud cycle, then commit with CAS; cloud scheduling is never disabled."""
import os,sys,subprocess,sqlite3,json,hashlib,httpx,base64,time,datetime,fcntl,tempfile,shutil
from pathlib import Path
BASE=Path('/Users/time/Documents/Codex/2026-10-22/referenced-chatgpt-conversation-this-is-an-3');SRC=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SRC));sys.path.insert(0,str(SRC/'ops'))
from openfeed.storage import Store
from export_db import export_db
SYNC_DIR=SRC/'.openfeed-local/cloud-sync'
DOCKER=['/opt/homebrew/bin/docker','--host','unix:///Users/time/Documents/Codex/.openfeed-colima/openfeed/docker.sock'];PY=BASE/'work/venv312/bin/python'
FIELDS=['title','description','source_url','kind','recipe','interval_minutes','enabled','schedule_phase_seconds']
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(data):return hashlib.sha256(data).hexdigest()
def configs(path):
 c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 try:
  result={}
  for r in c.execute('select id,'+','.join(FIELDS)+' from feeds'):
   row=dict(r);row['recipe']=json.loads(row['recipe']);row['enabled']=bool(row['enabled']);result[row.pop('id')]=row
  return result
 finally:c.close()
def command(args,**kw):return subprocess.run(args,capture_output=True,check=True,**kw).stdout
class GitHub:
 def __init__(self):
  r=command(['git','-C',str(BASE/'work/stage6/publish-repo'),'credential','fill'],input=b'protocol=https\nhost=github.com\n\n');token=dict(x.split('=',1) for x in r.decode().splitlines() if '=' in x)['password']
  self.client=httpx.Client(trust_env=False,timeout=90,limits=httpx.Limits(max_keepalive_connections=0),headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
 def call(self,repo,method,path,**kw):
  r=self.client.request(method,'https://api.github.com/repos/kobolibra/'+repo+path,**kw);r.raise_for_status();return r.json() if r.content else {}
 def fetch(self):
  head=self.call('openfeed-runtime','GET','/git/ref/heads/shadow-state')['object']['sha'];commit=self.call('openfeed-runtime','GET','/git/commits/'+head);nodes={n['path']:n for n in self.call('openfeed-runtime','GET','/git/trees/'+commit['tree']['sha'])['tree']}
  def raw(path):return base64.b64decode(self.call('openfeed-runtime','GET','/git/blobs/'+nodes[path]['sha'])['content'])
  checkpoint=json.loads(raw('checkpoint.json'));cache=SYNC_DIR/'remote.sqlite3'
  if not cache.exists() or digest(cache.read_bytes())!=checkpoint['database_sha256']:
   data=raw('openfeed.sqlite3');assert digest(data)==checkpoint['database_sha256'];cache.write_bytes(data);cache.chmod(0o600)
  return {'head':head,'tree':commit['tree']['sha'],'nodes':nodes,'raw':raw,'checkpoint':checkpoint,'path':cache}
 def pause(self):
  # Never disable scheduling: closing/sleeping the Mac must not stop cloud runs.
  deadline=time.monotonic()+900
  while True:
   active=[r for r in self.call('openfeed-feeds','GET','/actions/workflows/runtime-cloud.yml/runs?per_page=30')['workflow_runs'] if r['status']!='completed']
   busy=False
   for r in active:
    steps=[s for j in self.call('openfeed-feeds','GET','/actions/runs/'+str(r['id'])+'/jobs')['jobs'] for s in j['steps']]
    work=[s for s in steps if s['name'].startswith('Run validated') or s['name'].startswith('Run verified')]
    if not work or any(s['status']!='completed' for s in work):busy=True
   if not busy:return
   if time.monotonic()>=deadline:raise TimeoutError('Current cloud cycle still running; local edit retained')
   time.sleep(15)
 def resume(self):
  pass  # The cloud chain and native schedule stayed enabled throughout.
 def close(self):self.client.close()
def snapshot_local(path):
 code="""import sqlite3,tempfile,sys,os
fd,p=tempfile.mkstemp();os.close(fd);a=sqlite3.connect('file:/data/openfeed.sqlite3?mode=ro',uri=True);b=sqlite3.connect(p);a.backup(b);b.close();a.close()
with open(p,'rb') as f:sys.stdout.buffer.write(f.read())
os.unlink(p)
"""
 path.write_bytes(command([*DOCKER,'exec','openfeed-live-openfeed-1','python','-c',code]));path.chmod(0o600)
def local_state(status,**kw):
 data=json.dumps({'status':status,'checked_at':now(),**kw}).encode();command([*DOCKER,'exec','-i','openfeed-live-openfeed-1','python','-c',"import sys;open('/data/cloud-sync-state.json','wb').write(sys.stdin.buffer.read())"],input=data)
def apply_edits(remote,baseline,local,output):
 cloud=configs(remote);changed={i for i in set(baseline)|set(local) if baseline.get(i)!=local.get(i)}
 for i in changed:
  if cloud.get(i)!=baseline.get(i) and cloud.get(i)!=local.get(i):raise ValueError('Cloud source changed concurrently; local edit retained for review')
 shutil.copyfile(remote,output);store=Store(str(output));deleted=[]
 try:
  for i in sorted(changed):
   if i not in local:
    if store.get(i):store.delete(i)
    deleted.append(i);continue
   if cloud.get(i)==local.get(i):continue
   data={k:v for k,v in local[i].items() if k!='schedule_phase_seconds'}
   if i in cloud:
    old=cloud[i];old_target=old['recipe'].get('fetch_url') or old['source_url'];target=data['recipe'].get('fetch_url') or data['source_url']
    if old_target!=target and store.entries(i,1):raise ValueError('Populated source fetch identity cannot be changed')
    store.update(i,data)
   else:
    store.create({**data,'id':i})
   with store.db:store.db.execute('update feeds set schedule_phase_seconds=? where id=?',(local[i]['schedule_phase_seconds'],i))
  assert not store.db.execute('pragma foreign_key_check').fetchall()
 finally:store.close()
 assert configs(output)=={**{i:v for i,v in cloud.items() if i not in changed},**{i:local[i] for i in changed if i in local}}
 return changed,deleted

def commit_edits(g,remote,baseline,local):
 output=SYNC_DIR/'candidate.sqlite3';changed,deleted=apply_edits(remote['path'],baseline,local,output)
 stage=SYNC_DIR/'export';shutil.rmtree(stage,ignore_errors=True);export_db(output,stage,'https://kobolibra.github.io/openfeed-feeds')
 manifest=SYNC_DIR/'manifest.json';shutil.rmtree(SYNC_DIR/'manifest-export',ignore_errors=True);command([str(PY),str(SRC/'ops/export_db.py'),'--db',str(output),'--output',str(SYNC_DIR/'manifest-export'),'--manifest',str(manifest)])
 manifest.write_text(json.dumps(json.loads(manifest.read_text())['files'],indent=2));data=output.read_bytes();meta={**remote['checkpoint'],'database_sha256':digest(data),'previous_state_commit':remote['head'],'rss_manifest_sha256':digest(manifest.read_bytes()),'management_edit_at':now(),'management_source_ids':sorted(changed)}
 coverage=json.loads(remote['raw']('coverage.json'))
 for i in changed:
  if i not in local:coverage['sources'].pop(i,None)
  else:coverage['sources'][i]={'status':'not_tested','reason':'User updated source configuration from local UI'}
 tombstones=json.loads(remote['raw']('deleted-sources.json')) if 'deleted-sources.json' in remote['nodes'] else {'version':1,'sources':{}}
 for i in deleted:tombstones['sources'][i]={'deleted_at':now(),'reason':'Explicit authenticated local management deletion'}
 blob=g.call('openfeed-runtime','POST','/git/blobs',json={'content':base64.b64encode(data).decode(),'encoding':'base64'})['sha'];changes=[{'path':'openfeed.sqlite3','mode':'100644','type':'blob','sha':blob}]
 for path,text in [('checkpoint.json',json.dumps(meta,indent=2)),('rss-manifest.json',manifest.read_text()),('coverage.json',json.dumps(coverage,indent=2)),('deleted-sources.json',json.dumps(tombstones,indent=2))]:changes.append({'path':path,'mode':'100644','type':'blob','content':text})
 tree=g.call('openfeed-runtime','POST','/git/trees',json={'base_tree':remote['tree'],'tree':changes})['sha'];commit=g.call('openfeed-runtime','POST','/git/commits',json={'message':'Apply authenticated local source management without dropping cloud history','tree':tree,'parents':[remote['head']]})['sha']
 try:g.call('openfeed-runtime','PATCH','/git/refs/heads/shadow-state',json={'sha':commit,'force':False})
 except httpx.HTTPError:
  if g.call('openfeed-runtime','GET','/git/ref/heads/shadow-state')['object']['sha']!=commit:raise
 # Explicit deletions remove only the user-selected RSS URLs; other files remain unchanged.
 if deleted:
  repo='openfeed-feeds';h=g.call(repo,'GET','/git/ref/heads/main')['object']['sha'];co=g.call(repo,'GET','/git/commits/'+h);nodes={x['path']:x for x in g.call(repo,'GET','/git/trees/'+co['tree']['sha']+'?recursive=1')['tree']};rows=[{'path':'rss/'+i+'.xml','mode':'100644','type':'blob','sha':None} for i in deleted if 'rss/'+i+'.xml' in nodes];rows.append({'path':'subscriptions.opml','mode':'100644','type':'blob','content':(stage/'subscriptions.opml').read_text()});t=g.call(repo,'POST','/git/trees',json={'base_tree':co['tree']['sha'],'tree':rows})['sha'];new=g.call(repo,'POST','/git/commits',json={'message':'Remove user-deleted subscriptions','tree':t,'parents':[h]})['sha'];g.call(repo,'PATCH','/git/refs/heads/main',json={'sha':new,'force':False})
 return output,commit

def install_mirror(db,expected):
 # Briefly stop only the local UI so an edit cannot race the database replacement.
 command([*DOCKER,'stop','--time','30','openfeed-live-openfeed-1'])
 try:
  code="""import sqlite3,sys,tempfile,os,json
p='/data/openfeed.sqlite3';c=sqlite3.connect('file:'+p+'?mode=ro&immutable=1',uri=True);cols=['title','description','source_url','kind','recipe','interval_minutes','enabled','schedule_phase_seconds'];c.row_factory=sqlite3.Row;result={}
for r in c.execute('select id,'+','.join(cols)+' from feeds'):
 d=dict(r);d['recipe']=json.loads(d['recipe']);d['enabled']=bool(d['enabled']);result[d.pop('id')]=d
c.close();payload=json.loads(sys.stdin.buffer.read());assert result==payload['expected'],'A local edit arrived during sync; retained'
import base64
raw=base64.b64decode(payload['data']);fd,t=tempfile.mkstemp(dir='/data')
with os.fdopen(fd,'wb') as f:f.write(raw)
os.chmod(t,0o600);os.replace(t,p)
"""
  command([*DOCKER,'run','--rm','-i','--network','none','--read-only','-v','openfeed-live_openfeed-data:/data','openfeed-live-openfeed','python','-c',code],input=json.dumps({'expected':expected,'data':base64.b64encode(db.read_bytes()).decode()}).encode())
 finally:command([str(PY),str(BASE/'work/stage3/live_stack.py'),'up','-d','--no-build','--no-deps','openfeed'],cwd=BASE)

def cycle():
 localfile=SYNC_DIR/'local.sqlite3';snapshot_local(localfile);local=configs(localfile);baseline_path=SYNC_DIR/'baseline.json';baseline=json.loads(baseline_path.read_text());g=GitHub()
 try:
  if local!=baseline:
   local_state('pending');paused=False
   try:
    paused=True;g.pause();remote=g.fetch();db,commit=commit_edits(g,remote,baseline,local);print(now(),'Management edit committed',commit,flush=True)
   finally:
    if paused:g.resume()
   # Candidate is now durable; do not replay this edit if the UI mirror step fails.
   baseline_path.write_text(json.dumps(local));(SYNC_DIR/'installed-hash').write_text('')
   return
  remote=g.fetch();identity=remote['checkpoint']['database_sha256'];installed=SYNC_DIR/'installed-hash'
  if not installed.exists() or installed.read_text()!=identity:
   install_mirror(remote['path'],local);baseline_path.write_text(json.dumps(configs(remote['path'])));installed.write_text(identity)
  local_state('synced',cloud_run_id=remote['checkpoint'].get('run_id'),database_sha256=identity)
 finally:g.close()
def main():
 os.umask(0o077);SYNC_DIR.mkdir(mode=0o700,parents=True,exist_ok=True)
 if len(sys.argv)>1 and sys.argv[1]=='initialize':
  p=SYNC_DIR/'baseline.json';assert not p.exists();p.write_text(json.dumps(configs(Path(sys.argv[2]))));print('Initialized local configuration baseline');return

 with (SYNC_DIR/'daemon.lock').open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return
  while True:
   try:cycle()
   except Exception as exc:
    print(now(),'Sync error',type(exc).__name__,str(exc)[:160],flush=True)
    try:local_state('error')
    except Exception:pass
   if sys.argv[-1]=='once':return
   time.sleep(60)
if __name__=='__main__':main()
