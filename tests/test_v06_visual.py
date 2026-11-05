from tools.browser_support import chromium_executable
"""Real Chromium execution of cross-item visual selection."""
from pathlib import Path
import shutil
import pytest

def test_visual_coverage_and_highlights():
    executable=chromium_executable()
    if not executable: pytest.skip('Chromium unavailable')
    sync=pytest.importorskip('playwright.sync_api')
    with sync.sync_playwright() as p:
        browser=p.chromium.launch(executable_path=executable,args=['--no-sandbox'],headless=True)
        page=browser.new_page()
        page.set_content('<main>'+''.join(f'<article class="card"><h2><a href="/p/{i}">Report {i} macroeconomic research</a></h2><time datetime="2026-10-21">October 21</time></article>' for i in range(4))+'</main>')
        page.add_script_tag(path=str(Path(__file__).parents[1]/'static/picker.js'))
        result=page.evaluate("""() => {
          const doc=document, hit=OpenFeedPicker.chooseItem(doc.querySelector('article a'),doc);
          const rules={title:'h2 a',link:'a@href',date:'time@datetime'};
          const counts=OpenFeedPicker.coverage(doc,hit.selector,rules);
          const highlights=OpenFeedPicker.highlightMatches(doc,hit.selector,rules);
          return {counts,highlights,actual:doc.querySelectorAll('.of-match').length,fields:doc.querySelectorAll('.of-field-match').length};
        }""")
        assert result['counts']['total']==4
        assert result['counts']['fields']=={'title':4,'link':4,'date':4}
        assert result['actual']==4
        assert result['fields']==8
        assert result['highlights']['highlightedFields']==12
        browser.close()
