import html,json
import pytest
from openfeed.extract import extract_articles

def test_custom_components_json_and_hero_fallback():
 def attr(x):return html.escape(json.dumps(x),quote=True)
 page='<jb-article-wide articletitle="Hero" link="'+attr({'href':'/hero'})+'" teasermeta="'+attr({'date':'21.10.2026'})+'"></jb-article-wide>'
 page+='<jb-article-card teaserheader="'+attr({'headline':'Quoted "title" & more'})+'" link="'+attr({'href':'/one'})+'" teasermeta="'+attr({'date':'20.10.2026'})+'"></jb-article-card>'
 recipe={'item_selector':'jb-article-card,jb-article-wide','fields':{'title':':scope@teaserheader::json.headline ?? :scope@articletitle','link':':scope@link::json.href','date':':scope@teasermeta::json.date'}}
 items,_=extract_articles(page,'https://example.com',recipe)
 assert [x['title'] for x in items]==['Hero','Quoted "title" & more']
 assert [x['url'] for x in items]==['https://example.com/hero','https://example.com/one']
 assert all(x['published_at'] for x in items)

@pytest.mark.parametrize('raw',['{broken','x'*100001])
def test_bad_json_attribute_rejects_run(raw):
 page='<x-card payload="'+html.escape(raw,quote=True)+'"></x-card>'
 with pytest.raises(ValueError):extract_articles(page,'https://example.com',{'item_selector':'x-card','fields':{'title':':scope@payload::json.title'}})
