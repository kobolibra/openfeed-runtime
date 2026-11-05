"""Fail-closed validation of extracted articles before publishing a refreshed feed.

This module intentionally rejects malformed records, but does not assume a
shrinking first page is evidence of content loss: feeds often rotate naturally.
"""
from __future__ import annotations
from collections import Counter
from urllib.parse import urlsplit
from .security import check_url

MAX_RECORDS = 300
MAX_TITLE = 500
MAX_SUMMARY = 15000


def validate_items(items: list[dict]) -> tuple[list[dict], dict]:
    if not isinstance(items, list) or len(items) > MAX_RECORDS:
        raise ValueError('Invalid item collection or extraction budget exceeded')
    cleaned = []
    urls = set()
    rejected = Counter()
    for item in items:
        if not isinstance(item, dict):
            rejected['malformed'] += 1
            continue
        title = item.get('title')
        url = item.get('url')
        if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE:
            rejected['invalid_title'] += 1
            continue
        if not isinstance(url, str):
            rejected['invalid_link'] += 1
            continue
        try:
            check_url(url, resolve=False)
        except ValueError:
            rejected['invalid_link'] += 1
            continue
        if url in urls:
            rejected['duplicate'] += 1
            continue
        summary = item.get('summary') or ''
        if not isinstance(summary, str) or len(summary) > MAX_SUMMARY:
            rejected['invalid_summary'] += 1
            continue
        publication = item.get('published_at')
        if publication is not None and not isinstance(publication, str):
            rejected['invalid_date'] += 1
            continue
        urls.add(url)
        cleaned.append({**item, 'title': title.strip(), 'url': url, 'summary': summary})
    if items and not cleaned:
        raise ValueError('All extracted records failed validation; last good feed preserved')
    return cleaned, {'input_count': len(items), 'accepted':len(cleaned), 'rejected':dict(rejected),
                     'date_missing':sum(not x.get('published_at') for x in cleaned)}
