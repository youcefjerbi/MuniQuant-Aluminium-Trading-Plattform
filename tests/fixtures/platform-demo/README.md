# The platform's bundled demo, at the split

`database.sql` is the platform's bundled fictional demo (`fixtures/demo` at platform commit `26a0bcd`) after the
platform's own restore and `alembic upgrade head`, so at revision `d8317b920a11`, the revision the split tool
reads. `snapshots/` holds its one fictional source document; `manifest.json` gives the SHA-256 of every file.
`tests/test_split.py` splits it (DC1 step B3, "works on the demo data").
