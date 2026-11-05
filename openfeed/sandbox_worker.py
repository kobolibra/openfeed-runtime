"""Browser worker with no API/DB connection and Docker internal-only networking.

All outbound traffic MUST pass through egress_proxy on the internal Docker
network. This module alone is not a sandbox; the Compose network is essential.
"""
from __future__ import annotations
import asyncio
import base64
import json
import math
import os
import platform
import stat
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from .browser_ipc import write_atomic
from .security import check_url, UpstreamHTTPError

MAX_HTML=2_500_000
JOB_ID=re.compile(r'^[a-f0-9]{32}$')


def validate_internal_proxy(proxy_url: str) -> None:
    """Fail closed if the browser proxy points outside the Compose egress service."""
    p=urlsplit(proxy_url)
    if (p.scheme != 'http' or p.hostname != 'egress-proxy' or p.port != 8899
            or p.username is not None or p.password is not None
            or p.path not in ('', '/') or p.query or p.fragment):
        raise ValueError('Browser proxy must be the internal egress-proxy:8899 service')


async def wait_for_source(page, url: str, wait_selector: str) -> None:
    # Inspect the main response before subresources can stall DOMContentLoaded.
    response=await page.goto(url,wait_until='commit',timeout=20000)
    if response and response.status>=400:
        raise UpstreamHTTPError(response.status,url,response.headers.get('retry-after',''))
    if wait_selector:
        await page.locator(wait_selector).first.wait_for(state='attached',timeout=9000)
    else:
        await page.wait_for_load_state('domcontentloaded',timeout=9000)
        await page.wait_for_timeout(1200)


async def render(url: str, wait_selector: str) -> tuple[str, bytes]:
    from playwright.async_api import async_playwright
    check_url(url,resolve=False)
    if len(wait_selector)>180:raise ValueError('Wait selector too long')
    proxy_url=os.environ.get('OPENFEED_BROWSER_EGRESS_PROXY','http://egress-proxy:8899')
    validate_internal_proxy(proxy_url)
    async with async_playwright() as playwright:
        options={'headless':True,'proxy':{'server':proxy_url}}
        executable=os.getenv('OPENFEED_BROWSER_EXECUTABLE','')
        if executable:options['executable_path']=executable
        browser=await playwright.chromium.launch(**options)
        try:
            context=await browser.new_context(service_workers='block',accept_downloads=False,
                viewport={'width':1365,'height':900},
                user_agent=('Mozilla/5.0 (X11; Linux '+platform.machine()+') AppleWebKit/537.36 '
                            '(KHTML, like Gecko) Chrome/'+browser.version+' Safari/537.36 OpenFeedStudio/0.4'))
            count=0
            async def route_guard(route):
                nonlocal count
                count+=1
                if count>70 or route.request.resource_type not in ('document','script','xhr','fetch','stylesheet'):
                    return await route.abort()
                try:check_url(route.request.url,resolve=False)
                except Exception:return await route.abort()
                return await route.continue_()
            await context.route('**/*',route_guard)
            if hasattr(context,'route_web_socket'):
                await context.route_web_socket('**/*',lambda ws:ws.close())
            page=await context.new_page()
            try:
                await wait_for_source(page,url,wait_selector)
                final=page.url
                check_url(final,resolve=False)
                body=(await page.content()).encode('utf-8')
                if len(body)>MAX_HTML:raise ValueError('Rendered HTML exceeded limit')
                return final,body
            finally:
                await context.close()
        finally:
            await browser.close()


def read_job_safely(job: Path) -> dict:
    """Read a bounded regular job without following symlinks in the shared IPC volume."""
    fd = os.open(job, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NONBLOCK', 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 8192:
            raise ValueError('Invalid browser job file')
        data = os.read(fd, 8193)
        if len(data) > 8192:
            raise ValueError('Oversized browser job')
        payload = json.loads(data.decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('Browser job must be a JSON object')
        allowed={'id', 'url', 'wait_selector', 'submitted_at'}
        if set(payload)-allowed:
            raise ValueError('Unexpected browser job fields')
        if not isinstance(payload.get('id'), str) or not isinstance(payload.get('url'), str) or not isinstance(payload.get('wait_selector',''), str):
            raise ValueError('Invalid browser job field types')
        submitted=payload.get('submitted_at')
        if isinstance(submitted, bool) or not isinstance(submitted, (int,float)) or not math.isfinite(submitted):
            raise ValueError('Invalid browser job timestamp')
        return payload
    finally:
        os.close(fd)


async def process_job(root:Path,job:Path):
    # The caller publishes jobs via an atomic filesystem rename.
    try:
        ident=job.stem
        if not JOB_ID.fullmatch(ident):
            job.unlink(missing_ok=True);return
        payload=read_job_safely(job)
        if payload.get('id')!=ident or abs(time.time()-float(payload.get('submitted_at',0)))>55:
            raise ValueError('Stale or invalid browser job')
        url=payload['url'];wait=payload.get('wait_selector','')
        final,body=await asyncio.wait_for(render(url,wait),timeout=35)
        result={'url':final,'html':base64.b64encode(body).decode('ascii')}
    except UpstreamHTTPError as exc:
        result={'error':str(exc),'http_status':exc.status,'retry_after':exc.retry_after}
    except asyncio.TimeoutError:
        result={'error':'Browser render timed out; original feed retained'}
    except Exception as exc:
        result={'error':str(exc)[:240]}
    result['id']=job.stem
    out=root/'done'/(job.stem+'.json')
    try:
        write_atomic(out,json.dumps(result,separators=(',',':')).encode('utf-8'))
    finally:
        job.unlink(missing_ok=True)


async def main():
    root=Path(os.environ.get('OPENFEED_BROWSER_JOB_DIR','/browser-jobs'))
    pending=root/'pending';done=root/'done'
    if not pending.is_dir() or not done.is_dir():
        raise RuntimeError('Worker volume is missing; refuse to start')
    while True:
        current=time.time()
        # Remove orphan results; never retain page content indefinitely.
        for path in done.glob('*.json'):
            if path.is_symlink():
                path.unlink(missing_ok=True)
                continue
            if path.is_file() and current-path.stat().st_mtime>180:
                path.unlink(missing_ok=True)
        # Do not follow attacker-created symlinks during queue inspection.
        jobs=sorted((p for p in pending.glob('*.json') if not p.is_symlink() and p.is_file()),
                    key=lambda p:p.stat().st_mtime)
        if jobs:
            await process_job(root,jobs[0])
        else:
            await asyncio.sleep(0.25)

if __name__=='__main__':asyncio.run(main())
