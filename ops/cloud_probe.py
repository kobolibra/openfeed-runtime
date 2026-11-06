"""Read-only source response evidence, committed only to a separate private ref."""
import argparse,asyncio,hashlib,json,os,re,sqlite3,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from openfeed.security import fetch
from openfeed.extract import extract_articles
EXPIRY=1794053385
async def probe(db,ident,output):
    if time.time()>=EXPIRY:raise ValueError('Diagnostic validation deadline expired')
    if output.exists():raise ValueError('Diagnostic output must be new')
    before=hashlib.sha256(db.read_bytes()).hexdigest()
    c=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)
    try:row=c.execute('select source_url,recipe from feeds where id=?',(ident,)).fetchone()
    finally:c.close()
    if not row:raise ValueError('Unknown source ID')
    output.mkdir(parents=True,mode=0o700)
    final,body,enc=await fetch(row[0]);articles,selector=extract_articles(body.decode(enc,errors='replace'),final,json.loads(row[1]))
    (output/'response.bin').write_bytes(body)
    result={'source_id':ident,'final_url':final,'bytes':len(body),'response_sha256':hashlib.sha256(body).hexdigest(),'articles':len(articles),'selector':selector,'input_db_unchanged':hashlib.sha256(db.read_bytes()).hexdigest()==before,'production_written':False,'published':False}
    assert result['input_db_unchanged'];(output/'result.json').write_text(json.dumps(result,indent=2))
async def probes(db,identifiers,output):
    ids=list(dict.fromkeys(identifiers.split(',')))
    if len(ids)>5 or any(not re.fullmatch('[a-f0-9]{20,64}',ident) for ident in ids):raise ValueError('Invalid bounded diagnostic IDs')
    failed=False
    for index,ident in enumerate(ids):
        if index:await asyncio.sleep(60)
        target=output/ident if len(ids)>1 else output
        try:await probe(db,ident,target)
        except Exception as error:
            failed=True;target.mkdir(parents=True,exist_ok=True);(target/'error.json').write_text(json.dumps({'source_id':ident,'error':str(error),'production_written':False,'published':False},indent=2))
    if failed:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--feed-id',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();os.umask(0o077);asyncio.run(probes(a.db,a.feed_id,a.output))
