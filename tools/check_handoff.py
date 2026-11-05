"""A local handoff gate; does not inspect or modify runtime services."""
import json,sys
from datetime import datetime,timezone
from pathlib import Path
from maintenance_snapshot import source_fingerprint
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/maintenance'
def main():
    errors=[]
    for name in ['README.md','CURRENT.md','DECISIONS.md','CHANGELOG.md','ISSUES.json','LOCAL_RUNTIME.md','HANDOFF_TEMPLATE.md','CLOUD_HANDOFF.md','TASKS_CLOUD.json','RESOURCE_INDEX.md']:
        if not (D/name).is_file() or not (D/name).read_text().strip():errors.append('Missing/empty: '+name)
    try:
        issues=json.loads((D/'ISSUES.json').read_text())['issues'];ids=[r['id'] for r in issues]
        tasks=json.loads((D/'TASKS_CLOUD.json').read_text())['tasks'];known={t['id'] for t in tasks}
        if len(known)!=len(tasks) or any(dep not in known for t in tasks for dep in t['depends_on']):errors.append('Invalid cloud task dependencies')
        if len(ids)!=len(set(ids)):errors.append('Duplicate issue IDs')
        if any(not r.get('next_action') or not r.get('evidence') for r in issues):errors.append('Issue missing next action/evidence')
        snap=json.loads((D/'latest-snapshot.json').read_text());age=(datetime.now(timezone.utc)-datetime.fromisoformat(snap['captured_at'])).total_seconds()
        if not 0<=age<=86400:errors.append('Runtime snapshot stale (>24h) or future-dated')
        if snap['source_sha256']!=source_fingerprint():errors.append('Code changed after runtime snapshot; refresh snapshot and document deployment state')
    except (OSError,ValueError,KeyError,TypeError) as exc:errors.append('Invalid maintenance data: '+type(exc).__name__)
    checkpoint=D/'handoffs/latest.md'
    if not checkpoint.exists():errors.append('Missing handoffs/latest.md')
    else:
        text=checkpoint.read_text()
        for key in ['维护者：','部署状态：','验证：','未完成：','下一步：']:
            if key not in text:errors.append('Handoff missing '+key)
        for name in ['CURRENT.md','CHANGELOG.md','ISSUES.json','latest-snapshot.json']:
            if (D/name).exists() and (D/name).stat().st_mtime>checkpoint.stat().st_mtime:errors.append('Handoff predates updated '+name)
    for e in errors:print('FAIL:',e)
    if errors:return 1
    print('PASS: handoff records present, snapshot recent, source fingerprint matches. This does not certify website availability or truthful completeness.')
    return 0
if __name__=='__main__':sys.exit(main())
