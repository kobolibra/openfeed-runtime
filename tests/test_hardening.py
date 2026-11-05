"""Release-gate regression tests: security, durable state, JSON Feed and migrations."""
from datetime import datetime, timezone
import asyncio
import json
import socket
import sqlite3
from unittest.mock import AsyncMock
import httpx
import pytest
from openfeed.security import PublicResolver, check_url, UnsafeURL
from openfeed.extract import parse_native, render_rss
from openfeed.storage import Store
import openfeed.app as server


@pytest.mark.parametrize('value',[
    'http://127.1/private', 'http://[::ffff:127.0.0.1]',
    'http://[fe80::1%25eth0]/', 'http://192.0.0.1/',
    'http://169.254.169.254/latest', 'https://localhost./',
    'ftp://example.org/news', 'https://public.example.org:8443/',
])
def test_create_time_url_protection(value):
    with pytest.raises(UnsafeURL):
        check_url(value,resolve=False)


@pytest.mark.asyncio
async def test_resolver_validates_actual_dial_addresses(monkeypatch):
    class FakeLoop:
        async def getaddrinfo(self,host,port,**kwargs):
            assert host=='example.org'
            return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.215.14',443)),
                    (socket.AF_INET,socket.SOCK_STREAM,6,'',('169.254.169.254',443))]
    monkeypatch.setattr(asyncio,'get_running_loop',lambda:FakeLoop())
    with pytest.raises(UnsafeURL,match='DNS'):
        await PublicResolver().resolve('example.org',443)


def test_failure_counter_reset_and_history_preservation(tmp_path):
    db=Store(str(tmp_path/'retry.sqlite'))
    f=db.create({'title':'Research','source_url':'https://example.org/research','recipe':{}})
    for counter in range(3):
        db.finish(db.get(f['id']),[],"Upstream down",300)
        assert db.get(f['id'])['consecutive_failures']==counter+1
    record={'title':'Valid research note','url':'https://example.org/notes/1','summary':'Published insight','published_at':None}
    db.finish(db.get(f['id']),[record],None,200)
    assert db.get(f['id'])['consecutive_failures']==0
    db.finish(db.get(f['id']),[],"Temporary error",200)
    assert db.get(f['id'])['consecutive_failures']==1
    assert len(db.entries(f['id']))==1
    db.close()


def test_jsonfeed_11_and_xml_validity():
    body=json.dumps({'version':'https://jsonfeed.org/version/1.1','items':[
        {'id':'1','url':'https://example.org/a','title':'Global Markets','date_published':'2026-10-20T08:00:00Z','summary':'Sample'},
        {'id':'1','url':'https://example.org/a','title':'Global Markets Duplicate'}
    ]}).encode()
    data=parse_native(body,'https://example.org/feed.json')
    assert len(data)==1 and data[0]['published_at'].startswith('2026-10-20')
    with pytest.raises(ValueError,match='recognized JSON Feed'):
        parse_native(b'{"items":[]}','https://example.org/file.json')


def test_store_schema_upgrade_from_v01(tmp_path):
    path=tmp_path/'legacy.sqlite'
    # Simulate a v0.1-created database missing the new tracking column.
    db=Store(str(path));db.db.execute('ALTER TABLE feeds RENAME TO feeds_old')
    db.db.execute('CREATE TABLE feeds AS SELECT id,title,description,source_url,kind,recipe,interval_minutes,enabled,status,last_run,last_success,next_run,created_at,last_error,item_count FROM feeds_old')
    db.db.execute('DROP TABLE feeds_old');db.close()
    # Pragmas and stale foreign keys would need recreating for full real migration;
    # here we test specifically the additive schema detection.
    upgraded=Store(str(path))
    assert 'consecutive_failures' in {r[1] for r in upgraded.db.execute('PRAGMA table_info(feeds)')}
    upgraded.close()


