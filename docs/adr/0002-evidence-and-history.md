# ADR 0002: Immutable snapshots and append-only observations

Status: accepted for v0.1.

Context: reports change and sources disagree; a mutable capacity column cannot preserve provenance.

Decision: retain SHA-256-addressed source bytes, version documents by source and original URL, and store each sourced value as a separate dated observation. Retain both reported and normalized representations. Shared bytes do not erase separate publisher identities.

Alternatives: storing URLs alone loses revised evidence; overwriting latest values loses history; full bitemporal SQL is deferred until concrete queries require it.

Consequences: database plus snapshot storage must be backed up together. Exports verify evidence bytes. ISO date strings are an initial portability choice; PostgreSQL-native dates and exact Decimal specialization records are now implemented; legacy ISO strings/floats remain compatibility representations.
