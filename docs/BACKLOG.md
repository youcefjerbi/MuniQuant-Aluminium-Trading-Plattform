# Remaining acceptance work

Implementation was approved on 2026-10-10. Weekly reports describe completed code against all twelve requirement allocations. Remaining work is not hidden by the application release-candidate label.

| Priority | Remaining acceptance | Owner |
|---|---|---|
| P0 | Independent consumer accepts the closed 1.0.0 contract using frozen pilot artifact (Gate 5) | PM / consumer |
| P0 | Sponsor accepts final demonstration and operational handover (Gate 6) | PM / sponsor |
| P0 before shared hosting | Enable optional read authorization/TLS, secret lifecycle, reviewer onboarding and monitored coordinated PostgreSQL/snapshot restore | SE2 / operations |
| P1 | Broaden to recommended 50–100 meaningful facilities and 5–10 permitted source families; verify legal company metadata | PM / SE1 |
| P1 | Curate real historical effective-date changes and multiple capacity/status facts per asset; retain conflicting vintages | SE1 / PM |
| P1 | Independent curator usability review and deployment-specific performance thresholds (50-name, concurrent import and 500-record correctness checks are delivered) | SE1 / SE2 / PM |
| P1 | Add source-specific parsers for complex tables/OCR only with justified scope; review copyright/retention before redistribution | SE2 / PM |
| P1 | Optional scheduled acquisition cadence, host budgets and operational alarms (durable failed-parser logs are delivered) | SE2 |
| P2 | Extend the UI beyond its 1,000-record initial view using the delivered paginated records API | SE2 |

Protect provenance, hashing, identity, validation, contract and reproducibility ahead of dashboard breadth. No downstream/trading additions are authorized by this backlog.
