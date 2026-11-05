"""Bounded public-Internet fetch with DNS-validated socket addressing.

We deliberately ask aiohttp's resolver to supply the *actual dial addresses*.
Unlike a preliminary DNS-only check, the connector dials the vetted returned
IP, preventing a validation/connect DNS rebinding gap. Redirects are handled
manually and revalidated; proxies/environment variables are never trusted.

For hosted multi-tenant deployments this is defense-in-depth, not a replacement
for a separate egress-deny firewall for RFC1918/link-local/cloud metadata.
"""
from __future__ import annotations
import asyncio
import ipaddress
import os
import socket
import ssl
import errno
import re
import json
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from charset_normalizer import from_bytes
from urllib.parse import urlsplit, urljoin
from aiohttp import ClientSession, ClientTimeout, TCPConnector, ClientError
from aiohttp.abc import AbstractResolver

MAX_BYTES = 2_500_000
REDIRECTS = 3
USER_AGENT = 'OpenFeedStudio/0.4 (+private self-hosted RSS creator)'

class UnsafeURL(ValueError):
    pass

class UpstreamHTTPError(ValueError):
    """Structured status for diagnostics; never conflates robots and content."""
    def __init__(self,status,url,retry_after=''):
        self.status=int(status)
        self.url=url
        self.retry_after=str(retry_after)[:128]
        super().__init__(f'Upstream HTTP {self.status}')


def retry_after_seconds(value: str, now=None) -> int:
    """Bound both delta-seconds and HTTP-date without inventing immediate retries."""
    value=str(value or '').strip()
    try:
        if value.isdigit():seconds=int(value)
        else:
            stamp=parsedate_to_datetime(value)
            if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
            seconds=int((stamp-(now or datetime.now(timezone.utc))).total_seconds())
        return min(604800,max(0,seconds))
    except (ValueError,TypeError,OverflowError):return 0


def _public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.split('%', 1)[0])
        return ip.is_global and ip.ipv4_mapped is None if isinstance(ip, ipaddress.IPv6Address) else ip.is_global
    except ValueError:
        return False


