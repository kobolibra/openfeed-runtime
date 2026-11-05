import pytest
from tools.audit_sources import audit_one

HTML=b'''<html><main><article><h2><a href="/a">Extensive insights on global markets</a></h2><time datetime="2026-10-20">2026-10-20</time></article><article><h2><a href="/b">Extensive insights on emerging technology</a></h2><time datetime="2026-10-21">2026-10-21</time></article></main></html>'''
ROW={'name':'Research Test','source_url':'https://example.org/research'}

@pytest.mark.asyncio
async def test_auditor_extracts_without_claiming_production_ready():
    async def get(url): return url, HTML, 'utf-8'
    result=await audit_one(ROW,get)
    assert result['valid_items']==2
    assert result['status']=='candidate_requires_review'

@pytest.mark.asyncio
async def test_auditor_reports_blocked_network_and_no_false_success():
    async def get(url): raise OSError('DNS blocked')
    result=await audit_one(ROW,get)
    assert result['status']=='fetch_failed'
    assert result['valid_items']==0
