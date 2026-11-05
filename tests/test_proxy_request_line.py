import pytest
from openfeed.egress_proxy import validate_request_line, safe_forward_headers

@pytest.mark.parametrize('raw_line', [
    b'GET  http://example.com/ HTTP/1.1',
    b'GET\thttp://example.com/ HTTP/1.1',
    b'GET http://example.com/ HTTP/1.1 EXTRA',
    b'GET http://example.com/\x00 HTTP/1.1',
    b'GET http://example.com/ HTTP/2.0',
    b'POST http://example.com/ HTTP/1.1',
    b'CONNECT example.com:443\tHTTP/1.1',
    b'CONNECT example.com:443 HTTP/1.1\rZ',
])
def test_reject_ambiguous_request_lines(raw_line):
    with pytest.raises(ValueError):
        validate_request_line(raw_line)

def test_valid_proxy_request_lines():
    assert validate_request_line(b'CONNECT example.com:443 HTTP/1.1') == ('CONNECT','example.com:443','HTTP/1.1')
    assert validate_request_line(b'GET http://example.com/a HTTP/1.0')[0] == 'GET'

def test_connect_header_syntax_checked():
    with pytest.raises(ValueError):
        safe_forward_headers(b'CONNECT example.com:443 HTTP/1.1\r\nX-Test: one\r\n another\r\n\r\n')
