"""Alert selection: which prop rows match the configured filters, and which
of those are new since the last poll.

A row is new when its offer has never been seen, or when its price moved
(line or American odds changed since the stored fingerprint). That is the
point of an odds alert bot: a fresh offer and a moved price are both news;
an unchanged repeat is not.
"""

from __future__ import annotations

from typing import Any, Iterable

from config import Settings


def prop_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Flat rows from a view=props response. Empty board -> empty list."""
    rows = body.get("props")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _haystack(*values: Any) -> str:
    return " ".join(str(v or "").lower() for v in values)


def row_matches(row: dict[str, Any], cfg: Settings) -> bool:
    """User-configured market/book/player filters. Empty filter list = allow all."""
    if cfg.markets:
        tokens = _haystack(row.get("market_type"), row.get("stat_type"), row.get("market_label"))
        if not any(token in tokens for token in cfg.markets):
            return False
    if cfg.books:
        book_keys = {
            str(row.get("sportsbook_name") or "").lower(),
            str(row.get("book_name") or "").lower(),
        }
        if not any(book.lower() in book_keys for book in cfg.books):
            return False
    if cfg.players:
        name = str(row.get("player_name") or "").lower()
        if not any(token in name for token in cfg.players):
            return False
    return True


def offer_id(row: dict[str, Any]) -> str:
    """Stable per-selection id. offerId/canonical_offer_id encode prop +
    direction (…_1_over); propId alone is shared by the over/under pair."""
    return str(
        row.get("canonical_offer_id")
        or row.get("offerId")
        or row.get("id")
        or row.get("propId")
        or ""
    )


def fingerprint(row: dict[str, Any]) -> str:
    """Price identity: a moved line or American price is a new alert."""
    return f"{row.get('line')}|{row.get('odds')}"


def select_new(
    rows: Iterable[dict[str, Any]], cfg: Settings, store
) -> list[dict[str, Any]]:
    """Matching rows the store has not seen at this price, in board order."""
    out = []
    for row in rows:
        if not row_matches(row, cfg):
            continue
        key = offer_id(row)
        if not key:
            continue
        if store.is_new(key, fingerprint(row)):
            out.append(row)
    return out