def check_url(url: str, *, resolve: bool = True) -> str:
    if not isinstance(url, str) or not 0 < len(url) <= 2048:
        raise UnsafeURL('Invalid URL length')
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError as e:
        raise UnsafeURL('Malformed URL') from e
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or '\\' in p.netloc:
        raise UnsafeURL('Only public http(s) URLs without credentials are permitted')
    if port and port not in (80, 443):
        raise UnsafeURL('Only standard 80/443 destination ports are permitted')
    host = p.hostname.lower().rstrip('.')
    if not host or host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')):
        raise UnsafeURL('Private hostnames are blocked')
    try:
        ip = ipaddress.ip_address(host.split('%', 1)[0])
    except ValueError:
        ip = None
    if ip is not None and not _public_ip(host):
        raise UnsafeURL('Non-public address is blocked')
    # Legacy IPv4 spellings such as 127.1 and 0x7f000001 may be
    # interpreted by socket libraries even though ipaddress rejects them.
    if ip is None:
        try:
            expanded=socket.inet_ntoa(socket.inet_aton(host))
        except (OSError, UnicodeError):
            expanded=None
        if expanded and not _public_ip(expanded):
            raise UnsafeURL('Non-public numeric host is blocked')
    if resolve:
        try:
            records = socket.getaddrinfo(host, port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
        except OSError as e:
            raise UnsafeURL('Hostname could not be resolved') from e
        if not records or any(not _public_ip(info[4][0]) for info in records):
            raise UnsafeURL('Hostname must resolve only to public IP addresses')
    return url


def detect_charset(body: bytes, declared: str | None = None) -> str:
    import codecs
    # A Unicode signature describes actual bytes and takes priority over a
    # stale HTTP/meta declaration. Check UTF-32 before the UTF-16 prefix.
    for signature,encoding in ((codecs.BOM_UTF32_LE,'utf-32'),(codecs.BOM_UTF32_BE,'utf-32'),
                               (codecs.BOM_UTF8,'utf-8-sig'),(codecs.BOM_UTF16_LE,'utf-16'),
                               (codecs.BOM_UTF16_BE,'utf-16')):
        if body.startswith(signature):return encoding
    def text_codec(label):
        if not isinstance(label,str) or not re.fullmatch(r'[A-Za-z0-9._-]{1,50}',label):return None
        try:
            info=codecs.lookup(label)
            b'encoding probe'.decode(info.name,errors='ignore')  # Reject non-text codecs.
            return info.name
        except (LookupError,ValueError,TypeError):return None
    encoding=text_codec(declared)
    if encoding:return encoding
    match=re.search(rb'<meta[^>]+charset\s*=\s*[\"\']?([A-Za-z0-9._-]+)',body[:8192],re.I)
    if match:
        encoding=text_codec(match.group(1).decode('ascii',errors='ignore'))
        if encoding:return encoding
    try:
        body.decode('utf-8')
        return 'utf-8'
    except UnicodeDecodeError:
        best=from_bytes(body[:100000]).best()
        return text_codec(best.encoding) if best and text_codec(best.encoding) else 'utf-8'


class PublicResolver(AbstractResolver):
    """Resolve once per connection; aiohttp dials only these validated IPs."""
    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET):
        check_url('https://' + ('[' + host + ']' if ':' in host else host), resolve=False)
        mode = os.getenv('OPENFEED_DNS_MODE', 'system')
        if mode == 'doh':
            return await self._doh(host, port, family)
        if mode not in ('system','auto'):
            raise UnsafeURL('Unknown OPENFEED_DNS_MODE')
        try:
            info = await asyncio.get_running_loop().getaddrinfo(host, port, family=family, type=socket.SOCK_STREAM)
            if not info or any(not _public_ip(row[4][0]) for row in info):
                raise UnsafeURL('DNS returned a non-public IP address')
        except (OSError,UnsafeURL):
            if mode=='auto':return await self._doh(host,port,family)
            raise
        return [{'hostname': host, 'host': row[4][0], 'port': row[4][1],
                 'family': row[0], 'proto': row[2], 'flags': row[3]} for row in info]

    async def _doh(self, host, port, family):
        # Fixed TLS-authenticated resolver endpoint only. Its bootstrap lookup
        # uses the system network (including a local TUN); target lookups never
        # use Fake-IP answers. The connector still dials vetted IPs, retaining
        # the validation/connect binding. No proxy or arbitrary endpoint input.
        kinds = [28] if family == socket.AF_INET6 else [1]
        if family == socket.AF_UNSPEC:
            kinds.append(28)
        records = []
        async with ClientSession(timeout=ClientTimeout(total=8), trust_env=False) as client:
            for kind in kinds:
                async with client.get('https://dns.google/resolve',
                                      params={'name': host, 'type': str(kind)},
                                      allow_redirects=False) as response:
                    if response.status != 200:
                        raise UnsafeURL('Secure DNS request failed')
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(16384):
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise UnsafeURL('Secure DNS response too large')
                    answer = json.loads(body)
                    if answer.get('Status') != 0:
                        raise UnsafeURL('Secure DNS lookup failed')
                    for row in answer.get('Answer', []):
                        if row.get('type') not in (1, 28):
                            continue
                        address = row.get('data', '')
                        if not _public_ip(address):
                            raise UnsafeURL('Secure DNS returned a non-public IP address')
                        ip = ipaddress.ip_address(address)
                        if (row['type'] == 1) != (ip.version == 4):
                            raise UnsafeURL('Secure DNS address type mismatch')
                        records.append({'hostname': host, 'host': address, 'port': port,
                                        'family': socket.AF_INET if ip.version == 4 else socket.AF_INET6,
                                        'proto': socket.IPPROTO_TCP, 'flags': 0})
        if not records:
            raise UnsafeURL('Secure DNS returned no public addresses')
        return records

    async def close(self):
        pass


class ConfiguredProxyResolver(PublicResolver):
    """The sole private socket exception is the fixed operator-configured hop."""
    async def resolve(self,host,port=0,family=socket.AF_INET):
        if host=='host.lima.internal' and port==8900:
            return [{'hostname':host,'host':'192.168.5.2','port':8900,'family':socket.AF_INET,'proto':socket.IPPROTO_TCP,'flags':0}]
        return await super().resolve(host,port,family)


def configured_egress_proxy():
    value=os.getenv('OPENFEED_EGRESS_PROXY','')
    if value and value!='http://host.lima.internal:8900':raise UnsafeURL('Unsupported configured egress proxy')
    return value


