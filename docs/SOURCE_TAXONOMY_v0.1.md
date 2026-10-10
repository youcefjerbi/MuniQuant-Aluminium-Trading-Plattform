# SOURCE_TAXONOMY_v0.1

Priority: company publications, government, regulators, established industry/public bodies. Formats: HTML, PDF, structured CSV/API. No aggressive scraping or licensed access bypass.

Source governance fields: publisher, category, URL, approved hosts, acquisition method, access status, legal/access basis, retention/redistribution restrictions, reviewer, decision time . A public URL alone is not an access approval. review_required and restricted sources cannot be acquired. Synthetic fixtures remain clearly marked and do not count toward real coverage.

Document/version fields: title, original URL, source relation, publication timestamp (nullable with warning), retrieval timestamp, media type, SHA-256, storage reference, version and parser version. Every retrieval attempt records status, attempt number, error category and run identity without secrets.

Onboarding: classify source → document access basis → approve exact host/URL configuration → capture frozen fixture → verify bytes/hash → test adapter and locator → review candidate output → record source owner and maintenance policy. Target 5–10 source families after the pilot; three official source families have curator-approved bounded local-research capture policies in app.pilot; publisher redistribution licenses are not implied.
