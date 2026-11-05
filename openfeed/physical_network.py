"""macOS application-only physical egress, independent of global VPN routing."""
import ipaddress,re,socket,subprocess,sys,time
_CACHE={}

def physical_interface():
 import os
 name=os.getenv('OPENFEED_DIRECT_INTERFACE','')
 if sys.platform!='darwin' or not re.fullmatch(r'en[0-9]{1,3}',name):
  raise ValueError('Physical egress requires a macOS physical en interface')
 return name

def bind_physical(sock):
 name=physical_interface();index=socket.if_nametoindex(name)
 if sock.family==socket.AF_INET:sock.setsockopt(socket.IPPROTO_IP,25,index) # IP_BOUND_IF
 elif sock.family==socket.AF_INET6:sock.setsockopt(socket.IPPROTO_IPV6,125,index) # IPV6_BOUND_IF
 else:raise ValueError('Unsupported physical socket family')

def physical_dns_server():
 name=physical_interface();cached=_CACHE.get(name)
 if cached and cached[0]>time.monotonic():return cached[1]
 try:r=subprocess.run(['/usr/sbin/ipconfig','getpacket',name],capture_output=True,text=True,timeout=3)
 except subprocess.TimeoutExpired as exc:raise OSError('Physical DHCP DNS discovery timed out') from exc
 m=re.search(r'domain_name_server[^\n]*\{([^}]+)\}',r.stdout)
 if r.returncode or not m:raise OSError('No DHCP DNS on physical interface; no VPN fallback')
 servers=[x.strip() for x in m.group(1).split(',')]
 server=str(ipaddress.IPv4Address(servers[0]));_CACHE[name]=(time.monotonic()+30,server)
 return server

