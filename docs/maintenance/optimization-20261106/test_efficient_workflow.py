from pathlib import Path
import yaml
P=Path(__file__).resolve().parents[2]/'outputs/OpenFeed-cloud/runtime-cloud-efficient.yml'
def test_clock_has_native_wait_and_no_runtime_data_credentials():
 d=yaml.safe_load(P.read_text());jobs=d['jobs'];clock=jobs['interval'];assert clock['environment']['name']=='openfeed-publication-interval';assert 'OPENFEED_RUNTIME_KEY' not in str(clock);assert jobs['runtime']['permissions']=={'contents':'write','pages':'write'};assert jobs['authorize']['permissions']=={'contents':'read'};assert clock['permissions']=={'actions':'write','contents':'read'}
def test_single_writer_and_no_busy_wait_or_public_private_data_cache():
 d=yaml.safe_load(P.read_text());assert d['concurrency']['group']=='openfeed-runtime-state-writer';assert not d['concurrency']['cancel-in-progress'];assert 'while time.time()' not in P.read_text();assert 'actions/upload-artifact' not in P.read_text();cache=[x for x in d['jobs']['runtime']['steps'] if x.get('with',{}).get('cache')];assert len(cache)==1 and cache[0]['with']['cache']=='pip'
def test_authorized_claim_gates_both_work_and_next_generation():
 d=yaml.safe_load(P.read_text());jobs=d['jobs'];assert jobs['runtime']['needs']=='authorize' and jobs['interval']['needs']=='authorize';assert 'claimed' in jobs['runtime']['if'] and 'claimed' in jobs['interval']['if'];assert set(d['on'])=={'schedule','workflow_dispatch'};assert len(d['on']['schedule'])==1
