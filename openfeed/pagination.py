"""Bounded, same-origin follow-next pagination for public website feeds.

Only follows an explicit CSS next-page selector and never follows off-origin
links or silently starts pagination for existing recipes. This is deliberately
not a generic search/crawl engine.
"""
from __future__ import annotations

import asyncio
import os
import json
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from .extract import canonical_link, extract_articles, confirmed_empty_html, confirmed_empty_json, _json_path
from .security import check_url, UnsafeURL, public_request_options

MAX_PAGES = 3
MAX_ITEMS = 300


def normalized_origin(url: str) -> tuple[str, str, int]:
    """Treat explicit/default ports identically; never trust a redirect to a different origin."""
    parts = urlsplit(url)
    return parts.scheme, (parts.hostname or '').lower(), parts.port or (443 if parts.scheme == 'https' else 80)


def next_page(html: str, current: str, selector: str, expected_origin: tuple[str, str, int | None]) -> str | None:
    """Resolve the first matching next link; reject invalid/off-origin targets."""
    if not selector:
        return None
    try:
        doc = BeautifulSoup(html, 'lxml')
        node = doc.select_one(selector)
    except Exception as exc:
        raise ValueError('Invalid next-page CSS selector') from exc
    if node is None:
        return None
    if node.name != 'a':
        node = node.find('a', href=True)
    raw = node.get('href') if node else None
    if not raw:
        raise ValueError('Next-page selector matched an element without an anchor href')
    url = canonical_link(raw, current)
    if not url:
        raise UnsafeURL('Pagination target must be a public http(s) URL')
    check_url(url, resolve=False)
    parsed = urlsplit(url)
    origin = normalized_origin(url)
    if origin != (expected_origin[0], expected_origin[1], expected_origin[2] or (443 if expected_origin[0] == 'https' else 80)):
        raise UnsafeURL('Pagination cannot leave the original source origin')
    return url


async def collect_pages(
    source_url: str,
    recipe: dict,
    fetch_http,
    fetch_browser,
    *,
    pause=None,
) -> tuple[list[dict], dict]:
    """Fetch up to three pages with a bounded cross-page deduplication budget.

    Each callback returns (effective_url, raw_html, encoding). Callbacks must
    implement public-IP address validation including every redirect.
    """
    if recipe.get('json_offset_field'):
        return await collect_json_offset_pages(source_url,recipe,fetch_http,pause=pause)
    pages = max(1, min(MAX_PAGES, int(recipe.get('max_pages', 1))))
    selector = recipe.get('next_selector', '')
    if pages > 1 and not selector:
        raise ValueError('Multi-page extraction requires a next-page CSS selector')
    mode = recipe.get('fetch_mode', 'http')
    sleep = pause or asyncio.sleep
    delay = min(10.0, max(0.2, float(os.getenv('OPENFEED_PAGE_DELAY_SECONDS', '2'))))
    items = []
    unique = set()
    visited = set()
    url = recipe.get('fetch_url') or source_url
    check_url(url,resolve=False)
    origin = normalized_origin(url)
    reached_cap = False
    page_truncated = False
    empty_confirmed=False
    for page in range(pages):
        if url in visited:
            raise ValueError('Pagination loop detected; last known good feed was preserved')
        visited.add(url)
        if mode == 'browser':
            effective, body, encoding = await fetch_browser(url, recipe.get('wait_selector', ''))
        else:
            effective, body, encoding = await fetch_http(url, **public_request_options(recipe))
        parsed = urlsplit(effective)
        actual_origin = normalized_origin(effective)
        if pages > 1 and origin != actual_origin:
            raise UnsafeURL('A pagination redirect left the original source origin')
        text = body.decode(encoding, errors='replace')
        batch, _ = extract_articles(text, effective, recipe)
        if not batch and pages==1:empty_confirmed=confirmed_empty_json(text,recipe) if recipe.get('mode')=='json' else confirmed_empty_html(text,recipe)
        # Every extraction engine caps a page at 100 items. At that boundary
        # completeness is unknown, even when no next-page link is configured.
        page_truncated = page_truncated or len(batch) >= 100 or (
            recipe.get('mode') in ('pattern','pdf') and len(text)>1_300_000)
        for item in batch:
            if item['url'] not in unique:
                unique.add(item['url'])
                items.append(item)
                if len(items) >= MAX_ITEMS:
                    reached_cap = True
                    break
        if reached_cap:
            break
        # A page budget can truncate a listing even well below MAX_ITEMS.
        # Report truncation to the job inventory quality gate.
        next_url = next_page(text, effective, selector, origin) if selector else None
        if page + 1 >= pages:
            if next_url:
                reached_cap = True
            break
        if not next_url:
            break
        if next_url in visited:
            raise ValueError('Pagination loop detected; last known good feed was preserved')
        await sleep(delay)
        url = next_url
    metrics={'pages_fetched': len(visited), 'items_found': len(items), 'limit_reached': reached_cap or page_truncated}
    if empty_confirmed:metrics['empty_confirmed']=True
    return items,metrics


async def collect_json_offset_pages(source_url,recipe,fetch_http,*,pause=None):
    """Bounded same-origin JSON POST pagination with an exact server offset echo."""
    from .extract import check_json_contract
    pages=max(1,min(MAX_PAGES,int(recipe.get('max_pages',1))))
    url=recipe.get('fetch_url') or source_url
    check_url(url,resolve=False);origin=normalized_origin(url)
    field=recipe['json_offset_field'];body=dict(recipe.get('request_json') or {})
    offset=body.get(field);step=recipe.get('json_page_step',6)
    if type(offset) is not int or offset<0 or type(step) is not int or not 1<=step<=100:
        raise ValueError('Invalid JSON offset pagination configuration')
    sleep=pause or asyncio.sleep;items=[];seen=set();seen_pages=set();truncated=False
    count=0
    for page in range(pages):
        body[field]=offset
        effective,raw,encoding=await fetch_http(url,method='POST',json_data=dict(body),public_api_key=recipe.get('public_api_key',''))
        if normalized_origin(effective)!=origin:raise UnsafeURL('JSON pagination redirect left source origin')
        text=raw.decode(encoding,errors='replace');document=json.loads(text)
        check_json_contract(document,recipe)
        echo=_json_path(document,recipe['json_offset_response_path'])
        if type(echo) is not int or echo!=offset:raise ValueError('Server ignored JSON pagination offset')
        rows=_json_path(document,recipe.get('item_selector') or 'items')
        if not isinstance(rows,list) or len(rows)>step:raise ValueError('Unexpected JSON pagination page size')
        signature=json.dumps(rows,sort_keys=True,ensure_ascii=True)
        if rows and signature in seen_pages:raise ValueError('Server repeated JSON page; previous RSS preserved')
        seen_pages.add(signature);count+=1
        batch,_=extract_articles(text,effective,recipe)
        for item in batch:
            if item['url'] not in seen:seen.add(item['url']);items.append(item)
        if len(rows)<step:break
        if page+1==pages:truncated=True;break
        offset+=step
        await sleep(min(10.0,max(0.2,float(os.getenv('OPENFEED_PAGE_DELAY_SECONDS','2')))))
    # No matching records is not proof that the original source has no articles.
    return items,{'pages_fetched':count,'items_found':len(items),'limit_reached':truncated}
