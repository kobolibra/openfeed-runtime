"""Mac login/interval entry point. Restarts only the existing OpenFeed stack."""
import fcntl,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'work/local-trial/source'))
# Cloud production owns fetching/publication; local health may only maintain the UI.
CLOUD_CONTROL=R/'work/stage6/cloud-production.json'
if CLOUD_CONTROL.exists():
 cloud_control=json.loads(CLOUD_CONTROL.read_text())
 if '--health-only' not in sys.argv or cloud_control.get('phase')!='active':raise SystemExit(0)

 # The existing health agent keeps the local bridge alive; never starts a second writer.
 bridge=R/'work/local-trial/source/ops/local_cloud_sync.py'
 logs=R/'work/local-trial/source/.openfeed-local/cloud-sync'
 logs.mkdir(mode=0o700,parents=True,exist_ok=True)
 fd=os.open(str(logs/'daemon.log'),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
 with os.fdopen(fd,'a') as log:
  subprocess.Popen([sys.executable,str(bridge),'daemon'],cwd=R,stdout=log,stderr=log,start_new_session=True)


from openfeed.scheduling import claim_publication_slot
sys.path.insert(0,str(R/'work/local-trial/source/ops'))
from runtime_health import ensure_egress
S=R/'work/stage6/publisher-state';S.mkdir(parents=True,exist_ok=True);os.umask(0o077)
def health():
 try:
  with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8765/api/health',timeout=3) as r:return r.status==200
 except Exception:return False
def run(args,timeout=120):subprocess.run(args,cwd=R,env=env,check=True,timeout=timeout)
env={**os.environ,'PATH':'/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin','COLIMA_HOME':'/Users/time/Documents/Codex/.openfeed-colima','GIT_TERMINAL_PROMPT':'0'}
with (S/'cycle.lock').open('w') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit(0)
 if '--health-only' not in sys.argv:
  if not claim_publication_slot(S/'hourly-attempt.json'):raise SystemExit(0)
 ensure_egress()
 if not health():
  run(['/opt/homebrew/bin/colima','start','--profile','openfeed'],600)
  run([sys.executable,str(R/'work/stage3/live_stack.py'),'up','-d','--no-build'],180)
  for _ in range(30):
   if health():break
   time.sleep(2)
  else:raise RuntimeError('OpenFeed did not become healthy; old public RSS remains available')
 if '--health-only' in sys.argv:raise SystemExit(0)
 run([sys.executable,str(R/'work/local-trial/source/ops/publish_static.py'),'--repo',str(R/'work/stage6/publish-repo'),'--state',str(S),'--token-file',str(R/'work/local-trial/source/.openfeed-local/admin-token.txt')],420)
