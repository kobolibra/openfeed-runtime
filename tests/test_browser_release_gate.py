"""Verify fail-closed production guard for experimental browser extraction."""
import pytest
from openfeed.browser import browser_fetch

@pytest.mark.asyncio
async def test_browser_remains_disabled_by_default(monkeypatch):
    monkeypatch.delenv('OPENFEED_EXPERIMENTAL_BROWSER', raising=False)
    monkeypatch.delenv('OPENFEED_BROWSER_NETWORK_ISOLATED', raising=False)
    with pytest.raises(ValueError, match='disabled'):
        await browser_fetch('https://example.org')

@pytest.mark.asyncio
async def test_browser_requires_separate_network_isolation_opt_in(monkeypatch):
    monkeypatch.setenv('OPENFEED_EXPERIMENTAL_BROWSER','1')
    monkeypatch.delenv('OPENFEED_BROWSER_NETWORK_ISOLATED',raising=False)
    # Legacy opt-in flags are deliberately ignored: no in-process browser.
    monkeypatch.setenv('OPENFEED_UNSAFE_LOCAL_BROWSER','1')
    with pytest.raises(ValueError, match='isolated worker'):
        await browser_fetch('https://example.org')
