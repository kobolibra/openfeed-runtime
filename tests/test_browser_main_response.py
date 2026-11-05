from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from openfeed.sandbox_worker import wait_for_source
from openfeed.security import UpstreamHTTPError

@pytest.mark.asyncio
async def test_rejected_main_response_does_not_wait_for_subresources():
 page=SimpleNamespace(goto=AsyncMock(return_value=SimpleNamespace(status=429,headers={'retry-after':'600'})),wait_for_load_state=AsyncMock(),wait_for_timeout=AsyncMock())
 with pytest.raises(UpstreamHTTPError) as exc:await wait_for_source(page,'https://example.org/','')
 assert exc.value.status==429 and exc.value.retry_after=='600'
 assert page.goto.call_args.kwargs['wait_until']=='commit'
 page.wait_for_load_state.assert_not_called();page.wait_for_timeout.assert_not_called()

@pytest.mark.asyncio
async def test_dynamic_source_waits_for_its_content_not_unrelated_assets():
 selector=SimpleNamespace(first=SimpleNamespace(wait_for=AsyncMock()))
 page=SimpleNamespace(goto=AsyncMock(return_value=SimpleNamespace(status=200,headers={})),locator=lambda s:selector,wait_for_load_state=AsyncMock())
 await wait_for_source(page,'https://example.org/','.articles')
 selector.first.wait_for.assert_awaited_once_with(state='attached',timeout=9000)
 page.wait_for_load_state.assert_not_called()

@pytest.mark.asyncio
async def test_no_selector_requires_loaded_document():
 page=SimpleNamespace(goto=AsyncMock(return_value=SimpleNamespace(status=200,headers={})),wait_for_load_state=AsyncMock(),wait_for_timeout=AsyncMock())
 await wait_for_source(page,'https://example.org/','')
 page.wait_for_load_state.assert_awaited_once_with('domcontentloaded',timeout=9000)
