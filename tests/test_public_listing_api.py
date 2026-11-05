import json
import pytest
from openfeed.extract import extract_articles
from openfeed.app import Recipe
from openfeed import security

def test_unix_date_is_explicit_and_sorted():
    cfg={'mode':'json','item_selector':'results','date_format':'unix_seconds','sort_newest':True,'fields':{'title':'data.title','link':'data.link','date':'data.publishedDate'}}
    raw=json.dumps({'results':[{'data':{'title':'Earlier article','link':'https://example.org/a','publishedDate':1791984180}},{'data':{'title':'Later article','link':'https://example.org/b','publishedDate':1792070580}}]})
    rows,_=extract_articles(raw,'https://example.org/api',cfg)
    assert [r['title'] for r in rows]==['Later article','Earlier article']
    assert rows[0]['published_at']=='2026-10-15T13:23:00+00:00'
    cfg['date_format']='auto'
    assert all(r['published_at'] is None for r in extract_articles(raw,'https://example.org/api',cfg)[0])

@pytest.mark.parametrize('key',['a\r\nHost: evil','a b','a'*501])
def test_public_key_cannot_inject_headers(key):
    with pytest.raises(ValueError):Recipe(public_api_key=key)

@pytest.mark.asyncio
async def test_public_key_does_not_follow_cross_origin_redirect(monkeypatch):
    requests=[]
    class Response:
        charset='utf-8'
        def __init__(self,url,redirect=False):
            self.url=url;self.status=302 if redirect else 200
            self.headers={'Location':'https://other.example.org/list'} if redirect else {'Content-Type':'application/json'}
            self.content=self
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def iter_chunked(self,n):yield b'{"items":[]}'
    class Client:
        def __init__(self,**kwargs):assert kwargs['trust_env'] is False
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def get(self,url,**kwargs):
            requests.append((url,kwargs));return Response(url,len(requests)==1)
    monkeypatch.setattr(security,'ClientSession',Client)
    monkeypatch.setattr(security,'TCPConnector',lambda **kwargs:None)
    await security.fetch('https://example.org/list',public_api_key='public-frontend-key')
    assert requests[0][1]['headers']=={'X-Api-Key':'public-frontend-key'}
    assert 'headers' not in requests[1][1]
    with pytest.raises(ValueError,match='HTTPS'):
        await security.fetch('http://example.org/list',public_api_key='public-frontend-key')


@pytest.mark.parametrize('value,expected',[(1792584000000,'2026-10-21T12:00:00+00:00'),(True,None),('1792584000',None)])
def test_explicit_millisecond_dates_do_not_guess_units(value,expected):
    from openfeed.extract import parse_json_date
    assert parse_json_date(value,{'date_format':'unix_milliseconds'})==expected
