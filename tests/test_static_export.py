import importlib.util
from pathlib import Path
import pytest,httpx
from defusedxml.ElementTree import fromstring
P=Path(__file__).resolve().parents[1]/'ops/export_static.py';spec=importlib.util.spec_from_file_location('static_export',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
RAW=b'<rss version="2.0"><channel><title>Public RSS</title><item><title>One</title><link>https://example.org/a</link><guid>fixed-guid</guid></item></channel></rss>'

def test_static_self_link_changes_without_changing_guids():
 r=fromstring(m.rewrite_rss(RAW,'https://example.org/openfeed/rss/id.xml'))
 assert r.findtext('channel/item/guid')=='fixed-guid'
 assert r.find('channel/{'+m.ATOM+'}link').get('href')=='https://example.org/openfeed/rss/id.xml'

@pytest.mark.asyncio
async def test_failed_export_preserves_previous_release(tmp_path):
 output=tmp_path/'public';output.mkdir();(output/'previous.xml').write_text('keep')
 async def respond(request):
  if request.url.path=='/api/feeds':return httpx.Response(200,json=[{'id':'a'*26,'enabled':True,'title':'A','source_url':'https://example.org/a','status':'healthy'}])
  return httpx.Response(500)
 async with httpx.AsyncClient(base_url='http://127.0.0.1:8765',transport=httpx.MockTransport(respond)) as c:
  with pytest.raises(httpx.HTTPStatusError):await m.export(c,output,'https://example.org/openfeed')
 assert (output/'previous.xml').read_text()=='keep' and not list(tmp_path.glob('openfeed-static-*'))

@pytest.mark.parametrize('url',['http://example.org','https://localhost','https://a:b@example.org','https://example.org/?token=x'])
def test_public_url_validation(url):
 with pytest.raises(ValueError):m.public_base(url)
