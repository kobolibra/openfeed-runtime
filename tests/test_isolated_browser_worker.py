import asyncio
import base64
import json
from pathlib import Path
import pytest

from openfeed import browser
from openfeed.browser_ipc import request_render
from openfeed.egress_proxy import safe_destination, public_ip


def test_egress_proxy_rejects_private_targets():
    for host in ('localhost','127.0.0.1','192.168.1.1','10.0.0.7',
                 '169.254.169.254','2130706433','127.1','internal.local',
                 '0x7f000001','[::1]'):
        with pytest.raises(ValueError): safe_destination(host,443)
    assert safe_destination('research.example.com',443)==('research.example.com',443)
    assert public_ip('8.8.8.8')
    assert not public_ip('127.0.0.1')


@pytest.mark.asyncio
async def test_worker_transport_roundtrip_without_browser(tmp_path,monkeypatch):
    (tmp_path/'pending').mkdir();(tmp_path/'done').mkdir()
    monkeypatch.setenv('OPENFEED_BROWSER_JOB_DIR',str(tmp_path))
    html=b'<html><title>Mock rendered</title></html>'
    async def worker_stub():
        for _ in range(200):
            jobs=list((tmp_path/'pending').glob('*.json'))
            if jobs:
                job=jobs[0];payload=json.loads(job.read_text())
                (tmp_path/'done'/job.name).write_text(json.dumps({
                   'id':payload['id'],'url':payload['url'],'html':base64.b64encode(html).decode('ascii')}))
                return
            await asyncio.sleep(.01)
        raise AssertionError('job never appeared')
    task=asyncio.create_task(worker_stub())
    final,content,encoding=await request_render('https://research.example.com/list','article')
    await task
    assert final=='https://research.example.com/list'
    assert content==html and encoding=='utf-8'
    assert list((tmp_path/'pending').iterdir())==[]
    assert list((tmp_path/'done').iterdir())==[]


@pytest.mark.asyncio
async def test_unisolated_in_process_browser_is_disabled(monkeypatch):
    monkeypatch.delenv('OPENFEED_BROWSER_SANDBOXED_WORKER',raising=False)
    monkeypatch.setenv('OPENFEED_EXPERIMENTAL_BROWSER','1')
    monkeypatch.setenv('OPENFEED_BROWSER_NETWORK_ISOLATED','1')
    monkeypatch.delenv('OPENFEED_UNSAFE_LOCAL_BROWSER',raising=False)
    with pytest.raises(ValueError,match='isolated worker'):
        await browser.browser_fetch('https://research.example.com/')


@pytest.mark.asyncio
async def test_proxy_dial_rejects_private_dns(monkeypatch):
    import openfeed.egress_proxy as proxy
    clock=asyncio.get_running_loop().time
    class DNS:
        time=staticmethod(clock)
        async def getaddrinfo(self,*args,**kwargs):
            import socket
            return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))]
    monkeypatch.setattr(proxy.asyncio,'get_running_loop',lambda:DNS())
    with pytest.raises(ValueError,match='non-public'):
        await proxy.dial_public('research.example.com',443)

@pytest.mark.asyncio
async def test_egress_proxy_tunnel_works_to_validated_destination(monkeypatch):
    """Exercise real proxy streams without contacting the internet."""
    import openfeed.egress_proxy as proxy
    async def target(reader,writer):
        try:
            payload=await reader.read(5)
            writer.write(payload[::-1]);await writer.drain()
        finally:
            writer.close()
    upstream=await asyncio.start_server(target,'127.0.0.1',0)
    host,port=upstream.sockets[0].getsockname()
    real_dial=asyncio.open_connection
    async def synthetic_checked_dial(destination,remote_port):
        assert (destination,remote_port)==('public.example',443)
        return await real_dial(host,port)
    monkeypatch.setattr(proxy,'dial_public',synthetic_checked_dial)
    server=await asyncio.start_server(proxy.handle,'127.0.0.1',0)
    address=server.sockets[0].getsockname()
    reader,writer=await asyncio.open_connection(*address)
    writer.write(b'CONNECT public.example:443 HTTP/1.1\r\nHost: public.example:443\r\n\r\n')
    await writer.drain()
    response=await reader.readuntil(b'\r\n\r\n')
    assert b'200 Connection established' in response
    writer.write(b'ABCDE');await writer.drain()
    assert await asyncio.wait_for(reader.readexactly(5),2)==b'EDCBA'
    writer.close();await writer.wait_closed()
    server.close();upstream.close();await server.wait_closed();await upstream.wait_closed()

