import asyncio,json
import pytest
from openfeed.app import Recipe
from openfeed.extract import extract_articles
from openfeed.pagination import collect_pages

def recipe(**kw):
 return Recipe(mode='json',item_selector='data',fields={'title':'headline','link':'url'},request_method='POST',request_json={'q':'China','from':1},json_contract={'success':True,'parameters.q':'China'},json_filters={'format':'Opinion'},json_offset_field='from',json_offset_response_path='parameters.from',json_page_step=2,max_pages=3,**kw).model_dump()
def row(i,kind='Opinion'):return {'headline':str(i),'url':f'https://example.com/articles/{i}','format':kind}
def document(offset,rows):return {'success':True,'parameters':{'q':'China','from':offset},'data':rows}
async def no_pause(_):pass

def test_pages_filter_and_offset_advance():
 calls=[]
 async def fetch(url,**kw):
  n=kw['json_data']['from'];calls.append(n)
  rows={1:[row(1,'News Release'),row(2)],3:[row(3),row(2)],5:[row(5)]}[n]
  return url,json.dumps(document(n,rows)).encode(),'utf-8'
 items,metrics=asyncio.run(collect_pages('https://example.com/api',recipe(),fetch,None,pause=no_pause))
 assert calls==[1,3,5] and [x['title'] for x in items]==['2','3','5']
 assert metrics['pages_fetched']==3 and not metrics['limit_reached']

@pytest.mark.parametrize('fault',['offset','contract','repeat','oversize'])
def test_incomplete_or_wrong_response_fails_whole_run(fault):
 async def fetch(url,**kw):
  n=kw['json_data']['from'];rows=[row(1),row(2)] if fault=='repeat' else [row(n),row(n+1)]
  d=document(n,rows)
  if n>1:
   if fault=='offset':d['parameters']['from']=1
   if fault=='contract':d['parameters']['q']='Other'
   if fault=='oversize':d['data'].append(row(999))
  return url,json.dumps(d).encode(),'utf-8'
 with pytest.raises(ValueError):asyncio.run(collect_pages('https://example.com/api',recipe(),fetch,None,pause=no_pause))

def test_missing_filter_field_is_not_silently_discarded():
 d=document(1,[{'headline':'x','url':'https://example.com/x'}])
 with pytest.raises(ValueError):extract_articles(json.dumps(d),'https://example.com/api',recipe())

def test_cannot_configure_filtered_job_inventory():
 with pytest.raises(ValueError):recipe(content_type='jobs')

def test_zero_matches_not_official_empty():
 async def fetch(url,**kw):return url,json.dumps(document(1,[row(1,'News Release')])).encode(),'utf-8'
 items,metrics=asyncio.run(collect_pages('https://example.com/api',recipe(),fetch,None,pause=no_pause))
 assert not items and not metrics.get('empty_confirmed')

def test_woodmac_search_tracking_does_not_change_identity():
 from openfeed.extract import canonical_link
 base='https://www.woodmac.com/news/opinion/example/'
 assert canonical_link(base+'?_t_uuid=a&_t_id=x&_t_hit.pos=2&edition=uk',base)==base+'?edition=uk'
 assert canonical_link(base+'?_t_uuid=b&edition=uk',base)==base+'?edition=uk'
 other='https://example.com/news/opinion/example/?_t_uuid=a'
 assert canonical_link(other,base)==other
