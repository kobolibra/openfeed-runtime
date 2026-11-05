"""Diagnostic capture through the system transport for a FIXED public whitelist.
This is NOT OpenFeed's protected fetcher and must never be used for arbitrary
user URLs. It lets extraction/RSS be verified against genuine page captures
when fake-IP system DNS prevents the app's public-IP-pinned client from running.
"""
from __future__ import annotations
import argparse,asyncio,json
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from tools import verify_live_sources as live
ALLOWED={urlsplit(url).hostname for _,url in live.SOURCES}
ALLOWED|={h.removeprefix('www.') for h in ALLOWED}
async def capture(url):
 async with httpx.AsyncClient(timeout=12,follow_redirects=False,trust_env=True,headers={'User-Agent':live.USER_AGENT}) as client:
  for _ in range(4):
   parsed=urlsplit(url)
   if parsed.scheme!='https' or parsed.hostname not in ALLOWED or parsed.username or parsed.password or parsed.port not in (None,443):
    raise ValueError('Diagnostic transport refuses non-whitelisted destination/redirect')
   async with client.stream('GET',url) as response:
    if response.status_code in (301,302,303,307,308):
     from urllib.parse import urljoin
     url=urljoin(url,response.headers.get('location',''));continue
    if response.status_code>=400:raise ValueError('Upstream HTTP '+str(response.status_code))
    chunks=[];size=0
    async for chunk in response.aiter_bytes():
     chunks.append(chunk);size+=len(chunk)
     if size>2_500_000:raise ValueError('Capture exceeds size limit')
    return str(response.url),b''.join(chunks),response.charset_encoding or 'utf-8'
 raise ValueError('Too many capture redirects')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
 live.fetch=capture
 results=asyncio.run(live.run(Path(a.output)))
 path=Path(a.output)/'results.json';payload=json.loads(path.read_text());payload['transport']='System HTTPX diagnostic capture of fixed whitelisted public URLs; NOT protected OpenFeed fetch. App default DNS blocker remains.';path.write_text(json.dumps(payload,ensure_ascii=False,indent=2))
