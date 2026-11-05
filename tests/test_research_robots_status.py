import json
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from tools import research_inventory as research
from openfeed.security import UpstreamHTTPError

@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected,page_requested',[(403,'captured_requires_review',True),(404,'captured_requires_review',True),(405,'captured_requires_review',True),(429,'robots_unreachable',False),(503,'robots_unreachable',False)])
async def test_robots_http_status_is_not_a_disallow_rule(monkeypatch,tmp_path,status,expected,page_requested):
 url='https://example.org/insights';calls=[]
 async def fetch(address):
  calls.append(address)
  if address.endswith('/robots.txt'):raise UpstreamHTTPError(status,address)
  return address,b'<html><title>Public insights</title><main><article><h2><a href="/report">Real report</a></h2></article></main></html>','utf-8'
 monkeypatch.setattr(research,'fetch',fetch);monkeypatch.setattr(research.asyncio,'sleep',AsyncMock())
 inventory=tmp_path/'inventory.json';inventory.write_text(json.dumps({'urls':[{'index':1,'normalized_url':url}]}))
 await research.run(inventory,tmp_path/'out');rows=json.loads((tmp_path/'out/results.json').read_text())
 assert rows[0]['status']==expected
 assert (url in calls) is page_requested
 assert rows[0]['robots']['http_status']==status

@pytest.mark.asyncio
async def test_actual_disallow_rule_stops_resource_fetch(monkeypatch,tmp_path):
 calls=[]
 async def fetch(url):
  calls.append(url);assert url.endswith('/robots.txt')
  return url,b'User-agent: *\nDisallow: /search/\n','utf-8'
 monkeypatch.setattr(research,'fetch',fetch);monkeypatch.setattr(research.asyncio,'sleep',AsyncMock())
 inventory=tmp_path/'inventory.json';inventory.write_text(json.dumps({'urls':[{'index':1,'normalized_url':'https://example.org/search/'}]}))
 await research.run(inventory,tmp_path/'out');rows=json.loads((tmp_path/'out/results.json').read_text());assert rows[0]['status']=='robots_disallowed' and len(calls)==1
