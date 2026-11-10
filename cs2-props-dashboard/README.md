# CS2 Props Dashboard

A small web app that reads the live KashRock V7 API and shows the CS2 prop
board: every DFS app and sportsbook quote, filterable by board, market, book,
and player, plus a consensus-lines view that compares each book's price to the
cross-book fair price.

No sample data. Every row on the page came from `GET /v7/cs2/props` or
`GET /v7/cs2/lines` a moment ago. When the board is empty or a book's refresh
is delayed, the page says so instead of inventing rows.

## What it uses

| Endpoint | Purpose |
|---|---|
| `GET /v7/meta` | Book and market display names, your plan |
| `GET /v7/cs2/props` | The prop board (`board`, `view`, `market`, `book`, `player` filters) |
| `GET /v7/cs2/lines` | Consensus lines with per-book prices and EV (`view=consensus`) |

Full parameter reference: https://www.kashrock.com/docs/v7?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=docs_v7

## Prerequisites

- Python 3.10+
- A KashRock API key. The free Sandbox plan works (props are included; the
  daily request cap is the only limit). Get one at
  https://www.kashrock.com/console?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=signup_console

## Setup

```bash
cd examples/cs2-props-dashboard
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

Pages:

- `/` — prop quotes. Filter by board (DFS apps / sportsbooks / both), view,
  market, book, or player nickname. Paginate with the pager links.
- `/lines` — consensus lines: fair probability per outcome, the best book
  price, and EV percent per book.

Set `PORT` to change the port. `KASHROCK_BASE_URL` overrides the API host if
you are pointed at a different deployment.

## Self-check

```bash
python app.py --selftest
```

Hits `/v7/meta`, `/v7/cs2/props`, and `/v7/cs2/lines` live and prints what came
back. Exit code 0 means the app's data paths work against the real API.

## Rate limits

Every page load makes two API calls (props + meta). Plan limits are per
minute: Sandbox 10, Hobby 30, Builder 100, Pro 250, Quant 500. Normal browsing
will not come close; if you do hit a 429 the page shows the API's own message.

## Links

- API docs: https://www.kashrock.com/docs/v7?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=docs_v7
- SDK docs: https://www.kashrock.com/docs/sdk?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=docs_sdk
- Get a key: https://www.kashrock.com/console?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=signup_console
- KashRock: https://www.kashrock.com?utm_source=github&utm_medium=owned&utm_campaign=dev_examples&utm_content=home
