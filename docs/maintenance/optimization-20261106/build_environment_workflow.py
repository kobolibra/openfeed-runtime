from pathlib import Path
import yaml,re
logic=Path('work/production_relay_logic.py').read_text();clock=Path('work/optimization-20261106/environment_clock_logic.py').read_text()
d=yaml.safe_load(Path('outputs/OpenFeed-cloud/runtime-cloud-optimized.yml').read_text());d['name']='OpenFeed efficient scheduled RSS publication';d['on']={'schedule':[{'cron':'23 * * * *'}],'workflow_dispatch':{'inputs':{k:{'type':'string','required':False,'default':''} for k in ['root','generation','not_before','signature']}}};d['on']['workflow_dispatch']['inputs']['restart']={'type':'boolean','default':False};d['permissions']={}
base=d['jobs']['runtime'];base['permissions']={'contents':'write','pages':'write'};base['needs']='authorize';base['if']="needs.authorize.outputs.claimed == 'true'"
# Legacy operator-facing input is intentionally absent from production fetching.
base['steps'][0]['with']['ref']='14d068b0cf3fa3239c3862bec10bd048d13664be'
def py(text):return "python3 - <<'PYCLOCK'\n"+text+"\nPYCLOCK\n"
authorize=logic+'''
import os
assert len(os.environ.get('CHAIN_KEY',''))>=32,'Relay signing secret not configured'
inputs={k:os.environ.get('INPUT_'+k.upper(),'') for k in ['root','generation','not_before','signature']}
actor=os.environ['GITHUB_REPOSITORY_OWNER'] if os.environ['GITHUB_EVENT_NAME']=='schedule' else os.environ['GITHUB_ACTOR']
a=authorize(actor,os.environ['GITHUB_REPOSITORY_OWNER'],os.environ['CHAIN_KEY'],inputs,os.environ['GITHUB_RUN_ID'],time.time())
assert a is not None
with open(os.environ['GITHUB_OUTPUT'],'a') as f:
 for k in ['root','generation']:f.write(k+'='+str(a[k])+'\\n')
'''
reserve_code=logic+clock+'''
import os,subprocess
from pathlib import Path
def git(*args):return subprocess.run(['git',*args],check=True,capture_output=True,text=True,timeout=60).stdout.strip()
assert not git('status','--porcelain'),'Dirty scheduling metadata checkout'
claimed=reserve(git,claim,os.environ['ROOT_RUN'],int(os.environ['GENERATION']),os.environ['GITHUB_RUN_ID'],time.time(),os.environ.get('RESTART')=='true' and os.environ['GITHUB_ACTOR']==os.environ['GITHUB_REPOSITORY_OWNER'])
with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('claimed='+str(claimed).lower()+'\\n')
'''
auth={'if':"github.repository == 'kobolibra/openfeed-feeds' && github.ref == 'refs/heads/main' && (github.event_name == 'schedule' || github.actor == github.repository_owner || github.actor == 'github-actions[bot]')",'runs-on':'ubuntu-latest','timeout-minutes':3,'permissions':{'contents':'read'},'outputs':{'root':'${{ steps.authorize.outputs.root }}','generation':'${{ steps.authorize.outputs.generation }}','claimed':'${{ steps.claim.outputs.claimed }}'},'steps':[{'name':'Authenticate owner or signed schedule','id':'authorize','env':{'CHAIN_KEY':'${{ secrets.OPENFEED_RELAY_HMAC }}',**{'INPUT_'+k.upper():'${{ inputs.'+k+' }}' for k in ['root','generation','not_before','signature']}},'run':py(authorize)},{'uses':'actions/checkout@v4','with':{'repository':'kobolibra/openfeed-runtime','ref':'shadow-state','path':'state','sparse-checkout':'relay-cursor.json','sparse-checkout-cone-mode':False,'ssh-key':'${{ secrets.OPENFEED_RUNTIME_KEY }}'}},{'name':'Reserve one scheduling generation','id':'claim','working-directory':'state','env':{'ROOT_RUN':'${{ steps.authorize.outputs.root }}','GENERATION':'${{ steps.authorize.outputs.generation }}','RESTART':'${{ inputs.restart }}'},'run':py(reserve_code)}]}
clock_code=logic+clock+'''
import os,urllib.request
KEY=os.environ['CHAIN_KEY'];assert len(KEY)>=32
API='https://api.github.com/repos/'+REPO
def request(method,path,data=None):
 req=urllib.request.Request(API+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as response:return json.load(response) if method=='GET' else response.status
environment=request('GET','/environments/openfeed-publication-interval')
parent=request('GET','/actions/runs/'+os.environ['GITHUB_RUN_ID'])
next_at=release_time(environment,parent,time.time())
root=os.environ['ROOT_RUN'];generation=int(os.environ['GENERATION'])+1
inputs={'root':root,'generation':str(generation),'not_before':str(next_at),'signature':signature(KEY,root,generation,next_at),'restart':'false'}
retry_api(lambda:request('POST','/actions/workflows/runtime-cloud.yml/dispatches',{'ref':'main','inputs':inputs}))
print('Platform interval completed; next signed finite publication tick dispatched.')
'''
timer={'needs':'authorize','if':"always() && needs.authorize.result == 'success' && needs.authorize.outputs.claimed == 'true'",'runs-on':'ubuntu-latest','timeout-minutes':3,'environment':{'name':'openfeed-publication-interval'},'permissions':{'actions':'write','contents':'read'},'steps':[{'name':'Continue after platform timer without occupying an idle runner','env':{'GH_TOKEN':'${{ github.token }}','CHAIN_KEY':'${{ secrets.OPENFEED_RELAY_HMAC }}','ROOT_RUN':'${{ needs.authorize.outputs.root }}','GENERATION':'${{ needs.authorize.outputs.generation }}'},'run':py(clock_code)}]}
d['jobs']={'authorize':auth,'runtime':base,'interval':timer}
class D(yaml.SafeDumper):pass
D.add_representer(str,lambda d,s:d.represent_scalar('tag:yaml.org,2002:str',s,style='|' if '\n' in s else None))
out=Path('outputs/OpenFeed-cloud/runtime-cloud-efficient.yml');out.write_text('# Finite RSS build/publication. The platform environment timer waits before runner allocation.\n'+yaml.dump(d,Dumper=D,sort_keys=False,width=200))
for job in d['jobs'].values():
 for x in job['steps']:
  if 'run' not in x:continue
  for marker in ['PYCLOCK','PYLOG','PY']:
   token="<<'"+marker+"'\n"
   if token in x['run']:compile(x['run'].split(token,1)[1].rsplit('\n'+marker,1)[0],x.get('name','inline'),'exec')
assert all('while time.time()' not in x.get('run','') for j in d['jobs'].values() for x in j['steps'])
assert 'actions' not in base['permissions'] and 'OPENFEED_RUNTIME_KEY' not in str(timer)
print(out)
