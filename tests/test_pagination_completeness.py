import pytest
from openfeed.pagination import collect_pages

@pytest.mark.asyncio
async def test_page_budget_reveals_truncated_inventory():
    async def fetch(url):
        page='<article><h2><a href="/job1">Job 1</a></h2></article><a class="next" href="/page2">Next</a>'
        return url,page.encode(),'utf-8'
    items,meta=await collect_pages('https://jobs.example/page1',{'mode':'css','item_selector':'article','max_pages':1,'next_selector':'a.next'},fetch,None)
    assert len(items)==1
    assert meta['limit_reached'] is True

@pytest.mark.asyncio
async def test_full_inventory_without_next_is_not_truncated():
    async def fetch(url):
        page='<article><h2><a href="/job1">Job 1</a></h2></article>'
        return url,page.encode(),'utf-8'
    items,meta=await collect_pages('https://jobs.example/page1',{'mode':'css','item_selector':'article','max_pages':1,'next_selector':'a.next'},fetch,None)
    assert len(items)==1
    assert meta['limit_reached'] is False
