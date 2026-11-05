import json,time
from unittest.mock import AsyncMock
import pytest
from openfeed import browser_ipc as ipc,sandbox_worker as worker
from openfeed.security import UpstreamHTTPError

@pytest.mark.asyncio
async def test_worker_preserves_rate_limit_metadata(monkeypatch,tmp_path):
 (tmp_path/'pending').mkdir();(tmp_path/'done').mkdir();ident='c'*32;job=tmp_path/'pending'/(ident+'.json');job.write_text(json.dumps({'id':ident,'url':'https://example.org/a','wait_selector':'','submitted_at':time.time()}))
 monkeypatch.setattr(worker,'render',AsyncMock(side_effect=UpstreamHTTPError(429,'https://example.org/a','900')))
 await worker.process_job(tmp_path,job)
 result=json.loads((tmp_path/'done'/(ident+'.json')).read_text());assert result['http_status']==429 and result['retry_after']=='900' and 'html' not in result and not job.exists()

@pytest.mark.parametrize('status',[403,429,503])
@pytest.mark.asyncio
async def test_ipc_restores_structured_http_error(monkeypatch,tmp_path,status):
 (tmp_path/'pending').mkdir();(tmp_path/'done').mkdir();ident='d'*32
 monkeypatch.setattr(ipc,'job_dir',lambda:tmp_path);monkeypatch.setattr(ipc.secrets,'token_hex',lambda n:ident)
 (tmp_path/'done'/(ident+'.json')).write_text(json.dumps({'id':ident,'error':'Source unavailable','http_status':status,'retry_after':'900'}))
 with pytest.raises(UpstreamHTTPError) as exc:await ipc.request_render('https://example.org/a')
 assert exc.value.status==status and exc.value.retry_after=='900'
 assert not list((tmp_path/'pending').iterdir()) and not list((tmp_path/'done').iterdir())

@pytest.mark.parametrize('status',[True,'429',200,999])
@pytest.mark.asyncio
async def test_untrusted_worker_cannot_forge_invalid_status(monkeypatch,tmp_path,status):
 (tmp_path/'pending').mkdir();(tmp_path/'done').mkdir();ident='e'*32
 monkeypatch.setattr(ipc,'job_dir',lambda:tmp_path);monkeypatch.setattr(ipc.secrets,'token_hex',lambda n:ident)
 (tmp_path/'done'/(ident+'.json')).write_text(json.dumps({'id':ident,'error':'error','http_status':status}))
 with pytest.raises(ValueError,match='metadata'):await ipc.request_render('https://example.org/a')
