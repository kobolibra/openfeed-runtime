"""Source discovery, article extraction, selective HTML preview and RSS rendering."""
from __future__ import annotations
from datetime import datetime, timezone
from email.utils import format_datetime
from hashlib import sha256
from html import escape
from urllib.parse import urljoin, urldefrag, urlsplit, urlunsplit, parse_qsl, urlencode, quote
import json
import re
import regex
from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateparser
from defusedxml import ElementTree as SafeET
from lxml import html as LH


def clean_text(value: object, limit: int = 500) -> str:
    return ' '.join(str(value or '').split())[:limit]


def canonical_link(raw: str, base: str, *, keep_fragment: bool = False) -> str:
    if not isinstance(raw,str) or not raw.strip():return ''
    candidate = urljoin(base, raw.strip())
    if not keep_fragment:
        candidate = urldefrag(candidate)[0]
    p = urlsplit(candidate)
    if p.scheme not in ('http', 'https') or not p.hostname:
        return ''
    # Liepin embeds per-search identifiers in some public job detail links.
    # Remove only the known tracking keys on those paths, so a fresh listing
    # snapshot cannot generate a new RSS GUID for the same posting.
    if p.hostname.lower().rstrip('.') in ('liepin.com','www.liepin.com') and p.path.startswith(('/job/','/lptjob/','/a/')):
        tracking={'d_sfrom','d_ckId','d_curPage','d_pageSize','d_headId','d_posi'}
        pairs=parse_qsl(p.query,keep_blank_values=True)
        kept=[(k,v) for k,v in pairs if k not in tracking]
        if len(kept)!=len(pairs):
            candidate=urlunsplit((p.scheme,p.netloc,p.path,urlencode(kept),''))
    # Woodmac search adds per-request Optimizely tracking IDs to article URLs.
    if p.hostname.lower().rstrip('.') in ('woodmac.com','www.woodmac.com') and p.path.startswith(('/blogs/','/news/','/press-releases/')):
        tracking={'_t_id','_t_uuid','_t_q','_t_tags','_t_hit.id','_t_hit.pos'}
        pairs=parse_qsl(p.query,keep_blank_values=True)
        kept=[(k,v) for k,v in pairs if k not in tracking]
        if len(kept)!=len(pairs):candidate=urlunsplit((p.scheme,p.netloc,p.path,urlencode(kept),''))
    return candidate


def parse_date(value: str) -> str | None:
    if not value:
        return None
    try:
        value=re.sub(r'(\d{4})年(\d{1,2})月(\d{1,2})日?',r'\1-\2-\3',value)
        # Different defaults reveal an omitted year/month/day. A month-only
        # source date must never inherit today's day and look exact in RSS.
        dt = dateparser.parse(value, fuzzy=False, default=datetime(1991, 1, 1))
        other = dateparser.parse(value, fuzzy=False, default=datetime(1992, 2, 2))
        if dt is None or other is None or dt.date() != other.date():
            return None
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        if dt.year < 1990 or dt.year > datetime.now(timezone.utc).year + 2:
            return None
        return dt.isoformat()
    except (ValueError, TypeError, OverflowError):
        return None


def discover(raw_html: str, url: str) -> list[dict]:
    doc = BeautifulSoup(raw_html, 'html.parser')
    out = []
    for el in doc.select('link[rel~=alternate][href]'):
        kind = (el.get('type') or '').lower()
        if kind in ('application/rss+xml', 'application/atom+xml', 'application/feed+json'):
            dest = canonical_link(el['href'], url)
            if dest and dest != url and not any(x['url'] == dest for x in out):
                out.append({'url': dest, 'title': clean_text(el.get('title') or dest), 'type': kind})
    return out[:20]


