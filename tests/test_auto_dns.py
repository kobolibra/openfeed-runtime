import asyncio,socket
from unittest.mock import AsyncMock
import pytest
from openfeed.security import PublicResolver
from openfeed import egress_proxy as proxy

@pytest.mark.parametrize('system_address,fallback',[('93.184.215.14',False),('198.18.1.2',True)])
def test_http_auto_uses_system_or_secure_fallback(monkeypatch,system_address,fallback):
 monkeypatch.setenv('OPENFEED_DNS_MODE','auto')
 async def run():
  resolver=PublicResolver();secure=AsyncMock(return_value=[{'host':'1.1.1.1'}]);monkeypatch.setattr(resolver,'_doh',secure)
  monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',AsyncMock(return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(system_address,443))]))
  result=await resolver.resolve('example.com',443)
  assert secure.called==fallback;assert result[0]['host']==('1.1.1.1' if fallback else system_address)
 asyncio.run(run())

@pytest.mark.parametrize('system_address,fallback',[('93.184.215.14',False),('198.18.1.2',True)])
def test_proxy_auto_never_dials_fake_ip(monkeypatch,system_address,fallback):
 monkeypatch.setenv('OPENFEED_DNS_MODE','auto');calls=[]
 def secure(h,port):calls.append(h);return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('1.1.1.1',port))]
 monkeypatch.setattr(proxy,'secure_dns_addresses',secure)
 async def run():
  loop=asyncio.get_running_loop();monkeypatch.setattr(loop,'getaddrinfo',AsyncMock(return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(system_address,443))]));connect=AsyncMock();monkeypatch.setattr(loop,'sock_connect',connect);opened=AsyncMock(return_value=('r','w'));monkeypatch.setattr(asyncio,'open_connection',opened)
  await proxy.dial_public('example.com',443);assert bool(calls)==fallback;assert connect.call_args.args[1][0]==('1.1.1.1' if fallback else system_address);opened.call_args.kwargs['sock'].close()
 asyncio.run(run())
