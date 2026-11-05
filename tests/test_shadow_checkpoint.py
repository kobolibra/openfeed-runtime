import hashlib,json,sqlite3
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec
import pytest
spec=spec_from_file_location('checkpoint',Path(__file__).parents[1]/'ops/shadow_checkpoint.py');m=module_from_spec(spec);spec.loader.exec_module(m)

def test_private_shadow_checkpoint_and_stale_rejection(tmp_path):
 state=tmp_path/'state.db';c=sqlite3.connect(state);c.execute('create table x (n)');c.commit();c.close()
 cycle=tmp_path/'cycle';cycle.mkdir();shadow=cycle/'shadow.sqlite3';shadow.write_bytes(state.read_bytes())
 report={'shadow_only':True,'input_db_unchanged':True,'input_sha256':hashlib.sha256(state.read_bytes()).hexdigest()};(cycle/'report.json').write_text(json.dumps(report))
 c=sqlite3.connect(shadow);c.execute('insert into x values (1)');c.commit();c.close()
 report['shadow_sha256']=hashlib.sha256(shadow.read_bytes()).hexdigest();(cycle/'report.json').write_text(json.dumps(report))
 meta=m.promote(state,cycle,'test');assert meta['scope'].startswith('private shadow')
 c=sqlite3.connect(state);assert c.execute('select * from x').fetchall()==[(1,)];c.close()
 with pytest.raises(ValueError,match='State changed'):m.promote(state,cycle,'stale')


def test_checkpoint_rejects_tampered_candidate(tmp_path):
 state=tmp_path/'state.db';c=sqlite3.connect(state);c.execute('create table x (n)');c.commit();c.close()
 cycle=tmp_path/'cycle';cycle.mkdir();shadow=cycle/'shadow.sqlite3';shadow.write_bytes(state.read_bytes())
 report={'shadow_only':True,'input_db_unchanged':True,'input_sha256':hashlib.sha256(state.read_bytes()).hexdigest(),'shadow_sha256':hashlib.sha256(shadow.read_bytes()).hexdigest()}
 (cycle/'report.json').write_text(json.dumps(report))
 before=state.read_bytes();c=sqlite3.connect(shadow);c.execute('insert into x values (1)');c.commit();c.close()
 with pytest.raises(ValueError,match='Candidate hash'):m.promote(state,cycle,'tampered')
 assert state.read_bytes()==before
