import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ops'))
import sqlite3,shutil,json
import pytest
from local_cloud_sync import Store,configs,apply_edits
@pytest.fixture
def source(tmp_path):
 p=tmp_path/'original.sqlite3';s=Store(str(p));f=s.create({'title':'Test','source_url':'https://example.org/','recipe':{},'interval_minutes':720});s.close();return p,f['id']
def test_preserves_cloud_new_history_while_editing_title(source,tmp_path):
 p,i=source;base=configs(p);local=json.loads(json.dumps(base));local[i]['title']='Updated';s=Store(str(p));s.db.execute("insert into items (feed_id,guid,title,url,summary,first_seen_at,last_seen_at) values (?,?,?,?,?,?,?)",(i,'g','Article','https://example.org/a','','2026-11-06T00:00:00+00:00','2026-11-06T00:00:00+00:00'));s.close();out=tmp_path/'candidate.sqlite3';apply_edits(p,base,local,out);assert configs(out)[i]['title']=='Updated';c=sqlite3.connect(out);assert c.execute('select guid from items').fetchall()==[('g',)]
def test_conflicting_cloud_edit_refused(source,tmp_path):
 p,i=source;base=configs(p);local=json.loads(json.dumps(base));local[i]['title']='Local';s=Store(str(p));s.update(i,{'title':'Cloud'});s.close()
 with pytest.raises(ValueError,match='concurrently'):apply_edits(p,base,local,tmp_path/'out.sqlite3')
def test_create_preserves_ui_identifier_and_delete_is_explicit(source,tmp_path):
 p,i=source;base=configs(p);ident='a'*28;local={ident:{**base[i],'title':'New'}};out=tmp_path/'out.sqlite3';changed,deleted=apply_edits(p,base,local,out);assert set(configs(out))=={ident};assert deleted==[i]
def test_accepted_edit_can_be_replayed_after_lost_response(source,tmp_path):
 p,i=source;base=configs(p);local=json.loads(json.dumps(base));local[i]['title']='Updated';a=tmp_path/'a.sqlite3';apply_edits(p,base,local,a);b=tmp_path/'b.sqlite3';apply_edits(a,base,local,b);assert configs(a)==configs(b)
def test_management_wait_never_disables_cloud_schedule():
 from local_cloud_sync import GitHub
 g=GitHub.__new__(GitHub);calls=[]
 def call(repo,method,path,**kwargs):
  calls.append((method,path))
  if '/runs?' in path:return {'workflow_runs':[{'id':1,'status':'in_progress'}]}
  return {'jobs':[{'steps':[{'name':'Run validated bounded production state','status':'completed'}]}]}
 g.call=call;g.pause();g.resume();assert all(m=='GET' for m,_ in calls)
def test_same_source_edit_refuses_fetch_identity_change_with_history(source,tmp_path):
 p,i=source;base=configs(p);local=json.loads(json.dumps(base));local[i]['source_url']='https://other.example/'
 s=Store(str(p));s.db.execute("insert into items (feed_id,guid,title,url,summary,first_seen_at,last_seen_at) values (?,?,?,?,?,?,?)",(i,'g','Article','https://example.org/a','','2026-11-06T00:00:00+00:00','2026-11-06T00:00:00+00:00'));s.close()
 with pytest.raises(ValueError,match='identity'):apply_edits(p,base,local,tmp_path/'out.sqlite3')
