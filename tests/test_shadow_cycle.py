import hashlib,json,os,sqlite3,subprocess,sys
from pathlib import Path
from openfeed.storage import Store
ROOT=Path(__file__).resolve().parents[1]

def setup(tmp):
 db=tmp/'input.db';s=Store(str(db));f=s.create({'title':'A','source_url':'https://example.com/list','recipe':{'item_selector':'article','fields':{'title':'h2','link':'a@href'}}})
 s.finish(f,[{'title':'Old','url':'https://example.com/old'}],None,1);s.close()
 body=tmp/'body.html';body.write_text('<article><h2>New</h2><a href="/new">New</a></article>')
 key=json.dumps({'url':f['source_url'],'options':{}},sort_keys=True);mapping=tmp/'fixtures.json';mapping.write_text(json.dumps({key:{'path':'body.html'}}))
 return db,f,mapping

def invoke(db,f,out,mapping,mode='fixtures'):
 env={**os.environ,'OPENFEED_DB':'/must/not/open/production.sqlite','OPENFEED_ENABLE_SCHEDULER':'1'}
 return subprocess.run([sys.executable,str(ROOT/'ops/run_cycle.py'),'--input-db',str(db),'--output',str(out),'--mode',mode,'--fixtures',str(mapping),'--feed-id',f['id']],env=env,capture_output=True,text=True)

def test_fixture_refresh_exports_real_rss_without_touching_input(tmp_path):
 db,f,m=setup(tmp_path);before=db.read_bytes();out=tmp_path/'shadow'
 r=invoke(db,f,out,m);assert r.returncode==0,r.stderr
 report=json.loads((out/'report.json').read_text());assert report['results'][0]['result']['status']=='success'
 assert db.read_bytes()==before
 c=sqlite3.connect(out/'shadow.sqlite3');assert c.execute('select count(*) from items').fetchone()[0]==2;c.close()
 rss=(out/'rss'/(f['id']+'.xml')).read_text();assert 'New' in rss and 'Old' in rss
 assert report['published'] is False

def test_plan_never_fetches_and_existing_output_is_rejected(tmp_path):
 db,f,m=setup(tmp_path);out=tmp_path/'shadow';m.write_text('{}')
 r=invoke(db,f,out,m,'plan');assert r.returncode==0,r.stderr
 assert json.loads((out/'report.json').read_text())['results'][0]['result']['status']=='planned'
 assert not (out/'rss').exists()
 r=invoke(db,f,out,m);assert r.returncode!=0 and 'NEW directory' in r.stderr

def test_missing_capture_fails_closed_and_keeps_history(tmp_path):
 db,f,m=setup(tmp_path);m.write_text('{}');out=tmp_path/'shadow';r=invoke(db,f,out,m);assert r.returncode==0,r.stderr
 report=json.loads((out/'report.json').read_text());assert report['results'][0]['result']['status']=='error'
 c=sqlite3.connect(out/'shadow.sqlite3');assert c.execute('select count(*) from items').fetchone()[0]==1;c.close()

def test_429_creates_persistent_cooldown_in_shadow_only(tmp_path):
 db,f,m=setup(tmp_path);d=json.loads(m.read_text());key=next(iter(d));d[key]={'error':429,'retry_after':'600'};m.write_text(json.dumps(d));out=tmp_path/'shadow';r=invoke(db,f,out,m);assert r.returncode==0,r.stderr
 c=sqlite3.connect(out/'shadow.sqlite3');assert c.execute('select count(*) from domain_cooldowns').fetchone()[0]==1;c.close()
 c=sqlite3.connect(db);assert c.execute('select count(*) from domain_cooldowns').fetchone()[0]==0;c.close()

def configured(tmp,recipe):
 db=tmp/'input.db';s=Store(str(db));f=s.create({'title':'Shadow contract','source_url':'https://example.com/list','recipe':recipe})
 s.finish(f,[{'title':'Old','url':'https://example.com/old'}],None,1);s.close()
 m=tmp/'fixtures.json';m.write_text('{}');return db,f,m

