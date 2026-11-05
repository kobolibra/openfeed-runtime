import pytest
from unittest.mock import AsyncMock
from openfeed.storage import Store
from openfeed.security import UpstreamHTTPError
import openfeed.app as app

def test_cooldown_persists_and_cannot_be_shortened(tmp_path):
 p=str(tmp_path/'state.db');s=Store(p);s.cool_domain('Example.COM',600);s.cool_domain('example.com',10);s.close()
 s=Store(p);assert 590<=s.domain_delay('example.com')<=600
 assert s.domain_delay('other.example')==0
 assert len(s.cooldowns())==1;s.close()

@pytest.mark.asyncio
async def test_429_stops_sibling_without_losing_history_or_phase(tmp_path,monkeypatch):
 s=Store(str(tmp_path/'state.db'));monkeypatch.setattr(app,'store',s);monkeypatch.setattr(app,'_last_domain',{});monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
 a=s.create({'title':'A','source_url':'https://example.com/a','recipe':{}});b=s.create({'title':'B','source_url':'https://example.com/b','recipe':{}})
 s.finish(b,[{'title':'Old','url':'https://example.com/old'}],None,1)
 before=s.entries(b['id']);phase=s.get(b['id'])['schedule_phase_seconds']
 fetch=AsyncMock(side_effect=UpstreamHTTPError(429,a['source_url'],'120'));monkeypatch.setattr(app,'fetch',fetch)
 assert (await app.run_feed(a['id']))['status']=='error'
 result=await app.run_feed(b['id']);assert result['reason']=='domain_cooldown'
 assert fetch.await_count==1 and s.entries(b['id'])==before
 assert s.get(b['id'])['schedule_phase_seconds']==phase
 s.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('status,header,expected',[(403,'120',False),(503,'120',True),(503,'',False)])
async def test_only_rate_limit_or_explicit_service_retry_creates_cooldown(tmp_path,monkeypatch,status,header,expected):
 s=Store(str(tmp_path/'state.db'));monkeypatch.setattr(app,'store',s);monkeypatch.setattr(app,'_last_domain',{});monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
 f=s.create({'title':'A','source_url':'https://example.com/a','recipe':{}})
 monkeypatch.setattr(app,'fetch',AsyncMock(side_effect=UpstreamHTTPError(status,f['source_url'],header)))
 await app.run_feed(f['id']);assert bool(s.domain_delay('example.com'))==expected;s.close()
