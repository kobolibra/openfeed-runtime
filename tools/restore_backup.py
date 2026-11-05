"""Offline, fail-closed SQLite disaster recovery for OpenFeed Studio.

STOP the API and scheduler before running this command. A backup contains
feed IDs, content, and possibly sensitive source metadata.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

REQUIRED={'feeds','items','runs','feed_revisions'}

def validate_snapshot(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError('Backup must be a regular SQLite file')
    # Read-only URI avoids accidental backup file creation and mutation.
    from urllib.parse import quote
    connection=sqlite3.connect('file:'+quote(str(path.resolve()),safe='/')+'?mode=ro',uri=True)
    try:
        integrity=connection.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity!='ok':raise ValueError('SQLite backup failed integrity_check: '+str(integrity)[:100])
        tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not REQUIRED<=tables:raise ValueError('Backup is missing OpenFeed tables: '+', '.join(sorted(REQUIRED-tables)))
        broken=connection.execute('PRAGMA foreign_key_check').fetchone()
        if broken:raise ValueError('Backup contains invalid foreign keys')
        return {'feeds':connection.execute('SELECT count(*) FROM feeds').fetchone()[0],
                'items':connection.execute('SELECT count(*) FROM items').fetchone()[0]}
    finally:connection.close()

def restore(backup:Path,target:Path,*,replace:bool=False)->dict:
    backup=Path(backup).resolve();target=Path(target).absolute()
    if backup==target:raise ValueError('Backup and destination cannot be identical')
    report=validate_snapshot(backup)
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_symlink():raise ValueError('Destination may not be a symlink')
    if target.exists() and not replace:raise FileExistsError('Destination exists: explicitly use --replace')
    if any(Path(str(target)+suffix).exists() for suffix in ('-wal','-shm','-journal')):
        raise ValueError('Destination has SQLite WAL/SHM/journal files; stop the application and checkpoint first')
    # Keep a recovery copy of the current destination when replacing it.
    recovery=Path(str(target)+'.before-restore')
    if target.exists() and recovery.exists():raise FileExistsError('Existing recovery file would be overwritten')
    handle,temp=tempfile.mkstemp(prefix='.openfeed-restore-',dir=target.parent)
    os.close(handle)
    try:
        shutil.copyfile(backup,temp)
        validate_snapshot(Path(temp))
        os.chmod(temp,0o600)
        if target.exists():os.replace(target,recovery)
        try:os.replace(temp,target)
        except Exception:
            if recovery.exists():os.replace(recovery,target)
            raise
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return {'restored':str(target),'recovery_copy':str(recovery) if recovery.exists() else None,**report}

def main():
    parser=argparse.ArgumentParser(description='Offline OpenFeed SQLite restore; API must be stopped')
    parser.add_argument('backup',type=Path)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--replace',action='store_true',help='Replace existing stopped database and keep .before-restore copy')
    parser.add_argument('--execute',action='store_true',help='Perform the restore; without this flag only validate backup')
    args=parser.parse_args()
    result=restore(args.backup,args.destination,replace=args.replace) if args.execute else validate_snapshot(args.backup)
    print(result)
if __name__=='__main__':main()
