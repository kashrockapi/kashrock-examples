# LoL Research Dashboard

A small web app that reads the live KashRock V7 API for League of Legends:
the match schedule, match detail with per-map box scores, player and team
search, graded results, and the prop/line quote tapes for a single match.

No sample data. Every row came from a `/v7/lol/...` response. When a tape is
still warming or a match has no stats yet, the page says so.

## What it uses

| Endpoint | Purpose |
|---|---|
| `GET /v7/meta` | Plan and catalog check |
| `GET /v7/lol/matches` | Schedule and results list (`status`, `q`, `date`, paging) |
| `GET /v7/lol/matches/{match_ref}` | One match, `include=boxscore` for per-map player stats |
| `GET /v7/lol/players` | Player search by nickname (`q`) |
| `GET /v7/lol/teams` | Team search (`q`) |
| `GET /v7/lol/results` | Graded props/lines (`grade` filter) |
| `GET /v7/lol/history` | Quote tapes for one match (`match`, `kind=props` or `lines`) |

`match_ref` accepts a `kr_match_id` or the slug. Full parameter reference:
https://www.kashrock.com/docs/v7?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=docs_v7

Notes on the data:

- `history` tapes are built on demand. A fresh match can answer
  `available: false` with `status: warming` and a `retry_after_seconds`; the
  page shows that instead of an error. `kind=props` builds the whole tape in
  one request and can take a minute on a cold match; if the build exceeds the
  gateway limit the API answers 504 `request_timeout` and the page shows that
  message. `kind=lines` warms asynchronously and is the faster first check.
- `kind=contract` needs a `prop=` kr_prop id. This app uses `kind=props`
  (all prop tapes for the match) and `kind=lines`.
- History depth depends on plan: 7 days Sandbox, 90 days Hobby, full
  Builder and Pro.

## Prerequisites

- Python 3.10+
- A KashRock API key. Sandbox works for browsing matches, players, teams and
  results. Deeper history needs Hobby or higher. Get a key at
  https://www.kashrock.com/console?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=signup_console

## Setup

```bash
cd examples/lol-research-dashboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your key
```

## Run

```bash
python app.py
# open http://127.0.0.1:8000
```

Pages: Matches (with status/date/search filters), Match detail (box score per
map), Players, Teams, Results (graded), and per-match tapes.

## Self-check

```bash
python app.py --selftest
```

Hits every endpoint the app uses against the live API and prints what came
back, including one real history tape. Exit code 0 means the data paths work.

## Rate limits

Each page makes one API call (match detail makes one). Plan limits per minute:
Sandbox 10, Hobby 30, Builder 100, Pro 250, Quant 500.

## Links

- API docs: https://www.kashrock.com/docs/v7?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=docs_v7
- SDK docs: https://www.kashrock.com/docs/sdk?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=docs_sdk
- Get a key: https://www.kashrock.com/console?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=signup_console
- KashRock: https://www.kashrock.com?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=home