def physical_dns_addresses(host,port):
 import os
 mode=os.getenv("OPENFEED_PHYSICAL_DNS","dhcp")
 if mode=="encrypted":return _encrypted_addresses(host,port)
 if mode!="dhcp":raise ValueError("Unsupported physical DNS mode")
 import dns.message,dns.rdatatype,dns.flags
 query=dns.message.make_query(host,dns.rdatatype.A)
 server=physical_dns_server()
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
  bind_physical(sock);sock.settimeout(4);sock.connect((server,53));sock.send(query.to_wire());raw=sock.recv(65535)
 response=dns.message.from_wire(raw)
 if not query.is_response(response) or response.rcode()!=0 or response.flags&dns.flags.TC:
  raise OSError('Invalid physical DNS reply; no VPN fallback')
 from .egress_proxy import public_ip
 records=[]
 for answer in response.answer:
  if answer.rdtype!=dns.rdatatype.A:continue
  for record in answer:
   ip=record.address
   if not public_ip(ip):raise ValueError('Physical DNS returned non-public address')
   records.append((socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',(ip,port)))
 if not records:raise OSError('Physical DNS returned no public IPv4 addresses')
 return records

_ENCRYPTED_CACHE={}

class ResolverFailure(OSError):
 def __init__(self,rcode):
  self.rcode=rcode
  super().__init__('Encrypted DNS lookup failed (rcode='+str(rcode)+')')

def _physical_alias_hint(host):
 # A bounded alias hint only. Address answers still require encrypted DNS,
 # public IP validation and TLS verification against the ORIGINAL source host.
 import dns.message,dns.flags
 q=dns.message.make_query(host,'CNAME')
 with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
  bind_physical(sock);sock.settimeout(2);sock.connect((physical_dns_server(),53));sock.send(q.to_wire());r=dns.message.from_wire(sock.recv(65535))
 if not q.is_response(r) or r.rcode()!=0 or r.flags&dns.flags.TC:raise OSError('Invalid physical alias reply')
 rows=[]
 for a in r.answer:
  if a.rdtype==5 and str(a.name).rstrip('.').lower()==host.lower():
   rows.extend({'name':host,'type':5,'data':str(x.target),'TTL':a.ttl} for x in a)
 if not rows:raise OSError('No physical alias hint; original DNS failure retained')
 return rows

def _physical_doh_query(host,kind):
 """Fixed TLS-authenticated resolver; bootstrap never uses ambient DNS/proxy."""
 import http.client,json,ssl
 from urllib.parse import urlencode
 from .egress_proxy import safe_destination
 host,_=safe_destination(host,443)
 context=ssl.create_default_context();last=None
 for address in ('223.5.5.5','223.6.6.6'):
  connection=http.client.HTTPSConnection('dns.alidns.com',timeout=3,context=context)
  sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM);sock.settimeout(3)
  try:
   bind_physical(sock);sock.connect((address,443))
   connection.sock=context.wrap_socket(sock,server_hostname='dns.alidns.com')
   connection.request('GET','/resolve?'+urlencode({'name':host,'type':kind}),headers={'Accept':'application/dns-json','Connection':'close'})
   response=connection.getresponse();raw=response.read(65537)
   if response.status!=200 or len(raw)>65536:raise OSError('Encrypted DNS response unavailable or oversized')
   result=json.loads(raw)
   if result.get('Status')!=0:raise ResolverFailure(result.get('Status'))
   if result.get('TC'):raise OSError('Truncated encrypted DNS response')
   questions=result.get('Question')
   expected=5 if kind=='CNAME' else 1
   if not isinstance(questions,dict) or questions.get('name','').rstrip('.').lower()!=host.lower() or questions.get('type')!=expected:
    raise ValueError('Encrypted DNS question mismatch')
   answers=result.get('Answer',[])
   if not isinstance(answers,list) or len(answers)>64:raise ValueError('Invalid encrypted DNS answer set')
   return answers
  except (OSError,http.client.HTTPException) as exc:last=exc
  finally:
   connection.close();sock.close()
 if isinstance(last,ResolverFailure):raise last
 raise OSError('Physical encrypted DNS is unreachable') from last

def _encrypted_addresses(host,port):
 from .egress_proxy import public_ip,safe_destination
 key=(physical_interface(),host,port);cached=_ENCRYPTED_CACHE.get(key)
 if cached and cached[0]>time.monotonic():return cached[1]
 current=host.rstrip('.').lower();seen=set();ttls=[60]
 # Resolve the declared alias chain explicitly; never change the HTTPS Host/SNI.
 for _ in range(5):
  if current in seen:raise ValueError('Encrypted DNS alias loop')
  seen.add(current);safe_destination(current,port)
  try:answers=_physical_doh_query(current,'CNAME')
  except ResolverFailure as exc:
   if exc.rcode!=2:raise
   try:answers=_physical_alias_hint(current)
   except OSError:answers=[]  # CNAME SERVFAIL does not prove that an A lookup fails.
  aliases=[r for r in answers if r.get('type')==5 and r.get('name','').rstrip('.').lower()==current]
  targets={r.get('data','').rstrip('.').lower() for r in aliases}
  if len(targets)>1:raise ValueError('Ambiguous encrypted DNS alias')
  if not targets:break
  ttls.extend(r.get('TTL',0) for r in aliases);current=targets.pop()
 else:raise ValueError('Encrypted DNS alias chain exceeded limit')
 answers=_physical_doh_query(current,'A');allowed={current}
 # Recursive A answers may include another complete CNAME chain.
 for _ in range(5):
  rows=[r for r in answers if r.get('type')==5 and r.get('name','').rstrip('.').lower()==current]
  targets={r.get('data','').rstrip('.').lower() for r in rows}
  if len(targets)>1:raise ValueError('Ambiguous encrypted DNS alias')
  if not targets:break
  target=targets.pop();safe_destination(target,port)
  if target in allowed or target in seen:raise ValueError('Encrypted DNS alias loop')
  allowed.add(target);current=target;ttls.extend(r.get('TTL',0) for r in rows)
 else:raise ValueError('Encrypted DNS alias chain exceeded limit')
 records=[]
 for r in answers:
  if r.get('type')!=1:continue
  ip=r.get('data','')
  if not public_ip(ip) or ipaddress.ip_address(ip).version!=4:raise ValueError('Encrypted DNS returned non-public address')
  if r.get('name','').rstrip('.').lower()!=current:continue
  records.append((socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',(ip,port)));ttls.append(r.get('TTL',0))
 if not records:raise OSError('Encrypted DNS returned no public IPv4 addresses')
 records=list(dict.fromkeys(records));ttl=min(60,max(0,min(float(x) for x in ttls)))
 if len(_ENCRYPTED_CACHE)>=256:_ENCRYPTED_CACHE.clear()
 _ENCRYPTED_CACHE[key]=(time.monotonic()+ttl,records)
 return records
