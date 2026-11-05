import asyncio
import pytest
from openfeed import browser_ipc as ipc

@pytest.mark.asyncio
async def test_only_running_worker_job_starts_its_ipc_deadline(monkeypatch):
 entered=[];first=asyncio.Event();release=asyncio.Event()
 async def fake(url,selector):
  entered.append(url)
  if url.endswith('/1'):first.set();await release.wait()
  return url,b'html','utf-8'
 monkeypatch.setattr(ipc,'_request_render',fake)
 one=asyncio.create_task(ipc.request_render('https://example.org/1'))
 await first.wait();two=asyncio.create_task(ipc.request_render('https://example.org/2'))
 await asyncio.sleep(.01);assert entered==['https://example.org/1']
 release.set();await asyncio.gather(one,two)
 assert entered==['https://example.org/1','https://example.org/2']

@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_block_next_job(monkeypatch):
 first=asyncio.Event();release=asyncio.Event()
 async def fake(url,selector):
  if url.endswith('/1'):first.set();await release.wait()
  return url,b'html','utf-8'
 monkeypatch.setattr(ipc,'_request_render',fake)
 one=asyncio.create_task(ipc.request_render('https://example.org/1'));await first.wait()
 two=asyncio.create_task(ipc.request_render('https://example.org/2'));await asyncio.sleep(0);two.cancel()
 with pytest.raises(asyncio.CancelledError):await two
 release.set();await one
 assert (await ipc.request_render('https://example.org/3'))[0].endswith('/3')
