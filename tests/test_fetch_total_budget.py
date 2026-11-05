import asyncio
from unittest.mock import AsyncMock
import pytest
from openfeed import security as s

@pytest.mark.asyncio
async def test_total_deadline_cancels_stalled_chain_and_preserves_safe_error(monkeypatch):
 original=asyncio.timeout;budgets=[];cancelled=[]
 def short_budget(value):budgets.append(value);return original(.01)
 async def stuck(*a,**kw):
  try:await asyncio.sleep(10)
  finally:cancelled.append(True)
 monkeypatch.setattr(s.asyncio,'timeout',short_budget);monkeypatch.setattr(s,'_fetch_with_retry',stuck);monkeypatch.setenv('OPENFEED_FETCH_TIMEOUT','15')
 with pytest.raises(s.UpstreamConnectionError) as exc:await s.fetch('https://example.com/?private=secret')
 assert budgets==[45] and cancelled==[True] and 'private' not in str(exc.value)

@pytest.mark.asyncio
async def test_budget_is_bounded_and_options_pass_through(monkeypatch):
 original=asyncio.timeout;budgets=[]
 def budget(value):budgets.append(value);return original(value)
 call=AsyncMock(return_value=('url',b'OK','utf-8'));monkeypatch.setattr(s,'_fetch_with_retry',call);monkeypatch.setattr(s.asyncio,'timeout',budget);monkeypatch.setenv('OPENFEED_FETCH_TIMEOUT','9999')
 await s.fetch('https://example.com',method='POST',data={'q':'China'})
 assert budgets==[125] and call.call_args.kwargs['method']=='POST'
