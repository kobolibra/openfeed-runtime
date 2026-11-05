import importlib.util
from pathlib import Path
import sqlite3
import pytest
from openfeed.storage import Store

SPEC=importlib.util.spec_from_file_location('restore_backup',Path(__file__).resolve().parents[1]/'tools'/'restore_backup.py')
module=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

def test_backup_offline_restore_preserves_database_and_refuses_overwrite(tmp_path):
    db=Store(str(tmp_path/'source.db'))
    backup=tmp_path/'backup.sqlite3';db.backup_to(str(backup));db.close()
    output=tmp_path/'restored.db'
    assert module.validate_snapshot(backup)['feeds']==0
    first=module.restore(backup,output)
    assert first['restored']==str(output) and output.exists()
    with pytest.raises(FileExistsError):module.restore(backup,output)
    second=module.restore(backup,output,replace=True)
    assert Path(second['recovery_copy']).exists()
    connection=sqlite3.connect(output)
    try:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:connection.close()
    with pytest.raises(FileExistsError):module.restore(backup,output,replace=True)

def test_restore_rejects_corrupt_unrecognized_and_active_wal(tmp_path):
    broken=tmp_path/'broken.db';broken.write_bytes(b'not a database')
    with pytest.raises(sqlite3.DatabaseError):module.validate_snapshot(broken)
    alien=tmp_path/'alien.db';sqlite3.connect(alien).close()
    with pytest.raises(ValueError,match='missing OpenFeed'):module.validate_snapshot(alien)
    valid=tmp_path/'valid.db';store=Store(str(valid));store.close()
    target=tmp_path/'dest.db';(tmp_path/'dest.db-wal').write_bytes(b'active')
    with pytest.raises(ValueError,match='WAL'):module.restore(valid,target)
    assert not target.exists()
