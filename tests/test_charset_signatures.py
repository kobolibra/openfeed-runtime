import codecs
import pytest
from openfeed.security import detect_charset

@pytest.mark.parametrize('encoding',['utf-8-sig','utf-16','utf-32'])
def test_bom_overrides_stale_header_and_meta(encoding):
 text='<meta charset="gbk"><h1>中国研究</h1>'
 raw=text.encode(encoding)
 assert raw.decode(detect_charset(raw,'iso-8859-1'))==text

@pytest.mark.parametrize('label',['unknown-charset','base64_codec','zlib_codec','utf-8\r\nInjected: yes','x'*100])
def test_invalid_or_non_text_header_does_not_break_valid_document(label):
 raw='<h1>中国研究</h1>'.encode()
 assert raw.decode(detect_charset(raw,label))=='<h1>中国研究</h1>'

def test_invalid_meta_falls_back_to_valid_utf8():
 raw='<meta charset="bad-encoding"><h1>中国研究</h1>'.encode()
 assert raw.decode(detect_charset(raw))=='<meta charset="bad-encoding"><h1>中国研究</h1>'

def test_legacy_declaration_is_retained_without_bom():
 text='<h1>中国研究</h1>';raw=text.encode('gbk')
 assert raw.decode(detect_charset(raw,'gbk'))==text
