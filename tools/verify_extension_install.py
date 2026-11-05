"""Full Chromium MV3 installation smoke test for an environment with a working browser.

Requires: pip install playwright; playwright install chromium
Run: python tools/verify_extension_install.py

This is distinct from the DOM injection unit tests. It explicitly requires the
extension service worker to start and an actual chrome-extension:// popup page
to render, failing if Chromium cannot launch (as in constrained CI sandboxes).
"""
from pathlib import Path
import shutil
import os
from tempfile import TemporaryDirectory
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
EXT=ROOT/'extension'


def main():
    with TemporaryDirectory(prefix='of-extension-') as profile:
        with sync_playwright() as p:
            context=p.chromium.launch_persistent_context(
                profile,executable_path=os.environ.get('OPENFEED_CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('chromium-browser'),headless=True,
                args=[f'--disable-extensions-except={EXT}',f'--load-extension={EXT}'],
                timeout=25000)
            try:
                sw=context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker',timeout=15000)
                assert sw.url.startswith('chrome-extension://'), sw.url
                extension_id=sw.url.split('/')[2]
                manifest=sw.evaluate('chrome.runtime.getManifest()')
                assert manifest['manifest_version']==3
                assert manifest['permissions']==['activeTab','scripting','storage']
                popup=context.new_page()
                popup.goto(f'chrome-extension://{extension_id}/popup.html',wait_until='domcontentloaded')
                assert popup.locator('#studio').count()==1
                assert popup.locator('[data-field="item"]').count()==1
                print('PASS: extension service worker loaded and popup opened with real Chrome extension origin')
            finally:
                context.close()


if __name__=='__main__':main()
