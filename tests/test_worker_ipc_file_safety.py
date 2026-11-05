import json
import os
import pytest
from openfeed.sandbox_worker import read_job_safely


def test_worker_reads_normal_bounded_job(tmp_path):
    path = tmp_path / 'task.json'
    payload = {'id': 'abc', 'url': 'https://example.com', 'wait_selector': '', 'submitted_at': 1.0}
    path.write_text(json.dumps(payload))
    assert read_job_safely(path) == payload


def test_worker_rejects_symlinked_job(tmp_path):
    target = tmp_path / 'secret'
    target.write_text('{"secret":"do not read"}')
    link = tmp_path / 'task.json'
    link.symlink_to(target)
    with pytest.raises((OSError, ValueError)):
        read_job_safely(link)


def test_worker_rejects_oversized_job(tmp_path):
    path = tmp_path / 'task.json'
    path.write_bytes(b' ' * 8194)
    with pytest.raises(ValueError, match='Invalid browser job|Oversized browser job'):
        read_job_safely(path)


def test_worker_rejects_non_json_job(tmp_path):
    path = tmp_path / 'task.json'
    path.write_text('{')
    with pytest.raises(ValueError):
        read_job_safely(path)


@pytest.mark.asyncio
async def test_worker_timeout_is_actionable_and_removes_request(monkeypatch,tmp_path):
    import asyncio,time
    from unittest.mock import AsyncMock
    import openfeed.sandbox_worker as worker
    (tmp_path/'pending').mkdir();(tmp_path/'done').mkdir()
    ident='a'*32;job=tmp_path/'pending'/(ident+'.json')
    job.write_text(json.dumps({'id':ident,'url':'https://example.com','wait_selector':'','submitted_at':time.time()}))
    monkeypatch.setattr(worker,'render',AsyncMock(side_effect=asyncio.TimeoutError()))
    await worker.process_job(tmp_path,job)
    result=json.loads((tmp_path/'done'/(ident+'.json')).read_text())
    assert result['id']==ident and 'timed out' in result['error']
    assert not job.exists() and 'html' not in result
