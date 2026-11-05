"""Conservative recognition of access pages; never attempts to solve them.

Only a short page with both an explicit access heading and corroborating
structure is rejected. Vendor scripts or login links alone are not evidence.
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
