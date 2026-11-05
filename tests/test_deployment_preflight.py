from tools.preflight import inspect_environment


def test_unsecured_local_install_is_not_production_ready():
    data=inspect_environment({'OPENFEED_PUBLIC_URL':'http://localhost:8765','OPENFEED_ADMIN_TOKEN':'test'},which=lambda _:None,resolver=lambda *a,**kw: (_ for _ in ()).throw(OSError('offline')))
    assert data['production_go'] is False
    assert {'admin_token','public_https'}.issubset(data['blockers'])
    assert data['checks']['dns']['ok'] is False


def test_preflight_does_not_confuse_chromium_with_isolated_worker():
    data=inspect_environment({'OPENFEED_PUBLIC_URL':'https://feeds.example.com','OPENFEED_ADMIN_TOKEN':'secure-test-token-over-24-characters','OPENFEED_EXPERIMENTAL_BROWSER':'1'},which=lambda _: '/usr/bin/something',resolver=lambda *a,**kw:[object()])
    assert data['checks']['chromium']['ok'] is True
    assert not data['checks']['browser_disabled_by_default']['ok']
    assert 'browser_disabled_by_default' in data['blockers']
