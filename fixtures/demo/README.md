# Included demonstration database

`database.sql` is a complete SQLite database dump at the current migration head. It includes six fictional facilities, one example company, six capacity records, sourced relationships, identity evidence, and a deliberately pending name review. `snapshots/` contains the exact fictional source bytes. `manifest.json` verifies both the SQL and snapshots.

No credentials, real operational database, or third-party source copies are included. The real-source pilot remains reproducible with `python -m app.pilot`; PostgreSQL deployments use migrations and `python -m app.seed` rather than importing this SQLite-specific dump. Historical tables remain for migration compatibility and are not active application features.

From the repository root, after installing the application:

```sh
python scripts/restore_demo.py
export DATABASE_URL=sqlite:///data/demo.db
export SNAPSHOT_DIR=data/demo-snapshots
alembic check
export WRITE_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(24))')"
export WRITE_ACTOR=demo-curator
printf '%s\n' "$WRITE_TOKEN"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Enter your token in Workspace access. Resolve the pending review before exporting; the example company also has an explicit missing-identity-evidence warning. The restore command refuses existing paths, so it cannot replace your current database or evidence directory. Choose `--database` and `--snapshots` to install another copy.
