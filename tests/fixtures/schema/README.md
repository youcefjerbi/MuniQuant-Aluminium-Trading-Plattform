# Today's platform tables that move to the Workspace

`today-sqlite.json` and `today-postgresql.json` describe, exactly as the platform's migrations create them on
2026-10-21 (platform commit `26a0bcd`, revision `d8317b920a11`, SQLite and PostgreSQL 16; PostgreSQL 17 gives the
identical description):

- the Workspace tables: leads, research and practice trading, investigations, the map and the old trading screens;
- the platform tables whose licensed lead-feed rows move to the Workspace's lead store (`sources`, `source_access`,
  `source_snapshot`, `documents`, `document_version`, `source_document_relation`, `runs`, `retrieval_attempt`) and
  `audit`;
- on PostgreSQL, the triggers on these tables.

They were produced with `describe()` in `tests/test_schema.py` after `alembic upgrade head` in the platform
repository at that commit. `test_baseline_matches_todays_platform_tables` compares the Workspace baseline with them;
the only allowed differences are listed in that test and in the baseline migration's docstring.
