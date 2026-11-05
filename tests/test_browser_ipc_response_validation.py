import asyncio
import json
from pathlib import Path
import pytest
from openfeed import browser_ipc


@pytest.mark.parametrize('response', [
    {'html':'AA=='},
    {'url':'https://example.org/','html':123},
    {'url':'https://example.org/','html':'@notbase64'},
    {'url':'http://127.0.0.1/','html':'AA=='},
    {'error':{'malicious':'value'}},
])
def test_reject_malformed_worker_response(tmp_path, monkeypatch, response):
    (tmp_path/'pending').mkdir()
    (tmp_path/'done').mkdir()
    monkeypatch.setenv('OPENFEED_BROWSER_JOB_DIR',str(tmp_path))
    async def scenario():
        task=asyncio.create_task(browser_ipc.request_render('https://example.org/'))
        for _ in range(200):
            queued=list((tmp_path/'pending').glob('*.json'))
            if queued: break
            await asyncio.sleep(.005)
        assert queued
        identifier=queued[0].stem
        payload={'id':identifier, **response}
        (tmp_path/'done'/f'{identifier}.json').write_text(json.dumps(payload))
        with pytest.raises((ValueError, KeyError, TypeError)):
            await task
        assert not queued[0].exists()
        assert not (tmp_path/'done'/f'{identifier}.json').exists()
    asyncio.run(scenario())