@pytest.mark.asyncio
async def test_api_browser_job_ipc_to_published_rss(tmp_path,monkeypatch):
    """Full application -> IPC -> synthetic worker -> store -> RSS test."""
    import httpx
    from defusedxml import ElementTree as ET
    from openfeed.storage import Store
    import openfeed.app as server
    pending=tmp_path/'pending';done=tmp_path/'done';pending.mkdir();done.mkdir()
    db=Store(str(tmp_path/'database.sqlite3'))
    monkeypatch.setattr(server,'store',db)
    monkeypatch.setattr(server,'TOKEN','browser-worker-integration-secret')
    monkeypatch.setenv('OPENFEED_BROWSER_SANDBOXED_WORKER','1')
    monkeypatch.setenv('OPENFEED_BROWSER_JOB_DIR',str(tmp_path))
    monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
    url='https://reports.example.org/reports'
    html=b'<article><h2><a href="/first">First report</a></h2></article><article><h2><a href="/second">Second report</a></h2></article>'
    keep_running=True
    async def simulated_isolated_worker():
        processed=set()
        while keep_running:
            for job in pending.glob('*.json'):
                if job.name in processed:continue
                processed.add(job.name)
                data=json.loads(job.read_text())
                (done/job.name).write_text(json.dumps({'id':data['id'],'url':data['url'],'html':base64.b64encode(html).decode()}))
            await asyncio.sleep(.015)
    worker=asyncio.create_task(simulated_isolated_worker())
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app),base_url='http://testserver') as c:
            headers={'X-Admin-Token':'browser-worker-integration-secret'}
            created=await c.post('/api/feeds',headers=headers,json={'title':'Isolated browser feed',
                'source_url':url,'recipe':{'fetch_mode':'browser','mode':'css','item_selector':'article'}})
            assert created.status_code==201,created.text
            ident=created.json()['id']
            result=await c.post('/api/feeds/'+ident+'/run',headers=headers)
            assert result.status_code==200,result.text
            assert result.json()['inserted']==2
            response=await c.get('/rss/'+ident+'.xml')
            assert len(ET.fromstring(response.content).findall('./channel/item'))==2
    finally:
        keep_running=False
        await worker
        db.close()

def test_ipc_result_reader_rejects_symlinks(tmp_path):
    from openfeed.browser_ipc import read_regular_result
    original=tmp_path/'original.txt';original.write_text('{"secret":"value"}')
    link=tmp_path/'result.json';link.symlink_to(original)
    with pytest.raises(OSError):read_regular_result(link)


@pytest.mark.asyncio
async def test_ipc_rejects_mismatched_result_id(tmp_path, monkeypatch):
    (tmp_path/'pending').mkdir(); (tmp_path/'done').mkdir()
    monkeypatch.setenv('OPENFEED_BROWSER_JOB_DIR', str(tmp_path))
    async def bogus_worker():
        for _ in range(200):
            jobs=list((tmp_path/'pending').glob('*.json'))
            if jobs:
                job=jobs[0]
                (tmp_path/'done'/job.name).write_text(json.dumps({
                    'id':'0'*32, 'url':'https://research.example.com/',
                    'html':base64.b64encode(b'<html></html>').decode()}))
                return
            await asyncio.sleep(.01)
        raise AssertionError('No job received')
    task=asyncio.create_task(bogus_worker())
    with pytest.raises(ValueError, match='job ID mismatch'):
        await request_render('https://research.example.com/')
    await task
    assert not list((tmp_path/'pending').iterdir())
    assert not list((tmp_path/'done').iterdir())
