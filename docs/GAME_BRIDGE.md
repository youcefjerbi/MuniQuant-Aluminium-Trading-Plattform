# Practice bot on the championship game

`python -m app.game_bridge` lets the Workspace's paper engine trade the practice rounds of the Munich Quant
Championship simulator (repository `Batudlgc/muniquant-finals-sim`). It is step 3 of linking the research platform
with the game. Steps 1 and 2 are the shared event format ([EVENT_SCHEMA.md](EVENT_SCHEMA.md)) and Data Core plants in
the game's headlines. Both teams agreed on 6 Oct that research bots may practise on the game through its API.

The bridge is off unless started by hand. It trades **practice rounds only**: research bots never see or trade
finals scenarios, and the bridge refuses a server whose label or profile names a final.

## What it does

1. **Reads the game's feed** through the participant API (the simulator's `service/API.md`): `GET /market` for the
   step, pace and end of the round, and `GET /ticks?since=<seq>&round=<id>` for each step's price and headlines. It
   polls every 0.5 s by default, so it needs no WebSocket library.
2. **Posts the game price** of the newest step as a live research quote under the instrument `LME_AL_GAME`. That is
   never a real instrument code, so practice prices and trades cannot mix with real data.
3. **Turns each headline of the newest step into a live research event**. The game type becomes a research kind as
   EVENT_SCHEMA.md says ("Game type → research kind"); `new_supply` also gets the tag `new_capacity`. The title is the
   headline, the summary holds the type, the direction and whether it was scheduled, and the source reference names
   the round and step. Game events carry no Core plant IDs, so the Core need not run.
4. **Lets the paper engine decide**, with its usual rules ([the engine guide](EVENT_CHAIN_PAPER_ENGINE.md)): analogues of
   the same kind, sample count, agreement, threshold after costs, cooldown, daily limit, drawdown.
5. **Sends a BUY or SELL as a market order** of `--lots` lots. A BUY builds a long position up to `--max-lots`. A SELL
   only reduces a long position, because the engine never sells short. The paper decision's ID is the order's
   `request_id`, so a retry (for example after HTTP 429) cannot place a second order. Every order is in the audit log
   as `game_order` with the decision ID, whether it was sent, skipped (limit reached, nothing to sell) or failed.
6. **Learns each finished round.** It saves the round to `data/game-rounds/<round>.json` and imports it as history.
   Every headline becomes a historical event on a synthetic timeline where **one game day is 24 hours**, so the
   engine's fixed 24-hour outcome is one game day. A headline with a price one game day later gets an outcome: the
   price at its step, then the price at the same step the next day. Each learned round has its own block, at least a
   week before now and a week before the round learned before it, so no chain or outcome spans two rounds. Learning
   the same round again changes nothing.

Headlines the bridge sees late, because it joined mid-round or fell behind, are learned but never traded. The first
round on a new database only holds: the engine needs at least `--min-cases` analogues before it trades.

## Run it

Use a separate practice database. The Workspace has one paper account, and `setup` points it at `LME_AL_GAME`
(refused while it holds a position in another instrument).

```sh
# A local practice server, in the simulator repository (its data/ is git-ignored):
python -m service.app --seed 7 --demo-accounts 1 --keys-file data/keys.csv --autostart --port 8002 --label "Local practice"

# In this repository:
export DATABASE_URL=sqlite:///data/game-practice.db
alembic upgrade head
python -m app.game_bridge setup
export GAME_API_KEY=...          # the practice account's key (data/keys.csv above); never commit it
python -m app.game_bridge run --server http://127.0.0.1:8002 --rounds 3
```

For an online practice round, an organiser creates the account (`POST /admin/accounts`, or a one-time sign-in link)
and gives you its key and the server URL. Each output line is JSON: one per headline with the decision and any order,
and one per finished round with what was saved and learned. Open the Workspace with the same `DATABASE_URL` to see
the events and decisions on **Patterns & paper trades**.

| Option | Default | Meaning |
|---|---|---|
| `--server` | `GAME_SERVER_URL` | Game server URL |
| `--key-env` | `GAME_API_KEY` | Name of the environment variable that holds the key; the key itself is never an argument |
| `--lots` | 1 | Lots per order (the game allows 1 to 5) |
| `--max-lots` | 5 | Largest long position the bridge builds (the game's limit is 20) |
| `--rounds` | 1 | Stop after this many finished rounds; 0 keeps going |
| `--poll` | 0.5 | Seconds between two polls |
| `--rounds-dir` | `GAME_ROUNDS_DIR` or `data/game-rounds` | Where finished rounds are saved |
| `--no-learn` | off | Save finished rounds without learning them |

`python -m app.game_bridge learn FILE...` learns saved rounds, for example into another practice database.

### Paper settings for the game's pace

The research defaults assume real days: a one-hour cooldown would allow one trade every 60 game days. `setup`
enables the paper account for `LME_AL_GAME` with these values. Each is a flag (`--cooldown-seconds 120`, ...).

| Setting | Value | Why |
|---|---|---|
| `min_cases` | 3 | Analogues needed before a trade (the engine's lowest) |
| `edge_threshold_bps` | 10 | Expected move needed after costs |
| `fee_bps` / `slippage_bps` | 0 / 2 | The game charges no fee; about half a typical spread |
| `cooldown_seconds` | 60 | The engine's lowest: at the default pace (12 steps of 5 s) about one trade per game day |
| `max_daily_trades` | 20 | The engine's highest, per calendar day |
| `max_quote_age_seconds` / `max_event_age_seconds` | 60 | A step is 5 s by default |
| `min_similarity` / `min_agreement` | 0.65 / 0.8 | The engine's defaults |

## What is stored, and what is not

- Research events, quotes, outcomes and paper decisions under `LME_AL_GAME`; game orders in the audit log.
- `data/game-rounds/`: each finished round's prices and public headlines, git-ignored. Some game profiles replay real
  LME price moves, so keep these files private like the rest of `data/`.
- The API key stays in the environment. It is not stored in the database, the round files or the output.

## Limits

- The paper ledger keeps its own sizes (at most 10,000 cash units per trade), while game orders use `--lots`. The game
  closes every position at the end of a round; the paper position carries on into the next round.
- One trade per cooldown, long only, and only the LME book (a two-market round's second book is not traded).
- The engine refuses an event when more than 500 `LME_AL_GAME` events fall in its 72-hour window. A local 20-day round
  had 14 headlines, so a 63-day quarter has about 45: that is about 11 quarters in three days. The bridge then logs
  and skips headlines; use a new practice database or wait.
- Analogues match on kind and words (headline, type, direction). This is the engine's unvalidated experimental rule,
  not a strategy, and the game's news sizes are still a group decision.

## Open points

- A practice account and the server URL for online practice rounds (Batu).
- Event format open points 2 and 3: whether records with `type` null are exchanged, and what `confidence` means in the
  game. The bridge sends no `confidence`.
- If the organiser switches off the headline `direction`, the summary has no direction, and headlines of both
  directions can match each other.
