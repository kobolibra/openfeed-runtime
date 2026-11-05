"""v0.4 acceptance: pagination, safe URL scope, atomic recipe history and UI/API."""
import json
import sqlite3
from unittest.mock import AsyncMock

import httpx
import pytest
from defusedxml import ElementTree as XML
from openfeed.pagination import collect_pages, next_page
from openfeed.security import UnsafeURL
from openfeed.storage import Store
import openfeed.app as server

ROOT = 'https://www.example.org/insights'

def page(number, links, onward=''):
    cards=''.join(f'<article><h2><a href="/reports/{n}">Original investment research memo on markets and policy {n}</a></h2><time datetime="2026-10-20">October 20</time><p>Financial markets and global macro</p></article>' for n in links)
    nxt=f'<a class="pagination-next" href="{onward}">Next</a>' if onward else ''
    return f'<html><main>{cards}</main><nav>{nxt}</nav></html>'.encode()

@pytest.mark.asyncio
async def test_bounded_pagination_dedup_and_same_origin():
    paths={ROOT:page(1,[1,2],'/insights?page=2'),
           ROOT+'?page=2':page(2,[2,3],'/insights?page=3'),
           ROOT+'?page=3':page(3,[3,4],'/insights?page=4')}
    visits=[];pauses=[]
    async def fetch(url):
        visits.append(url)
        return (url,paths[url],'utf-8')
    recipe={'mode':'css','item_selector':'article','next_selector':'.pagination-next','max_pages':3}
    items,metrics=await collect_pages(ROOT,recipe,fetch,None,pause=lambda seconds: append_pause(pauses,seconds))
    assert [v['url'].split('/')[-1] for v in items]==['1','2','3','4']
    assert len(visits)==3 and metrics['pages_fetched']==3
    assert len(pauses)==2 and all(n>=0.2 for n in pauses)

async def append_pause(pauses,seconds):
    pauses.append(seconds)

@pytest.mark.parametrize('href',[ 'https://evil.example/stolen', '//evil.example/page', 'http://www.example.org/private', 'http://127.0.0.1/', 'file:///etc/passwd' ])
def test_pagination_does_not_leave_public_source_origin(href):
    with pytest.raises((ValueError,UnsafeURL)):
        next_page(f'<a class="next" href="{href}">Next</a>',ROOT,'.next',('https','www.example.org',None))

@pytest.mark.asyncio
async def test_pagination_loop_and_missing_selector():
    async def fetch(u):return (u,page(1,[1,2],ROOT),'utf-8')
    with pytest.raises(ValueError,match='loop'):
        await collect_pages(ROOT,{'mode':'css','item_selector':'article','next_selector':'a.pagination-next','max_pages':2},fetch,None,pause=lambda _: append_pause([],0))
    with pytest.raises(ValueError,match='requires'):
        await collect_pages(ROOT,{'mode':'css','max_pages':3},fetch,None)


def test_recipe_revisions_persist_recover_and_preserve_guids(tmp_path):
    path=str(tmp_path/'revision.sqlite')
    db=Store(path)
    f=db.create({'title':'Research','source_url':ROOT,'recipe':{'item_selector':'article'}})
    id=f['id']
    assert [x['revision'] for x in db.revisions(id)]==[1]
    db.finish(f,[{'title':'Research one','url':'https://www.example.org/r/1','summary':'','published_at':None}],None,5)
    guid=db.entries(id)[0]['guid']
    db.update(id,{'title':'Changed','recipe':{'item_selector':'.wrong'}})
    assert db.get(id)['recipe']['item_selector']=='.wrong'
    assert [x['revision'] for x in db.revisions(id)]==[2,1]
    db.close()
    restored=Store(path)
    feed=restored.restore_revision(id,1)
    assert feed['id']==id and feed['title']=='Research'
    assert feed['recipe']['item_selector']=='article'
    assert restored.entries(id)[0]['guid']==guid
    assert [r['action'] for r in restored.revisions(id)][:2]==['restored','updated']
    restored.close()


def test_no_cross_source_history_revert_after_items(tmp_path):
    db=Store(str(tmp_path/'switch.sqlite'))
    f=db.create({'title':'A','source_url':ROOT,'recipe':{}})
    db.update(f['id'],{'source_url':'https://www.example.org/other'})
    db.finish(db.get(f['id']),[{'title':'Found','url':'https://www.example.org/r/a','published_at':None}],None,1)
    with pytest.raises(ValueError, match='different source URL'):
        db.restore_revision(f['id'],1)
    db.close()


