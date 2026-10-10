# End-to-end acceptance evidence

Technical demonstration completed 2026-10-10. Automated checks are distinct from independent human usability/sign-off. Recommended team cadence: 30-minute planning at cycle start, asynchronous work mid-cycle, 45–60-minute artifact demo at cycle end. The three role reports use Done/Evidence/Blockers/Decision/Next. No meetings or staff hours are invented.

| Step from PDF pp.20–21,27–28 | Demonstrated artifact |
|---|---|
| Select permitted source | Alcoa/Hydro/Rio Tinto audited exact-host policies |
| Retrieve real document | app.pilot retrieves seven configured official URLs; ten byte-distinct registered versions retained |
| Preserve evidence and hash | Original binary Portland PDF and HTML; SHA-256 snapshots |
| Register metadata | Source, access decision, document/version, date/URL/media and snapshot registries |
| Extract industrial fact | Portland page 1 nameplate 358,000 t/year; Hydro Husnes 2024 capacity 197,000 t/year |
| Resolve facility | Curated Portland/Husnes identities and aliases, no fuzzy auto-acceptance |
| Normalize attribute | Exact Decimal values in canonical t/year |
| Validate | Real pilot WARN: 13 warnings, zero BLOCK/ERROR; deliberately corrupt fixtures block export |
| Export package | Closed 1.0.0 JSON with three versioned capacity records and four ownership/operator relationships |
| Trace exact evidence | Every parsed record includes publisher, original URL, document ID/hash and page/text locator |
| Rerun frozen acquisition | evidence_cli replay reruns adapters against preserved bytes, offline |
| Reproduce logical output | Equivalent build hash 415879f2f8a9c5feae9f966947f9be1765b3dd1bb9d490141d7294296edf59e2 |
| Consumer independent of DB | scripts/consume_evidence.py validates schema and joins publisher/document/locator |

Other technical UAT: 50 difficult names preserve ambiguity; 500 labelled synthetic facilities and observations import/export correctly; simultaneous CSV imports retain one build/fact; populated legacy migrations preserve IDs, hashes, aliases and a high-precision reported value; individual review actors and read-only credentials are enforced; invalid units/date/value/hash/prohibited-field fixtures are rejected. These fixtures do not inflate real coverage.

Pilot coverage: 15 facilities / three countries / five companies / three source families. Only two facilities currently have capacity observations. Source revisions explain three parsed records. No global industry completeness, real closure/restart history, production throughput, SLA attainment or independent human acceptance is claimed.
