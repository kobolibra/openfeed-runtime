import asyncio
from unittest.mock import AsyncMock
import pytest
from openfeed import security as s

@pytest.mark.asyncio
async def test_transient_get_recovers_once(monkeypatch):
    call=AsyncMock(side_effect=[s.UpstreamConnectionError(TimeoutError()),('url',b'ok','utf-8')])
    monkeypatch.setattr(s,'_fetch_once',call);monkeypatch.setattr(s.asyncio,'sleep',AsyncMock())
    assert await s.fetch('https://example.com')==('url',b'ok','utf-8')
    assert call.await_count==2

@pytest.mark.asyncio
async def test_persistent_failure_stops_after_one_retry(monkeypatch):
    call=AsyncMock(side_effect=s.UpstreamConnectionError(TimeoutError()))
    monkeypatch.setattr(s,'_fetch_once',call);monkeypatch.setattr(s.asyncio,'sleep',AsyncMock())
    with pytest.raises(s.UpstreamConnectionError):await s.fetch('https://example.com')
    assert call.await_count==2

@pytest.mark.asyncio
async def test_post_is_never_replayed(monkeypatch):
    call=AsyncMock(side_effect=s.UpstreamConnectionError(TimeoutError()));monkeypatch.setattr(s,'_fetch_once',call)
    with pytest.raises(s.UpstreamConnectionError):await s.fetch('https://example.com',method='POST',data={'query':'China'})
    assert call.await_count==1

@pytest.mark.asyncio
@pytest.mark.parametrize('status',[401,403,429,503])
async def test_http_rejections_are_not_immediately_retried(monkeypatch,status):
    call=AsyncMock(side_effect=s.UpstreamHTTPError(status,'https://example.com','600'));monkeypatch.setattr(s,'_fetch_once',call)
    with pytest.raises(s.UpstreamHTTPError):await s.fetch('https://example.com')
    assert call.await_count==1