def connection_failure_category(error: BaseException) -> str:
    """Classify transport failures without exposing URL queries or credentials."""
    pending = [error]
    seen = set()
    causes = []
    while pending and len(seen) < 12:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        causes.append(current)
        for child in (getattr(current, 'os_error', None), current.__cause__, current.__context__):
            if isinstance(child, BaseException):
                pending.append(child)
    proxy_errors=[e for e in causes if type(e).__name__=='ClientHttpProxyError']
    if proxy_errors:
        return {504:'egress_timeout',502:'egress_connection',403:'egress_policy',407:'egress_auth'}.get(proxy_errors[0].status,'egress_error')
    if any(isinstance(e, (ssl.SSLCertVerificationError, ssl.CertificateError)) or
           type(e).__name__ == 'ClientConnectorCertificateError' for e in causes):
        return 'tls_certificate'
    if any(isinstance(e, socket.gaierror) for e in causes):
        return 'dns_resolution'
    if any(isinstance(e, (asyncio.TimeoutError, TimeoutError)) for e in causes):
        return 'timeout'
    if any(isinstance(e, ssl.SSLError) or type(e).__name__ == 'ClientConnectorSSLError' for e in causes):
        return 'tls_handshake'
    codes = {getattr(e, 'errno', None) for e in causes}
    if errno.ECONNRESET in codes or any(isinstance(e, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)) or
                                            type(e).__name__ == 'ServerDisconnectedError' for e in causes):
        return 'connection_closed'
    if errno.ECONNREFUSED in codes:
        return 'connection_refused'
    if codes.intersection({errno.ENETUNREACH, errno.EHOSTUNREACH}):
        return 'network_unreachable'
    return 'transport_error'


class UpstreamConnectionError(ValueError):
    def __init__(self, error: BaseException):
        self.category = connection_failure_category(error)
        stage=(getattr(error,'headers',None) or {}).get('X-OpenFeed-Stage','')
        detail=('; stage='+stage) if stage in ('dns','tcp') else ''
        super().__init__(f'Upstream connection failed: {self.category} ({type(error).__name__})'+detail)


def public_request_options(recipe: dict) -> dict:
    """Use identical public API requests for preview, refresh and diagnosis."""
    options={}
    if recipe.get('request_method')=='POST':
        options['method']='POST'
        if recipe.get('request_json') is not None:options['json_data']=recipe['request_json']
        else:options['data']=recipe.get('request_data') or {}
    if recipe.get('public_api_key'):options['public_api_key']=recipe['public_api_key']
    return options


def validate_json_request(value):
    """Bound a public JSON request body before networking or serialization."""
    if not isinstance(value,dict) or len(value)>20:raise ValueError('JSON request must be a bounded object')
    nodes=0
    def visit(item,depth=0):
        nonlocal nodes
        nodes+=1
        if depth>4 or nodes>500:raise ValueError('JSON request nesting or item limit exceeded')
        if isinstance(item,dict):
            if len(item)>50 or any(not isinstance(k,str) or not k or len(k)>80 for k in item):raise ValueError('Invalid JSON request keys')
            for child in item.values():visit(child,depth+1)
        elif isinstance(item,list):
            if len(item)>50:raise ValueError('JSON request array too large')
            for child in item:visit(child,depth+1)
        elif item is None or isinstance(item,(bool,int,float)):
            if isinstance(item,float) and not __import__('math').isfinite(item):raise ValueError('Non-finite JSON number')
        elif isinstance(item,str):
            if len(item)>2000:raise ValueError('JSON request string too large')
        else:raise ValueError('Unsupported JSON request value')
    visit(value)
    try:raw=json.dumps(value,allow_nan=False,ensure_ascii=False).encode('utf-8')
    except (ValueError,OverflowError,UnicodeError) as e:raise ValueError('Invalid JSON request body') from e
    if len(raw)>16384:raise ValueError('JSON request body too large')
    return value


