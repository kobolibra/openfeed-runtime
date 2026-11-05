"""Public-only forward proxy for the Docker-isolated browser network.

TLS CONNECT is passed through without decryption; DNS is resolved and checked
at the point of socket connection (IP pinned), excluding localhost, RFC1918,
link-local and metadata endpoints. This proxy is not exposed to the host.
"""
from __future__ import annotations
import asyncio
import ipaddress
import os
import socket
import re
import time
from urllib.parse import urlsplit

MAX_HEADERS=16_384
MAX_TRANSFER=20_000_000
MAX_SECONDS=32
HEADER_NAME=re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")
FORBIDDEN_FORWARD={b"host",b"proxy-authorization",b"proxy-authenticate",b"proxy-connection",b"connection",b"keep-alive",b"transfer-encoding",b"te",b"trailer",b"upgrade",b"expect",b"content-length"}

def safe_forward_headers(initial: bytes) -> list[bytes]:
    """Only ordinary single-line headers: block request smuggling and control headers."""
    lines=initial.split(b"\r\n")
    if len(initial)>MAX_HEADERS or len(lines)>100:
        raise ValueError("Oversized proxy headers")
    forwarded=[]
    for raw in lines[1:]:
        if not raw:
            continue
        if raw[:1] in (b" ",b"\t") or b":" not in raw:
            raise ValueError("Malformed or folded header")
        name,value=raw.split(b":",1)
        if not HEADER_NAME.fullmatch(name) or any(ch<32 and ch!=9 or ch==127 for ch in value):
            raise ValueError("Invalid HTTP header")
        if name.lower() in FORBIDDEN_FORWARD:
            continue
        forwarded.append(name+b":"+value)
    return forwarded


def validate_http_target(target: str) -> tuple[str, int, str]:
    """Validate an absolute-form proxy target before DNS or socket access.

    Never forward URL credentials, fragments, whitespace, percent-encoded CR/LF,
    or ambiguous netloc syntax to a backend HTTP server.
    """
    if not target.isascii() or any(ord(c) <= 32 or ord(c) == 127 for c in target):
        raise ValueError('Unsafe URL character')
    try:
        parts = urlsplit(target)
        if parts.scheme != 'http' or not parts.hostname or parts.username is not None or parts.password is not None:
            raise ValueError('Invalid public HTTP URL')
        if parts.fragment or '#' in target or '\\' in target:
            raise ValueError('Ambiguous proxy URL')
        port = parts.port or 80
        hostname, port = safe_destination(parts.hostname, port)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('Invalid proxy target URL') from exc
    path = parts.path or '/'
    if parts.query:
        path += '?' + parts.query
    if re.search(r'(?i)%0[ad]|%7f|%00', path):
        raise ValueError('Encoded control character in target')
    # Delimiters and query characters must be represented as origin-form bytes.
    if any(ord(c) < 33 or ord(c) == 127 for c in path):
        raise ValueError('Unsafe origin-form path')
    return hostname, port, path


def public_ip(address: str) -> bool:
    try:
        ip=ipaddress.ip_address(address)
        return ip.is_global and not (isinstance(ip,ipaddress.IPv6Address) and ip.ipv4_mapped is not None)
    except ValueError:
        return False


def safe_destination(host: str, port: int):
    if not host or port not in (80,443) or len(host)>253 or any(c in host for c in '\r\n\x00@/\\'):
        raise ValueError('Invalid proxy target')
    value=host.rstrip('.').lower()
    if value in ('localhost','localhost.localdomain') or value.endswith(('.local','.internal','.localhost')):
        raise ValueError('Private target hostname')
    if '%' in value:
        raise ValueError('Scoped addresses are not supported')
    try:
        address=ipaddress.ip_address(value.strip('[]'))
    except ValueError:
        address=None
    if address and not public_ip(str(address)):
        raise ValueError('Non-public proxy target')
    # Strict ASCII DNS form; avoid numeric/legacy host ambiguities and IDN.
    if not address:
        import re
        if not re.fullmatch(r'(?=.{1,253}$)[a-z0-9-]+(?:\.[a-z0-9-]+)*',value):
            raise ValueError('Unsupported destination host')
        # Numeric alternative IPv4 forms must not reach libc parsers.
        if len(value.split('.'))==1 and value.isdigit():
            raise ValueError('Ambiguous numeric hostname')
        try:
            expanded=socket.inet_ntoa(socket.inet_aton(value))
        except (OSError,UnicodeError):
            expanded=None
        if expanded and not public_ip(expanded):
            raise ValueError('Legacy private IP literal')
    return value,port


