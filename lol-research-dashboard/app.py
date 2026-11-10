"""LoL research dashboard: matches, players, teams, results, and prop tapes.

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

from flask import Flask, abort, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kashrock_client import KashRockClient, KashRockError  # noqa: E402

app = Flask(__name__)

SPORT = "lol"
PAGE_SIZE = 50
ENV_PATH = Path(__file__).resolve().parent / ".env"
STATUSES = {"": "All", "not_started": "Upcoming", "live": "Live", "finished": "Finished"}
GRADES = {"all": "All", "hit": "Hit", "miss": "Miss", "push": "Push", "void": "Void"}
HISTORY_KINDS = {"props": "Prop Tapes", "lines": "Line Tapes"}


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


def _query(args: dict) -> str:
    """Current filters as a query string, minus offset (pager sets it)."""
    return urlencode({k: v for k, v in args.items() if k != "offset" and v not in ("", "0")})


def _page(body: dict, key: str) -> dict:
    items = body.get(key) or []
    return {
        "items": items,
        "total": body.get("total") or body.get(f"total_{key}") or len(items),
        "has_more": bool(body.get("has_more")),
        "available": body.get("available", True),
        "reason": body.get("reason"),
        "hint": body.get("hint"),
    }


@app.route("/")
def matches():
    args = {
        "status": request.args.get("status", ""),
        "q": request.args.get("q", ""),
        "date": request.args.get("date", ""),
        "offset": request.args.get("offset", "0"),
    }
    params = {"limit": PAGE_SIZE, "offset": int(args["offset"] or 0)}
    if args["status"]:
        params["status"] = args["status"]
    if args["q"]:
        params["q"] = args["q"]
    if args["date"]:
        params["date"] = args["date"]
    kr = client()
    ctx = {"error": None, "args": args, "statuses": STATUSES}
    try:
        ctx.update(_page(kr.get(f"/v7/{SPORT}/matches", params), "matches"))
    except KashRockError as exc:
        ctx["error"] = str(exc)
    ctx["query_string"] = _query(args)
    return render_template("matches.html", **ctx)


@app.route("/match/<path:match_ref>")
def match_detail(match_ref: str):
    kr = client()
    ctx = {"error": None, "match_ref": match_ref}
    try:
        body = kr.get(f"/v7/{SPORT}/matches/{match_ref}", {"include": "boxscore"})
        ctx["match"] = body.get("match") or {}
        ctx["available"] = body.get("available", True)
        ctx["reason"] = body.get("reason")
        ctx["hint"] = body.get("hint")
    except KashRockError as exc:
        if exc.status == 404:
            abort(404)
        ctx["error"] = str(exc)
    return render_template("match.html", **ctx)


@app.route("/players")
def players():
    args = {"q": request.args.get("q", ""), "offset": request.args.get("offset", "0")}
    params = {"limit": PAGE_SIZE, "offset": int(args["offset"] or 0)}
    if args["q"]:
        params["q"] = args["q"]
    kr = client()
    ctx = {"error": None, "args": args}
    try:
        ctx.update(_page(kr.get(f"/v7/{SPORT}/players", params), "players"))
    except KashRockError as exc:
        ctx["error"] = str(exc)
    ctx["query_string"] = _query(args)
    return render_template("players.html", **ctx)


@app.route("/teams")
def teams():
    args = {"q": request.args.get("q", ""), "offset": request.args.get("offset", "0")}
    params = {"limit": PAGE_SIZE, "offset": int(args["offset"] or 0)}
    if args["q"]:
        params["q"] = args["q"]
    kr = client()
    ctx = {"error": None, "args": args}
    try:
        ctx.update(_page(kr.get(f"/v7/{SPORT}/teams", params), "teams"))
    except KashRockError as exc:
        ctx["error"] = str(exc)
    ctx["query_string"] = _query(args)
    return render_template("teams.html", **ctx)


@app.route("/results")
def results():
    args = {"grade": request.args.get("grade", "all"), "offset": request.args.get("offset", "0")}
    params = {"limit": PAGE_SIZE, "offset": int(args["offset"] or 0), "grade": args["grade"]}
    kr = client()
    ctx = {"error": None, "args": args, "grades": GRADES}
    try:
        ctx.update(_page(kr.get(f"/v7/{SPORT}/results", params), "results"))
    except KashRockError as exc:
        ctx["error"] = str(exc)
    ctx["query_string"] = _query(args)
    return render_template("results.html", **ctx)


@app.route("/history/<path:match_ref>")
def history(match_ref: str):
    """Prop and line tapes for one match. Tapes can still be warming; show that honestly."""
    kind = request.args.get("kind", "props")
    if kind not in HISTORY_KINDS:
        abort(404)
    kr = client()
    ctx = {"error": None, "match_ref": match_ref, "kind": kind, "kinds": HISTORY_KINDS}
    try:
        body = kr.get(f"/v7/{SPORT}/history", {"match": match_ref, "kind": kind, "limit": 20}, timeout=90.0)
        ctx["tapes"] = body.get("tapes") or []
        ctx["count"] = body.get("count")
        ctx["available"] = body.get("available", True)
        ctx["status"] = body.get("status")
        ctx["reason"] = body.get("reason")
        ctx["hint"] = body.get("hint")
        ctx["retry_after"] = body.get("retry_after_seconds")
    except KashRockError as exc:
        ctx["error"] = str(exc)
    return render_template("history.html", **ctx)


@app.route("/healthz")
def healthz():
    return {"ok": True}


def selftest() -> int:
    """Prove every page's data path against the live API."""
    kr = client()
    print(f"base: {kr.base_url} sport: {SPORT}")

    meta = kr.get("/v7/meta", {"sport": SPORT})
    print(f"meta: plan={meta.get('plan')} sports={len(meta.get('sports') or [])}")

    matches = kr.get(f"/v7/{SPORT}/matches", {"limit": 3, "status": "finished"})
    rows = matches.get("matches") or []
    print(f"matches(finished): total={matches.get('total')} returned={len(rows)}")
    if rows:
        m = rows[0]
        print(f"  first: {m.get('team1')} vs {m.get('team2')} {m.get('score1')}-{m.get('score2')} ({m.get('kr_match_id')})")
    else:
        print("  no finished matches returned")

    players = kr.get(f"/v7/{SPORT}/players", {"q": "faker", "limit": 3})
    plist = players.get("players") or []
    print(f"players(q=faker): total={players.get('total_players')} returned={len(plist)}")
    for p in plist[:3]:
        print(f"  {p.get('nickname') or p.get('name')} team={p.get('team')} role={p.get('role')} id={p.get('player_id') or p.get('id')}")

    teams = kr.get(f"/v7/{SPORT}/teams", {"q": "t1", "limit": 3})
    tlist = teams.get("teams") or []
    print(f"teams(q=t1): total={teams.get('total')} returned={len(tlist)}")
    for t in tlist[:3]:
        print(f"  {t.get('name')} id={t.get('canonical_team_id') or t.get('id')}")

    results = kr.get(f"/v7/{SPORT}/results", {"limit": 3})
    rlist = results.get("results") or []
    print(f"results: returned={len(rlist)} has_more={results.get('has_more')}")
    for r in rlist[:3]:
        print(f"  {r.get('player_name')} {r.get('stat_type')} {r.get('direction')} grade={r.get('grade')} ({r.get('id')})")

    # History tapes: kind=lines warms asynchronously (available:false +
    # retry_after_seconds is a correct contract answer, not a failure).
    # kind=props builds synchronously and can take a minute on a cold match,
    # so the route gives it a long timeout; a 504 request_timeout is shown.
    if rows:
        ref = rows[0].get("kr_match_id") or rows[0].get("slug")
        hist = kr.get(f"/v7/{SPORT}/history", {"match": ref, "kind": "lines", "limit": 2}, timeout=90.0)
        print(f"history(match={ref}, kind=lines): available={hist.get('available')} status={hist.get('status')} retry_after={hist.get('retry_after_seconds')}")
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