def _value_css(node: Tag, selector: str, attr_default: str = 'text') -> str:
    if not selector:
        return ''
    if ' ?? ' in selector:
        options=selector.split(' ?? ')
        if len(options)>3:raise ValueError('At most three CSS field fallbacks are allowed')
        for option in options:
            value=_value_css(node,option,attr_default)
            if value:return value
        return ''
    if '::json.' in selector:
        source,path=selector.rsplit('::json.',1)
        css,sep,attribute=source.rpartition('@')
        if not sep or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,79}',attribute) or not path or len(path)>300:
            raise ValueError('Invalid JSON attribute field')
        el=node if css==':scope' else node.select_one(css)
        if el is None or not el.has_attr(attribute):return ''
        raw=el.get(attribute,'')
        if not isinstance(raw,str) or len(raw)>100000:raise ValueError('JSON attribute exceeds size limit')
        try:value=_json_path(json.loads(raw),path)
        except (ValueError,TypeError,RecursionError) as exc:raise ValueError('Invalid JSON attribute') from exc
        return str(value) if isinstance(value,(str,int,float)) and not isinstance(value,bool) else ''
    base, sep, suffix = selector.rpartition('@')
    if sep and (suffix in ('href','src','datetime','title','content','articletitle','articleteaser')):
        selector, attr = base, suffix
    else:
        attr = attr_default
    el = node if selector == ':scope' else node.select_one(selector)
    if not el:
        return ''
    if attr != 'text':
        return str(el.get(attr, '')).strip()
    if el.name == 'time' and el.get('datetime'):
        return str(el['datetime']).strip()
    return el.get_text(' ', strip=True)


def _value_xpath(el, expression: str) -> str:
    if not expression:
        return ''
    res = el.xpath(expression)
    if not isinstance(res, list):
        return str(res)
    if not res:
        return ''
    first = res[0]
    if isinstance(first, (str, float, bool)):
        return str(first)
    return ' '.join(first.itertext()).strip()


def infer_candidates(raw_html: str, limit: int = 8) -> list[dict]:
    """Rank repeated article containers without running remote page scripts.

    This is a heuristic, not a proof that every matched node is an article.
    Results are exposed with match counts so the operator can correct them.
    """
    doc = BeautifulSoup(raw_html[:1_300_000], 'lxml')
    proposals: dict[str, dict] = {}
    selector_cache: dict[str, list] = {}
    for container in doc.select('main, [role="main"], article, section, div, ul, ol')[:1800]:
        children = [n for n in container.find_all(recursive=False) if isinstance(n, Tag)]
        if len(children) < 2:
            continue
        for group_tag in ('article', 'li', 'div', 'section', 'a'):
            group = [c for c in children if c.name == group_tag]
            if not (2 <= len(group) <= 500):
                continue
            eligible = [c for c in group if c.find('a', href=True) and len(c.get_text(' ', strip=True)) >= 20]
            if len(eligible) < 2:
                continue
            common = set(eligible[0].get('class', []))
            for item in eligible[1:12]:
                common.intersection_update(item.get('class', []))
            classes = [c for c in sorted(common) if re.fullmatch(r'[a-zA-Z][\w-]{1,45}', c) and not re.search(r'(active|selected|hover|\d{4,})',c,re.I)]
            # Avoid an ancestor class derived from a randomly-generated build identifier.
            selector = group_tag + ''.join('.'+c for c in classes[:2])
            if container.name == 'main' or container.find_parent('main'):
                selector = 'main ' + selector
            elif container.name == 'article':
                selector = 'article > '+selector
            try:
                if selector not in selector_cache:
                    selector_cache[selector] = doc.select(selector)
                matched = selector_cache[selector]
            except Exception:
                continue
            useful = [x for x in matched if x.find('a', href=True) and len(x.get_text(' ',strip=True))>=20]
            if len(useful) < 2 or len(useful)>500:
                continue
            headings=sum(bool(x.select_one('h1,h2,h3,h4,h5')) for x in useful)
            dates=sum(bool(x.select_one('time,[datetime]')) for x in useful)
            avg=min(350, sum(len(x.get_text(' ',strip=True)) for x in useful[:12])/min(12,len(useful)))
            score= 8*headings/len(useful)+3*dates/len(useful)+min(3,avg/80)+min(3,len(useful)/6)
            if group_tag=='article':score+=6
            if container.name=='main':score+=3
            if classes:score+=2
            if any(x.name in ('nav','header','footer') or x.get('role') in ('navigation','menu') for x in [container,*list(container.parents)[:5]]):score-=22
            if re.search(r'nav|menu|footer|sidebar|breadcrumb|filter',selector,re.I):score-=15
            if score<1:continue
            fields={'title':'h2, h3, h4, h1, a', 'link':'a@href',
                    'date':'time', 'summary':'p'}
            if useful[0].select_one('h2 a, h3 a'):
                fields['title']='h2 a, h3 a'
                fields['link']='a@href'
            obj={'selector':selector,'count':len(useful),'score':round(score,1),
                 'sample_titles':[clean_text((x.select_one('h2,h3,h4,a') or x).get_text(' ',strip=True),120) for x in useful[:3]],
                 'fields':fields}
            previous=proposals.get(selector)
            if previous is None or obj['score']>previous['score']:
                proposals[selector]=obj
    return sorted(proposals.values(),key=lambda x:(-x['score'], -x['count'], x['selector']))[:limit]


