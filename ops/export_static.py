"""Export only RSS and OPML for static hosting; never publish the management app."""
import argparse,hashlib,json,re,shutil,tempfile,os
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from defusedxml.ElementTree import fromstring
import httpx

ATOM='http://www.w3.org/2005/Atom'
ET.register_namespace('atom',ATOM)

def public_base(value):
 p=urlsplit(value)
 if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.port not in (None,443):raise ValueError('A public HTTPS base URL without credentials/query is required')
 if p.hostname in ('localhost','127.0.0.1','::1') or p.hostname.endswith('.local'):raise ValueError('Reader cannot subscribe to localhost')
 return value.rstrip('/')

def rewrite_rss(raw,url):
 root=fromstring(raw,forbid_dtd=True,forbid_entities=True,forbid_external=True)
 channel=root.find('channel')
 if root.tag!='rss' or channel is None:raise ValueError('Not a valid RSS channel')
 ids=[e.findtext('guid') for e in channel.findall('item')]
 if any(not x for x in ids) or len(set(ids))!=len(ids):raise ValueError('Missing or duplicate RSS GUID')
 link=next((e for e in channel.findall('{'+ATOM+'}link') if e.get('rel')=='self'),None)
 if link is None:link=ET.SubElement(channel,'{'+ATOM+'}link',{'rel':'self','type':'application/rss+xml'})
 link.set('href',url)
 return ET.tostring(root,encoding='utf-8',xml_declaration=True)

async def export(client,output,base,ids=None):
 base=public_base(base);response=await client.get('/api/feeds');response.raise_for_status();feeds=response.json()
 selected=[f for f in feeds if f['enabled'] and (ids is None or f['id'] in ids)]
 if ids is not None and ids-{f['id'] for f in selected}:raise ValueError('Unknown or paused feed selected')
 if not selected:raise ValueError('No enabled feeds selected')
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 stage=Path(tempfile.mkdtemp(prefix='openfeed-static-',dir=output.parent));(stage/'rss').mkdir();report=[]
 try:
  opml=ET.Element('opml',{'version':'2.0'});ET.SubElement(ET.SubElement(opml,'head'),'title').text='OpenFeed subscriptions';body=ET.SubElement(opml,'body')
  for feed in selected:
   ident=feed['id']
   if not re.fullmatch('[a-f0-9]{20,64}',ident):raise ValueError('Invalid feed identifier')
   response=await client.get('/rss/'+ident+'.xml');response.raise_for_status();url=base+'/rss/'+ident+'.xml';raw=rewrite_rss(response.content,url);(stage/'rss'/(ident+'.xml')).write_bytes(raw)
   ET.SubElement(body,'outline',{'type':'rss','text':feed['title'],'title':feed['title'],'xmlUrl':url,'htmlUrl':feed['source_url']})
   report.append({'id':ident,'title':feed['title'],'last_refresh_status':feed['status'],'last_success':feed.get('last_success'),'sha256':hashlib.sha256(raw).hexdigest()})
  (stage/'subscriptions.opml').write_bytes(ET.tostring(opml,encoding='utf-8',xml_declaration=True))
  # No database, recipes, admin token, status API or management HTML in stage.
  (stage/'.nojekyll').touch()
  if output.exists():
   backup=output.with_name(output.name+'.previous')
   if backup.exists():raise ValueError('Previous export exists; preserve or remove it explicitly')
   output.rename(backup)
   try:stage.rename(output)
   except BaseException:backup.rename(output);raise
   shutil.rmtree(backup)
  else:stage.rename(output)
  return {'public_base':base,'feeds':len(report),'includes_last_known_content':True,'refresh_errors':sum(r['last_refresh_status']=='error' for r in report),'files':report}
 finally:
  if stage.exists():shutil.rmtree(stage)

async def main():
 import asyncio
 p=argparse.ArgumentParser();p.add_argument('--public-base',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--token-file',type=Path,required=True);p.add_argument('--feed-id',action='append');p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8765',headers={'X-Admin-Token':a.token_file.read_text().strip()},trust_env=False,timeout=30) as client:report=await export(client,a.output,a.public_base,set(a.feed_id) if a.feed_id else None)
 a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2));a.report.chmod(0o600);print(json.dumps({'feeds':report['feeds'],'refresh_errors':report['refresh_errors'],'published':False}))
if __name__=='__main__':__import__('asyncio').run(main())
