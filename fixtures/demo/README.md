# Included Workspace demonstration database

`database.sql` is the Workspace half of the platform's fictional demo: `tools/split.py` split the platform's bundled
demo (at revision `d8317b920a11`) into a Data Core and a Workspace database, and this is the Workspace one at the
Workspace migration head. It holds the old trading screens' shared practice account and empty research, lead,
investigation and map tables. `manifest.json` verifies it.

The demo's six fictional facilities, company, capacity records and source document went to the Data Core side;
the Data Core repository bundles exactly that database as its own demo. Restore both for the full demo:

```sh
# In the Data Core repository: restore, then start the Core (here on port 8000)
python scripts/restore_demo.py
DATABASE_URL=sqlite:///data/demo.db SNAPSHOT_DIR=data/demo-snapshots WRITE_TOKEN=... uvicorn app.main:app --port 8000

# In this repository: restore, then start the Workspace against that Core (here on port 8001)
python scripts/restore_demo.py
DATABASE_URL=sqlite:///data/demo.db SNAPSHOT_DIR=data/demo-snapshots CORE_URL=http://127.0.0.1:8000 CORE_TOKEN=... uvicorn app.main:app --port 8001
```

No credentials, real operational database or third-party source copies are included. The restore command refuses
existing paths, so it cannot replace your current database or snapshot directory.
