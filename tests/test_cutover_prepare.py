import sys,sqlite3,shutil
from pathlib import Path
import pytest
from openfeed.storage import Store
sys.path.insert(0,str(Path(__file__).parents[1]/'ops'))
from prepare_cutover import prepare

def inputs(tmp_path):
 a=tmp_path/'mac.db';b=tmp_path/'cloud.db';s=Store(str(a));f=s.create({'title':'A','source_url':'https://example.com/list','recipe':{}});s.finish(f,[{'title':'shared','url':'https://example.com/shared'}],None,1);s.close();shutil.copyfile(a,b);return a,b,f

def test_union_retains_mac_identity_and_cloud_provenance_without_writing_inputs(tmp_path):
 a,b,f=inputs(tmp_path)
 for path,name in [(a,'mac-only'),(b,'cloud-only')]:
  s=Store(str(path));s.finish(f,[{'title':name,'url':'https://example.com/'+name}],None,1);s.close()
 c=sqlite3.connect(b);c.execute("update items set first_seen_at='2026-01-02T00:00:00+00:00',last_seen_at='2099-01-01T00:00:00+00:00',title='newer' where url='https://example.com/shared'");c.commit();c.close()
 r=prepare(a,b,tmp_path/'stage');assert r['union_items']==3 and r['first_seen_conflicts_archived']==1 and r['mac_only']==r['cloud_only']==1 and r['input_databases_unchanged']
 c=sqlite3.connect(tmp_path/'stage/openfeed.sqlite3');assert c.execute("select title from items where url='https://example.com/shared'").fetchone()[0]=='newer';c.close()
 with pytest.raises(ValueError,match='must be new'):prepare(a,b,tmp_path/'stage')

@pytest.mark.parametrize('sql',["update feeds set schedule_phase_seconds=schedule_phase_seconds+1","update feeds set source_url='https://example.com/other'","update items set url='https://example.com/wrong'"])
def test_rejects_phase_scope_or_guid_url_conflict(tmp_path,sql):
 a,b,f=inputs(tmp_path);c=sqlite3.connect(b);c.execute(sql);c.commit();c.close()
 with pytest.raises(ValueError):prepare(a,b,tmp_path/'bad')
 assert not (tmp_path/'bad').exists()
