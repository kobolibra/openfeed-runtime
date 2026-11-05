"""Find the explicitly configured, PATH or Playwright-managed Chromium binary."""
import os
from pathlib import Path
import shutil
from concurrent.futures import ThreadPoolExecutor


def chromium_executable():
    configured=os.getenv('OPENFEED_CHROMIUM_PATH')
    if configured:
        if not Path(configured).is_file():
            raise FileNotFoundError('OPENFEED_CHROMIUM_PATH does not exist: '+configured)
        return configured
    system=shutil.which('chromium') or shutil.which('chromium-browser')
    if system:return system
    try:
        from playwright.sync_api import sync_playwright
        def managed_path():
            with sync_playwright() as p:
                return p.chromium.executable_path
        # Also safe when a test calls discovery from an active asyncio loop.
        with ThreadPoolExecutor(max_workers=1) as pool:
            managed=pool.submit(managed_path).result()
        return managed if Path(managed).is_file() else None
    except ImportError:
        return None