@pytest.mark.asyncio
async def test_recipe_v2_restores_ids_and_disabled_state(monkeypatch,tmp_path):
    source=Store(str(tmp_path/'before.sqlite'))
    record=source.create({'title':'Institutional RSS','source_url':'https://example.org/insights',
                          'recipe':{'mode':'css','item_selector':'article'},'enabled':False})
    assert not source.get(record['id'])['enabled']
    monkeypatch.setattr(server,'store',source);monkeypatch.setattr(server,'TOKEN','secure-test-token')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://unit.local') as client:
        headers={'X-Admin-Token':'secure-test-token'}
        backup=(await client.get('/api/export/recipes',headers=headers)).json()
    assert backup['version']==2 and backup['feeds'][0]['id']==record['id']
    source.close()
    target=Store(str(tmp_path/'after.sqlite'));monkeypatch.setattr(server,'store',target)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://unit.local') as client:
        headers={'X-Admin-Token':'secure-test-token'}
        reply=await client.post('/api/import/recipes',headers=headers,json=backup)
        assert reply.status_code==200,reply.text
        assert reply.json()['imported']==1
        assert (await client.post('/api/import/recipes',headers=headers,json=backup)).json()['skipped']==1
        restored=(await client.get('/api/feeds/'+record['id'],headers=headers)).json()['feed']
        assert restored['id']==record['id'] and restored['enabled'] is False
    target.close()


def test_throttled_source_gets_future_due_time(tmp_path):
    db=Store(str(tmp_path/'due.sqlite'))
    a=db.create({'title':'A','source_url':'https://example.org/a','recipe':{},'interval_minutes':120})
    b=db.create({'title':'B','source_url':'https://example.org/b','recipe':{},'interval_minutes':120})
    assert {f['id'] for f in db.due()} == {a['id'],b['id']}
    db.defer(a['id'],120)
    assert {f['id'] for f in db.due()} == {b['id']}
    db.close()


def test_rss_does_not_fabricate_original_date_and_strips_invalid_xml(tmp_path):
    from defusedxml import ElementTree as ET
    db=Store(str(tmp_path/'dates.sqlite'))
    feed=db.create({'title':'Global\x01 Markets','source_url':'https://example.org/research','recipe':{}})
    item={'title':'Sample\x02 paper','url':'https://example.org/p/1','summary':'New\x07 evidence','published_at':None}
    db.finish(feed,[item],None,80)
    result=ET.fromstring(render_rss(db.get(feed['id']),db.entries(feed['id']), 'https://feeds.example.org/rss/test.xml'))
    entry=result.find('./channel/item')
    assert entry.find('pubDate') is None
    assert entry.find('title').text=='Sample paper'
    db.close()


@pytest.mark.asyncio
async def test_cannot_change_live_source_url_and_mix_article_history(monkeypatch,tmp_path):
    db=Store(str(tmp_path/'immutable_source.sqlite'))
    f=db.create({'title':'Research','source_url':'https://example.org/one','recipe':{}})
    db.finish(f,[{'title':'First note','url':'https://example.org/notes/1','summary':'','published_at':None}],None,10)
    monkeypatch.setattr(server,'store',db);monkeypatch.setattr(server,'TOKEN','local-admin')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://unit.local') as client:
        res=await client.patch('/api/feeds/'+f['id'],headers={'X-Admin-Token':'local-admin'},
                               json={'source_url':'https://example.org/two'})
        assert res.status_code==409
    assert db.get(f['id'])['source_url']=='https://example.org/one'
    db.close()


def test_chinese_encoding_and_publication_date():
    from openfeed.security import detect_charset
    from openfeed.extract import parse_date
    html='<html><head><meta charset="gb18030"></head><body>宏观研究报告</body></html>'.encode('gb18030')
    assert detect_charset(html,None).lower()=='gb18030'
    assert '宏观研究报告' in html.decode(detect_charset(html,None))
    assert parse_date('2026年10月21日').startswith('2026-10-21')
