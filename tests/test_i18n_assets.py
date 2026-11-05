from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]/'static'

def test_all_i18n_keys_have_chinese_translations():
    html=(ROOT/'index.html').read_text()
    script=(ROOT/'i18n.js').read_text()
    keys=set(re.findall(r'data-i18n="([a-z_]+)"',html))
    assert len(keys)>20
    for key in keys:
        assert re.search(r'\b'+re.escape(key)+r'\s*:',script),key
    assert 'id="language-toggle"' in html
    assert "OpenFeedI18n?.toggle()" in (ROOT/'app.js').read_text()