def test_three_post_pages_and_repeat_preserve_guid_and_first_seen(tmp_path):
 recipe={'mode':'json','item_selector':'data','fields':{'title':'headline','link':'url'},'request_method':'POST','request_json':{'q':'China','from':1},'json_contract':{'success':True,'parameters.q':'China'},'json_offset_field':'from','json_offset_response_path':'parameters.from','json_page_step':2,'max_pages':3}
 db,f,m=configured(tmp_path,recipe);mapping={}
 for n,rows in [(1,[1,2]),(3,[2,3]),(5,[5])]:
  body=tmp_path/f'p{n}.json';body.write_text(json.dumps({'success':True,'parameters':{'q':'China','from':n},'data':[{'headline':f'Article {i}','url':f'https://example.com/{i}'} for i in rows]}))
  key=json.dumps({'url':f['source_url'],'options':{'method':'POST','json_data':{'q':'China','from':n},'public_api_key':''}},sort_keys=True)
  mapping[key]={'path':body.name}
 m.write_text(json.dumps(mapping));out=tmp_path/'first';r=invoke(db,f,out,m);assert r.returncode==0,r.stderr
 report=json.loads((out/'report.json').read_text());assert report['results'][0]['result']['found']==4
 first=sqlite3.connect(out/'shadow.sqlite3');identity=first.execute('select guid,first_seen_at from items order by guid').fetchall();phase=first.execute('select schedule_phase_seconds from feeds').fetchone();first.close()
 # Immediate restart must retain the global start gap rather than fetch again.
 blocked=tmp_path/'blocked';r=invoke(out/'shadow.sqlite3',f,blocked,m);assert r.returncode==0,r.stderr
 d=json.loads((blocked/'report.json').read_text());assert d['results']==[] and d['deferred'][0]['reason']=='global_start_gap'
 # After the global gap but inside the domain gap, the domain guard applies.
 c=sqlite3.connect(out/'shadow.sqlite3');c.execute('update shadow_cycle_starts set started=started-61');c.commit();c.close()
 blocked=tmp_path/'domain-blocked';r=invoke(out/'shadow.sqlite3',f,blocked,m);assert r.returncode==0,r.stderr
 d=json.loads((blocked/'report.json').read_text());assert d['results']==[] and d['deferred'][0]['reason']=='domain_start_gap'
 # Controlled elapsed time: a later cycle may fetch without duplicate entries.
 c=sqlite3.connect(out/'shadow.sqlite3');c.execute('update shadow_cycle_starts set started=started-301');c.commit();c.close()
 again=tmp_path/'second';r=invoke(out/'shadow.sqlite3',f,again,m);assert r.returncode==0,r.stderr
 second=sqlite3.connect(again/'shadow.sqlite3');assert second.execute('select guid,first_seen_at from items order by guid').fetchall()==identity
 assert second.execute('select schedule_phase_seconds from feeds').fetchone()==phase;second.close()
 assert json.loads((again/'report.json').read_text())['results'][0]['result']['inserted']==0
 assert f['id'] in json.loads((again/'manifest.json').read_text())

def test_browser_fixture_requires_exact_wait_selector(tmp_path):
 db,f,m=configured(tmp_path,{'fetch_mode':'browser','wait_selector':'article','item_selector':'article','fields':{'title':'h2','link':'a@href'}})
 (tmp_path/'browser.html').write_text('<article><h2>Browser result</h2><a href="/browser">Read</a></article>')
 key=json.dumps({'url':f['source_url'],'options':{'wait_selector':'article'}},sort_keys=True)
 m.write_text(json.dumps({key:{'path':'browser.html'}}));out=tmp_path/'browser';r=invoke(db,f,out,m);assert r.returncode==0,r.stderr
 assert json.loads((out/'report.json').read_text())['results'][0]['result']['status']=='success'
 # A browser capture is not an HTTP capture and cannot fall back to HTTP.
 m.write_text(json.dumps({json.dumps({'url':f['source_url'],'options':{}},sort_keys=True):{'path':'browser.html'}}))
 out=tmp_path/'wrong';r=invoke(db,f,out,m);assert r.returncode==0,r.stderr
 assert json.loads((out/'report.json').read_text())['results'][0]['result']['status']=='error'

def test_deadline_during_pagination_keeps_committed_history_and_schedule(tmp_path):
 db,f,m=configured(tmp_path,{'max_pages':2,'next_selector':'a.next','item_selector':'article','fields':{'title':'h2','link':'a@href'}})
 (tmp_path/'page.html').write_text('<article><h2>Partial</h2><a href="/partial">Read</a></article><a class="next" href="/page2">Next</a>')
 m.write_text(json.dumps({json.dumps({'url':f['source_url'],'options':{}},sort_keys=True):{'path':'page.html'}}))
 out=tmp_path/'cancelled'
 r=subprocess.run([sys.executable,str(ROOT/'ops/run_cycle.py'),'--input-db',str(db),'--output',str(out),'--mode','fixtures','--fixtures',str(m),'--feed-id',f['id'],'--budget-seconds','0.1'],capture_output=True,text=True)
 assert r.returncode==0,r.stderr
 assert json.loads((out/'report.json').read_text())['results'][0]['result']['status']=='cycle_deadline'
 for path in [db,out/'shadow.sqlite3']:
  c=sqlite3.connect(path);assert c.execute('select count(*) from items').fetchone()[0]==1
  assert c.execute('select count(*) from runs').fetchone()[0]==1;c.close()


def test_same_host_report_explains_deferred_sources(tmp_path):
 db,f,m=setup(tmp_path);s=Store(str(db));other=s.create({'title':'B','source_url':'https://example.com/other','recipe':{}});s.close()
 out=tmp_path/'plan'
 r=subprocess.run([sys.executable,str(ROOT/'ops/run_cycle.py'),'--input-db',str(db),'--output',str(out),'--feed-id',f['id'],'--feed-id',other['id']],capture_output=True,text=True)
 assert r.returncode==0,r.stderr
 d=json.loads((out/'report.json').read_text());assert len(d['selected'])==1
 assert len(d['deferred'])==1 and d['deferred'][0]['reason']=='same_host'
 assert len(d['next_schedule'])==2