@pytest.mark.asyncio
async def test_api_paged_feed_then_failed_second_page_retains_last_good(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'api-v04.sqlite'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','release-token')
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    monkeypatch.setenv('OPENFEED_PAGE_DELAY_SECONDS','0.2')
    mapping={ROOT:page(1,[1,2],'/insights?page=2'),ROOT+'?page=2':page(2,[3,4])}
    async def ok(url):return url,mapping[url],'utf-8'
    monkeypatch.setattr(server,'fetch',ok)
    headers={'X-Admin-Token':'release-token'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://unit.example') as client:
        assert (await client.get('/api/feeds/missing/revisions')).status_code==401
        data={'title':'Test paged research','source_url':ROOT,'recipe':{'mode':'css','item_selector':'article','next_selector':'.pagination-next','max_pages':2}}
        resp=await client.post('/api/feeds',json=data,headers=headers)
        assert resp.status_code==201,resp.text
        ident=resp.json()['id']
        result=(await client.post('/api/feeds/'+ident+'/run',headers=headers)).json()
        assert result['status']=='success' and result['found']==4 and result['inserted']==4
        rss=XML.fromstring((await client.get(f'/rss/{ident}.xml')).content)
        assert len(rss.findall('./channel/item'))==4
        rev=(await client.get(f'/api/feeds/{ident}/revisions',headers=headers)).json()
        assert rev[0]['revision']==1
        changed=(await client.patch(f'/api/feeds/{ident}',json={'title':'Changed name'},headers=headers)).json()
        assert changed['title']=='Changed name'
        revert=await client.post(f'/api/feeds/{ident}/restore/1',headers=headers)
        assert revert.status_code==200 and revert.json()['feed']['title']=='Test paged research'
        assert (await client.get('/api/feeds/'+ident+'/revisions',headers=headers)).json()[0]['action']=='restored'
        async def fail_second(url):
            if '?page=2' in url: raise ValueError('Upstream 503')
            return await ok(url)
        monkeypatch.setattr(server,'fetch',fail_second)
        res=await client.post('/api/feeds/'+ident+'/run',headers=headers)
        assert res.json()['status']=='error'
        assert len(XML.fromstring((await client.get(f'/rss/{ident}.xml')).content).findall('./channel/item'))==4
    db.close()


def test_migration_existing_v03_database_without_revision_table(tmp_path):
    path=str(tmp_path/'upgrade.sqlite')
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE feeds (id TEXT PRIMARY KEY,title TEXT,description TEXT,source_url TEXT,kind TEXT,recipe TEXT,interval_minutes INTEGER,enabled INTEGER,status TEXT,last_run TEXT,last_success TEXT,next_run TEXT,created_at TEXT,last_error TEXT,item_count INTEGER,consecutive_failures INTEGER)')
        db.execute('INSERT INTO feeds VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('a'*28,'Old feed','',ROOT,'web','{"mode":"css"}',120,0,'new',None,None,None,'2026-10-01','',0,0))
    db=Store(path)
    revisions=db.revisions('a'*28)
    assert len(revisions)==1 and revisions[0]['action']=='migrated'
    data=json.loads(revisions[0]['snapshot'])
    assert data['enabled'] is False and data['recipe']=={'mode':'css'}
    assert db.get('a'*28)['enabled'] is False
    db.close()


def test_inflight_old_recipe_cannot_commit_after_edit(tmp_path):
    db=Store(str(tmp_path/'stale.sqlite'))
    f=db.create({'title':'Research','source_url':ROOT,'recipe':{'mode':'css','item_selector':'article'}})
    original=db.get(f['id'])
    db.update(f['id'],{'recipe':{'mode':'css','item_selector':'.new-card'}})
    stale=db.finish(original,[{'title':'From stale page','url':'https://www.example.org/old','summary':'','published_at':None}],None,900)
    assert stale['status']=='stale'
    assert db.get(f['id'])['recipe']['item_selector']=='.new-card'
    assert db.entries(f['id'])==[]
    assert db.get(f['id'])['last_success'] is None
    fresh=db.get(f['id'])
    db.finish(fresh,[{'title':'New correct item','url':'https://www.example.org/new','summary':'','published_at':None}],None,80)
    assert db.entries(f['id'])[0]['url']=='https://www.example.org/new'
    db.close()


@pytest.mark.asyncio
async def test_api_concurrent_rule_edit_rejects_inflight_stale_results(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'concurrent.sqlite'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','secure')
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    record=db.create({'title':'Source','source_url':ROOT,'recipe':{'mode':'css','item_selector':'article'}})
    async def change_while_fetching(url):
        db.update(record['id'],{'recipe':{'mode':'css','item_selector':'.new-layout'}})
        return url,page(1,[1,2]),'utf-8'
    monkeypatch.setattr(server,'fetch',change_while_fetching)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://unit') as client:
        response=await client.post('/api/feeds/'+record['id']+'/run',headers={'X-Admin-Token':'secure'})
        assert response.json()['status']=='stale'
        assert db.entries(record['id'])==[]
        assert db.get(record['id'])['recipe']['item_selector']=='.new-layout'
    db.close()
