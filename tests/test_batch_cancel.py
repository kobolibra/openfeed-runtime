import pytest
import httpx
from openfeed.batch_jobs import BatchJobs
from openfeed.storage import Store
import openfeed.app as server


def test_cancel_pending_running_interrupted_and_persistence(tmp_path):
    path = str(tmp_path / "jobs.sqlite")
    jobs = BatchJobs(path)
    a = jobs.create(["a", "b"])
    assert jobs.cancel(a["id"])
    assert jobs.get(a["id"])["status"] == "cancelled"
    assert not jobs.claim(a["id"])
    assert not jobs.resume(a["id"])
    b = jobs.create(["c", "d"])
    assert jobs.claim(b["id"])
    assert jobs.finish_one(b["id"], "c", {"feed_id": "c"})
    assert jobs.cancel(b["id"])
    assert not jobs.finish_one(b["id"], "d", {"feed_id": "d"})
    assert jobs.get(b["id"])["completed"] == 1
    jobs.close()
    restored = BatchJobs(path)
    assert restored.get(b["id"])["status"] == "cancelled"
    assert not restored.cancel(b["id"])
    restored.close()


@pytest.mark.asyncio
async def test_cancel_api_authorization_and_status(monkeypatch, tmp_path):
    path = str(tmp_path / "app.sqlite")
    store = Store(path)
    jobs = BatchJobs(path)
    monkeypatch.setattr(server, "store", store)
    monkeypatch.setattr(server, "batch_jobs", jobs)
    monkeypatch.setattr(server, "TOKEN", "secret")
    job = jobs.create(["a"])
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        url = "/api/feeds/batch-jobs/" + job["id"] + "/cancel"
        assert (await client.post(url)).status_code in (401, 403)
        headers = {"X-Admin-Token": "secret"}
        response = await client.post(url, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        assert (await client.post(url, headers=headers)).status_code == 409
        assert (await client.post("/api/feeds/batch-jobs/no-such-id/cancel", headers=headers)).status_code == 404
    jobs.close()
    store.close()
