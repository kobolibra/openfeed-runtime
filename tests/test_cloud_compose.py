from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
def test_http_cycle_has_no_browser_dependency():
 services=yaml.safe_load((ROOT/'compose.cloud.yaml').read_text())['services']
 assert set(services['cycle']['depends_on'])=={'browser-volume-init'}
 assert services['browser-worker']['profiles']==['browser']
 assert services['egress-proxy']['profiles']==['browser']
def test_optional_browser_retains_isolation_and_resource_limits():
 d=yaml.safe_load((ROOT/'compose.cloud.yaml').read_text());s=d['services'];worker=s['browser-worker']
 assert d['networks']['browser-private']['internal'] is True
 assert worker['networks']==['browser-private'] and worker['read_only'] is True
 assert worker['cap_drop']==['ALL'] and worker['pids_limit']==256
 assert worker['environment']['OPENFEED_BROWSER_EGRESS_PROXY']=='http://egress-proxy:8899'
 assert worker['depends_on']['egress-proxy']['condition']=='service_started'
 assert s['cycle']['mem_limit']=='512m' and s['egress-proxy']['read_only'] is True