def infer_selector(doc: BeautifulSoup) -> str:
    for selector in ['main article', 'article', '.article-item', '.post-item', '.news-item', '.research-card', '.views-row', '.post', 'main li', '.listing-item']:
        try:
            nodes = doc.select(selector)
        except Exception:
            continue
        valid = [n for n in nodes if n.find('a', href=True) and len(n.get_text(' ', strip=True)) > 18]
        if 2 <= len(valid) <= 150:
            return selector
    # Generic DOMs often use bespoke card class names, not <article> tags.
    # Rank visible sibling-card patterns before forcing manual selectors.
    suggestions=infer_candidates(str(doc),limit=1)
    if suggestions:
        return suggestions[0]['selector']
    raise ValueError('Could not infer a repeated article container. Use a CSS/XPath selector.')


def _json_path(value, path: str):
    """Safe dotted/array-key projection (not an executable JSONPath expression)."""
    if not path or len(path) > 300:
        raise ValueError('JSON field path is empty or too long')
    for part in path.split('.'):
        if not part or part.startswith('_') or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,79}|[0-9]{1,5}', part):
            raise ValueError('Invalid JSON field path component')
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit():
            idx = int(part)
            value = value[idx] if idx < len(value) else None
        else:
            return None
        if value is None:
            return None
    return value


def check_json_contract(document,recipe):
    for path,expected in (recipe.get('json_contract') or {}).items():
        actual=_json_path(document,path)
        if json.dumps(actual,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):
            raise ValueError('JSON response contract failed: '+path)


def confirmed_empty_json(content: str,recipe: dict) -> bool:
    path=recipe.get('empty_json_path') or ''
    if recipe.get('mode')!='json' or not path or not recipe.get('json_contract'):return False
    document=json.loads(content)
    check_json_contract(document,recipe)
    records=_json_path(document,path)
    return isinstance(records,list) and not records


_EMBEDDED_CALENDAR = re.compile(
    r'(?<![\w\d])(?:'
    r'\d{4}-\d{1,2}-\d{1,2}'
    r'|\d{4}年\d{1,2}月\d{1,2}日'
    r'|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\.?\s+\d{1,2},?\s+\d{4}'
    r')(?![\w\d])', re.IGNORECASE)


def embedded_calendar_date(value) -> str | None:
    # Explicit opt-in only. Bounded built-in grammar; no arbitrary regex/eval,
    # relative dates, omitted year, or ambiguous numeric day/month guessing.
    if not isinstance(value, str) or len(value) > 5000:
        return None
    candidates = _EMBEDDED_CALENDAR.findall(value)
    dates = [parse_date(candidate) for candidate in candidates]
    if not dates or any(date is None for date in dates) or len(set(dates)) != 1:
        return None
    return dates[0]


