import pytest,json
from unittest.mock import AsyncMock
from openfeed.storage import Store
from openfeed.extract import confirmed_empty_native,extract_articles
import openfeed.app as server

URL='https://example.org/careers?city=Shanghai'
CFG={'mode':'css','item_selector':'article','fields':{'title':'h2','link':'a@href'},'required_selectors':['option[value="59"][selected]'],'empty_selector':'#results > p','empty_text':'There are no results for the selected options.'}
SCOPE='<select><option value="59" selected>Shanghai</option></select>'
GOOD=SCOPE+'<article><h2>Research Analyst</h2><a href="/careers/123">Read</a></article>'
EMPTY=SCOPE+'<div id="results"><p>There are no results for the selected options.</p></div>'
NATIVE=b'<rss version="2.0"><channel><title>Official Jobs</title><link>https://example.org/jobs</link></channel></rss>'

@pytest.mark.asyncio
async def test_confirmed_empty_preserves_history_then_scope_change_fails(monkeypatch,tmp_path):
 db=Store(str(tmp_path/'state.sqlite'));monkeypatch.setattr(server,'store',db);monkeypatch.setattr(server,'_last_domain',{});monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
 f=db.create({'title':'Shanghai jobs','source_url':URL,'recipe':CFG})
 monkeypatch.setattr(server,'fetch',AsyncMock(side_effect=[(URL,b.encode(),'utf-8') for b in [GOOD,EMPTY,GOOD.replace(' selected','')]]))
 assert (await server.run_feed(f['id']))['status']=='success'
 guid=db.entries(f['id'])[0]['guid']
 result=await server.run_feed(f['id']);assert result['status']=='success' and result['found']==0
 assert 'official empty listing confirmed' in result['message']
 assert db.entries(f['id'])[0]['guid']==guid and db.get(f['id'])['status']=='healthy'
 result=await server.run_feed(f['id']);assert result['status']=='error' and 'Required source marker' in result['message']
 assert db.entries(f['id'])[0]['guid']==guid
 db.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('body,cfg,success',[(EMPTY,CFG,True),(EMPTY,{},False),(EMPTY.replace('There are no results','Please log in'),CFG,False),(EMPTY.replace(' selected',''),CFG,False)])
async def test_zero_items_requires_specific_marker_and_scope(monkeypatch,tmp_path,body,cfg,success):
 db=Store(str(tmp_path/'state.sqlite'));monkeypatch.setattr(server,'store',db);monkeypatch.setattr(server,'_last_domain',{});monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0');monkeypatch.setattr(server,'fetch',AsyncMock(return_value=(URL,body.encode(),'utf-8')))
 f=db.create({'title':'Jobs','source_url':URL,'recipe':cfg});r=await server.run_feed(f['id']);assert (r['status']=='success') is success;assert db.entries(f['id'])==[];db.close()

@pytest.mark.asyncio
async def test_native_empty_is_opt_in_and_malformed_items_do_not_count_as_empty(monkeypatch,tmp_path):
 db=Store(str(tmp_path/'state.sqlite'));monkeypatch.setattr(server,'store',db);monkeypatch.setattr(server,'_last_domain',{});monkeypatch.setenv('OPENFEED_MIN_DOMAIN_INTERVAL','0')
 f=db.create({'title':'Official RSS','source_url':URL,'kind':'native','recipe':{}})
 mocked=AsyncMock(return_value=(URL,NATIVE,'utf-8'));monkeypatch.setattr(server,'fetch',mocked)
 assert (await server.run_feed(f['id']))['status']=='error'
 db.update(f['id'],{'recipe':{'allow_empty_native':True}})
 assert (await server.run_feed(f['id']))['status']=='success'
 mocked.return_value=(URL,NATIVE.replace(b'</channel>',b'<item><title>Broken entry</title></item></channel>'),'utf-8')
 assert (await server.run_feed(f['id']))['status']=='error'
 assert db.entries(f['id'])==[];db.close()

@pytest.mark.parametrize('body',[b'<html><body>Sign in</body></html>',b'<rss/>',b'{"version":"https://jsonfeed.org/version/1.1","title":"Jobs","items":[{}]}'])
def test_empty_confirmation_rejects_login_or_discarded_items(body):
 assert not confirmed_empty_native(body)
