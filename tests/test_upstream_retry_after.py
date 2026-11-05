from datetime import datetime,timezone,timedelta
from email.utils import format_datetime
from unittest.mock import AsyncMock
import pytest
from openfeed.security import retry_after_seconds,UpstreamHTTPError
from openfeed.storage import Store
import openfeed.app as server

@pytest.mark.parametrize('value,expected',[('3600',3600),('garbage',0),('-1',0),('9999999999',604800),('',0)])
def test_bounded_server_retry_hint(value,expected):
 assert retry_after_seconds(value)==expected

def test_absolute_http_date_and_past_date():
 now=datetime(2026,10,23,tzinfo=timezone.utc)
 assert retry_after_seconds(format_datetime(now+timedelta(seconds=1800)),now)==1800
 assert retry_after_seconds(format_datetime(now-timedelta(days=1)),now)==0

@pytest.mark.asyncio
async def test_429_keeps_old_items_and_honors_server_wait_without_shortening_backoff(monkeypatch,tmp_path):
 db=Store(str(tmp_path/'state.sqlite'));monkeypatch.setattr(server,'store',db);monkeypatch.setattr(server,'_last_domain',{});monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
 url='https://example.org/research';f=db.create({'title':'Research','source_url':url,'recipe':{}})
 db.finish(f,[{'title':'Existing research','url':'https://example.org/a','summary':'','published_at':None}],None,1)
 monkeypatch.setattr(server,'fetch',AsyncMock(side_effect=UpstreamHTTPError(429,url,'3600')))
 result=await server.run_feed(f['id']);assert result['status']=='error' and result['retry_after']==3600
 assert db.get(f['id'])['status']=='error' and len(db.entries(f['id']))==1
 assert (datetime.fromisoformat(db.get(f['id'])['next_run'])-datetime.now(timezone.utc)).total_seconds()>3590
 monkeypatch.setattr(server,'fetch',AsyncMock(side_effect=UpstreamHTTPError(503,url,'1')))
 await server.run_feed(f['id'])
 assert (datetime.fromisoformat(db.get(f['id'])['next_run'])-datetime.now(timezone.utc)).total_seconds()>590
 db.close()