def parse_json_date(value,recipe):
    mode=recipe.get('date_format','auto')
    if mode=='embedded_calendar':return embedded_calendar_date(value)
    if mode not in ('unix_seconds','unix_milliseconds'):return parse_date(str(value or ''))
    try:
        if isinstance(value,bool) or not re.fullmatch(r'[0-9]{12,14}' if mode=='unix_milliseconds' else r'[0-9]{9,11}',str(value)):return None
        dt=datetime.fromtimestamp(int(value)/(1000 if mode=='unix_milliseconds' else 1),timezone.utc)
        return parse_date(dt.isoformat())
    except (ValueError,OverflowError,OSError):return None


def extract_json_articles(content: str, url: str, recipe: dict) -> tuple[list[dict], str]:
    """Extract records from a public JSON document without evaluating code."""
    if len(content) > 2_500_000:
        raise ValueError('JSON source exceeds size limit')
    try:
        document = json.loads(content)
    except (ValueError, TypeError) as exc:
        raise ValueError('Source is not valid JSON') from exc
    check_json_contract(document,recipe)
    path = recipe.get('item_selector') or 'items'
    records = _json_path(document, path)
    if not isinstance(records, list):
        raise ValueError('JSON item path must resolve to an array')
    if len(records) > 500:
        raise ValueError('JSON item path contains more than 500 records')
    filters=recipe.get('json_filters') or {}
    if filters:
        filtered=[]
        for row in records:
            if not isinstance(row,dict):raise ValueError('JSON filtered record is not an object')
            for key in filters:
                if not isinstance(_json_path(row,key),str):
                    raise ValueError('Missing or invalid JSON filter field: '+key)
            if all(_json_path(row,key)==expected for key,expected in filters.items()):filtered.append(row)
        records=filtered
    fields = recipe.get('fields') or {}
    if recipe.get('sort_newest'):
        records = sorted(records, key=lambda row: parse_json_date(_json_path(row, fields.get('date') or 'date'),recipe) or ''
                         if isinstance(row, dict) else '', reverse=True)
    seen, result = set(), []
    for row in records[:100]:
        if not isinstance(row, dict):
            continue
        def value(field, default):
            key = fields.get(field) or default
            raw = _json_path(row, key)
            return str(raw) if isinstance(raw, (str, int, float)) and not isinstance(raw, bool) else ''
        title = clean_text(value('title', 'title'), 300)
        raw_link = value('link', 'url')
        template = recipe.get('link_template') or ''
        if template:
            if template.count('{value}') != 1 or len(template)>2048:
                raise ValueError('JSON link template requires one {value} placeholder')
            direct = _json_path(row, recipe['direct_link_field']) if recipe.get('direct_link_field') else ''
            if isinstance(direct,str) and recipe.get('direct_link_base') and urlsplit(direct).path.lower().endswith('.pdf'):
                direct = urljoin(recipe['direct_link_base'],direct)
            raw_link = direct if isinstance(direct,str) and direct.startswith(('https://','http://')) else template.replace('{value}',quote(raw_link,safe=''))
        link = canonical_link(raw_link, url)
        if not title or not link or link == url or link in seen:
            continue
        seen.add(link)
        result.append({'title': title, 'url': link,
            'published_at': parse_json_date(value('date', 'date'),recipe),
            'summary': clean_text(value('summary', 'summary'), 2000)})
    return result, path


