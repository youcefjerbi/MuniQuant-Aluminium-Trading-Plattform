# Manual review operating policy

Sponsor-authorized pilot policy, 2026-10-10. The service target is triage within two business days; source-rights and identity conflicts are escalated to the project owner within one business day. These targets describe future team operations, not elapsed performance.

Categories: alias/name normalization; same name in different countries; same name at multiple sites; company-versus-facility confusion; absent canonical identity; superseded identity; conflicting source/date; access or provenance failure.

A reviewer must inspect exact source bytes and locator, country, facility class, company/site distinction and dated context. Fuzzy distance alone never justifies acceptance. Select a recorded candidate only after corroboration; if the site is missing, create the curated identity, attach it to the review with a source-based reason, then decide. Extracted candidates require facility kind and reported country to agree. Reject candidates when evidence cannot identify a safe match. Rejection is preserved in frozen recipes.

The server records individual reviewer credentials, reason, time, selected identity and audit entry. Final decisions cannot be overwritten. Acceptance of an extracted candidate creates its observation and an audited alias in the same transaction. Adding a candidate is separately audited. Supersession retains original IDs and cannot create cycles; never rewrite historic evidence silently.

BLOCK/ERROR findings prohibit export. Correct source/input configuration, resolve/reject candidates, or restore exact missing bytes. WARN requires documented curator consideration; conflicting facts remain distinct. INFO is informational. Restricted/review-required access stops capture and export of affected evidence. No licensing dispute is resolved by technical success.
