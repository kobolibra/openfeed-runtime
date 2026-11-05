import pytest
from openfeed.app import Recipe
from openfeed.pagination import collect_pages

@pytest.mark.parametrize('url',['http://127.0.0.1/api','http://169.254.169.254/a','https://example.org:1234/a','file:///etc/passwd'])
def test_fetch_override_remains_public_only(url):
 with pytest.raises(ValueError):Recipe(fetch_url=url)

@pytest.mark.asyncio
async def test_canonical_page_and_api_request_are_distinct():
 calls=[]
 async def http(url,**options):calls.append((url,options));return url,b'{"items":[{"title":"Public article","url":"https://example.org/article"}]}','utf-8'
 recipe={'mode':'json','fetch_url':'https://example.org/api','request_method':'POST','request_json':{'size':6},'item_selector':'items'}
 rows,_=await collect_pages('https://example.org/perspectives/',recipe,http,None)
 assert calls==[('https://example.org/api',{'method':'POST','json_data':{'size':6}})] and rows[0]['url']=='https://example.org/article'

def test_page_correction_and_restore_preserve_fetch_and_guid(tmp_path):
 from openfeed.storage import Store,same_fetch_identity
 db=Store(str(tmp_path/'canonical.sqlite'))
 f=db.create({'title':'Insights','source_url':'https://example.org/api','recipe':{'mode':'json'}})
 db.finish(f,[{'title':'Real article','url':'https://example.org/a','published_at':None}],None,1);guid=db.entries(f['id'])[0]['guid']
 updated={**f,'source_url':'https://example.org/perspectives/','recipe':{'mode':'json','fetch_url':f['source_url']}}
 assert same_fetch_identity(f,updated)
 db.update(f['id'],{'source_url':updated['source_url'],'recipe':updated['recipe']})
 db.restore_revision(f['id'],1)
 assert db.get(f['id'])['id']==f['id'] and db.entries(f['id'])[0]['guid']==guid
 assert not same_fetch_identity(f,{**f,'source_url':'https://example.org/unrelated'})
 db.close()

def test_populated_api_allows_only_unchanged_fetch_target(monkeypatch,tmp_path):
 from openfeed.storage import Store
 import openfeed.app as app
 from fastapi import HTTPException
 db=Store(str(tmp_path/'patch.sqlite'));monkeypatch.setattr(app,'store',db)
 f=db.create({'title':'Insights','source_url':'https://example.org/api','recipe':{'mode':'json'}})
 db.finish(f,[{'title':'Real article','url':'https://example.org/a','published_at':None}],None,1)
 out=app.patch(f['id'],app.Update(source_url='https://example.org/perspectives/',recipe=app.Recipe(mode='json',fetch_url='https://example.org/api')))
 assert out['id']==f['id'] and out['item_count']==1
 with pytest.raises(HTTPException) as exc:app.patch(f['id'],app.Update(source_url='https://example.org/unrelated',recipe=app.Recipe(mode='json')))
 assert exc.value.status_code==409
 with pytest.raises(HTTPException) as exc:app.patch(f['id'],app.Update(recipe=app.Recipe(mode='json',fetch_url='https://example.org/other-api')))
 assert exc.value.status_code==409
 db.close()
