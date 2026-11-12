# Shared event format (draft v0.1)

Status: **draft for agreement**, 10 Nov 2026. From: Aleks (research track). For: Orhun, Jacob & Pau (event library),
Batu, and the research track.

On 6 Oct both teams agreed on one event schema, so the research event database can feed the game's event generation
(CONTEXT §1, "Research link"; open decision 7 in CONTEXT §6). This draft turns the proposal in §6 into a record both
sides can read and write, and maps the research platform's event kinds to the game's 12 event types. This is the
only copy: it lives in the research platform's repository because both teams can read it here, and the simulator
repository (`muniquant-finals-sim`) links to it. Change it here, by pull request. The Europe list in the mapping is
also the `EUROPE` set of the simulator's plant headlines (`sim/plant_headlines.py`); change them together.

## The record

One event per record, as JSON lines (`events.jsonl`). The game's `events.csv` keeps its three columns
(`timestamp,type,direction`); `timestamp` there is `available_at` here.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string | yes | Stable across reruns: `<source>:<key>[:<revision>]`, e.g. `permutable:trade_policy:2025-02-10` |
| `type` | string or null | yes | One of the game's event types (`sim/catalog.py`); null when none fits (kept for research, unused by the game) |
| `available_at` | UTC ISO 8601 | yes | When the news was first known (first headline). Event studies and backtests use this time, so no later news leaks in |
| `occurred_at` | UTC ISO 8601 or null | no | When it happened, if the source says; never after `available_at` |
| `direction` | +1, -1 or null | yes | Expected effect on the aluminium price (+1 = up). Null when unknown |
| `source` | string | yes | `permutable`, `workspace`, `core`, `organiser` or `synthetic` |
| `source_ref` | string | yes | The source's own reference: Permutable topic and day, Workspace event id, Core document id |
| `source_topic` | string | no | Permutable topic name |
| `headline` | string | no | Text shown to players; game headlines follow the rules in `sim/headlines.py` (no real company names, no numbers that suggest a size) |
| `countries` | list of ISO 3166-1 alpha-2 | no | Countries involved |
| `plants` | list of Core entity ids | no | Facilities involved (Data Core `external_entity_id`) |
| `tags` | list of lowercase strings | no | Free tags, e.g. `new_capacity`, `power`, `export_ban` |
| `n_headlines`, `sentiment_surprise` | number | no | Permutable-derived, game side only |
| `confidence` | 0 to 1 | no | How sure the `type` and `direction` are: 1 = set by the organiser, lower for a rule-based mapping |

Who fills what:

- **Direction.** The game takes it from Permutable's sentiment surprise (`sim/permutable.py`) or from the organiser.
  The research platform stores Permutable events and headlines as leads only and never reads vendor sentiment, impact
  or signal fields, so its records leave `direction` null unless a curator sets it.
- **Plants and countries.** The research side links events to Data Core plants (facility type, country, owners), which
  is what decides between several game types below.

## Research kind → game type

The research platform's events have one of ten kinds. First matching row wins; "linked plant" is a Core facility in
`plants`.

| Research kind | Condition | Game type |
|---|---|---|
| `supply` | tag `new_capacity` | `new_supply` |
| `supply` | a linked plant is a smelter | `smelter_outage` |
| `supply` | a linked plant is a bauxite mine | `bauxite_disruption` |
| `supply` | a linked plant is an alumina refinery | `alumina` |
| `supply` | country `CN`, no linked plant | `china_output` |
| `energy` | a European country (EU, `NO`, `IS`, `GB`, `CH`) | `energy_europe` |
| `energy` | a linked smelter elsewhere | `smelter_outage` |
| `weather`, `logistics` | a linked bauxite mine | `bauxite_disruption` |
| `weather`, `logistics` | a linked alumina refinery | `alumina` |
| `weather` | a linked smelter | `smelter_outage` |
| `policy` | country `CN` | `china_policy` |
| `policy`, `sanction` | otherwise | `trade_policy` |
| `conflict` | – | `geopolitics` |
| `demand` | – | `demand` |
| `corporate` | tag `new_capacity` | `new_supply` |
| any other | – | null (research only) |

Two game types have no research kind and are set by the organiser or from Permutable: `lme_stocks` (scheduled stock
reports) and `macro_usd` (central banks, the US dollar).

## Game type → research kind

For research bots that read the game's news on practice rounds: `lme_stocks` → `other`, `china_output` → `supply`,
`china_policy` → `policy`, `trade_policy` → `policy`, `energy_europe` → `energy`, `smelter_outage` → `supply`,
`bauxite_disruption` → `supply`, `alumina` → `supply`, `macro_usd` → `other`, `demand` → `demand`, `new_supply` →
`supply` (tag `new_capacity`), `geopolitics` → `conflict`. Game prices and events go under the research instrument
`LME_AL_GAME`, never a real instrument code, so practice trades cannot mix with real data.

## Rules

- All times in UTC, with the offset written out.
- No licensed raw data in a shared file: Permutable records and LSEG prices stay in each team's private `data/` folder;
  an event record carries references, not vendor rows.
- Finals scenarios (event schedules, seeds, parameters) are organiser-only and never in a repository or a shared file.
- Research bots may practise on game rounds, never on finals scenarios, and whoever sees a finals scenario does not
  compete (CONTEXT §1, "Fairness").

## Open for agreement

1. Who owns the mapping tables (proposal: Jacob & Pau, with the event library).
2. Whether records with `type` null are exchanged at all, or stay on the research side.
3. The meaning and use of `confidence` in the game (today the game ignores it).
4. Where the shared `events.jsonl` lives between the teams (it may hold references to licensed data, so not in git).
