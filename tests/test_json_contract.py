import json
import pytest
from openfeed.app import Recipe
from openfeed.extract import extract_json_articles,confirmed_empty_json
from openfeed.pagination import collect_pages

CFG={'mode':'json','item_selector':'result','json_contract':{'statusCode':200},'empty_json_path':'result'}

def test_official_empty_json_requires_success_contract():
 assert confirmed_empty_json('{"statusCode":200,"result":[]}',CFG)
 assert not confirmed_empty_json('{"statusCode":200}',CFG)
 assert not confirmed_empty_json('{"statusCode":200,"result":{}}',CFG)
 assert not confirmed_empty_json('{"result":[]}',{'mode':'json','empty_json_path':'result'})
 with pytest.raises(ValueError,match='contract'):confirmed_empty_json('{"statusCode":403,"result":[]}',CFG)


def test_ignored_server_filter_is_rejected_before_items():
 cfg={'mode':'json','item_selector':'data','json_contract':{'parameters.q':'China','parameters.ssf':['Opinion']}}
 body={'parameters':{'q':'China','ssf':['Opinion','News Release']},'data':[{'title':'Wrong category','url':'https://example.org/a'}]}
 with pytest.raises(ValueError,match='parameters.ssf'):extract_json_articles(json.dumps(body),'https://example.org/api',cfg)
 body['parameters']['ssf']=['Opinion'];assert len(extract_json_articles(json.dumps(body),'https://example.org/api',cfg)[0])==1

@pytest.mark.parametrize('bad',[{'empty_json_path':'result'},{'mode':'json','item_selector':'result','empty_json_path':'other','json_contract':{'success':True}},{'mode':'json','item_selector':'result','empty_json_path':'result'},{'mode':'css','json_contract':{'status':200}}])
def test_empty_json_contract_configuration_is_explicit(bad):
 with pytest.raises(ValueError):Recipe(**bad)

@pytest.mark.asyncio
async def test_empty_json_carries_quality_evidence():
 async def fetch(url,**options):return url,b'{"statusCode":200,"result":[]}', 'utf-8'
 rows,metrics=await collect_pages('https://example.org/api',CFG,fetch,None)
 assert rows==[] and metrics['empty_confirmed'] is True

@pytest.mark.parametrize('fake',[{'statusCode':True,'result':[]},{'statusCode':'200','result':[]},{'statusCode':200,'result':[{}]}])
def test_wrong_types_and_discarded_rows_are_not_official_empty(fake):
 try:result=confirmed_empty_json(json.dumps(fake),CFG)
 except ValueError:result=False
 assert not result
