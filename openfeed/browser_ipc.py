"""Filesystem IPC transport to an isolated browser container.

The API container NEVER starts Chromium. Browser pages run on a separate
Docker INTERNAL network, with only the explicit public-only egress proxy.
The shared volume contains short-lived request/response files, not the DB.
"""
from __future__ import annotations
import asyncio
import base64
import json
import os
from pathlib import Path
import secrets
import time
import tempfile
import weakref
from .security import check_url, UpstreamHTTPError

MAX_RESPONSE = 3_600_000
MAX_WAIT = 42.0
MAX_ENCODED_HTML = 3_400_000



def job_dir():
    folder = os.getenv('OPENFEED_BROWSER_JOB_DIR', '')
    if not folder or not os.path.isdir(folder):
        raise ValueError('Isolated browser job directory is not available')
    return Path(folder)


def write_atomic(path: Path, data: bytes):
    # Unique temp names prevent deadlocks after a crash left a .tmp artifact.
    fd,temp=tempfile.mkstemp(prefix='.openfeed-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


def read_regular_result(path: Path):
    # Prevent a compromised worker volume from redirecting the API process to
    # /data, /proc, or another file via a symlink.
    import stat
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_CLOEXEC',0)|getattr(os,'O_NONBLOCK',0))
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_RESPONSE:
            raise ValueError('Invalid browser result file')
        with os.fdopen(fd,'rb',closefd=False) as handle:
            data=handle.read(MAX_RESPONSE+1)
        if len(data)>MAX_RESPONSE:
            raise ValueError('Browser worker returned an oversized result')
        return data
    finally:
        os.close(fd)


_worker_locks = weakref.WeakKeyDictionary()


async def request_render(url: str, wait_selector: str = '') -> tuple[str,bytes,str]:
    # One isolated worker consumes jobs serially. Queue in the API before
    # starting the job deadline, rather than expiring the next caller's job
    # while Chromium is still processing the previous source.
    loop=asyncio.get_running_loop()
    lock=_worker_locks.setdefault(loop,asyncio.Lock())
    async with lock:
        return await _request_render(url,wait_selector)


async def _request_render(url: str, wait_selector: str = '') -> tuple[str,bytes,str]:
    check_url(url,resolve=False)
    if len(wait_selector)>180:
        raise ValueError('Browser wait selector is too long')
    root=job_dir()
    pending=root/'pending';done=root/'done'
    if not pending.is_dir() or not done.is_dir():
        raise ValueError('Isolated browser worker directories are missing')
    if sum(1 for _ in pending.glob('*.json'))>=20:
        raise ValueError('Isolated browser queue is full')
    identifier=secrets.token_hex(16)
    queued=pending/(identifier+'.json')
    result=done/(identifier+'.json')
    write_atomic(queued,json.dumps({'id':identifier,'url':url,'wait_selector':wait_selector,
                 'submitted_at':time.time()},separators=(',',':')).encode())
    deadline=time.monotonic()+MAX_WAIT
    try:
        while time.monotonic()<deadline:
            if result.exists():
                payload=read_regular_result(result)
                response=json.loads(payload)
                if not isinstance(response, dict) or response.get('id') != identifier:
                    raise ValueError('Browser worker result job ID mismatch')
                error=response.get('error')
                if error is not None:
                    if not isinstance(error,str):
                        raise ValueError('Invalid browser error response')
                    status=response.get('http_status')
                    if status is not None:
                        delay=response.get('retry_after','')
                        if type(status) is not int or not 400<=status<=599 or not isinstance(delay,str) or len(delay)>128:
                            raise ValueError('Invalid browser HTTP error metadata')
                        raise UpstreamHTTPError(status,url,delay)
                    raise ValueError('Browser worker: '+error[:220])
                final=response.get('url')
                encoded=response.get('html')
                if not isinstance(final,str) or not isinstance(encoded,str) or len(encoded)>MAX_ENCODED_HTML:
                    raise ValueError('Invalid or oversized browser result payload')
                check_url(final,resolve=False)
                html=base64.b64decode(encoded,validate=True)
                if len(html)>2_500_000:
                    raise ValueError('Browser worker HTML exceeds limit')
                return final,html,'utf-8'
            await asyncio.sleep(0.15)
        raise ValueError('Isolated browser worker timed out; original Feed retained')
    finally:
        queued.unlink(missing_ok=True)
        result.unlink(missing_ok=True)
