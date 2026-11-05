"""Read-only local runtime snapshot. Never export tokens or full recipes."""
import argparse,hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]

def source_fingerprint():
    h=hashlib.sha256()
    files=sorted([*ROOT.glob('openfeed/*.py'),*ROOT.glob('ops/*.py')])
    for p in files:
        h.update(str(p.relative_to(ROOT)).encode());h.update(b'\0');h.update(p.read_bytes())
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--token-file',type=Path,default=ROOT/'.openfeed-local/admin-token.txt');args=parser.parse_args()
    token=args.token_file.read_text().strip()
    with httpx.Client(base_url='http://127.0.0.1:8765',headers={'X-Admin-Token':token},trust_env=False,timeout=30) as client:
        a=client.get('/api/feeds');a.raise_for_status();feeds=a.json()
        b=client.get('/api/status');b.raise_for_status();status=b.json()
    now=datetime.now(timezone.utc)
    fields=['id','title','enabled','status','last_run','last_success','next_run','consecutive_failures','item_count','interval_minutes','schedule_phase_seconds']
    rows=[]
    for f in feeds:
        row={k:f.get(k) for k in fields}
        # Error text can contain URLs or page data, so retain only its fingerprint.
        row['last_error_sha256']=hashlib.sha256((f.get('last_error') or '').encode()).hexdigest()
        row['recipe_sha256']=hashlib.sha256(json.dumps(f.get('recipe',{}),sort_keys=True).encode()).hexdigest()
        rows.append(row)
    result={'captured_at':now.isoformat(),'scope':'Read-only API observation; not source acceptance or deployed-code verification','source_sha256':source_fingerprint(),'api_version':status.get('version'),'scheduling':status.get('scheduling'),'counts':{'total':len(rows),'healthy':sum(x['status']=='healthy' for x in rows),'error':sum(x['status']=='error' for x in rows),'paused':sum(not x['enabled'] for x in rows)},'feeds':rows}
    folder=ROOT/'docs/maintenance';archive=folder/'snapshots';archive.mkdir(exist_ok=True)
    raw=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    path=archive/(now.strftime('%Y%m%dT%H%M%S%fZ')+'.json');path.write_text(raw)
    temp=folder/'latest-snapshot.tmp';temp.write_text(raw);os.replace(temp,folder/'latest-snapshot.json')
    print(json.dumps({'captured_at':result['captured_at'],'counts':result['counts'],'snapshot':str(path)},ensure_ascii=False))
if __name__=='__main__':main()
