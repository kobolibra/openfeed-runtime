from fastapi.testclient import TestClient
from openfeed import app as application
from openfeed.storage import Store


def test_job_lifecycle_http_requires_auth_and_returns_state(tmp_path, monkeypatch):
    store = Store(str(tmp_path / 'test.sqlite3'))
    monkeypatch.setattr(application, 'store', store)
    monkeypatch.setattr(application, 'TOKEN', 'test-secret')
    feed = store.create({'title': 'Jobs', 'source_url': 'https://jobs.example/list',
                         'recipe': {'content_type': 'jobs', 'complete_inventory': True}})
    def report(urls):
        store.finish(store.get(feed['id']), [{'title': u, 'url': u} for u in urls], None, 1)
    a = 'https://jobs.example/a'; b = 'https://jobs.example/b'
    report([a, b]); report([a]); report([a])
    client = TestClient(application.app)
    endpoint = '/api/feeds/' + feed['id'] + '/lifecycle'
    assert client.get(endpoint).status_code == 401
    response = client.get(endpoint, headers={'X-Admin-Token': 'test-secret'})
    assert response.status_code == 200
    results = {x['url']: x for x in response.json()['items']}
    assert results[b]['availability'] == 'possibly_closed'
    report([a, b])
    assert all(x['availability'] == 'observed' for x in client.get(endpoint, headers={'X-Admin-Token': 'test-secret'}).json()['items'])
    store.close()

def test_item_events_api_requires_auth(tmp_path,monkeypatch):
    store=Store(str(tmp_path/'events.sqlite3'))
    monkeypatch.setattr(application,'store',store)
    monkeypatch.setattr(application,'TOKEN','secret-long-token')
    feed=store.create({'title':'Reports','source_url':'https://research.example/list'})
    store.finish(store.get(feed['id']),[{'title':'New memo','url':'https://research.example/1'}],None,1)
    client=TestClient(application.app)
    endpoint=f'/api/feeds/{feed["id"]}/events'
    assert client.get(endpoint).status_code==401
    response=client.get(endpoint,headers={'X-Admin-Token':'secret-long-token'})
    assert response.status_code==200
    assert response.json()['events'][0]['event_type']=='new'
    store.close()
