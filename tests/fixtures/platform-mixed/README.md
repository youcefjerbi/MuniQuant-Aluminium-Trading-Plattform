# A platform database with every kind of record

Made on 2026-10-21 by `generate.py` running the platform's own code at commit `26a0bcd` (revision `d8317b920a11`),
all through the platform API. Fictional only, no licensed data:

- Data Core records: two plants, a company, a source, an operator update, a status fact and an ownership link;
- the licensed lead feed (Permutable): its source and access decision, three synthetic vendor responses (events,
  headlines, a reference response) with their saved copies, capture runs and attempt logs, and one lead with a
  revision and a headline, confirmed with the operator update and its fact;
- research events linked through the ownership link, an investigation with an evidence entry citing the operator
  update and a note citing a vendor response, and a map location and dependency.

`tests/test_split.py` splits it (DC1 step B3, "Permutable material goes to the Workspace side"). Regenerate only if
the fixture itself must change, from a checkout of the platform at `26a0bcd` with the native module built:

```sh
python /path/to/tests/fixtures/platform-mixed/generate.py /tmp/platform-mixed
```

Then copy `database.sql` and `snapshots/` here and rewrite `manifest.json`. IDs and times change on every run.
