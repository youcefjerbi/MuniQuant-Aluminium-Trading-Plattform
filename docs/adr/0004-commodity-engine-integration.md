# ADR 0004: Integrate Commodity Engine capabilities into MuniQuant

Status: accepted on 3 October 2026.

## Context

MuniQuant is the project repository and already owns the browser UI, HTTP routes,
paper-trading module, UUID identities and Alembic history. Commodity Engine contains
stronger provenance, normalization, resolution, quality and export concepts, but
replacing the MuniQuant application wholesale would break existing consumers and
discard working product behavior.

## Decision

Keep MuniQuant as the authoritative modular monolith and port capabilities through
additive models, services, endpoints and one new migration:

- extend sources with acquisition, coverage, frequency and licence metadata;
- record source-access configuration separately from retrieval attempts, storing
  credential references rather than secrets;
- retain immutable document snapshots and add explicit SUCCESS, UNCHANGED and FAILED
  retrieval evidence;
- strengthen deterministic entity-name normalization and persist review candidate
  methods/scores;
- normalize governed unit aliases in Python while preserving reported value/unit;
- run versioned, persisted cross-record quality checks;
- expose observation-to-evidence trace and CEP v1 JSONL exports;
- represent supersession without changing existing UUIDs or rewriting history;
- keep the existing draft export byte-compatible at the schema boundary.

## Trade-offs

The implementation duplicates a small amount of normalization capability already
present in C++. This is intentional: Python owns governed aliases and dimensions,
while the compiled kernel remains available for stable numerical/name-distance
operations. Consolidate only after profiling and after the unit catalog is stable.

Quality runs are synchronous and the pilot workspace/export loads bounded result
sets into memory. That keeps transactions and failure behavior simple, but must be
replaced by batch jobs and pagination at production volume.

Supersession columns establish the storage contract but no correction/merge UI is
provided yet. Exposing that workflow before its authorization and review policy is
agreed would make accidental historical changes too easy.

The CEP v1 JSONL endpoint is additive. The older draft JSON package remains the
contract used by frozen bundles, avoiding a forced migration for current consumers.

## Consequences

MuniQuant gains the useful Commodity Engine behaviors without importing a second
application shell, database identity scheme or migration history. New deployments
must run migration `d8f4c2a91b07`. Existing routes, UI navigation, paper trading,
UUIDs and draft exports continue to work.
