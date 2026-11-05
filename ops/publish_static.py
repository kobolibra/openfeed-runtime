"""Publish local RSS snapshots to one dedicated GitHub Pages repository."""
import argparse,asyncio,fcntl,json,os,re,shutil,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path
import httpx
from defusedxml.ElementTree import fromstring
from xml.etree import ElementTree as ET
from export_static import export,public_base

REMOTE='https://github.com/kobolibra/openfeed-feeds.git'

def equivalent(old,new):
 """Ignore only the successful-fetch timestamp; all content and GUID changes count."""
 try:
  roots=[fromstring(b,forbid_dtd=True,forbid_entities=True,forbid_external=True) for b in (old,new)]
  for root in roots:
   channel=root.find('channel')
   if channel is None:return old==new
   for stamp in channel.findall('lastBuildDate'):channel.remove(stamp)
  return ET.tostring(roots[0])==ET.tostring(roots[1])
 except Exception:return old==new

def sync_files(stage,repo,include_refresh_times=False):
 changed=[]
 for src in sorted(stage.rglob('*')):
  if not src.is_file():continue
  relative=src.relative_to(stage); name=relative.as_posix()
  if name not in ('.nojekyll','subscriptions.opml') and not re.fullmatch(r'rss/[a-f0-9]{20,64}\.xml',name):raise ValueError('Unexpected export file')
  dst=repo/relative
  if dst.is_symlink() or any(p.is_symlink() for p in dst.parents if p!=repo.parent):raise ValueError('Symlink in publication path')
  raw=src.read_bytes()
  if dst.exists() and (equivalent(dst.read_bytes(),raw) if name.endswith('.xml') and not include_refresh_times else dst.read_bytes()==raw):continue
  dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw);changed.append(name)
 # Never delete old feed URLs when a feed is paused or temporarily unavailable.
 return changed

def git(repo,*args):
 env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'Never'}
 r=subprocess.run(['/usr/bin/git','-C',str(repo),*args],env=env,text=True,capture_output=True,timeout=120)
 if r.returncode:raise RuntimeError('Git '+args[0]+' failed: '+r.stderr[-1500:])
 return r.stdout.strip()

async def publish(a):
 repo=a.repo.resolve();a.state.mkdir(parents=True,exist_ok=True)
 with (a.state/'publish.lock').open('w') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return {'result':'already_running'}
  if git(repo,'remote','get-url','origin')!=REMOTE:raise ValueError('Unexpected publication repository')
  if git(repo,'branch','--show-current')!='main':raise ValueError('Expected main branch')
  if git(repo,'status','--porcelain'):raise ValueError('Publication checkout has unexpected local changes')
  git(repo,'fetch','origin','main');git(repo,'merge','--ff-only','origin/main')
  # Unpushed local commits from a transient push failure are retried below.
  with tempfile.TemporaryDirectory(prefix='export-',dir=a.state) as temp:
   stage=Path(temp)/'public'
   async with httpx.AsyncClient(base_url='http://127.0.0.1:8765',headers={'X-Admin-Token':a.token_file.read_text().strip()},trust_env=False,timeout=30) as client:
    report=await export(client,stage,public_base(a.public_base))
   changed=sync_files(stage,repo,a.include_refresh_times)
   if changed:
    git(repo,'add','--',*changed)
    git(repo,'-c','user.name=OpenFeed Publisher','-c','user.email=167677307+kobolibra@users.noreply.github.com','commit','-m','Update OpenFeed RSS snapshots')
   ahead=git(repo,'rev-list','--count','origin/main..HEAD')
   if int(ahead):git(repo,'push','origin','HEAD:main')
   result={'result':'pushed' if int(ahead) else 'unchanged','at':datetime.now(timezone.utc).isoformat(),'changed_files':len(changed),'commit':git(repo,'rev-parse','HEAD'),'feeds':report['feeds'],'refresh_errors':report['refresh_errors']}
   (a.state/'last-export.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
   (a.state/'last-success.json').write_text(json.dumps(result,indent=2))
   return result

def main():
 os.umask(0o077)
 p=argparse.ArgumentParser();p.add_argument('--include-refresh-times',action='store_true');p.add_argument('--repo',type=Path,required=True);p.add_argument('--state',type=Path,required=True);p.add_argument('--token-file',type=Path,required=True);p.add_argument('--public-base',default='https://kobolibra.github.io/openfeed-feeds');a=p.parse_args()
 try:print(json.dumps(asyncio.run(publish(a))),flush=True)
 except Exception as e:
  result={'result':'failed','at':datetime.now(timezone.utc).isoformat(),'error':str(e)}
  a.state.mkdir(parents=True,exist_ok=True);(a.state/'last-failure.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True);raise SystemExit(1)
if __name__=='__main__':main()