def extract_pdf_articles(content: str, url: str, recipe: dict) -> tuple[list[dict], str]:
    """Discover public PDF publications from ordinary listing pages.

    PDF URLs are linked, not downloaded or republished. Operators can scope
    discovery to an explicit CSS container to avoid navigation/footer links.
    """
    doc = BeautifulSoup(content[:1_300_000], 'lxml')
    selector = recipe.get('item_selector') or 'a[href]'
    try:
        nodes = doc.select(selector)
    except Exception as exc:
        raise ValueError('Invalid PDF CSS selector') from exc
    if len(nodes) > 2000:
        raise ValueError('PDF selector matches too many elements')
    seen, items = set(), []
    for node in nodes:
        # An operator may select publication cards rather than anchor nodes.
        links = [node] if node.name == 'a' else node.select('a[href]')
        for anchor in links[:40]:
            href = anchor.get('href') or ''
            dest = canonical_link(href, url)
            # Support direct .pdf URLs and explicitly PDF-typed download
            # endpoints. Never infer binary MIME type from vague link text.
            pdf_path=bool(dest and re.search(r'\.pdf$', urlsplit(dest).path, re.I))
            pdf_attr=(anchor.get('type') or '').lower().split(';',1)[0].strip()=='application/pdf'
            if not dest or not (pdf_path or pdf_attr) or dest in seen:
                continue
            title = clean_text(anchor.get_text(' ', strip=True) or anchor.get('title') or '', 300)
            if not title:
                title = clean_text(urlsplit(dest).path.rsplit('/', 1)[-1].rsplit('.',1)[0].replace('-', ' ').replace('_',' '),300)
            if not title:
                continue
            date_el = node.select_one('time[datetime],time') if node.name != 'a' else None
            published = parse_date((date_el.get('datetime') or date_el.get_text(' ', strip=True)) if date_el else '')
            seen.add(dest)
            items.append({'title':title,'url':dest,'published_at':published,'summary':'PDF research publication'})
            if len(items) >= 100:
                return items, selector
    return items, selector


def _feed43_compile(pattern: str, *, capture_limit: int = 2000):
    """Small, bounded Feed43-like literal DSL; never runs user-supplied regex."""
    if not isinstance(pattern, str) or not pattern or len(pattern) > 500 or '{%}' not in pattern:
        raise ValueError('Pattern requires {%} and must be <= 500 characters')
    parts = re.split(r'(\{\%\}|\{\*\})', pattern)
    compiled = ''.join(r'([\s\S]{1,'+str(capture_limit)+'}?)' if part == '{%}' else
                       r'[\s\S]{0,10000}?' if part == '{*}' else re.escape(part)
                       for part in parts)
    return regex.compile(compiled)


def _feed43_render(template: str, captures: tuple[str, ...]):
    """Accept numeric groups and Feed43-style {%1} placeholders."""
    template = str(template or '')
    if template.isdigit():
        idx = int(template) - 1
        return captures[idx].strip() if 0 <= idx < len(captures) else ''
    def repl(match):
        idx = int(match.group(1)) - 1
        return captures[idx].strip() if 0 <= idx < len(captures) else ''
    return re.sub(r'\{\%(\d{1,2})\}', repl, template)[:2500]


def response_html(content: str, recipe: dict) -> str:
    """Decode a bounded public API's HTML field without running page scripts."""
    path = recipe.get('response_html_path') or ''
    if not path:
        return content
    if len(content) > 8_000_000:
        raise ValueError('Wrapped HTML response exceeds size limit')
    try:
        value = _json_path(json.loads(content), path)
    except (ValueError, TypeError) as exc:
        raise ValueError('Wrapped HTML source is not valid JSON') from exc
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Wrapped HTML path must contain a nonempty HTML string')
    return value


def check_page_contract(content: str, recipe: dict):
    required=recipe.get('required_selectors') or []
    if not required:return
    doc=BeautifulSoup(content,'lxml')
    for selector in required:
        if doc.select_one(selector) is None:
            raise ValueError('Required source marker missing; original scope or page structure changed')


