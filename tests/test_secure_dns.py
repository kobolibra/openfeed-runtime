"""Secure DNS keeps actual dial addresses public under Fake-IP system DNS."""
import json
import socket
import pytest
import openfeed.security as security

class Response:
    status = 200
    def __init__(self, answer):
        self.answer = answer
        self.content = self
    async def iter_chunked(self, limit):
        body=json.dumps(self.answer).encode()
        for offset in range(0,len(body),7):yield body[offset:offset+7]
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass

class Client:
    answer = {}
    def __init__(self, **kwargs): assert kwargs['trust_env'] is False
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    def get(self, url, **kwargs):
        assert url == 'https://dns.google/resolve'
        assert kwargs['allow_redirects'] is False
        assert kwargs['params']['name'] == 'example.org'
        return Response(self.answer)

@pytest.mark.asyncio
async def test_secure_dns_returns_vetted_socket_addresses(monkeypatch):
    monkeypatch.setenv('OPENFEED_DNS_MODE', 'doh')
    monkeypatch.setattr(security, 'ClientSession', Client)
    monkeypatch.setattr(Client, 'answer', {'Status':0, 'Answer':[
        {'type':5,'data':'edge.example.org.'}, {'type':1,'data':'93.184.215.14'}]})
    rows = await security.PublicResolver().resolve('example.org',443)
    assert rows == [{'hostname':'example.org','host':'93.184.215.14','port':443,
                     'family':socket.AF_INET,'proto':socket.IPPROTO_TCP,'flags':0}]

@pytest.mark.asyncio
@pytest.mark.parametrize('address', ['198.18.0.34','127.0.0.1','169.254.169.254','10.1.2.3','::ffff:127.0.0.1'])
async def test_secure_dns_rejects_mixed_public_and_private_answers(monkeypatch,address):
    monkeypatch.setenv('OPENFEED_DNS_MODE','doh')
    monkeypatch.setattr(security,'ClientSession',Client)
    monkeypatch.setattr(Client,'answer',{'Status':0,'Answer':[
        {'type':1,'data':'93.184.215.14'}, {'type':28 if ':' in address else 1,'data':address}]})
    with pytest.raises(security.UnsafeURL,match='non-public'):
        await security.PublicResolver().resolve('example.org',443)

@pytest.mark.asyncio
@pytest.mark.parametrize('answer',[{'Status':3},{'Status':0}, {'Status':0,'Answer':[{'type':1,'data':'2606:4700:4700::1111'}]}])
async def test_secure_dns_fails_closed(monkeypatch,answer):
    monkeypatch.setenv('OPENFEED_DNS_MODE','doh')
    monkeypatch.setattr(security,'ClientSession',Client)
    monkeypatch.setattr(Client,'answer',answer)
    with pytest.raises(security.UnsafeURL): await security.PublicResolver().resolve('example.org',443)

@pytest.mark.asyncio
async def test_unknown_dns_mode_fails_closed(monkeypatch):
    monkeypatch.setenv('OPENFEED_DNS_MODE','typo')
    with pytest.raises(security.UnsafeURL): await security.PublicResolver().resolve('example.org',443)

@pytest.mark.parametrize('value',['October 2026','2026-10','2026','Oct 22','13:45','2026年10月'])
def test_incomplete_dates_never_invent_day_or_year(value):
    from openfeed.extract import parse_date
    assert parse_date(value) is None

@pytest.mark.parametrize('value',['October 22, 2026','2026-10-22','2026年10月22日','Thu, 22 Oct 2026 13:45:00 GMT'])
def test_complete_publication_dates_still_parse(value):
    from openfeed.extract import parse_date
    assert parse_date(value).startswith('2026-10-22')

def test_article_card_can_be_the_anchor_itself():
    from openfeed.extract import extract_articles
    items,_=extract_articles('<main><a class="article" href="/memo"><h2>Economic outlook</h2></a></main>',
        'https://example.org/insights',{'mode':'css','item_selector':'a.article','fields':{'title':'h2','link':':scope@href'}})
    assert len(items)==1 and items[0]['url']=='https://example.org/memo'

def test_fragment_identities_are_opt_in_for_real_inline_publications():
    from openfeed.extract import extract_articles
    html='<section><div id="one"><h2>Research role</h2></div><div id="two"><h2>Risk role</h2></div></section>'
    recipe={'mode':'xpath','item_selector':'//div','fields':{'title':'./h2','link':"concat('https://example.org/jobs#',@id)"}}
    assert extract_articles(html,'https://example.org/jobs',recipe)[0]==[]
    items,_=extract_articles(html,'https://example.org/jobs',{**recipe,'keep_fragments':True})
    assert {x['url'] for x in items}=={'https://example.org/jobs#one','https://example.org/jobs#two'}

def test_post_api_configuration_is_bounded_and_cannot_be_browser_mode():
    from openfeed.app import Recipe
    from pydantic import ValidationError
    assert Recipe(mode='json',request_method='POST',request_data={'pageIndex':'0'}).request_data=={'pageIndex':'0'}
    for config in [{'mode':'css','request_method':'POST'}, {'mode':'json','fetch_mode':'browser','request_method':'POST'}, {'mode':'json','request_method':'POST','request_data':{'x':'z'*501}}]:
        with pytest.raises(ValidationError):Recipe(**config)

def test_link_whitespace_matches_browser_href_semantics():
    from openfeed.extract import canonical_link
    assert canonical_link('\n    /research/one\n   ','https://example.org/list')=='https://example.org/research/one'

def test_json_latest_sort_precedes_feed_budget():
    from openfeed.extract import extract_articles
    rows=[{'title':f'Report {n}','url':f'https://example.org/report/{n}','date':f'2026-{n//28+1:02d}-{n%28+1:02d}'} for n in range(110)]
    items,_=extract_articles(json.dumps({'items':rows}),'https://example.org/api',{'mode':'json','item_selector':'items','sort_newest':True})
    assert len(items)==100 and items[0]['title']=='Report 109' and items[-1]['title']=='Report 10'

@pytest.mark.asyncio
async def test_saved_json_post_recipe_reaches_real_fetch_pipeline():
    from openfeed.pagination import collect_pages
    calls=[]
    async def http(url,**kwargs):
        calls.append((url,kwargs))
        return url,b'{"data":{"items":[{"title":"China outlook","url":"https://example.org/notes/1","date":"2026-10-22"}]}}','utf-8'
    async def browser(*args):raise AssertionError('Public JSON must not silently switch browser mode')
    items,_=await collect_pages('https://example.org/search',{'mode':'json','item_selector':'data.items','request_method':'POST','request_data':{'catalog':'china'}},http,browser)
    assert items[0]['title']=='China outlook' and calls==[('https://example.org/search',{'method':'POST','data':{'catalog':'china'}})]

def test_public_json_resolves_real_pdf_paths_and_article_ids():
    from openfeed.extract import extract_articles
    recipe={'mode':'json','item_selector':'items','fields':{'link':'id'},'link_template':'https://example.org/news?id={value}','direct_link_field':'document','direct_link_base':'https://example.org/files/'}
    items,_=extract_articles(json.dumps({'items':[{'id':'7','title':'Report','document':'2026/report.pdf'},{'id':'8','title':'Article','document':'Article body'}]}),'https://example.org/api',recipe)
    assert [r['url'] for r in items]==['https://example.org/files/2026/report.pdf','https://example.org/news?id=8']
