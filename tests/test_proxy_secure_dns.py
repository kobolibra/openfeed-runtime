import asyncio,json,socket
from unittest.mock import AsyncMock,MagicMock
import pytest
from openfeed import egress_proxy as p

@pytest.mark.parametrize('address',['198.18.1.2','127.0.0.1','10.0.0.1','169.254.169.254'])
def test_secure_dns_rejects_nonpublic(monkeypatch,address):
 response=MagicMock();response.__enter__.return_value=response;response.status=200
 response.read.return_value=json.dumps({'Status':0,'Answer':[{'type':1,'data':address}]}).encode()
 opener=MagicMock();opener.open.return_value=response
 monkeypatch.setattr('urllib.request.build_opener',lambda *a:opener)
 with pytest.raises(ValueError,match='non-public'):p.secure_dns_addresses('example.com',443)

def test_doh_dials_verified_ip_without_system_resolution(monkeypatch):
 monkeypatch.setenv('OPENFEED_DNS_MODE','doh')
 monkeypatch.setattr(p,'secure_dns_addresses',lambda h,port:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('93.184.215.14',port))])
 async def run():
  loop=asyncio.get_running_loop();connect=AsyncMock();monkeypatch.setattr(loop,'sock_connect',connect)
  connection=AsyncMock(return_value=('reader','writer'));monkeypatch.setattr(asyncio,'open_connection',connection)
  result=await p.dial_public('example.com',443)
  assert result==('reader','writer');assert connect.call_args.args[1]==('93.184.215.14',443)
  connection.call_args.kwargs['sock'].close()
 asyncio.run(run())

def test_closed_client_does_not_raise():
 async def run():
  reader=asyncio.StreamReader();reader.feed_eof();writer=MagicMock();writer.drain=AsyncMock();writer.wait_closed=AsyncMock()
  await p.handle(reader,writer);assert writer.close.called
 asyncio.run(run())
