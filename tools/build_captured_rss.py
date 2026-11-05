"""Generate and independently validate RSS from the reviewed real captures.
No arbitrary capture URL, no manufactured publication dates, no network bypass
inside the production app. Recipes start paused until deployment DNS is fixed.
"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
import feedparser
from bs4 import BeautifulSoup
from openfeed.extract import extract_articles,render_rss,canonical_link
from openfeed.quality import validate_items
from openfeed.storage import Store
PROFILES=[
 ('oaktree','Oaktree Memos','https://www.oaktreecapital.com/Insights/memos',{'mode':'xpath','item_selector':"//div[contains(concat(' ',normalize-space(@class),' '),' my-4 ')][a[contains(@class,'oc-title-link') and starts-with(@href,'/insights/memo/')]]",'fields':{'title':"a[contains(@class,'oc-title-link')][1]",'link':"a[contains(@class,'oc-title-link')][1]/@href",'date':"substring-after(time/@datetime,'>')"}},'/insights/memo/'),
 ('bofa','BofA Institute Transformation','https://institute.bankofamerica.com/transformation.html',{'mode':'css','item_selector':'.aem-wrap--tile','fields':{'title':'h3.tile__headline','link':'a.tile-anchor@href','date':'time[datetime]','summary':'.tile__body p'}},'/transformation/'),
 ('gold','World Gold Council Industry Insights','https://www.gold.org/industry-insights',{'mode':'css','item_selector':'article.m-blog-card','fields':{'title':'.m-blog-card__copy h3','link':'a.m-blog-card__copy@href','date':'time[datetime]','summary':'.wgc-field-introduction'}},('/responsible-gold/','/industry-insights/')),
 ('kkr','KKR Latest Insights','https://www.kkr.com/insights',{'mode':'css','item_selector':'main .teaser','fields':{'title':'p.article-teaser__title','link':'a.article-teaser__link@href','date':'time[datetime*="-"]','summary':'p.article-teaser__summary'}},'/insights/'),
 ('morgan-stanley','Morgan Stanley Insights Articles','https://www.morganstanley.com/insights',{'mode':'css','item_selector':'.cmp-insightssectionheader-inside-block, .cmp-storycard:has(a.cmp-storycard__titleLink[href^="/insights/articles/"])','fields':{'title':'h2 a, a.cmp-storycard__titleLink','link':'h2 a, a.cmp-storycard__titleLink@href','date':'time[datetime]','summary':'.cmp-storycard__description, .cmp-insightssectionheader--summary p'}},'/insights/articles/'),
 ('liepin','猎聘 · 华泰柏瑞基金职位','https://www.liepin.com/company-jobs/8652522/',{'mode':'css','item_selector':'.job-detail-box','fields':{'title':'.job-title-box','link':'a@href','date':'time[datetime]','summary':'.job-salary'}},('/job/','/a/','/lptjob/')),
]
def build(captures,out):
 out.mkdir(parents=True,exist_ok=True);dbfile=out/'captured-feeds.sqlite3'
 if dbfile.exists():raise FileExistsError('Use a new output directory; never overwrite a stored source database')
 db=Store(str(dbfile));results=[];bundle=[]
 try:
  for name,title,url,recipe,path_prefix in PROFILES:
   raw=(captures/(name+'.html')).read_bytes()
   recipe.update(fetch_mode='http',max_pages=1,min_items=1)
   items,selector=extract_articles(raw.decode('utf-8',errors='replace'),url,recipe)
   items,quality=validate_items(items)
   assert items and not quality['rejected'],(name,quality)
   assert all(any(prefix in x['url'] for prefix in (path_prefix if isinstance(path_prefix,tuple) else (path_prefix,))) for x in items),(name,'Non-article URL found')
   assert len({x['url'] for x in items})==len(items)
   # Each produced title/link must be backed by a matching actual source anchor.
   doc=BeautifulSoup(raw,'lxml');from urllib.parse import urljoin
   source_links={canonical_link(a['href'],url) for a in doc.select('a[href]')}
   assert all(x['url'] in source_links for x in items)
   identifier=hashlib.sha256(('openfeed-capture-20261022:'+name).encode()).hexdigest()[:28]
   f=db.create({'id':identifier,'title':title,'source_url':url,'description':'Verified against a captured public listing on 2026-10-22; paused pending protected network setup.','recipe':recipe,'enabled':False})
   db.finish(db.get(identifier),items,None,1)
   first_guids={x['guid'] for x in db.entries(identifier)}
   repeat=db.finish(db.get(identifier),items,None,1)
   assert repeat['inserted']==0 and {x['guid'] for x in db.entries(identifier)}==first_guids
   xml=render_rss(db.get(identifier),db.entries(identifier),f'http://localhost:8765/rss/{identifier}.xml')
   db.finish(db.get(identifier),[],'Verification-only injected fetch failure',1)
   assert render_rss(db.get(identifier),db.entries(identifier),f'http://localhost:8765/rss/{identifier}.xml')==xml
   # Leave the provided snapshot healthy, paused, and explicitly bounded.
   db.finish(db.get(identifier),items,None,1)
   xml=render_rss(db.get(identifier),db.entries(identifier),f'http://localhost:8765/rss/{identifier}.xml')
   parsed=feedparser.parse(xml)
   assert not parsed.bozo and len(parsed.entries)==len(items)
   assert {e.link for e in parsed.entries}=={i['url'] for i in items}
   assert {e.title for e in parsed.entries}=={i['title'] for i in items}
   (out/(name+'.xml')).write_bytes(xml)
   bundle.append({k:db.get(identifier)[k] for k in ('id','title','source_url','description','kind','interval_minutes','recipe','enabled')})
   result={'name':name,'title':title,'feed_id':identifier,'source_url':url,'capture_sha256':hashlib.sha256(raw).hexdigest(),'items':len(items),'dated_items':sum(bool(i['published_at']) for i in items),'rss_valid':True,'links_match_source_anchors':True,'repeat_inserted':0,'failure_preserved_rss':True,'recipe':recipe,'samples':items[:5],'scope':'One captured listing; not whole archive, not default app fetch or cloud subscription.'}
   results.append(result);print(name,len(items),'valid RSS items',flush=True)
  (out/'reviewed-recipes.json').write_text(json.dumps({'format':'openfeed-recipes','version':2,'feeds':bundle},ensure_ascii=False,indent=2))
  (out/'results.json').write_text(json.dumps({'created_at':datetime.now(timezone.utc).isoformat(),'transport':'Fixed-domain system-transport capture; production app DNS protection unchanged','results':results},ensure_ascii=False,indent=2))
  db.backup_to(str(out/'captured-feeds-backup.sqlite3'))
 finally:db.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--captures',required=True);p.add_argument('--output',required=True);a=p.parse_args();build(Path(a.captures),Path(a.output))