def confirmed_empty_html(content: str, recipe: dict) -> bool:
    selector=recipe.get('empty_selector') or ''
    expected=recipe.get('empty_text') or ''
    if not selector or not expected:return False
    content=response_html(content,recipe)
    check_page_contract(content,recipe)
    doc=BeautifulSoup(content,'lxml')
    return any(clean_text(node.get_text(' ',strip=True),1000)==clean_text(expected,1000)
               for node in doc.select(selector))


def confirmed_empty_native(content: bytes) -> bool:
    """A genuine empty document, never an array of discarded malformed entries."""
    try:
        if content.lstrip().startswith(b'{'):
            obj=json.loads(content)
            return (isinstance(obj,dict) and str(obj.get('version','')).startswith('https://jsonfeed.org/version/1')
                    and isinstance(obj.get('title'),str) and bool(obj['title'].strip()) and obj.get('items')==[])
        root=SafeET.fromstring(content)
        local=root.tag.rsplit('}',1)[-1].lower()
        if local=='rss':
            channel=root.find('channel')
            return (channel is not None and channel.find('item') is None
                    and bool((channel.findtext('title') or '').strip()) and bool((channel.findtext('link') or '').strip()))
        if local=='feed':
            names=[node.tag.rsplit('}',1)[-1] for node in root]
            return 'entry' not in names and all(any(node.tag.rsplit('}',1)[-1]==name and (node.text or '').strip() for node in root) for name in ('title','id'))
    except Exception:
        return False
    return False


def extract_articles(html: str, url: str, recipe: dict | None = None) -> tuple[list[dict], str]:
    cfg = recipe or {}
    html = response_html(html, cfg)
    check_page_contract(html,cfg)
    mode = cfg.get('mode', 'css')
    if mode == 'json':
        return extract_json_articles(html, url, cfg)
    if mode == 'pdf':
        return extract_pdf_articles(html, url, cfg)
    from .access_barriers import reject_access_page
    reject_access_page(html)
    fields = cfg.get('fields') or {}
    if mode == 'xpath':
        root = LH.fromstring(html, base_url=url)
        selector = cfg.get('item_selector') or '//article'
        nodes = root.xpath(selector)
        if not isinstance(nodes, list):
            raise ValueError('XPath item rule must return a list of nodes')
    elif mode == 'css':
        doc = BeautifulSoup(html, 'lxml')
        selector = cfg.get('item_selector') or infer_selector(doc)
        nodes = doc.select(selector)
    elif mode == 'pattern':
        pattern = cfg.get('item_selector','')
        # Feed43 global search narrows the portion of the HTML to scan. The
        # first global capture is used as the scoped region, as in Feed43.
        region = html[:1_300_000]
        global_pattern = cfg.get('global_pattern') or ''
        try:
            if global_pattern:
                global_match = _feed43_compile(global_pattern, capture_limit=1_300_000).search(region, timeout=0.4)
                if not global_match:
                    raise ValueError('Feed43 global search returned no match')
                region = global_match.group(1)
            # Reject impossible patterns before running potentially expensive
            # bounded wildcard matching against long, repetitive pages.
            expr = _feed43_compile(pattern)
            literals = [part for part in re.split(r'(?:\{\%\}|\{\*\})', pattern) if part]
            cursor = 0
            impossible = False
            for literal in literals:
                pos = region.find(literal, cursor)
                if pos < 0:
                    impossible = True
                    break
                cursor = pos + len(literal)
            if impossible:
                return [], pattern
            nodes=[]
            for match in expr.finditer(region, timeout=0.4):
                nodes.append(match)
                if len(nodes) >= 100:
                    break
        except TimeoutError as exc:
            raise ValueError('Feed43 global/item pattern timed out') from exc
        selector=pattern
    else:
        raise ValueError('Unsupported extraction mode')
    if len(nodes) > 500:
        raise ValueError('Item selector matches too many elements')
    seen = set()
    result = []
    for el in nodes:
        if len(result) >= 100:
            break
        if mode == 'css':
            if not isinstance(el, Tag):
                continue
            title = _value_css(el, fields.get('title', 'h2, h3, h4, a'))
            link = _value_css(el, fields.get('link', 'a@href'))
            date = _value_css(el, fields.get('date', 'time'))
            excerpt = _value_css(el, fields.get('summary', 'p'))
            if not title:
                a = el.find('a', href=True)
                title = a.get_text(' ', strip=True) if a else ''
        elif mode == 'pattern':
            captures=el.groups()
            def part(field, default):
                return _feed43_render(fields.get(field, default), captures)
            title=clean_text(BeautifulSoup(part('title','2'),'html.parser').get_text(' ',strip=True),300)
            link=part('link','1')
            date=part('date','3')
            excerpt=clean_text(BeautifulSoup(part('summary','4'),'html.parser').get_text(' ',strip=True),2000)
        else:
            if not hasattr(el, 'xpath'):
                continue
            title = _value_xpath(el, fields.get('title') or '(.//h2|.//h3|.//a)[1]')
            link = _value_xpath(el, fields.get('link') or '(.//a/@href)[1]')
            date = _value_xpath(el, fields.get('date') or '(.//time/@datetime|.//time/text())[1]')
            excerpt = _value_xpath(el, fields.get('summary') or '(.//p)[1]')
        link = canonical_link(link, url, keep_fragment=bool(cfg.get('keep_fragments')))
        title = clean_text(title, 300)
        if not title or not link or link == url or link in seen:
            continue
        seen.add(link)
        result.append({'title': title, 'url': link, 'published_at': parse_json_date(date,cfg), 'summary': clean_text(excerpt, 2000)})
    return result, selector


