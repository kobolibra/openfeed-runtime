"""Publication plumbing, disabled until an explicit validated production control."""
import hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path
from datetime import datetime,timezone
from export_db import export_db
from publish_static import sync_files
from pages_build import build_published_commit
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
    if previous.get('result')=='attempt_reserved':
        if not previous.get('candidate_sha256'):raise ValueError('Pending publication requires its frozen candidate')
        return {**previous,'slot':slot,'reuse_candidate':True}
    if previous.get('slot')==slot:return None
    return {'slot':slot,'timezone':'Asia/Shanghai','result':'attempt_reserved','at':datetime.now(timezone.utc).isoformat()}

def freeze_publication(state,intent):
    candidate=state/'publication-candidate.sqlite3'
    if intent.get('reuse_candidate'):
        if not candidate.exists() or hashlib.sha256(candidate.read_bytes()).hexdigest()!=intent['candidate_sha256']:
            raise ValueError('Frozen publication candidate is missing or changed')
    else:
        temp=state/'publication-candidate.tmp';shutil.copyfile(state/'openfeed.sqlite3',temp);os.replace(temp,candidate);candidate.chmod(0o600)
        intent={**intent,'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),'origin_slot':intent['slot']}
    (state/'publication-state.json').write_text(json.dumps(intent,indent=2));return intent

def complete_publication(state,publication):
    path=state/'publication-state.json';intent=json.loads(path.read_text())
    intent.update(result='complete',public_commit=publication['commit'],pages=publication['pages'],completed_at=datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(intent,indent=2))

def git(repo,*args):
    r=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,check=True,timeout=120)
    return r.stdout.strip()

def publish_committed_state(state,public_repo):
    # The caller must push the corresponding private DB+slot reservation first.
    if not os.getenv('OPENFEED_PAGES_TOKEN'):raise ValueError('Explicit production Pages token required before any public write')
    intent=json.loads((state/'publication-state.json').read_text())
    candidate=state/'publication-candidate.sqlite3'
    if intent.get('result')!='attempt_reserved' or not candidate.exists() or hashlib.sha256(candidate.read_bytes()).hexdigest()!=intent.get('candidate_sha256'):raise ValueError('Expected verified frozen publication candidate')
    remote=git(public_repo,'remote','get-url','origin')
    if remote.rstrip('/').removesuffix('.git')!=REMOTE:raise ValueError('Wrong public publication repository')
    if git(public_repo,'branch','--show-current')!='main' or git(public_repo,'status','--porcelain'):
        raise ValueError('Public checkout must be clean main')
    git(public_repo,'fetch','origin','main');git(public_repo,'merge','--ff-only','origin/main')
    with tempfile.TemporaryDirectory(prefix='private-rss-export-') as temp:
        stage=Path(temp)/'public';report=export_db(candidate,stage,BASE)
        changed=sync_files(stage,public_repo)
        if changed:
            git(public_repo,'add','--',*changed)
            git(public_repo,'-c','user.name=OpenFeed Cloud Publisher','-c','user.email=openfeed@users.noreply.github.com','commit','-m','Update OpenFeed RSS snapshots')
        ahead=int(git(public_repo,'rev-list','--count','origin/main..HEAD'))
        if ahead:git(public_repo,'push','origin','HEAD:main')
        commit=git(public_repo,'rev-parse','HEAD')
        pages=build_published_commit(commit)
        return {'result':'pushed' if ahead else 'unchanged','changed_files':len(changed),'feeds':report['feeds'],'commit':commit,'pages':pages}
