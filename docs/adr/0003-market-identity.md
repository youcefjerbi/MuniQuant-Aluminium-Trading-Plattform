# ADR 0003: Preserve distinct market observations

Status: accepted for v0.1; export contract remains draft.

Context: the market scope adds cash, futures, regional premiums and China alongside industrial reference data.

Decision: give market observations their own model, share document/source provenance, preserve decimal strings and source currencies, and require a concrete futures contract and prompt date. Each price type is a row.

Alternatives: one generic aluminium price loses maturity, region and price-type meaning; converting all prices to USD loses the source representation.

Consequences: no implicit currency conversion, continuous-contract construction, all-in price or prediction. Active/front selections are labels with dated concrete contracts. Licensed-provider onboarding is a separate delivery dependency.
