"""Esports odds monitor: best price per side across books, and what moved.

Polls GET /v7/{sport}/lines, prints the best price for each side of each
market next to the consensus fair price, and on every later poll prints the
prices that changed. Needs Hobby or above (lines are not on Sandbox).

Run:

    pip install -r requirements.txt
    cp .env.example .env        # put your key in .env
    python monitor.py cs2       # Ctrl+C to stop
    python monitor.py cs2 --once

Docs: https://www.kashrock.com/docs/odds
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kashrock_client import KashRockClient, KashRockError  # noqa: E402

ENV_PATH = Path(__file__).resolve().parent / ".env"
Key = Tuple[str, str, str]  # (matchup, market label, outcome)


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def best_prices(board: dict) -> Dict[Key, dict]:
    """One row per side: the best open book price, the fair price, the book count."""
    out: Dict[Key, dict] = {}
    for ev in board.get("events") or []:
        matchup = f"{ev.get('home_team')} vs {ev.get('away_team')}"
        for mk in ev.get("markets") or []:
            label = mk.get("market_label") or mk.get("market")
            for oc in mk.get("outcomes") or []:
                prices = [p for p in oc.get("prices") or [] if p.get("suspended") is not True]
                if not prices:
                    continue
                top = max(prices, key=lambda p: p["decimal"])
                out[(matchup, label, oc["name"])] = {
                    "book": top["source"],
                    "decimal": top["decimal"],
                    "fair": oc.get("fair_decimal"),
                    "books": len(prices),
                }
    return out


def show(rows: Dict[Key, dict], limit: int) -> None:
    for (matchup, label, name), r in list(rows.items())[:limit]:
        fair = f"fair {r['fair']:.2f}" if r.get("fair") else "no fair price"
        print(f"{matchup:<40} {label:<22} {name:<20} {r['decimal']:>6.2f} @ {r['book']:<16} {fair} ({r['books']} books)")


def moves(old: Dict[Key, dict], new: Dict[Key, dict]) -> None:
    changed = [(k, old[k], v) for k, v in new.items() if k in old and (old[k]["decimal"], old[k]["book"]) != (v["decimal"], v["book"])]
    if not changed:
        print("  no best-price moves since the last poll")
    for (matchup, label, name), a, b in changed:
        print(f"  MOVE {matchup} | {label} | {name}: {a['decimal']:.2f} ({a['book']}) -> {b['decimal']:.2f} ({b['book']})")


def fetch(kr: KashRockClient, sport: str, limit: int) -> dict:
    """One poll. A 429 waits the API's Retry-After; a plan gate stops and names the plan."""
    while True:
        try:
            return kr.get(f"/v7/{sport}/lines", {"limit": limit})
        except KashRockError as exc:
            if exc.status == 429:
                wait = exc.retry_after or 5
                print(f"  rate limited, waiting {wait:.0f}s (Retry-After)")
                time.sleep(wait)
                continue
            if exc.status == 403:
                raise SystemExit(f"{exc.message}\nLines need Hobby or above: https://www.kashrock.com/pricing")
            raise


def main() -> int:
    ap = argparse.ArgumentParser(description="Esports odds monitor")
    ap.add_argument("sport", nargs="?", default="cs2")
    ap.add_argument("--events", type=int, default=10, help="events per poll")
    ap.add_argument("--rows", type=int, default=20, help="rows to print")
    ap.add_argument("--every", type=int, default=60, help="seconds between polls")
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    load_dotenv(ENV_PATH)
    kr = KashRockClient.from_env()

    board = fetch(kr, args.sport, args.events)
    if board.get("available") is False:
        print(f"Board not available: {board.get('reason')} {board.get('hint') or ''}")
        return 1
    rows = best_prices(board)
    print(f"{args.sport}: {board.get('total_events')} events on the board, {len(rows)} priced sides in the first {args.events}")
    show(rows, args.rows)
    while not args.once:
        time.sleep(args.every)
        new = best_prices(fetch(kr, args.sport, args.events))
        print(time.strftime("%H:%M:%S"), "poll")
        moves(rows, new)
        rows = new
    return 0


if __name__ == "__main__":
    sys.exit(main())
