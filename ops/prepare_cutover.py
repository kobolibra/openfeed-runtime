"""Prepare a new private union snapshot. Never replaces either running input."""
import argparse,hashlib,json,os,sqlite3
from datetime import datetime
from pathlib import Path
FIELDS=('feed_id','guid','title','url','summary','published_at','first_seen_at','last_seen_at','missing_count','availability')
SCOPE='select id,source_url,recipe,interval_minutes,schedule_phase_seconds,enabled from feeds'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def readonly(path):
    c=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    if c.execute('pragma integrity_check').fetchone()[0]!='ok':c.close();raise ValueError('Invalid input SQLite')
    return c
def prepare(mac,cloud,output):
    if output.exists():raise ValueError('Cutover staging directory must be new')
    before={'mac':digest(mac),'cloud':digest(cloud)};a=readonly(mac);b=readonly(cloud)
    try:
        if set(map(tuple,a.execute(SCOPE)))!=set(map(tuple,b.execute(SCOPE))):raise ValueError('Source scope, recipe, interval, phase or enabled state differs')
        if any(tuple(r[1] for r in c.execute('pragma table_info(items)'))!=FIELDS for c in (a,b)):raise ValueError('Unsupported item schema')
        mac_rows={(r['feed_id'],r['guid']):dict(r) for r in a.execute('select * from items')}
        cloud_rows={(r['feed_id'],r['guid']):dict(r) for r in b.execute('select * from items')}
        merged=dict(mac_rows);ledger=[];cloud_updates=0
        for key,row in cloud_rows.items():
            old=mac_rows.get(key)
            if old is None:merged[key]=row;continue
            if old['url']!=row['url']:raise ValueError('Shared GUID has different URL')
            if old['first_seen_at']!=row['first_seen_at']:ledger.append({'feed_id':key[0],'guid':key[1],'mac_first_seen_at':old['first_seen_at'],'cloud_first_seen_at':row['first_seen_at'],'selected':'Mac production first_seen; cloud provenance retained here'})
            stamps=[datetime.fromisoformat(x['last_seen_at']) for x in (old,row)]
            if any(t.tzinfo is None for t in stamps):raise ValueError('Item last_seen requires timezone')
            if stamps[1]>stamps[0]:merged[key]={**row,'first_seen_at':old['first_seen_at']};cloud_updates+=1
        output.mkdir(parents=True,mode=0o700);dest=output/'openfeed.sqlite3';write=sqlite3.connect(dest)
        try:
            a.backup(write)
            with write:
                write.executemany('insert or replace into items ('+','.join(FIELDS)+') values ('+','.join('?' for _ in FIELDS)+')',[tuple(row[k] for k in FIELDS) for row in merged.values()])
                write.execute('create table if not exists shadow_cycle_starts (host text primary key, started real not null)')
                if b.execute("select 1 from sqlite_master where type='table' and name='shadow_cycle_starts'").fetchone():
                    write.executemany('insert into shadow_cycle_starts values (?,?) on conflict(host) do update set started=max(started,excluded.started)',[tuple(r) for r in b.execute('select host,started from shadow_cycle_starts')])
            assert write.execute('pragma integrity_check').fetchone()[0]=='ok'
            result_keys=set(write.execute('select feed_id,guid from items'));assert result_keys==mac_rows.keys()|cloud_rows.keys()
            first={(f,g):t for f,g,t in write.execute('select feed_id,guid,first_seen_at from items')};assert all(first[k]==r['first_seen_at'] for k,r in mac_rows.items())
        finally:write.close()
        dest.chmod(0o600);raw=json.dumps(ledger,indent=2);(output/'first-seen-provenance.json').write_text(raw);(output/'first-seen-provenance.json').chmod(0o600)
        assert digest(mac)==before['mac'] and digest(cloud)==before['cloud']
        report={'scope':'Offline cutover rehearsal; not a final stopped-writer snapshot','input_sha256':before,'output_sha256':digest(dest),'mac_items':len(mac_rows),'cloud_items':len(cloud_rows),'union_items':len(merged),'mac_only':len(mac_rows.keys()-cloud_rows.keys()),'cloud_only':len(cloud_rows.keys()-mac_rows.keys()),'first_seen_conflicts_archived':len(ledger),'cloud_newer_metadata_selected':cloud_updates,'mac_first_seen_preserved':True,'all_guid_keys_preserved':True,'source_scope_phase_preserved':True,'input_databases_unchanged':True,'production_changed':False,'published':False}
        (output/'report.json').write_text(json.dumps(report,indent=2));return report
    finally:a.close();b.close()
if __name__=='__main__':
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('--mac-db',type=Path,required=True);p.add_argument('--cloud-db',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.mac_db,a.cloud_db,a.output)))
