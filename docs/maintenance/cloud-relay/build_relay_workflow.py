from pathlib import Path
import yaml,hashlib,json
logic=Path('work/relay_logic.py').read_text()
header="""import os,urllib.request,urllib.error,datetime,subprocess
from pathlib import Path
def output(**rows):
 with open(os.environ['GITHUB_OUTPUT'],'a') as f:
  for k,v in rows.items():f.write(str(k)+'='+str(v)+'\\n')
def api(method,path,data=None):
 request=urllib.request.Request('https://api.github.com/repos/'+REPO+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
 with urllib.request.urlopen(request,timeout=25) as response:return response.status
"""
guard=logic+header+"""
assert len(os.environ.get('CHAIN_KEY',''))>=32,'Relay signing secret not configured'
inputs={k:os.environ.get('INPUT_'+k.upper(),'') for k in ['root','generation','not_before','signature']}
a=authorize(os.environ['GITHUB_ACTOR'],os.environ['GITHUB_REPOSITORY_OWNER'],os.environ['CHAIN_KEY'],inputs,os.environ['GITHUB_RUN_ID'],time.time())
if a is None:
 api('PUT','/actions/workflows/runtime-cloud.yml/disable');output(active='false')
else:
 if a['not_before']>time.time():time.sleep(a['not_before']-time.time())
 output(active='true',root=a['root'],generation=a['generation'],slot_start=int(time.time()))
"""
claim_code=logic+"""
import os,subprocess
from pathlib import Path
def git(*args):return subprocess.run(['git',*args],check=True,capture_output=True,text=True,timeout=90).stdout.strip()
def output(value):
 with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('claimed='+value+'\\n')
assert not git('status','--porcelain'),'Dirty private state'
p=Path('relay-cursor.json');old=json.loads(p.read_text()) if p.exists() else None
new=claim(old,os.environ['ROOT_RUN'],int(os.environ['GENERATION']),os.environ['GITHUB_RUN_ID'],time.time(),os.environ.get('RESTART')=='true' and os.environ['GITHUB_ACTOR']==os.environ['GITHUB_REPOSITORY_OWNER'])
if new is None:output('false')
else:
 p.write_text(json.dumps(new,indent=2));git('config','user.name','OpenFeed Relay');git('config','user.email','openfeed@users.noreply.github.com');git('add','--','relay-cursor.json');git('commit','-m','Reserve bounded relay tick '+os.environ['GITHUB_RUN_ID']);git('push','origin','HEAD:shadow-state');output('true')
"""
relay=logic+header+"""
next_at=int(os.environ['SLOT_START'])+600
while time.time()<min(next_at,EXPIRY):time.sleep(min(20,min(next_at,EXPIRY)-time.time()))
if time.time()>=EXPIRY:api('PUT','/actions/workflows/runtime-cloud.yml/disable')
else:
 root=os.environ['ROOT_RUN'];generation=int(os.environ['GENERATION'])+1
 inputs={'root':root,'generation':str(generation),'not_before':str(next_at),'signature':signature(os.environ['CHAIN_KEY'],root,generation,next_at),'restart':'false'}
 for attempt in range(2):
  try:
   api('POST','/actions/workflows/runtime-cloud.yml/dispatches',{'ref':'main','inputs':inputs});break
  except (urllib.error.URLError,TimeoutError):
   if attempt:raise
   time.sleep(3)
"""
def python_block(s):return "python3 - <<'PYRELAY'\n"+s+"\nPYRELAY\n"
old=yaml.safe_load(Path('outputs/OpenFeed-cloud/runtime-cloud-48h.yml').read_text())
on=old.pop(True,None) or old.pop('on');on['workflow_dispatch']={'inputs':{k:{'type':'string','required':False,'default':''} for k in ['root','generation','not_before','signature']}};on['workflow_dispatch']['inputs']['restart']={'type':'boolean','default':False}
old['on']=on;old['name']='OpenFeed bounded automatic shadow';old['concurrency']['queue']='max';job=old['jobs']['shadow'];job['if']="github.ref == 'refs/heads/main' && (github.actor == github.repository_owner || github.actor == 'github-actions[bot]')"
steps=job['steps'];steps[0]={'name':'Verify signed owner relay and finite deadline','id':'deadline','env':{'GH_TOKEN':'${{ github.token }}','CHAIN_KEY':'${{ secrets.OPENFEED_RELAY_HMAC }}',**{'INPUT_'+k.upper():'${{ inputs.'+k+' }}' for k in ['root','generation','not_before','signature']}},'run':python_block(guard)}
claim_step={'name':'Claim a single private-state generation','id':'claim','if':"steps.deadline.outputs.active == 'true'",'working-directory':'runtime/private-state','env':{'ROOT_RUN':'${{ steps.deadline.outputs.root }}','GENERATION':'${{ steps.deadline.outputs.generation }}','RESTART':'${{ inputs.restart }}'},'run':python_block(claim_code)}
steps.insert(4,claim_step);steps[5]['if']="steps.deadline.outputs.active == 'true' && steps.claim.outputs.claimed == 'true'"
steps.append({'name':'Schedule the next signed cloud tick','if':"always() && steps.claim.outputs.claimed == 'true'",'env':{'GH_TOKEN':'${{ github.token }}','CHAIN_KEY':'${{ secrets.OPENFEED_RELAY_HMAC }}','ROOT_RUN':'${{ steps.deadline.outputs.root }}','GENERATION':'${{ steps.deadline.outputs.generation }}','SLOT_START':'${{ steps.deadline.outputs.slot_start }}'},'run':python_block(relay)})
class Dumper(yaml.SafeDumper):pass
Dumper.add_representer(str,lambda d,s:d.represent_scalar('tag:yaml.org,2002:str',s,style='|' if '\n' in s else None))
out=Path('outputs/OpenFeed-cloud/runtime-cloud-signed-relay.yml');out.write_text(yaml.dump(old,Dumper=Dumper,sort_keys=False,width=200))
for step in [steps[0],claim_step,steps[-1]]:
 body=step['run'].split("python3 - <<'PYRELAY'\n",1)[1].rsplit('\nPYRELAY',1)[0];compile(body,'workflow-inline','exec')
assert steps[5]['name']=='Run verified finite shadow only';assert old['permissions']['contents']=='read';assert old['concurrency']['cancel-in-progress'] is False
Path('work/cloud-evidence/relay-predeployment.json').write_text(json.dumps({'workflow_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'logic_sha256':hashlib.sha256(logic.encode()).hexdigest(),'bounded_expiry':1794053385,'interval_seconds':600,'new_secret':'OPENFEED_RELAY_HMAC','scope':'signed triggering only; no personal token, no public source/state/logs','logic_tests_passed':8,'all_inline_python_compiles':True},indent=2));print(out,len(out.read_bytes()))
