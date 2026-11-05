import pytest
from openfeed.sandbox_worker import validate_internal_proxy

@pytest.mark.parametrize('url', [
    'http://127.0.0.1:8899',
    'http://localhost:8899',
    'http://example.com:8899',
    'http://egress-proxy:8080',
    'https://egress-proxy:8899',
    'http://user:password@egress-proxy:8899',
    'http://egress-proxy:8899/other',
    'http://egress-proxy:8899/?x=1',
    'http://egress-proxy:8899/#fragment',
])
def test_browser_disallows_any_noninternal_proxy(url):
    with pytest.raises(ValueError): validate_internal_proxy(url)

def test_browser_accepts_dedicated_proxy():
    validate_internal_proxy('http://egress-proxy:8899')
