import pytest
from openfeed.security import validate_json_request,fetch
from openfeed.app import Recipe
from openfeed.pagination import collect_pages

@pytest.mark.parametrize('body',[{'size':6,'from':1},{'filters':['China','Opinion'],'enabled':False,'cursor':None},{}])
def test_json_types_and_roundtrip(body):
 assert Recipe(mode='json',request_method='POST',request_json=body).request_json==body
 assert validate_json_request(body)==body

@pytest.mark.parametrize('body',[{'a':float('nan')},{'a':float('inf')},{'a':[0]*51},{'a':{'b':{'c':{'d':{'e':0}}}}},{'a':'x'*2001},{'a':object()},{'a':set()}, {'':0}])
def test_json_request_limits(body):
 with pytest.raises(ValueError):validate_json_request(body)

def test_json_requires_explicit_post_no_form_mix():
 with pytest.raises(ValueError):Recipe(mode='json',request_json={'a':1})
 with pytest.raises(ValueError):Recipe(mode='json',request_method='POST',request_json={'a':1},request_data={'a':'2'})

@pytest.mark.asyncio
async def test_json_payload_reaches_transport_without_stringifying():
 calls=[]
 async def http(url,**options):
  calls.append(options);return url,b'{"items":[{"title":"A real item","url":"https://example.org/a"}]}','utf-8'
 cfg={'mode':'json','request_method':'POST','request_json':{'size':6,'filters':['China'],'active':False},'item_selector':'items','fields':{'title':'title','link':'url'}}
 items,_=await collect_pages('https://example.org/api',cfg,http,None)
 assert len(items)==1 and calls==[{'method':'POST','json_data':cfg['request_json']}]

@pytest.mark.asyncio
async def test_303_removes_json_body_before_redirect(monkeypatch):
 from openfeed import security
 calls=[]
 class Response:
  charset='utf-8'
  def __init__(self,url,status):self.url=url;self.status=status;self.headers={'Location':'https://other.example.org/list'} if status==303 else {'Content-Type':'application/json'};self.content=self
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def iter_chunked(self,n):yield b'{"items":[]}'
 class Client:
  def __init__(self,**kwargs):assert kwargs['trust_env'] is False
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  def post(self,url,**kwargs):calls.append(('POST',kwargs));return Response(url,303)
  def get(self,url,**kwargs):calls.append(('GET',kwargs));return Response(url,200)
 monkeypatch.setattr(security,'ClientSession',Client);monkeypatch.setattr(security,'TCPConnector',lambda **kwargs:None)
 await fetch('https://example.org/api',method='POST',json_data={'size':6})
 assert calls[0][1]['json']=={'size':6} and calls[1][0]=='GET' and 'json' not in calls[1][1]

@pytest.mark.asyncio
async def test_json_does_not_weaken_private_url_guard():
 with pytest.raises(ValueError):await fetch('http://127.0.0.1/',method='POST',json_data={'a':1})

@pytest.mark.asyncio
async def test_307_cannot_forward_json_to_other_origin(monkeypatch):
 from openfeed import security
 calls=[]
 class Response:
  status=307;headers={'Location':'https://other.example.org/api'}
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
 class Client:
  def __init__(self,**kwargs):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  def post(self,url,**kwargs):calls.append(url);return Response()
 monkeypatch.setattr(security,'ClientSession',Client);monkeypatch.setattr(security,'TCPConnector',lambda **kwargs:None)
 with pytest.raises(ValueError,match='original origin'):await fetch('https://example.org/api',method='POST',json_data={'q':'China'})
 assert calls==['https://example.org/api']

def test_all_public_api_paths_share_request_options():
 from openfeed.security import public_request_options
 cfg={'request_method':'POST','request_json':{'q':'China','filters':['Opinion']},'public_api_key':'public-key'}
 assert public_request_options(cfg)=={'method':'POST','json_data':cfg['request_json'],'public_api_key':'public-key'}
 assert public_request_options({'request_method':'POST','request_data':{'page':'2'}})=={'method':'POST','data':{'page':'2'}}
 assert public_request_options({})=={}