def secure_dns_addresses(host: str, port: int):
    """Fixed authenticated DNS endpoint; never trust VPN Fake-IP answers."""
    import json
    import urllib.request
    from urllib.parse import urlencode
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    url='https://dns.google/resolve?'+urlencode({'name':host,'type':'A'})
    with opener.open(url,timeout=8) as response:
        if response.status!=200:raise ValueError('Secure DNS request failed')
        raw=response.read(65537)
        if len(raw)>65536:raise ValueError('Secure DNS response too large')
    answer=json.loads(raw)
    if answer.get('Status')!=0:raise ValueError('Secure DNS lookup failed')
    addresses=[]
    for row in answer.get('Answer',[]):
        if row.get('type')!=1:continue
        address=row.get('data','')
        if not public_ip(address) or ipaddress.ip_address(address).version!=4:
            raise ValueError('Secure DNS returned non-public address')
        addresses.append((socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',(address,port)))
    if not addresses:raise ValueError('Secure DNS returned no public addresses')
    return addresses


class DialFailure(OSError):
    def __init__(self,stage,timed_out=False):
        self.stage=stage;self.timed_out=timed_out
        super().__init__('Dedicated egress '+stage+' '+('timeout' if timed_out else 'connection failure'))


async def dial_public(host: str, port: int):
    deadline=asyncio.get_running_loop().time()+10
    host,port=safe_destination(host,port)
    upstream=os.getenv('OPENFEED_PROXY_UPSTREAM','')
    if upstream:
        if upstream!='http://host.lima.internal:8900':raise ValueError('Unknown trusted proxy hop')
        reader,writer=await asyncio.wait_for(asyncio.open_connection('192.168.5.2',8900),5)
        try:
            writer.write(f'CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n'.encode('ascii'));await writer.drain()
            reply=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),12)
            if len(reply)>MAX_HEADERS or not reply.startswith(b'HTTP/1.1 200 '):raise OSError('Trusted physical proxy could not connect')
            return reader,writer
        except BaseException:writer.close();raise
    mode=os.getenv('OPENFEED_DNS_MODE','system')
    direct=bool(os.getenv('OPENFEED_DIRECT_INTERFACE'))
    try:literal=ipaddress.ip_address(host)
    except ValueError:literal=None
    if literal:
        family=socket.AF_INET if literal.version==4 else socket.AF_INET6
        records=[(family,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',(host,port))]
    elif direct:
        from .physical_network import physical_dns_addresses
        try:records=await asyncio.wait_for(asyncio.to_thread(physical_dns_addresses,host,port),8)
        except (OSError,TimeoutError) as exc:raise DialFailure('dns',isinstance(exc,TimeoutError)) from exc
    elif mode=='doh':
        records=await asyncio.to_thread(secure_dns_addresses,host,port)
    elif mode in ('system','auto'):
        try:
            records=await asyncio.get_running_loop().getaddrinfo(host,port,type=socket.SOCK_STREAM)
            if not records or any(not public_ip(row[4][0]) for row in records):
                raise ValueError('DNS returned non-public address')
        except (OSError,ValueError):
            if mode!='auto':raise
            records=await asyncio.to_thread(secure_dns_addresses,host,port)
    else:raise ValueError('Unknown OPENFEED_DNS_MODE')
    if not records or any(not public_ip(row[4][0]) for row in records):
        raise ValueError('DNS returned non-public address')
    return await connect_addresses(records,direct,deadline)


async def connect_addresses(records,direct,deadline):
    # All addresses were validated above. Share the remaining caller budget;
    # do not let the first black-holed address consume every fallback's time.
    last=None;loop=asyncio.get_running_loop()
    for index,(family,stype,proto,_,sockaddr) in enumerate(records):
        remaining=deadline-loop.time()
        if remaining<=0:raise DialFailure('tcp',True)
        budget=remaining/(len(records)-index)
        sock=socket.socket(family,stype,proto);sock.setblocking(False)
        try:
            if direct:
                from .physical_network import bind_physical
                bind_physical(sock)
            await asyncio.wait_for(loop.sock_connect(sock,sockaddr),budget)
            return await asyncio.open_connection(sock=sock)
        except (OSError,TimeoutError) as exc:
            sock.close();last=exc
        except BaseException:
            sock.close();raise
    raise DialFailure('tcp',isinstance(last,TimeoutError)) from last


async def pump(reader,writer):
    amount=0
    try:
        while True:
            data=await asyncio.wait_for(reader.read(65536),MAX_SECONDS)
            if not data: break
            amount+=len(data)
            if amount>MAX_TRANSFER:break
            writer.write(data)
            await asyncio.wait_for(writer.drain(),MAX_SECONDS)
    except (OSError,asyncio.TimeoutError,ConnectionError):
        pass
    finally:
        writer.close()


def validate_request_line(request_line: bytes) -> tuple[str, str, str]:
    """Strictly parse the HTTP proxy request line; reject ambiguous framing."""
    if len(request_line)>8192 or not re.fullmatch(rb'(CONNECT|GET|HEAD) [^\x00-\x20\x7f]+ HTTP/1\.[01]', request_line):
        raise ValueError('Invalid proxy request line')
    return tuple(request_line.decode('ascii', 'strict').split(' ', 2))


async def handle(client_reader,client_writer):
    remote_w=None
    established=False
    host="unparsed"
    started=time.monotonic()
    try:
        initial=await asyncio.wait_for(client_reader.readuntil(b'\r\n\r\n'),8)
        if len(initial)>MAX_HEADERS: raise ValueError('Oversized proxy request')
        method,target,version=validate_request_line(initial.split(b'\r\n',1)[0])
        # CONNECT headers are untrusted too; validate their syntax even though
        # nothing from them is forwarded into the TLS tunnel.
        safe_forward_headers(initial)
        if version not in ('HTTP/1.1','HTTP/1.0'):
            raise ValueError('Invalid proxy HTTP version')
        if method=='CONNECT':
            if target.count(':')!=1: raise ValueError('Unsupported CONNECT target')
            host,raw_port=target.rsplit(':',1)
            if not raw_port.isdigit(): raise ValueError('Invalid port')
            port=int(raw_port)
            if port!=443 and not (port==80 and os.getenv('OPENFEED_PROXY_ALLOW_HTTP_TUNNEL')=='1'): raise ValueError('Only HTTPS CONNECT port is allowed')
            remote_r,remote_w=await asyncio.wait_for(dial_public(host,port),10 if os.getenv('OPENFEED_DIRECT_INTERFACE') else 14)
            client_writer.write(b'HTTP/1.1 200 Connection established\r\n\r\n')
            established=True
            await client_writer.drain()
        elif method in ('GET','HEAD'):
            host,port,path=validate_http_target(target)
            # Reject bad headers before opening an upstream socket.
            kept=safe_forward_headers(initial)
            remote_r,remote_w=await asyncio.wait_for(dial_public(host,port),10 if os.getenv('OPENFEED_DIRECT_INTERFACE') else 14)
            request=(f'{method} {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n'.encode('ascii') +
                     (b'\r\n'.join(kept)+b'\r\n' if kept else b'')+b'\r\n')
            remote_w.write(request);await remote_w.drain()
        else: raise ValueError('Disallowed HTTP method')
        if method=='CONNECT':
            await asyncio.wait_for(asyncio.gather(pump(remote_r,client_writer),pump(client_reader,remote_w)),MAX_SECONDS+8)
        else:
            # Ordinary GET/HEAD requests have no request body. Never forward
            # bytes after the header terminator as an upstream second request.
            await asyncio.wait_for(pump(remote_r,client_writer),MAX_SECONDS+8)
    except (ValueError,OSError,asyncio.TimeoutError,UnicodeError,asyncio.IncompleteReadError,asyncio.LimitOverrunError) as exc:
        if os.getenv('OPENFEED_PROXY_DIAGNOSTICS')=='1':print('Egress failure:', 'host='+host, 'phase='+('tunnel' if established else getattr(exc,'stage','connect')), 'elapsed='+str(round(time.monotonic()-started,3)), type(exc).__name__,str(exc)[:180],flush=True)
        if established:
            return  # Never inject an HTTP error into an established TLS tunnel.
        try:
            code=b'504 Gateway Timeout' if (isinstance(exc,asyncio.TimeoutError) or getattr(exc,'timed_out',False)) else (b'502 Bad Gateway' if isinstance(exc,OSError) else b'403 Forbidden')
            stage=getattr(exc,'stage','unknown')
            diagnostic=(b'X-OpenFeed-Stage: '+stage.encode()+b'\r\n') if stage in ('dns','tcp') else b''
            client_writer.write(b'HTTP/1.1 '+code+b'\r\n'+diagnostic+b'Connection: close\r\nContent-Length: 0\r\n\r\n')
            await client_writer.drain()
        except OSError:pass
    finally:
        if remote_w is not None:
            remote_w.close()
        client_writer.close()
        try:await client_writer.wait_closed()
        except (OSError,ConnectionError):pass


async def main():
    bind=os.getenv('OPENFEED_PROXY_BIND','0.0.0.0')
    if os.getenv('OPENFEED_DIRECT_INTERFACE') and bind!='127.0.0.1':raise ValueError('Host physical proxy must be loopback-only')
    server=await asyncio.start_server(handle,bind,int(os.getenv('OPENFEED_PROXY_PORT','8899')),limit=MAX_HEADERS)
    async with server:await server.serve_forever()

if __name__=='__main__':asyncio.run(main())
