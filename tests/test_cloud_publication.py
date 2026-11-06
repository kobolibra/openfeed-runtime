import sys,json
from pathlib import Path
from datetime import datetime,timezone
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'ops'))
from cloud_publish import publication_intent

def test_shadow_cannot_publish_and_production_requires_cutover(tmp_path):
 assert publication_intent(tmp_path) is None
 p=tmp_path/'runtime-control.json';p.write_text(json.dumps({'mode':'shadow','publish_enabled':True}));assert publication_intent(tmp_path) is None
 p.write_text(json.dumps({'mode':'production','publish_enabled':True}))
 with pytest.raises(ValueError,match='stopped Mac'):publication_intent(tmp_path)

def test_publication_reserves_hour_and_respects_beijing_boundary(tmp_path):
 (tmp_path/'runtime-control.json').write_text(json.dumps({'mode':'production','publish_enabled':True,'mac_writer_stopped':True,'final_mac_snapshot_sha256':'a'*64}))
 now=datetime(2026,11,5,0,5,tzinfo=timezone.utc);intent=publication_intent(tmp_path,now);assert intent['slot']=='2026-11-05T08'
 (tmp_path/'publication-state.json').write_text(json.dumps({**intent,'result':'complete'}));assert publication_intent(tmp_path,now) is None
 assert publication_intent(tmp_path,datetime(2026,11,5,14,0,tzinfo=timezone.utc)) is not None
 assert publication_intent(tmp_path,datetime(2026,11,5,14,1,tzinfo=timezone.utc)) is None
 assert publication_intent(tmp_path,datetime(2026,11,5,23,0,tzinfo=timezone.utc)) is None
