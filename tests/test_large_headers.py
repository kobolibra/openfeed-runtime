import asyncio
import pytest
from openfeed import security

@pytest.mark.asyncio
async def test_legitimate_large_csp_and_oversized_header_are_distinguished(monkeypatch):
 async def handle(reader,writer):
  request=await reader.readuntil(b'\r\n\r\n');large=b'/oversized ' in request
  body=b'<html><main><article><h2>Research outlook</h2></article></main></html>'
  csp=b"default-src 'self'; connect-src "+b'https://public.example/ '*(2200 if large else 500)
  writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Security-Policy: '+csp+b'\r\nContent-Length: '+str(len(body)).encode()+b'\r\nConnection: close\r\n\r\n'+body)
  await writer.drain();writer.close();await writer.wait_closed()
 server=await asyncio.start_server(handle,'127.0.0.1',0);port=server.sockets[0].getsockname()[1];origin=f'http://127.0.0.1:{port}'
 def fixture_only_url(url,**kwargs):
  assert url.startswith(origin+'/');return url
 # The fixture intentionally uses loopback; production URL/DNS gates are
 # covered separately and are not changed by the implementation.
 monkeypatch.setattr(security,'check_url',fixture_only_url)
 try:
  _,body,_=await security.fetch(origin+'/normal');assert b'Research outlook' in body
  with pytest.raises(ValueError,match='ClientResponseError'):await security.fetch(origin+'/oversized')
 finally:server.close();await server.wait_closed()
