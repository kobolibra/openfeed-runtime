"""Conservative recognition of access pages; never attempts to solve them.

Only an interstitial page - never a content page - is rejected. Every signature
requires corroborating evidence on top of the shared guards below (short page,
tiny visible text after stripping scripts/styles, and no real article body).
Heading-less WAF fingerprints are accepted only because the fingerprints
themselves (Cloudflare Ray blocks, Akamai edgesuite reference pages, Aliyun
``aliyun_waf_aa`` interstitials, ``vercel.link/security-checkpoint`` shells)
never appear inside genuine article pages. Vendor mentions or login links
alone are not evidence.

Detected families (all verified against production captures on 2026-11-15,
see tests/test_access_barriers.py):
- challenge: Cloudflare "Just a moment" / "Attention Required" interstitials;
  Vercel Security Checkpoint shell.
- captcha:   classic verify-human pages with a real captcha widget.
- login_wall: short sign-in pages with a password form.
- access_denied: Akamai Edgesuite "Access Denied / you don't have permission
  to access" pages and CloudFront "The request could not be satisfied" pages.
- waf:        heading-less WAF interstitials (Aliyun WAF meta fingerprint,
  Akamai/edgescore "The requested URL was rejected").

Intentionally NOT classified as barriers (they stay extraction failures):
plain 5xx/nginx error pages (HTTP-status layer owns those), Google Scholar
"unusual traffic" pages (no reliable non-heading corroboration), empty-result
content pages such as "no results were found" banners (they are content, not
barriers), and pages with more than ~2000 chars of visible text or a real
article body - those are always treated as content.
"""
from __future__ import annotations
from bs4 import BeautifulSoup

class AccessBarrierError(ValueError):
    def __init__(self,kind: str):
        self.kind=kind
        super().__init__(f'Source access barrier: {kind}; existing RSS preserved')


def reject_access_page(content: str) -> None:
    if '<' not in content[:200]:
        return
    # Avoid reparsing large article/list pages for a short interstitial check.
    if len(content)>300_000:
        return
    doc=BeautifulSoup(content,'lxml')
    for el in doc.select('script, style, template, [hidden], [aria-hidden="true"]'):
        el.decompose()
    visible=' '.join(doc.stripped_strings)
    if len(visible)>2000:
        return
    # A real article can mention access errors and contain a login/captcha box.
    if any(len(' '.join(n.stripped_strings))>=250 for n in doc.select('article')):
        return
    headings={' '.join(n.stripped_strings).strip().casefold().rstrip('.!… ') for n in doc.select('title,h1,h2,h3')}
    raw=content.casefold()
    challenge=headings & {'just a moment','checking your browser','checking your browser before accessing this site','please wait while we verify your browser','正在验证您的浏览器'}
    if challenge and any(s in raw for s in ('_cf_chl_opt','/cdn-cgi/challenge-platform/','cf-browser-verification')):
        raise AccessBarrierError('challenge')
    captcha=headings & {'verify you are human','please verify you are a human','人机验证','安全验证'}
    if captcha and doc.select_one('.g-recaptcha, .h-captcha, .cf-turnstile, #px-captcha, iframe[src*="captcha"]'):
        raise AccessBarrierError('captcha')
    login=headings & {'sign in to continue','log in to continue','login to continue','请先登录','登录后查看'}
    if login and doc.select_one('form input[type="password"]'):
        raise AccessBarrierError('login_wall')
    # Cloudflare "Attention Required" interstitial (managed challenge served
    # with the ray id block and /cdn-cgi challenge assets).
    cf_attention=headings & {'attention required! | cloudflare','attention required'}
    if cf_attention and ('ray id' in raw or 'cloudflare' in raw):
        raise AccessBarrierError('challenge')
    # Akamai Edgesuite denial (S&P Global, McKinsey, ...): heading plus the
    # exact Apache-style refusal sentence; long pages bail out above.
    if headings & {'access denied'} and "you don't have permission to access" in raw:
        raise AccessBarrierError('access_denied')
    # CloudFront block page (observed as an HTTP 200 body via upstream
    # proxies): heading plus the reference sentence; requires the heading so a
    # real article discussing this error string is never rejected.
    if headings & {'error: the request could not be satisfied'} and 'the request could not be satisfied' in raw:
        raise AccessBarrierError('access_denied')
    # Vercel Security Checkpoint shell (heading and the checkpoint redirect).
    if (headings & {'vercel security checkpoint'} or 'vercel.link/security-checkpoint' in raw):
        raise AccessBarrierError('challenge')
    # Aliyun WAF interstitial: no stable heading; the meta fingerprint plus
    # WAF-specific assets never appear on content pages.
    if ('aliyun_waf_aa' in raw or '--aliyun-zoom-ratio' in raw or 'aliyun_waf' in raw) and raw.count('aliyun') >= 5:
        raise AccessBarrierError('waf')
    # Akamai/OpenEdge plain rejection page (~110 B body, no headings at all).
    if 'the requested url was rejected' in raw and len(content) < 5000:
        raise AccessBarrierError('waf')
