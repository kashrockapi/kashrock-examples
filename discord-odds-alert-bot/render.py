"""Render one prop row as a plain alert payload.

The payload is data only — bot.py turns it into a Discord embed, and tests
assert on the dict without needing discord.py. Times are shown in Eastern
per house style. Field names follow the live /v7/{sport}/props?view=props
slim row shape (verified against the production API).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _american(odds: Any) -> str:
    if isinstance(odds, bool) or not isinstance(odds, (int, float)):
        return ""
    return f"{int(odds):+d}"


def _line_text(line: Any) -> str:
    if isinstance(line, bool):
        return ""
    if isinstance(line, (int, float)):
        return f"{line:g}"
    return str(line or "")


def _event_time_et(row: dict[str, Any]) -> str:
    raw = str(row.get("event_time") or row.get("start_time") or "")
    if not raw:
        return ""
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt.astimezone(ET).strftime("%b %-d, %-I:%M %p ET")


def alert_payload(row: dict[str, Any], sport: str) -> dict[str, Any]:
    """One alert: who, what, where, price. Missing optional fields stay ""."""
    direction = str(row.get("direction") or "").capitalize()
    line_text = _line_text(row.get("line"))
    selection = f"{direction} {line_text}".strip()

    book = str(row.get("book_name") or row.get("sportsbook_name") or "").strip()
    match = str(
        row.get("canonical_event_name")
        or " vs ".join(
            part for part in (row.get("home_team"), row.get("away_team")) if part
        )
        or ""
    ).strip()

    odds_american = _american(row.get("odds"))
    price_bits = [b for b in (selection, odds_american) if b]

    deeplink = str(row.get("deeplink") or "")
    if not deeplink:
        links = row.get("links")
        if isinstance(links, dict):
            deeplink = str(links.get("bet") or "")

    return {
        "sport": sport,
        "player": str(row.get("player_name") or row.get("canonical_player_name") or ""),
        "market": str(
            row.get("market_label") or row.get("market_type") or row.get("stat_type") or ""
        ),
        "match": match,
        "event_time_et": _event_time_et(row),
        "book": book,
        "selection": selection,
        "odds_american": odds_american,
        "odds_decimal": row.get("decimal_odds") or row.get("payout_multiplier") or "",
        "price": " · ".join(price_bits),
        "deeplink": deeplink,
    }