async def _fetch_once(url: str, *, method: str = 'GET', data: dict | None = None, json_data: dict | None = None, public_api_key: str = '') -> tuple[str, bytes, str]:
    if json_data is not None:
        validate_json_request(json_data)
        if method!='POST' or data is not None:raise ValueError('JSON body requires POST without form data')
    if not isinstance(public_api_key,str) or len(public_api_key)>500 or any(ord(c)<33 or ord(c)>126 for c in public_api_key):
        raise ValueError('Invalid public API key')
    if public_api_key and urlsplit(url).scheme!='https':
        raise ValueError('Public API key requires HTTPS')
    if method not in ('GET', 'POST') or (data is not None and (
            not isinstance(data, dict) or len(data) > 20 or
            any(not isinstance(k, str) or not isinstance(v, str) or len(k) > 80 or len(v) > 500 for k, v in data.items()))):
        raise ValueError('Invalid bounded public request')
    timeout = min(60., max(3., float(os.getenv('OPENFEED_FETCH_TIMEOUT', '15'))))
    byte_limit = min(8_000_000, max(100_000, int(os.getenv('OPENFEED_MAX_FETCH_BYTES', str(MAX_BYTES)))))
    headers = {'User-Agent': USER_AGENT,
               'Accept': 'text/html,application/rss+xml,application/atom+xml,application/xml,text/xml,application/json,application/feed+json;q=0.8,*/*;q=0.3'}
    proxy=configured_egress_proxy()
    connector = TCPConnector(resolver=ConfiguredProxyResolver() if proxy else PublicResolver(), use_dns_cache=False, limit=4, ttl_dns_cache=0)
    current = url
    async with ClientSession(connector=connector, timeout=ClientTimeout(total=timeout), headers=headers,
                             trust_env=False, raise_for_status=False, max_line_size=32768, max_field_size=32768) as client:
        for _ in range(REDIRECTS + 1):
            check_url(current, resolve=False)
            try:
                # Public frontend key is sent only to its original HTTPS origin.
                same_origin = (urlsplit(current).scheme,urlsplit(current).hostname,urlsplit(current).port or 443)==(urlsplit(url).scheme,urlsplit(url).hostname,urlsplit(url).port or 443)
                options={'allow_redirects':False}
                if proxy:options['proxy']=proxy
                if public_api_key and same_origin:options['headers']={'X-Api-Key':public_api_key}
                request = client.post(current, **({'json':json_data} if json_data is not None else {'data':data}), **options) if method == 'POST' else client.get(current, **options)
                async with request as response:
                    if response.status in (301, 302, 303, 307, 308):
                        target = response.headers.get('Location')
                        if not target:
                            raise ValueError('Redirect without Location')
                        redirected = urljoin(current, target)
                        if method=='POST' and json_data is not None and response.status in (307,308):
                            a,b=urlsplit(current),urlsplit(redirected)
                            if (a.scheme,a.hostname,a.port or 443)!=(b.scheme,b.hostname,b.port or 443):
                                raise UnsafeURL('JSON POST redirect cannot leave original origin')
                        current = redirected
                        if response.status in (301, 302, 303):
                            method, data, json_data = 'GET', None, None
                        continue
                    if response.status >= 400:
                        raise UpstreamHTTPError(response.status,str(response.url),response.headers.get('Retry-After',''))
                    content_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                    permitted = content_type.startswith('text/') or content_type in (
                        'application/xhtml+xml', 'application/xml', 'application/rss+xml',
                        'application/atom+xml', 'application/json', 'application/feed+json',
                        'application/rdf+xml')
                    if content_type and not permitted:
                        raise ValueError(f'Unsupported content type: {content_type}')
                    data = bytearray()
                    async for chunk in response.content.iter_chunked(32768):
                        data.extend(chunk)
                        if len(data) > byte_limit:
                            raise ValueError('Page exceeds maximum fetch size')
                    return str(response.url), bytes(data), detect_charset(bytes(data), response.charset)
            except (ClientError, asyncio.TimeoutError) as e:
                raise UpstreamConnectionError(e) from e
    raise ValueError('Too many redirects')


async def _fetch_with_retry(url: str, *, method: str = 'GET', data: dict | None = None, json_data: dict | None = None, public_api_key: str = '') -> tuple[str, bytes, str]:
    """Retry one transient GET failure; never replay POST or bypass access errors."""
    options=dict(method=method,data=data,json_data=json_data,public_api_key=public_api_key)
    try:
        return await _fetch_once(url,**options)
    except UpstreamConnectionError as exc:
        if method!='GET' or data is not None or json_data is not None or exc.category not in {
            'timeout','dns_resolution','connection_closed','connection_refused',
            'network_unreachable','egress_timeout','egress_connection'}:
            raise
        # Bounded jitter avoids synchronized retries. HTTP rejection, certificate
        # failures, invalid content and extraction failures are never retried here.
        import random
        await asyncio.sleep(random.uniform(1,3))
        return await _fetch_once(url,**options)


async def fetch(url: str, **options) -> tuple[str, bytes, str]:
    # One deadline covers redirects and the immediate retry, not each hop anew.
    budget=min(125.,max(45.,2*float(os.getenv('OPENFEED_FETCH_TIMEOUT','15'))+5))
    try:
        async with asyncio.timeout(budget):
            return await _fetch_with_retry(url,**options)
    except asyncio.TimeoutError as exc:
        raise UpstreamConnectionError(exc) from exc
