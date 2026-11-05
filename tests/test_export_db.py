import hashlib,sys
from pathlib import Path
from xml.etree import ElementTree as ET
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'ops'))
from export_db import export_db,semantic_hash
from openfeed.storage import Store

def test_database_export_preserves_error_history_and_public_whitelist(tmp_path):
 db=tmp_path/'private.sqlite3';s=Store(str(db));f=s.create({'title':'Private source','source_url':'https://example.com/news','recipe':{}})
 s.finish(f,[{'title':'Retained article','url':'https://example.com/old'}],None,1);s.finish(s.get(f['id']),[],'Network failed',1);s.close()
 before=db.read_bytes();out=tmp_path/'public';report=export_db(db,out,'https://kobolibra.github.io/openfeed-feeds');assert db.read_bytes()==before
 assert {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file()}=={'.nojekyll','subscriptions.opml','rss/'+f['id']+'.xml'}
 raw=(out/'rss'/(f['id']+'.xml')).read_bytes();assert b'Retained article' in raw
 assert report['files'][f['id']]['status']=='error' and report['published'] is False
 root=ET.fromstring((out/'subscriptions.opml').read_bytes());assert root.find('./body/outline').get('xmlUrl').endswith('/rss/'+f['id']+'.xml')
 with pytest.raises(ValueError,match='fresh'):export_db(db,out,'https://example.com')

def test_semantic_hash_ignores_only_refresh_stamp():
 a=b'<rss><channel><lastBuildDate>old</lastBuildDate><item><guid>x</guid><title>A</title></item></channel></rss>'
 assert semantic_hash(a)==semantic_hash(a.replace(b'old',b'new'))
 assert semantic_hash(a)!=semantic_hash(a.replace(b'<title>A',b'<title>B'))
