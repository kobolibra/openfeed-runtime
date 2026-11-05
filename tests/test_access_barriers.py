import pytest
from openfeed.access_barriers import reject_access_page,AccessBarrierError
from openfeed.extract import extract_articles

@pytest.mark.parametrize('html,kind',[
 ('<title>Just a moment...</title><h1>Checking your browser</h1><script>window._cf_chl_opt={}</script>','challenge'),
 ('<h1>Verify you are human</h1><div class="cf-turnstile"></div>','captcha'),
 ('<h1>请先登录</h1><form><input type="password"></form>','login_wall'),
])
def test_recognizes_short_access_pages(html,kind):
 with pytest.raises(AccessBarrierError) as exc:reject_access_page(html)
 assert exc.value.kind==kind

@pytest.mark.parametrize('html',[
 '<title>Research</title><h1>New research</h1><script src="/cdn-cgi/challenge-platform/sensor.js"></script>',
 '<title>Annual report</title><p>Sign in to continue</p><form><input type="password"></form>',
 '<h1>Verify you are human</h1><p>A guide to captcha technology</p>',
 '<article><h1>Verify you are human</h1><p>'+('Research explains captcha technology. '*15)+'</p></article><div class="cf-turnstile"></div>',
 '<h1>Research</h1><footer><a href="/login">请先登录</a><div class="g-recaptcha"></div></footer>',
])
def test_normal_articles_and_embedded_widgets_are_not_barriers(html):
 reject_access_page(html)

def test_challenge_cannot_publish_its_support_link_as_an_article():
 html='<title>Just a moment...</title><script>window._cf_chl_opt={}</script><h1>Checking your browser</h1><a href="https://example.org/help">Support</a>'
 with pytest.raises(AccessBarrierError):extract_articles(html,'https://example.org/',{'mode':'css','item_selector':'a','fields':{'title':':scope','link':':scope@href'}})

def test_required_empty_marker_is_not_enough_to_accept_challenge():
 html='<title>Just a moment...</title><script>window._cf_chl_opt={}</script><div class="listing">暂无职位</div>'
 with pytest.raises(AccessBarrierError):extract_articles(html,'https://example.org/',{'required_selectors':['.listing'],'empty_selector':'.listing','empty_text':'暂无职位'})

def test_json_records_do_not_treat_summary_html_as_page_barrier():
 raw='{"items":[{"title":"Just a moment...","url":"https://example.org/a","summary":"<script>window._cf_chl_opt={}</script>"}]}'
 items,_=extract_articles(raw,'https://example.org/',{'mode':'json','item_selector':'','fields':{'title':'title','link':'url','summary':'summary'}})
 assert len(items)==1

@pytest.mark.asyncio
async def test_http_200_challenge_refresh_preserves_published_items(monkeypatch,tmp_path):
 from unittest.mock import AsyncMock
 from openfeed.storage import Store
 import openfeed.app as server
 from openfeed.diagnostics import failure_summary
 db=Store(str(tmp_path/'state.sqlite'))
 monkeypatch.setattr(server,'store',db);monkeypatch.setattr(server,'_last_domain',{})
 monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
 f=db.create({'title':'Research','source_url':'https://example.org/list','recipe':{'item_selector':'a','fields':{'title':':scope','link':':scope@href'}}})
 db.finish(f,[{'title':'Prior article','url':'https://example.org/prior','summary':'','published_at':None}],None,1)
 before=db.entries(f['id'])
 html=b'<title>Just a moment...</title><script>window._cf_chl_opt={}</script><a href="https://example.org/help">Contact support</a>'
 monkeypatch.setattr(server,'fetch',AsyncMock(return_value=(f['source_url'],html,'utf-8')))
 result=await server.run_feed(f['id'])
 assert result['status']=='error' and 'access barrier: challenge' in result['message']
 assert db.entries(f['id'])==before
 assert failure_summary([db.get(f['id'])])['error_counts']['access']==1
 db.close()
