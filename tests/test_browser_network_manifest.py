"""Offline structural checks; cannot substitute for Docker/network runtime audit."""
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]


def test_browser_private_network_and_proxy_not_published():
    overlay=yaml.safe_load((ROOT/'compose.browser.yaml').read_text())
    services=overlay['services']
    assert overlay['networks']['browser-private']['internal'] is True
    assert services['browser-worker']['networks']==['browser-private']
    assert set(services['egress-proxy']['networks'])=={'browser-private','outbound'}
    assert 'ports' not in services['browser-worker']
    assert 'ports' not in services['egress-proxy']
    assert services['browser-worker']['read_only'] is True
    assert services['browser-worker']['cap_drop']==['ALL']
    assert services['egress-proxy']['cap_drop']==['ALL']
    assert services['openfeed']['environment']['OPENFEED_BROWSER_SANDBOXED_WORKER']=='1'
    assert services['openfeed']['environment']['OPENFEED_EXPERIMENTAL_BROWSER']=='0'


def test_main_app_cannot_launch_chromium():
    source=(ROOT/'openfeed/browser.py').read_text()
    assert 'chromium.launch' not in source
    assert 'request_render' in source


def test_worker_is_non_root_and_only_mounts_job_volume():
    text=(ROOT/'Dockerfile.browser-worker').read_text()
    assert 'USER 10001:10001' in text
    browser=yaml.safe_load((ROOT/'compose.browser.yaml').read_text())['services']['browser-worker']
    mounts=' '.join(browser['volumes'])
    assert '/data' not in mounts and '/browser-jobs' in mounts
