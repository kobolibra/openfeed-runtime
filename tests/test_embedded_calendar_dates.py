import pytest
from openfeed.extract import embedded_calendar_date,extract_articles
from openfeed.app import Recipe

@pytest.mark.parametrize('text,date',[
 ('Market Commentary Oct 8, 2026 Credit Quarterly: New terms','2026-10-08'),
 ('memos Sep 22, 2026 Shall We Repeal the Laws of Economics','2026-09-22'),
 ('Published 2026年10月8日 Latest research','2026-10-08'),
 ('Research | 2026-10-08 | title','2026-10-08'),
 ('Oct 8, 2026 / Oct 8, 2026','2026-10-08'),
 ('15 days ago',None),('Oct 2026',None),('01/02/2026',None),
 ('Oct 8, 2026 updated Oct 9, 2026',None),
 ('Feb 30, 2026',None),('Feb 30, 2026 and Oct 8, 2026',None),
 ('x'*5001+' Oct 8, 2026',None),('2026-10-081',None),
])
def test_exact_calendar_only(text,date):
 result=embedded_calendar_date(text)
 assert (result[:10] if result else None)==date

@pytest.mark.parametrize('mode',['css','xpath','pattern','json'])
def test_explicit_date_mode_across_extractors(mode):
 recipes={
 'css':({'mode':'css','item_selector':'article','fields':{'title':'h2','link':'a@href','date':'p'}},'<article><h2>Research</h2><a href="/a">Read</a><p>Commentary Oct 8, 2026 Research</p></article>'),
 'xpath':({'mode':'xpath','item_selector':'//article','fields':{'title':'.//h2/text()','link':'.//a/@href','date':'.//p/text()'}},'<article><h2>Research</h2><a href="/a">Read</a><p>Commentary Oct 8, 2026 Research</p></article>'),
 'pattern':({'mode':'pattern','item_selector':'<a href="{%}">{%}</a><p>{%}</p>','fields':{'title':'2','link':'1','date':'3'}},'<a href="/a">Research</a><p>Commentary Oct 8, 2026 Research</p>'),
 'json':({'mode':'json','item_selector':'items','fields':{'title':'title','link':'url','date':'date'}},'{"items":[{"title":"Research","url":"https://example.org/a","date":"Commentary Oct 8, 2026 Research"}]}'),
 }
 recipe,body=recipes[mode]
 old=extract_articles(body,'https://example.org/list',recipe)[0]
 assert old and old[0]['published_at'] is None
 recipe['date_format']='embedded_calendar';Recipe(**recipe)
 new=extract_articles(body,'https://example.org/list',recipe)[0]
 assert new[0]['published_at'].startswith('2026-10-08')