def parse_native(content: bytes, url: str) -> list[dict]:
    # Supports RSS, Atom and JSON Feed 1.0/1.1. Refuses DTD entity expansion.
    if content.lstrip().startswith(b'{'):
        try:
            obj=json.loads(content)
        except (ValueError, UnicodeError) as e:
            raise ValueError('Invalid JSON Feed') from e
        if not isinstance(obj,dict) or not str(obj.get('version','')).startswith('https://jsonfeed.org/version/1'):
            raise ValueError('Not a recognized JSON Feed document')
        records=obj.get('items',[])
        if not isinstance(records,list):
            raise ValueError('JSON Feed items must be an array')
        seen=set();items=[]
        for record in records[:150]:
            if not isinstance(record,dict):
                continue
            link=canonical_link(record.get('url') or record.get('external_url') or '',url)
            title=clean_text(record.get('title') or '',300)
            if link and title and link not in seen:
                seen.add(link)
                items.append({'title':title,'url':link,
                              'published_at':parse_date(record.get('date_published') or record.get('date_modified') or ''),
                              'summary':clean_text(record.get('summary') or '',2000)})
        return items
    # defusedxml blocks dangerous entity expansion; no external entity resolution.
    root = SafeET.fromstring(content)
    tag = root.tag.lower()
    if tag.endswith('rss') or tag.endswith('rdf'):
        nodes = root.findall('./channel/item') if tag.endswith('rss') else [e for e in root if e.tag.lower().endswith('item')]
        def find(el, name):
            for child in el:
                if child.tag.rsplit('}',1)[-1].lower() == name.lower():
                    return child.text or ''
            return ''
        entries = [{'title':find(n,'title'),'url':find(n,'link'), 'published_at':parse_date(find(n,'pubDate') or find(n,'date')), 'summary':find(n,'description')} for n in nodes]
    elif tag.endswith('feed'):
        entries = []
        for n in root:
            if not n.tag.endswith('entry'):
                continue
            def val(name):
                for ch in n:
                    if ch.tag.endswith(name): return ch.text or ''
                return ''
            link = ''
            for ch in n:
                if ch.tag.endswith('link') and ch.attrib.get('rel', 'alternate') == 'alternate':
                    link = ch.attrib.get('href','')
                    break
            entries.append({'title':val('title'), 'url':link, 'published_at':parse_date(val('published') or val('updated')), 'summary':val('summary')})
    else:
        raise ValueError('Not a recognized RSS or Atom document')
    seen=set(); items=[]
    for e in entries[:150]:
        link=canonical_link(e.get('url',''),url)
        title=clean_text(e.get('title'),300)
        if link and title and link not in seen:
            seen.add(link)
            items.append({'title':title,'url':link,'published_at':e.get('published_at'),'summary':clean_text(e.get('summary'),2000)})
    return items


