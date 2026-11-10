# Discord Odds Alert Bot

A small Discord bot that polls the [KashRock](https://www.kashrock.com/?utm_source=github&utm_medium=social&utm_campaign=discord_odds_alert_bot) esports props API and posts new or repriced player-prop offers to a channel. Built as a developer-acquisition example: everything it does goes through the public V7 REST API with a normal API key.

## What it does

- Polls `GET /v7/{sport}/props` (`board=all`, `view=props`, `format=slim`) on a configurable interval.
- Posts Discord embeds: player, market, match, book, line, direction, American odds, start time (Eastern), and a link to the offer.
- Filters by sport, market, book, and player substring via env vars or `bot.config.json`.
- Dedupes through a JSON state file so the same offer at the same price never alerts twice; a moved line or price alerts once as new.
- `/odds` slash command shows the current filtered board on demand (does not touch alert state).
- `--selftest` runs one live fetch/filter/render cycle with no Discord account needed. `--dry-run` runs the poll loop and prints alerts as JSON lines.

## API endpoints used

Verified against `openapi.public.json` at the repo root:

| Route | Use |
|---|---|
| `GET /v7/{sport}/props` | Props board: `board` (dfs/main/all), `view=props`, `format=slim`, optional `market`, `player`, `book`, `limit`, `offset` |

That is the only route the bot calls. Sports: `apex`, `cod`, `cs2`, `deadlock`, `dota2`, `lol`, `mlbb`, `r6`, `valorant` (from `GET /v7/meta`).

## Plans and rate limits

The bot paces itself with a client-side token bucket (`KASHROCK_RPM`). Match it to your plan's requests-per-minute:

| Plan | Price | Requests/min | Notes |
|---|---|---|---|
| Sandbox | free | 10 | CS2 props and match discovery only; 1,500 credits per UTC day; good for trying the bot |
| Hobby | $29/mo | 30 | All sports props, sportsbook (`main`) board |
| Builder | $99/mo | 100 | Everything in Hobby plus history and live WebSocket |
| Pro | $199/mo | 250 | Everything in Builder plus signal alerts |
| Quant | $299/mo | 500 | Everything in Pro plus arb, CLV, portfolio |

With the defaults (one sport, one request per poll) even Sandbox's 10 requests/minute is plenty: a 5-minute poll uses 12 requests/hour. Multi-sport polling multiplies requests per poll, so raise `POLL_INTERVAL_MINUTES` or pick fewer sports on low tiers. Props calls cost 5 credits each; check `GET /v6/usage` for your quota.

Get a key at [kashrock.com](https://www.kashrock.com/?utm_source=github&utm_medium=social&utm_campaign=discord_odds_alert_bot). Full API docs: [kashrock.com/docs](https://www.kashrock.com/docs?utm_source=github&utm_medium=social&utm_campaign=discord_odds_alert_bot).

## Setup

1. Create a Discord application at <https://discord.com/developers/applications>, add a bot, and invite it to your server with permission to send messages and use slash commands in the target channel. The bot only sends messages, so no privileged intents are needed.
2. `cp .env.example .env` and fill in `KASHROCK_API_KEY`, `DISCORD_TOKEN`, and `DISCORD_CHANNEL_ID`.
3. `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
4. `python bot.py --selftest` proves the key, filters, and formatting against the live API before Discord is involved.
5. `python bot.py` connects, syncs `/odds`, and starts polling.

Optional: set `DISCORD_GUILD_ID` to sync slash commands to one guild instantly (global sync can take up to an hour). Set `STATE_FILE` to move dedupe state. Or skip `.env` entirely and use a `bot.config.json` file; real environment variables always win.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `KASHROCK_API_KEY` | — | Required. KashRock API key |
| `DISCORD_TOKEN` | — | Required for posting (`DISCORD_BOT_TOKEN` also accepted) |
| `DISCORD_CHANNEL_ID` | — | Channel for scheduled posts; `/odds` works without it |
| `DISCORD_GUILD_ID` | — | Guild for instant slash-command sync |
| `KASHROCK_SPORT` | `cs2` | Comma-separated sports |
| `KASHROCK_BOARD` | `all` | `dfs`, `main`, or `all` |
| `KASHROCK_MARKETS` | — | Comma-separated market filters (e.g. `kills,headshots`) |
| `KASHROCK_BOOKS` | — | Comma-separated book keys from `/v7/meta` |
| `KASHROCK_PLAYERS` | — | Comma-separated player-name substrings |
| `POLL_INTERVAL_MINUTES` | `5` | Poll cadence |
| `KASHROCK_RPM` | `10` | Client-side requests-per-minute budget |
| `STATE_FILE` | `./odds_alert_state.json` | Dedupe state path |
| `MAX_ALERTS_PER_MESSAGE` | `20` | Fields per Discord embed (Discord caps at 25) |

## Files

- `bot.py` — Discord client, poll task, `/odds` command, CLI modes
- `runner.py` — poll cycle, selftest and dry-run drivers
- `kashrock_client.py` — `GET /v7/{sport}/props` client + token-bucket rate limiter
- `config.py` — env/JSON settings
- `alerts.py` — market/book/player filters and new-offer selection
- `state.py` — JSON dedupe store
- `render.py` — prop row to alert payload (Eastern times)
- `embeds.py` — payloads to Discord embeds
- `tests/test_odds_alert_bot.py` — pytest, all HTTP mocked

## Tests

```
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Covers filter logic, alert rendering, dedupe persistence and repricing, rate-limit pacing on a fake clock, and the client's URL construction and error mapping. No live calls.
