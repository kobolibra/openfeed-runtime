import importlib.util,sys
from pathlib import Path
from types import SimpleNamespace
import pytest,httpx
from starlette.responses import JSONResponse
@pytest.fixture
def wrapper(monkeypatch):
 root=Path(__file__).resolve().parents[1]
 class Inner:
  router=SimpleNamespace()
  async def __call__(self,scope,receive,send):await JSONResponse([])(scope,receive,send)
 fake=SimpleNamespace(app=Inner(),store=SimpleNamespace(close=lambda:None),batch_jobs=SimpleNamespace(close=lambda:None),TOKEN='test-only',ROOT=root)
 monkeypatch.setitem(sys.modules,'openfeed.app',fake)
 spec=importlib.util.spec_from_file_location('isolated_local_cloud_ui',root/'ops/local_cloud_ui.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m.app
@pytest.mark.asyncio
async def test_local_cloud_ui_does_not_start_a_second_fetcher(wrapper):
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=wrapper),base_url='http://local') as c:
  for path in ['/api/feeds/abc/run','/api/feeds/batch-jobs','/api/feeds/bulk-refresh','/api/schedule/spread']:
   assert (await c.post(path)).status_code==409
  assert (await c.get('/api/cloud-status')).status_code==401
  assert (await c.get('/api/feeds')).status_code==200
@pytest.mark.asyncio
async def test_local_cloud_ui_exposes_sync_indicator(wrapper):
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=wrapper),base_url='http://local') as c:
  r=await c.get('/static/app.js');assert r.status_code==200 and '/api/cloud-status' in r.text
