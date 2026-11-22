"""CS2 live dashboard: live matches, score and player stats, then pushes.

1. GET /v7/cs2/live lists every live match with its state and streams
   (Hobby: 15 seconds behind; Builder and up: real time).
2. GET /v7/cs2/live?game=<kr_match_id>&include=boxscore reads one match.
3. With --stream, opens WS /v7/live/ws and prints each push for that match
   (Builder and up; Sandbox and Hobby are refused at the handshake).

A live match with no live source says so (has_live_stats false + reason);
this prints that instead of an empty board.

Run:

    pip install -r requirements.txt
    cp .env.example .env
    python live.py                 # list live matches, show the first board
    python live.py --stream        # then follow it over the WebSocket

Docs: https://www.kashrock.com/docs/live-data and https://www.kashrock.com/docs/websockets
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kashrock_client import KashRockClient, KashRockError  # noqa: E402

ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def show_board(game: dict) -> None:
    print(f"\n{game.get('team1')} vs {game.get('team2')}  [{game.get('kr_match_id')}]")
    if not game.get("has_live_stats"):
        print(f"  no live stats right now: {game.get('reason')} (no plan adds coverage for a match)")
        return
    frame = ((game.get("include") or {}).get("boxscore") or {}).get("boxscore") or {}
    blue, red = frame.get("blue") or {}, frame.get("red") or {}
    print(f"  series {blue.get('series_score')}-{red.get('series_score')}, map {blue.get('map_score')}-{red.get('map_score')}, updated {frame.get('upstream_ts')}")
    print(f"  {'player':<16}{'side':<6}{'K':>4}{'D':>4}{'A':>4}  alive")
    for p in frame.get("players") or []:
        print(f"  {str(p.get('nickname')):<16}{str(p.get('side')):<6}{p.get('kills', 0):>4}{p.get('deaths', 0):>4}{p.get('assists', 0):>4}  {'yes' if p.get('alive') else 'no'}")

async def stream(base_url: str, api_key: str, match_id: str, seconds: int) -> None:
    url = base_url.replace("https://", "wss://").replace("http://", "ws://") + "/v7/live/ws"
    async with websockets.connect(url, additional_headers={"x-api-key": api_key}) as ws:
        await ws.send(json.dumps({"op": "subscribe", "sport": "cs2", "game_id": match_id}))
        loop = asyncio.get_running_loop()
        end = loop.time() + seconds
        while loop.time() < end:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(end - loop.time(), 0.1))
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            print(f"  push: {msg.get('op')} {msg.get('type') or msg.get('plan') or msg.get('reason') or ''}")


def main() -> int:
    ap = argparse.ArgumentParser(description="CS2 live dashboard")
    ap.add_argument("--stream", action="store_true", help="follow the first live match over the WebSocket")
    ap.add_argument("--seconds", type=int, default=30, help="how long to stream")
    args = ap.parse_args()
    load_dotenv(ENV_PATH)
    kr = KashRockClient.from_env()

    try:
        board = kr.get("/v7/cs2/live")
    except KashRockError as exc:
        if exc.status == 403:
            print(f"{exc.message}\nLive data needs Hobby or above: https://www.kashrock.com/pricing")
            return 1
        raise
    games = board.get("games") or []
    if not games:
        print("No CS2 match is live right now. That is a real answer, not an error.")
        return 0
    print(f"{len(games)} live CS2 match(es):")
    for g in games:
        stats = "live stats" if g.get("has_live_stats") else f"no live stats ({g.get('reason')})"
        print(f"  {g.get('team1')} vs {g.get('team2')}  {g.get('live_state')}  {stats}  [{g['kr_match_id']}]")
    pick = next((g for g in games if g.get("has_live_stats")), games[0])
    first = pick["kr_match_id"]
    detail = kr.get("/v7/cs2/live", {"game": first, "include": "boxscore"})
    for game in detail.get("games") or [pick]:
        show_board(game)
    if args.stream:
        print(f"\nstreaming {first} for {args.seconds}s")
        try:
            asyncio.run(stream(kr.base_url, os.environ["KASHROCK_API_KEY"], first, args.seconds))
        except websockets.exceptions.InvalidStatus as exc:
            print(f"socket refused ({exc.response.status_code}): the live WebSocket needs Builder or above")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
