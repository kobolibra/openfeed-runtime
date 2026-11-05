"""Audit regressions: cross-origin redirects, URL origin normalization, lock affordance."""
import pytest
from openfeed.pagination import collect_pages, next_page
from openfeed.security import UnsafeURL
from pathlib import Path

BASE='https://site.example/articles'
HTML=b'<main><article><a href="/a">A substantial analysis of global equity markets</a></article><article><a href="/b">Another substantial research analysis on bonds</a></article></main>'

@pytest.mark.asyncio
async def test_pagination_blocks_cross_origin_first_page_redirect():
    async def redirect(_):
        return 'https://redirected.example/articles', HTML, 'utf-8'
    with pytest.raises(UnsafeURL, match='redirect'):
        await collect_pages(BASE, {'mode':'css','item_selector':'article','next_selector':'a.next','max_pages':2}, redirect, None)

@pytest.mark.asyncio
async def test_pagination_normalizes_explicit_https_port():
    html=HTML.decode().replace('</main>','<a class="next" href="https://site.example:443/articles?p=2">Next</a></main>')
    url=next_page(html,BASE,'.next',('https','site.example',None))
    assert url=='https://site.example:443/articles?p=2'


def test_lock_action_clears_client_token():
    code=Path('static/app.js').read_text()
    assert "storage.removeItem('openfeed-token')" in code


def test_readme_does_not_claim_pagination_missing():
    assert 'RSSHub/RSS-Bridge integration, pagination, API-specific extraction' not in Path('README.md').read_text()
