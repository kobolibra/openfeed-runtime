import pytest
from openfeed.egress_proxy import validate_http_target

@pytest.mark.parametrize('target', [
    'http://user:pass@public.example/',
    'http://public.example/hello#fragment',
    'http://public.example/hello%0d%0aHost:evil',
    'http://public.example/%00',
    'http://public.example:bad/path',
    'http://public.example:8080/path',
    'http://127.0.0.1/',
    'http://public.example/has\\backslash',
    'http://public.example/a b',
    'http://public.example/你好',
])
def test_reject_ambiguous_or_unsafe_targets(target):
    with pytest.raises(ValueError):
        validate_http_target(target)

def test_valid_public_target():
    assert validate_http_target('http://public.example/articles?q=china%20macro') == (
        'public.example', 80, '/articles?q=china%20macro')
