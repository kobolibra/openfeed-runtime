import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock
import pytest
from openfeed import egress_proxy as p
from openfeed import physical_network as network


def test_dhcp_timeout_is_a_handled_network_error(monkeypatch):
    network._CACHE.clear()
    monkeypatch.setattr(network, 'physical_interface', lambda: 'en0')
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('ipconfig', 3)
    monkeypatch.setattr(network.subprocess, 'run', timeout)
    with pytest.raises(OSError, match='discovery timed out'):
        network.physical_dns_server()


def test_encrypted_dns_has_a_total_budget_before_socket_connect(monkeypatch):
    monkeypatch.setenv('OPENFEED_DIRECT_INTERFACE', 'en0')
    monkeypatch.delenv('OPENFEED_PROXY_UPSTREAM', raising=False)
    budgets=[]
    original=asyncio.wait_for
    async def limit(awaitable, timeout):
        budgets.append(timeout)
        return await original(awaitable, 0.01)
    async def stalled(*args):
        await asyncio.sleep(1)
    monkeypatch.setattr(p.asyncio, 'to_thread', stalled)
    monkeypatch.setattr(p.asyncio, 'wait_for', limit)
    with pytest.raises(p.DialFailure) as error:
        asyncio.run(p.dial_public('example.com',443))
    assert budgets == [8]
    assert error.value.stage == "dns" and error.value.timed_out


def test_no_plain_http_error_is_written_inside_established_tls(monkeypatch):
    async def run():
        reader=asyncio.StreamReader()
        reader.feed_data(b'CONNECT example.com:443 HTTP/1.1\r\nHost: example.com\r\n\r\n')
        reader.feed_eof()
        client=MagicMock();client.drain=AsyncMock();client.wait_closed=AsyncMock()
        remote=MagicMock()
        monkeypatch.setattr(p,'dial_public',AsyncMock(return_value=(MagicMock(),remote)))
        monkeypatch.setattr(p,'pump',AsyncMock(side_effect=TimeoutError('tunnel expired')))
        await p.handle(reader,client)
        data=b''.join(call.args[0] for call in client.write.call_args_list)
        assert data == b'HTTP/1.1 200 Connection established\r\n\r\n'
        assert remote.close.called and client.close.called
    asyncio.run(run())


def test_connect_failure_has_host_phase_and_elapsed_without_url_secrets(monkeypatch,capsys):
    async def run():
        reader=asyncio.StreamReader();reader.feed_data(b'CONNECT example.com:443 HTTP/1.1\r\n\r\n');reader.feed_eof()
        writer=MagicMock();writer.drain=AsyncMock();writer.wait_closed=AsyncMock()
        monkeypatch.setenv('OPENFEED_PROXY_DIAGNOSTICS','1')
        monkeypatch.setattr(p,'dial_public',AsyncMock(side_effect=TimeoutError()))
        await p.handle(reader,writer)
        assert b'504' in writer.write.call_args.args[0]
    asyncio.run(run())
    assert 'host=example.com phase=connect elapsed=' in capsys.readouterr().out


def test_browser_tunnel_and_selector_failures_are_classified_separately():
    from openfeed.diagnostics import failure_summary
    rows=[{'id':'a','enabled':True,'status':'error','last_error':'Browser worker: net::ERR_TUNNEL_CONNECTION_FAILED'},
          {'id':'b','enabled':True,'status':'error','last_error':'Browser worker: Locator.wait_for: Timeout 9000ms exceeded.'}]
    summary=failure_summary(rows)
    assert summary['error_feed_ids']['transport']==['a']
    assert summary['error_feed_ids']['extraction']==['b']
