import asyncio,socket
from unittest.mock import AsyncMock,MagicMock
import pytest
from openfeed import egress_proxy as p
from openfeed.security import UpstreamConnectionError
from aiohttp import ClientHttpProxyError

def records():return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443)),(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.4.4',443))]

@pytest.mark.asyncio
async def test_bad_first_address_does_not_consume_fallback_budget(monkeypatch):
 loop=asyncio.get_running_loop();budgets=[];original=asyncio.wait_for
 async def wait(coro,timeout):budgets.append(timeout);return await original(coro,timeout)
 connect=AsyncMock(side_effect=[TimeoutError(),None]);monkeypatch.setattr(loop,'sock_connect',connect);monkeypatch.setattr(p.asyncio,'wait_for',wait)
 open_=AsyncMock(return_value=('r','w'));monkeypatch.setattr(p.asyncio,'open_connection',open_)
 assert await p.connect_addresses(records(),False,loop.time()+10)==('r','w')
 assert 0<budgets[0]<=5 and budgets[1]>budgets[0]
 assert connect.await_count==2;open_.call_args.kwargs['sock'].close()

@pytest.mark.asyncio
async def test_expired_shared_budget_never_opens_socket():
 with pytest.raises(p.DialFailure) as e:await p.connect_addresses(records(),False,asyncio.get_running_loop().time()-1)
 assert e.value.stage=='tcp' and e.value.timed_out

@pytest.mark.asyncio
async def test_failure_closes_socket_and_labels_tcp(monkeypatch):
 loop=asyncio.get_running_loop();monkeypatch.setattr(loop,'sock_connect',AsyncMock(side_effect=ConnectionRefusedError()))
 with pytest.raises(p.DialFailure) as e:await p.connect_addresses(records(),False,loop.time()+1)
 assert e.value.stage=='tcp' and not e.value.timed_out

@pytest.mark.parametrize('stage',['dns','tcp','secret-query=bad\r\n'])
def test_only_safe_stage_is_exposed(stage):
 e=ClientHttpProxyError(None,(),status=504,headers={'X-OpenFeed-Stage':stage})
 text=str(UpstreamConnectionError(e));assert ('; stage=' in text)==(stage in ['dns','tcp'])
 assert 'secret-query' not in text
