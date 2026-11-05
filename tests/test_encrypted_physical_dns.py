import socket
import pytest
from openfeed import physical_network as p

@pytest.fixture(autouse=True)
def setup(monkeypatch):
 monkeypatch.setattr(p,'physical_interface',lambda:'en0');p._ENCRYPTED_CACHE.clear()

def row(name,kind,data,ttl=30):return {'name':name+'.','type':kind,'data':data,'TTL':ttl}

def test_aliases_resolve_to_public_addresses_without_changing_source_identity(monkeypatch):
 calls=[]
 def query(host,kind):
  calls.append((host,kind))
  if host=='research.example' and kind=='CNAME':return [row(host,5,'cdn.example.')]
  if kind=='CNAME':return []
  return [row(host,1,'8.8.8.8')]
 monkeypatch.setattr(p,'_physical_doh_query',query)
 result=p._encrypted_addresses('research.example',443)
 assert result[0][4]==('8.8.8.8',443)
 assert calls==[('research.example','CNAME'),('cdn.example','CNAME'),('cdn.example','A')]
 assert p._encrypted_addresses('research.example',443)==result and len(calls)==3

@pytest.mark.parametrize('ip',['127.0.0.1','10.0.0.1','169.254.169.254','198.18.3.151'])
def test_encrypted_dns_rejects_all_private_and_fake_ip_answers(monkeypatch,ip):
 monkeypatch.setattr(p,'_physical_doh_query',lambda host,kind:[] if kind=='CNAME' else [row(host,1,ip)])
 with pytest.raises(ValueError,match='non-public'):p._encrypted_addresses('research.example',443)

def test_alias_loop_and_ambiguous_aliases_are_rejected(monkeypatch):
 monkeypatch.setattr(p,'_physical_doh_query',lambda host,kind:[row(host,5,host)])
 with pytest.raises(ValueError,match='loop'):p._encrypted_addresses('research.example',443)
 monkeypatch.setattr(p,'_physical_doh_query',lambda host,kind:[row(host,5,'one.example'),row(host,5,'two.example')])
 with pytest.raises(ValueError,match='Ambiguous'):p._encrypted_addresses('research.example',443)

def test_private_alias_never_reaches_address_lookup(monkeypatch):
 monkeypatch.setattr(p,'_physical_doh_query',lambda host,kind:[row(host,5,'localhost')])
 with pytest.raises(ValueError):p._encrypted_addresses('research.example',443)

def test_only_servfail_can_use_alias_hint_and_address_still_comes_from_doh(monkeypatch):
 calls=[]
 def query(host,kind):
  calls.append((host,kind))
  if host=='research.example':raise p.ResolverFailure(2)
  return [] if kind=='CNAME' else [row(host,1,'8.8.4.4')]
 monkeypatch.setattr(p,'_physical_doh_query',query)
 monkeypatch.setattr(p,'_physical_alias_hint',lambda host:[row(host,5,'cdn.example')])
 assert p._encrypted_addresses('research.example',443)[0][4]==('8.8.4.4',443)
 assert ('research.example','A') not in calls and ('cdn.example','A') in calls

@pytest.mark.parametrize('rcode',[3,5])
def test_nxdomain_and_refused_do_not_fallback(monkeypatch,rcode):
 def query(*args):raise p.ResolverFailure(rcode)
 monkeypatch.setattr(p,'_physical_doh_query',query)
 def unexpected(*args):raise AssertionError('must not fallback')
 monkeypatch.setattr(p,'_physical_alias_hint',unexpected)
 with pytest.raises(p.ResolverFailure):p._encrypted_addresses('research.example',443)

def test_unrelated_address_does_not_get_dialed(monkeypatch):
 monkeypatch.setattr(p,'_physical_doh_query',lambda host,kind:[] if kind=='CNAME' else [row('unrelated.example',1,'8.8.8.8')])
 with pytest.raises(OSError,match='no public'):p._encrypted_addresses('research.example',443)

def test_zero_ttl_does_not_become_permanent_pin(monkeypatch):
 calls=[]
 def query(host,kind):calls.append(kind);return [] if kind=='CNAME' else [row(host,1,'8.8.8.8',0)]
 monkeypatch.setattr(p,'_physical_doh_query',query)
 p._encrypted_addresses('research.example',443);p._encrypted_addresses('research.example',443)
 assert calls.count('A')==2

def test_cname_servfail_without_alias_can_still_have_valid_encrypted_a(monkeypatch):
 def query(host,kind):
  if kind=='CNAME':raise p.ResolverFailure(2)
  return [row(host,1,'8.8.8.8')]
 monkeypatch.setattr(p,'_physical_doh_query',query)
 def unavailable(*a):raise OSError('no alias hint')
 monkeypatch.setattr(p,'_physical_alias_hint',unavailable)
 assert p._encrypted_addresses('research.example',443)[0][4]==('8.8.8.8',443)
