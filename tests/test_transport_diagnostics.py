import asyncio
import errno
import socket
import ssl
from unittest.mock import AsyncMock
import pytest
from aiohttp import ClientConnectorError, ServerDisconnectedError
from openfeed.security import UpstreamConnectionError, connection_failure_category
from openfeed.storage import Store
import openfeed.app as server

@pytest.mark.parametrize('error,expected',[
 (socket.gaierror(-2,'private diagnostic'),'dns_resolution'),
 (ssl.SSLCertVerificationError(1,'certificate rejected'),'tls_certificate'),
 (ssl.SSLError(1,'handshake failure'),'tls_handshake'),
 (asyncio.TimeoutError(),'timeout'),
 (ConnectionResetError(errno.ECONNRESET,'reset'),'connection_closed'),
 (ConnectionResetError(),'connection_closed'),
 (ServerDisconnectedError(),'connection_closed'),
 (ConnectionRefusedError(errno.ECONNREFUSED,'refused'),'connection_refused'),
 (OSError(errno.ENETUNREACH,'unreachable'),'network_unreachable'),
 (RuntimeError('unknown'),'transport_error'),
])
def test_categories(error,expected):
 assert connection_failure_category(error)==expected


def test_wrapped_connector_and_cycle_do_not_expose_sensitive_exception_text():
 inner=ConnectionResetError(errno.ECONNRESET,'https://example.org/?secret=do-not-log')
 wrapped=ClientConnectorError(None,inner)
 inner.__cause__=wrapped
 error=UpstreamConnectionError(wrapped)
 assert error.category=='connection_closed'
 assert 'secret' not in str(error) and 'do-not-log' not in str(error)


@pytest.mark.asyncio
async def test_failed_transport_preserves_prior_rss_and_reports_actionable_reason(monkeypatch,tmp_path):
 db=Store(str(tmp_path/'state.sqlite'));monkeypatch.setattr(server,'store',db)
 monkeypatch.setattr(server,'_last_domain',{});monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
 f=db.create({'title':'Research','source_url':'https://example.org/list','recipe':{}})
 db.finish(f,[{'title':'Existing','url':'https://example.org/a','summary':'','published_at':None}],None,1)
 before=db.entries(f['id'])
 monkeypatch.setattr(server,'fetch',AsyncMock(side_effect=UpstreamConnectionError(asyncio.TimeoutError())))
 outcome=await server.run_feed(f['id'])
 assert outcome['status']=='error'
 assert 'timeout' in db.get(f['id'])['last_error']
 assert db.entries(f['id'])==before
 db.close()

@pytest.mark.asyncio
async def test_fetch_turns_empty_timeout_into_safe_actionable_error(monkeypatch):
 import openfeed.security as security
 class Request:
  async def __aenter__(self):raise asyncio.TimeoutError('https://example.org/?key=private')
  async def __aexit__(self,*args):pass
 class Session:
  def __init__(self,**kwargs):self.connector=kwargs['connector']
  async def __aenter__(self):return self
  async def __aexit__(self,*args):await self.connector.close()
  def get(self,*args,**kwargs):return Request()
 monkeypatch.setattr(security,'ClientSession',Session)
 with pytest.raises(UpstreamConnectionError) as result:
  await security.fetch('https://example.org/list?key=private')
 assert result.value.category=='timeout'
 assert 'private' not in str(result.value)

@pytest.mark.parametrize('status,expected',[(504,'egress_timeout'),(502,'egress_connection'),(403,'egress_policy')])
def test_shared_proxy_errors_are_not_opaque_transport_errors(status,expected):
 from aiohttp import ClientHttpProxyError
 assert connection_failure_category(ClientHttpProxyError(None,(),status=status))==expected
