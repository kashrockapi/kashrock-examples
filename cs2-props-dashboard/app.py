"""CS2 props dashboard: live DFS and sportsbook prop board from KashRock V7.

Run:

    pip install -r requirements.txt
    cp .env.example .env   # then put your key in .env
    python app.py          # http://127.0.0.1:8000

Self-check against the live API (no server needed):

    python app.py --selftest
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlencode

from flask import Flask, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kashrock_client import KashRockClient, KashRockError  # noqa: E402

app = Flask(__name__)

BOARDS = {"all": "DFS + Sportsbooks", "dfs": "DFS Apps", "main": "Sportsbooks"}
VIEWS = {"rows": "Every Quote", "best": "Best Price Only", "groups": "Grouped"}
PAGE_SIZE = 200
ENV_PATH = Path(__file__).resolve().parent / ".env"


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (KEY=value lines, # comments). No dependency."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def client() -> KashRockClient:
    _load_dotenv(ENV_PATH)
    return KashRockClient.from_env()


def _props_page(kr: KashRockClient, args: dict) -> dict:
    """One page of the props board. Returns rows plus the response envelope."""
    params = {
        "board": args.get("board") or "all",
        "view": args.get("view") or "rows",
        "format": "slim",
        "limit": PAGE_SIZE,
        "offset": int(args.get("offset") or 0),
    }
    for key in ("market", "book", "player"):
        if args.get(key):
            params[key] = args[key]
    body = kr.get("/v7/cs2/props", params)
    rows = body.get("props") or body.get("rows") or []
    if args.get("view") == "groups":
        rows = _flatten_groups(body.get("groups") or [])
    return {
        "rows": rows,
        "total": body.get("total") or body.get("total_groups") or 0,
        "returned": len(rows),
        "has_more": bool(body.get("has_more")),
        "available": body.get("available", True),
        "reason": body.get("reason"),
        "hint": body.get("hint"),
        "books": body.get("books") or [],
        "stale_books": body.get("stale_books") or [],
        "generated_at": body.get("generated_at"),
        "args": args,
    }


def _flatten_groups(groups: list) -> list:
    """groups view -> flat rows, one per book quote inside each group."""
    rows = []
    for group in groups:
        for side_key in ("dfs", "main"):
            for quote in group.get(side_key) or []:
                rows.append({**quote, "_player": group.get("player_name"), "_stat": group.get("stat_type")})
    return rows


def _meta(kr: KashRockClient) -> dict:
    """Book and market display names. A failure is reported to the page, not hidden."""
    body = kr.get("/v7/meta", {"sport": "cs2"})
    books = {b.get("key"): b.get("display_name") or b.get("key") for b in body.get("books") or []}
    markets = {m.get("slug"): m.get("label") or m.get("slug") for m in body.get("markets") or []}
    return {"books": books, "markets": markets, "plan": body.get("plan")}


@app.route("/")
def index():
    args = {
        "board": request.args.get("board", "all"),
        "view": request.args.get("view", "rows"),
        "market": request.args.get("market", ""),
        "book": request.args.get("book", ""),
        "player": request.args.get("player", ""),
        "offset": request.args.get("offset", "0"),
    }
    kr = client()
    ctx = {"error": None, "meta_error": None}
    try:
        ctx.update(_props_page(kr, args))
    except KashRockError as exc:
        ctx["error"] = str(exc)
    try:
        ctx["meta"] = _meta(kr)
    except KashRockError as exc:
        ctx["meta_error"] = str(exc)
        ctx["meta"] = {"books": {}, "markets": {}, "plan": None}
    ctx.update(BOARDS=BOARDS, VIEWS=VIEWS)
    ctx["query_string"] = urlencode(
        {k: v for k, v in args.items() if k != "offset" and v not in ("", "0")}
    )
    return render_template("props.html", **ctx)


@app.route("/lines")
def lines():
    """Consensus lines board: fair price per outcome plus each book's price and EV."""
    kr = client()
    ctx = {"error": None, "events": [], "available": True}
    try:
        body = kr.get("/v7/cs2/lines", {"view": "consensus", "format": "slim", "limit": 100})
        ctx["events"] = body.get("events") or []
        ctx["available"] = body.get("available", True)
        ctx["reason"] = body.get("reason")
        ctx["hint"] = body.get("hint")
        ctx["checked_at"] = body.get("checked_at") or body.get("fetched_at")
    except KashRockError as exc:
        ctx["error"] = str(exc)
    return render_template("lines.html", **ctx)


@app.route("/healthz")
def healthz():
    return {"ok": True}


def selftest() -> int:
    """Prove the client and both data paths against the live API."""
    kr = client()
    print(f"base: {kr.base_url}")
    meta = kr.get("/v7/meta", {"sport": "cs2"})
    print(f"meta: plan={meta.get('plan')} sports={len(meta.get('sports') or [])} markets={len(meta.get('markets') or [])}")

    props = kr.get("/v7/cs2/props", {"board": "all", "view": "rows", "format": "slim", "limit": 5})
    rows = props.get("props") or []
    print(f"props: total={props.get('total')} returned={len(rows)} available={props.get('available')}")
    if rows:
        r = rows[0]
        print(f"  first row: {r.get('player_name')} {r.get('stat_type')} {r.get('line')} {r.get('direction')} @ {r.get('book_name')} ({r.get('propId')})")
    else:
        print(f"  board empty: reason={props.get('reason')} hint={props.get('hint')}")

    lines = kr.get("/v7/cs2/lines", {"view": "consensus", "format": "slim", "limit": 3})
    events = lines.get("events") or []
    print(f"lines: events={len(events)} available={lines.get('available')} reason={lines.get('reason')}")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        try:
            raise SystemExit(selftest())
        except KashRockError as exc:
            print(f"selftest failed: {exc}", file=sys.stderr)
            raise SystemExit(1)
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="127.0.0.1", port=port, debug=False)
