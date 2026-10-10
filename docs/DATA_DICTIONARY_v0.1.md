# DATA_DICTIONARY_v0.1 — proposed

| Field/domain | Meaning / invariant |
|---|---|
| external_entity_id | Stable upstream ID; not private MEI authoritative identity |
| company / facility | Company or industrial physical site; not a security/instrument |
| facility_type | bauxite mine, alumina refinery, primary aluminium smelter |
| country / region | Controlled geographic references; ISO country code |
| commodity / product | Controlled aluminium-chain product references |
| alias | Name linked to entity, provenance and audit; collisions allowed, not silently merged |
| ownership / operator | Separate sourced dated roles; owner need not equal operator |
| reported_value / unit | Exact sourced value and original dimensional unit |
| normalized_value / unit | Decimal standardized value; t/year, MW or percentage according to dimension; no implicit dimension conversion |
| valid_from / valid_to | Native date validity interval; end cannot precede start; conflicting vintages retained |
| published_at | Source publication timestamp/date; missing value warns |
| retrieved_at | UTC acquisition timestamp, distinct from validity and publication |
| source_id / document_id | Required provenance references in candidate export |
| content_hash | SHA-256 of exact acquired bytes, verified before export |
| evidence_reference | Page/table/row/section locator supporting the attribute |
| resolution_status | Exact/normalized/alias unique match or audited manual decision; candidate/ambiguous cannot become trusted automatically |
| quality_status | PASS/WARN/FAIL, derived from machine-readable findings |
| severity | INFO/WARN/ERROR/BLOCK; BLOCK excludes candidate export |
| pipeline_version / parser_version | Versioned acquisition and extraction transformations |
| package_version | Draft until Gate 5; breaking frozen contract change increments version |

Baseline differs: one entities table, JSON aliases, string dates, capacity float, combined document/version and draft nested exports. These are explicitly implementation gaps, not fulfilled normalized-schema requirements.
