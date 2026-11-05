"""Export a consistent SQLite snapshot into a public-file whitelist only."""
import argparse,hashlib,json,sqlite3,sys,tempfile,re
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from openfeed.storage import Store
from openfeed.extract import render_rss
from export_static import public_base,rewrite_rss

def semantic_hash(raw):
    from defusedxml.ElementTree import fromstring
    root=fromstring(raw,forbid_dtd=True,forbid_entities=True,forbid_external=True)
    channel=root.find('channel')
    for node in channel.findall('lastBuildDate'):channel.remove(node)
    return hashlib.sha256(ET.tostring(root)).hexdigest()

def export_db(db,output,base):
    base=public_base(base)
    if output.exists():raise ValueError('Export requires a fresh output directory')
    manifest={}
    with tempfile.TemporaryDirectory(prefix='openfeed-export-') as temp:
        snapshot=Path(temp)/'snapshot.sqlite3'
        read=sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True);write=sqlite3.connect(snapshot)
        try:read.backup(write)
        finally:write.close();read.close()
        store=Store(str(snapshot))
        try:
            feeds=store.list()
            if not feeds:raise ValueError('No sources to export')
            output.mkdir(parents=True,mode=0o700);(output/'rss').mkdir()
            opml=ET.Element('opml',{'version':'2.0'});ET.SubElement(ET.SubElement(opml,'head'),'title').text='OpenFeed subscriptions';body=ET.SubElement(opml,'body')
            for feed in feeds:
                ident=feed['id']
                if not re.fullmatch('[a-f0-9]{20,64}',ident):raise ValueError('Invalid feed identifier')
                url=base+'/rss/'+ident+'.xml'
                raw=rewrite_rss(render_rss(feed,store.entries(ident,100),url),url)
                (output/'rss'/(ident+'.xml')).write_bytes(raw)
                manifest[ident]={'sha256':hashlib.sha256(raw).hexdigest(),'semantic_sha256':semantic_hash(raw),'status':feed['status']}
                if feed['enabled']:ET.SubElement(body,'outline',{'type':'rss','text':feed['title'],'title':feed['title'],'xmlUrl':url,'htmlUrl':feed['source_url']})
            (output/'subscriptions.opml').write_bytes(ET.tostring(opml,encoding='utf-8',xml_declaration=True));(output/'.nojekyll').touch()
        finally:store.close()
    return {'feeds':len(manifest),'includes_last_known_content':True,'files':manifest,'published':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--public-base',default='https://kobolibra.github.io/openfeed-feeds');a=p.parse_args()
    report=export_db(a.db,a.output,a.public_base);a.manifest.write_text(json.dumps(report,indent=2));print(json.dumps({'feeds':report['feeds'],'published':False}))
if __name__=='__main__':main()