def safe_preview(raw_html: str) -> str:
    """No active content or remote resource requests in editor snapshot."""
    doc = BeautifulSoup(raw_html[:1_300_000], 'html.parser')
    for e in list(doc.find_all(['script','style','link','meta','iframe','object','embed','form','svg','base','noscript','video','audio','source','picture','canvas'])):
        e.decompose()
    for e in doc.find_all(True):
        clean = {}
        for k,v in list(e.attrs.items()):
            if k in ('class','id','role') or k.startswith('data-') and k not in ('data-src','data-href','data-srcset'):
                clean[k] = v
            elif k == 'href' and e.name == 'a':
                clean['data-original-href'] = v
            elif k == 'datetime' and e.name == 'time':
                clean[k] = v
        e.attrs = clean
    body = doc.body or doc
    inner = str(body)
    # Restrictive srcdoc CSP, no scripts, no links, no active forms and no remote assets.
    return ('<!doctype html><html><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; form-action \'none\';">'
            '<style>body{font:14px/1.5 system-ui;padding:16px;color:#263044}body *{max-width:100%}a{color:#426aab;cursor:crosshair}article,li,section{padding:3px} .of-selected{outline:3px solid #2b79d4!important;background:#dceefd!important}</style>'
            '</head><body>' + inner + '</body></html>')


def xml_escape(value: object, *, attribute: bool = False) -> str:
    # XML 1.0 forbids most C0 control characters even when HTML-escaped.
    raw=str(value or '')
    clean=''.join(c for c in raw if c in '\t\n\r' or '\u0020' <= c <= '\ud7ff' or '\ue000' <= c <= '\ufffd' or '\U00010000' <= c <= '\U0010ffff')
    return escape(clean, quote=attribute)

def render_rss(feed: dict, entries: list[dict], self_url: str) -> bytes:
    title=xml_escape(feed['title'])
    desc=xml_escape(feed.get('description') or f'Updates from {feed["source_url"]}')
    src=xml_escape(feed['source_url'],attribute=True)
    stamp=feed.get('last_success') or feed.get('created_at')
    now=format_datetime(datetime.fromisoformat(stamp).astimezone(timezone.utc),usegmt=True) if stamp else format_datetime(datetime.now(timezone.utc),usegmt=True)
    parts=['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>',
           f'<title>{title}</title><link>{src}</link><description>{desc}</description>',
           f'<lastBuildDate>{now}</lastBuildDate>',f'<atom:link href="{xml_escape(self_url,attribute=True)}" rel="self" type="application/rss+xml"/>']
    for x in entries[:100]:
        dt=parse_date(x.get('published_at') or '')
        date_xml=f'<pubDate>{format_datetime(datetime.fromisoformat(dt),usegmt=True)}</pubDate>' if dt else ''
        guid=x['guid']
        parts.append('<item>' + f'<title>{xml_escape(x["title"])}</title>' +
                     f'<link>{xml_escape(x["url"],attribute=True)}</link>' +
                     f'<guid isPermaLink="false">{xml_escape(guid)}</guid>' +
                     date_xml +
                     f'<description>{xml_escape(x.get("summary") or "")}</description>' + '</item>')
    parts.append('</channel></rss>')
    return ''.join(parts).encode('utf-8')


def guid_for(url: str) -> str:
    return sha256(url.encode('utf8')).hexdigest()
