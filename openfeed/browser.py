"""Fail-closed access to the separately isolated Chromium worker.

The FastAPI/web process never starts Chromium or permits an environment-flag
'bypass'. The browser runs in a different container, on an internal-only
Docker network with a public-IP-only egress proxy. See compose.browser.yaml.
"""
from __future__ import annotations
import os


async def browser_fetch(url: str, wait_selector: str = '') -> tuple[str, bytes, str]:
    if os.getenv('OPENFEED_BROWSER_SANDBOXED_WORKER','0') != '1':
        raise ValueError('Browser mode is disabled: configure the isolated worker Compose profile')
    from .browser_ipc import request_render
    return await request_render(url,wait_selector)
