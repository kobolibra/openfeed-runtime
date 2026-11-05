"""Publication plumbing, disabled until an explicit validated production control."""
import json,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone
from export_db import export_db
from publish_static import sync_files
from openfeed.scheduling import publication_slot

BASE='https://kobolibra.github.io/openfeed-feeds'
REMOTE='https://github.com/kobolibra/openfeed-feeds'

def publication_intent(state,now=None):
    control_path=state/'runtime-control.json'
    if not control_path.exists():return None
    control=json.loads(control_path.read_text())
    if control.get('mode')!='production' or control.get('publish_enabled') is not True:return None
    if control.get('mac_writer_stopped') is not True or not control.get('final_mac_snapshot_sha256'):
        raise ValueError('Production publication requires final snapshot and stopped Mac writer')
    slot=publication_slot(now)
    if slot is None:return None
    previous_path=state/'publication-state.json'
    previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
    if previous.get('slot')==slot:return None
    return {'slot':slot,'timezone':'Asia/Shanghai','result':'attempt_reserved','at':datetime.now(timezone.utc).isoformat()}

def git(repo,*args):
    r=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,check=True,timeout=120)
    return r.stdout.strip()

def publish_committed_state(state,public_repo):
    # The caller must push the corresponding private DB+slot reservation first.
    remote=git(public_repo,'remote','get-url','origin')
    if remote.rstrip('/').removesuffix('.git')!=REMOTE:raise ValueError('Wrong public publication repository')
    if git(public_repo,'branch','--show-current')!='main' or git(public_repo,'status','--porcelain'):
        raise ValueError('Public checkout must be clean main')
    git(public_repo,'fetch','origin','main');git(public_repo,'merge','--ff-only','origin/main')
    with tempfile.TemporaryDirectory(prefix='private-rss-export-') as temp:
        stage=Path(temp)/'public';report=export_db(state/'openfeed.sqlite3',stage,BASE)
        changed=sync_files(stage,public_repo)
        if changed:
            git(public_repo,'add','--',*changed)
            git(public_repo,'-c','user.name=OpenFeed Cloud Publisher','-c','user.email=openfeed@users.noreply.github.com','commit','-m','Update OpenFeed RSS snapshots')
        ahead=int(git(public_repo,'rev-list','--count','origin/main..HEAD'))
        if ahead:git(public_repo,'push','origin','HEAD:main')
        return {'result':'pushed' if ahead else 'unchanged','changed_files':len(changed),'feeds':report['feeds'],'commit':git(public_repo,'rev-parse','HEAD')}
