import asyncio,socket
import pytest
from openfeed.security import configured_egress_proxy,ConfiguredProxyResolver,UnsafeURL,check_url
from openfeed.physical_network import bind_physical

def test_only_fixed_operator_proxy_hop(monkeypatch):
 monkeypatch.setenv('OPENFEED_EGRESS_PROXY','http://evil.example:8900')
 with pytest.raises(UnsafeURL):configured_egress_proxy()
 monkeypatch.setenv('OPENFEED_EGRESS_PROXY','http://host.lima.internal:8900')
 assert configured_egress_proxy().endswith(':8900')
 r=asyncio.run(ConfiguredProxyResolver().resolve('host.lima.internal',8900));assert r[0]['host']=='192.168.5.2'
 with pytest.raises(UnsafeURL):check_url('http://host.lima.internal:8900',resolve=False)

def test_cannot_bind_vpn_interface(monkeypatch):
 from openfeed.physical_network import physical_interface
 monkeypatch.setenv('OPENFEED_DIRECT_INTERFACE','utun4')
 with pytest.raises(ValueError):physical_interface()

def test_bind_only_physical_interface(monkeypatch):
 from openfeed import physical_network as p
 monkeypatch.setattr(p.sys,'platform','darwin');monkeypatch.setenv('OPENFEED_DIRECT_INTERFACE','en0');monkeypatch.setattr(p.socket,'if_nametoindex',lambda name:4)
 calls=[]
 class Sock:
  family=socket.AF_INET
  def setsockopt(self,*args):calls.append(args)
 bind_physical(Sock());assert calls==[(socket.IPPROTO_IP,25,4)]

def test_physical_dns_rejects_private_results(monkeypatch):
 import dns.message,dns.rrset
 from openfeed import physical_network as p
 monkeypatch.setattr(p,'physical_dns_server',lambda:'192.168.1.1');monkeypatch.setattr(p,'bind_physical',lambda s:None)
 class Sock:
  def __enter__(self):return self
  def __exit__(self,*args):pass
  def settimeout(self,*args):pass
  def connect(self,*args):pass
  def send(self,data):self.query=dns.message.from_wire(data)
  def recv(self,n):
   r=dns.message.make_response(self.query);r.answer.append(dns.rrset.from_text('example.com.',60,'IN','A','127.0.0.1'));return r.to_wire()
 monkeypatch.setattr(p.socket,'socket',lambda *a:Sock())
 with pytest.raises(ValueError,match='non-public'):p.physical_dns_addresses('example.com',443)
