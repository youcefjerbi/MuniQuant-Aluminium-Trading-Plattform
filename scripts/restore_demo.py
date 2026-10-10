"""Restore the bundled fictional SQLite demo without overwriting existing data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=Path('data/demo.db'))
    parser.add_argument('--snapshots', type=Path, default=Path('data/demo-snapshots'))
    args = parser.parse_args()
    if args.database.exists() or args.snapshots.exists():
        parser.error('Destination already exists. Choose new paths; existing data is never replaced.')
    source = Path(__file__).resolve().parents[1] / 'fixtures' / 'demo'
    manifest = json.loads((source / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        path = (source / name).resolve()
        if not path.is_relative_to(source.resolve()):
            parser.error('Invalid fixture path')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            parser.error('Fixture checksum mismatch: ' + name)
    args.database.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix='.demo-', suffix='.db', dir=args.database.parent)
    os.close(handle)
    created_snapshots = False
    try:
        with sqlite3.connect(temporary) as database:
            database.executescript((source / 'database.sql').read_text())
            if database.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Demo database integrity check failed')
            if database.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Demo database contains broken references')
        args.snapshots.mkdir(parents=True, exist_ok=False)
        created_snapshots = True
        for snapshot in (source / 'snapshots').iterdir():
            if snapshot.is_file():
                shutil.copy2(snapshot, args.snapshots / snapshot.name)
        # An exclusive hard link also protects against another process creating the target.
        os.link(temporary, args.database)
    except Exception:
        if created_snapshots:
            shutil.rmtree(args.snapshots)
        raise
    finally:
        Path(temporary).unlink(missing_ok=True)
    print('Restored fictional demo database:', args.database)
    print('Preserved evidence snapshots:', args.snapshots)

if __name__ == '__main__':
    main()
