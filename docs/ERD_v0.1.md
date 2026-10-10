# Implemented domain relationships

Gate 1 approved 2026-10-10; additive migrations preserve legacy external entity IDs. app/models.py and the migration chain are the precise schema source.

```mermaid
erDiagram
  ENTITIES ||--o| COMPANY : specializes
  ENTITIES ||--o| FACILITY : specializes
  ENTITIES ||--o{ ENTITY_ALIAS : names
  ENTITIES ||--o| ENTITY_SUPERSESSION : supersedes
  COUNTRY ||--o{ REGION : contains
  COUNTRY ||--o{ FACILITY : locates
  REGION ||--o{ FACILITY : locates
  FACILITY_TYPE ||--o{ FACILITY : classifies
  COMMODITY ||--o{ FACILITY : produces
  COMPANY ||--o{ COMPANY_FACILITY_RELATIONSHIP : owns_or_operates
  FACILITY ||--o{ COMPANY_FACILITY_RELATIONSHIP : has
  DOCUMENT_VERSION ||--o{ COMPANY_FACILITY_RELATIONSHIP : supports
  SOURCE ||--o{ SOURCE_ACCESS : governs
  SOURCE ||--o{ SOURCE_DOCUMENT_RELATION : publishes
  DOCUMENTS ||--o| DOCUMENT_VERSION : versions
  SOURCE_SNAPSHOT ||--o{ DOCUMENT_VERSION : preserves
  RUNS ||--o{ RETRIEVAL_ATTEMPT : logs
  DOCUMENTS ||--o{ OBSERVATIONS : supports
  FACILITY ||--o{ OBSERVATION_DETAIL : attributes
  OBSERVATIONS ||--|| OBSERVATION_DETAIL : exact_value_dates
  DOCUMENTS ||--o{ ENTITY_EVIDENCE : supports_identity
  ENTITIES ||--o{ ENTITY_EVIDENCE : traced_to
  DOCUMENTS ||--o{ EVIDENCE_BUILD : parses
  EVIDENCE_BUILD ||--o{ CANDIDATE : extracts
  REVIEWS ||--o{ CANDIDATE : audits
  ENTITIES ||--o{ REVIEWS : selects
```

Capacity/status are database views over attributed observations. Facility alias is a view over entity_alias. Known unit/attribute dimensions are database CHECK constraints; native normalized dates and exact decimals reside in observation_detail. Quality findings are recomputed from persisted evidence rather than treated as stale stored truth. Reviews hold one immutable final decision and audits hold candidate additions, aliases and mutations. Source/document versions intentionally retain the legacy document ID per version; source plus URL plus version is unique.
