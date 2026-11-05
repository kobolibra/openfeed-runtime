import pytest
from openfeed.egress_proxy import safe_forward_headers


def test_proxy_preserves_only_end_to_end_headers():
    data=(b'GET http://public.example/path HTTP/1.1\r\n'
          b'Host: fake.internal\r\nContent-Length: 444\r\nTransfer-Encoding: chunked\r\n'
          b'Proxy-Authorization: Basic hidden\r\nUpgrade: websocket\r\n'
          b'Accept: application/json\r\nUser-Agent: OpenFeed\r\n\r\n')
    assert safe_forward_headers(data)==[b'Accept: application/json',b'User-Agent: OpenFeed']


@pytest.mark.parametrize('bad',[
    b'GET / HTTP/1.1\r\n Folded: injected\r\n\r\n',
    b'GET / HTTP/1.1\r\nBad Header: yes\r\n\r\n',
    b'GET / HTTP/1.1\r\nX-Test: ok\x00wrong\r\n\r\n',
    b'GET / HTTP/1.1\r\nHeaderWithoutColon\r\n\r\n',
])
def test_proxy_rejects_ambiguous_headers(bad):
    with pytest.raises(ValueError):
        safe_forward_headers(bad)

@pytest.mark.asyncio
async def test_proxy_http_request_rewrites_host_and_removes_smuggling_headers(monkeypatch):
    import asyncio
    from openfeed import egress_proxy as proxy
    received=[]
    async def upstream(reader, writer):
        data=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),2)
        received.append(data)
        writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK')
        await writer.drain();writer.close()
    origin=await asyncio.start_server(upstream,'127.0.0.1',0)
    origin_addr=origin.sockets[0].getsockname()
    async def dial(host,port):
        assert (host,port)==('public.example',80)
        return await asyncio.open_connection(*origin_addr)
    monkeypatch.setattr(proxy,'dial_public',dial)
    gateway=await asyncio.start_server(proxy.handle,'127.0.0.1',0)
    r,w=await asyncio.open_connection(*gateway.sockets[0].getsockname())
    w.write(b'GET http://public.example/report HTTP/1.1\r\nHost: internal.local\r\n'
            b'Content-Length: 123\r\nTransfer-Encoding: chunked\r\n'
            b'X-Request-Id: safe\r\n\r\n');await w.drain()
    response=await asyncio.wait_for(r.read(),4)
    assert b'200 OK' in response
    assert len(received)==1
    assert received[0].startswith(b'GET /report HTTP/1.1\r\nHost: public.example\r\n')
    assert b'Content-Length:' not in received[0] and b'Transfer-Encoding:' not in received[0]
    assert b'X-Request-Id: safe' in received[0]
    w.close();await w.wait_closed()
    gateway.close();origin.close();await gateway.wait_closed();await origin.wait_closed()

@pytest.mark.asyncio
async def test_proxy_does_not_forward_second_request_as_body(monkeypatch):
    import asyncio
    from openfeed import egress_proxy as proxy
    received=[]
    async def upstream(reader,writer):
        received.append(await reader.readuntil(b'\r\n\r\n'))
        writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK')
        await writer.drain()
        try:
            leftover=await asyncio.wait_for(reader.read(100),.15)
            received.append(leftover)
        except asyncio.TimeoutError:
            received.append(b'')
        writer.close()
    origin=await asyncio.start_server(upstream,'127.0.0.1',0)
    async def dial(host,port):
        return await asyncio.open_connection(*origin.sockets[0].getsockname())
    monkeypatch.setattr(proxy,'dial_public',dial)
    gateway=await asyncio.start_server(proxy.handle,'127.0.0.1',0)
    reader,writer=await asyncio.open_connection(*gateway.sockets[0].getsockname())
    writer.write(b'GET http://public.example/ HTTP/1.1\r\nHost: public.example\r\n\r\n'
                 b'GET /admin HTTP/1.1\r\nHost: internal.local\r\n\r\n')
    await writer.drain()
    assert b'200 OK' in await asyncio.wait_for(reader.read(),2)
    assert received[1]==b''
    writer.close();await writer.wait_closed()
    gateway.close();origin.close();await gateway.wait_closed();await origin.wait_closed()
