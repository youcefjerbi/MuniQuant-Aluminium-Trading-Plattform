# ERD_v0.1 — proposed, Gate 1 pending

```mermaid
erDiagram
  EXTERNAL_ENTITY ||--o| COMPANY : specializes
  EXTERNAL_ENTITY ||--o| FACILITY : specializes
  EXTERNAL_ENTITY ||--o{ ENTITY_ALIAS : names
  EXTERNAL_ENTITY ||--o{ ENTITY_SUPERSESSION : retains_history
  COUNTRY ||--o{ REGION : contains
  COUNTRY ||--o{ FACILITY : locates
  REGION ||--o{ FACILITY : locates
  FACILITY_TYPE ||--o{ FACILITY : classifies
  COMMODITY ||--o{ FACILITY_PRODUCT : identifies
  FACILITY ||--o{ FACILITY_PRODUCT : produces
  COMPANY ||--o{ COMPANY_FACILITY_RELATIONSHIP : owns_or_operates
  FACILITY ||--o{ COMPANY_FACILITY_RELATIONSHIP : has
  DOCUMENT_VERSION ||--o{ COMPANY_FACILITY_RELATIONSHIP : supports
  SOURCE ||--o{ SOURCE_ACCESS : governs
  SOURCE ||--o{ SOURCE_DOCUMENT_RELATION : publishes
  DOCUMENT ||--o{ SOURCE_DOCUMENT_RELATION : originates
  DOCUMENT ||--o{ DOCUMENT_VERSION : versions
  SOURCE_SNAPSHOT ||--o{ DOCUMENT_VERSION : preserves
  ACQUISITION_RUN ||--o{ RETRIEVAL_ATTEMPT : logs
  DOCUMENT_VERSION ||--o{ ATTRIBUTE_OBSERVATION : supports
  FACILITY ||--o{ ATTRIBUTE_OBSERVATION : has
  UNIT ||--o{ ATTRIBUTE_OBSERVATION : normalizes
  RESOLUTION_CANDIDATE ||--o{ REVIEW_DECISION : audits
  EXTERNAL_ENTITY ||--o{ REVIEW_DECISION : selects
  ATTRIBUTE_OBSERVATION ||--o{ QUALITY_FINDING : validates
```

All relationships above are proposed foreign keys; run manifests also preserve parser version and input hashes. Capacity and status are constrained specializations of attributed observations. Supersession does not delete historical IDs. Preserve baseline IDs through additive migrations; no production tables are created in this Gate 1 proposal.
