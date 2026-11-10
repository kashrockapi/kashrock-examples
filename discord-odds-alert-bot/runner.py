"""Poll-cycle logic with no Discord dependency: fetch, filter, dedupe-select,
render, and the --selftest / --dry-run drivers. bot.py owns the Discord side.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any

from alerts import fingerprint, offer_id, prop_rows, select_new
from config import Settings
from kashrock_client import KashRockClient, KashRockError, RateLimiter
from render import alert_payload
from state import SeenStore

log = logging.getLogger("odds-alert-bot")

# Failures one fetch can hit: API HTTP errors, transport errors (OSError
# covers URLError/TimeoutError), bad JSON (ValueError). Anything else is a
# bug and should crash loudly.
FETCH_ERRORS = (KashRockError, OSError, ValueError)


async def collect_sport(
    settings: Settings, client: KashRockClient, store: SeenStore, sport: str
) -> list[tuple[dict, dict]] | None:
    """(row, payload) pairs for one sport that are new or repriced.

    Returns None when the fetch failed; the error is logged and the caller
    moves on to the next sport instead of dying.
    """
    try:
        body = await asyncio.to_thread(
            client.get_props, sport, board=settings.board, view="props"
        )
    except FETCH_ERRORS as exc:
        log.warning("props fetch failed for %s: %s", sport, exc)
        return None
    return [
        (row, alert_payload(row, sport))
        for row in select_new(prop_rows(body), settings, store)
    ]


async def poll_cycle(
    settings: Settings, client: KashRockClient, store: SeenStore
) -> tuple[bool, list[tuple[str, list[tuple[dict, dict]]]]]:
    """One poll across all configured sports.

    Returns (first_run, [(sport, pairs)]) for sports that produced alerts;
    failed sports are logged and omitted. first_run is True when the state
    store was empty before this poll — callers should seed the baseline
    (mark everything, post one summary) instead of flooding the channel
    with the whole board as "new". Nothing is marked or saved here.
    """
    first_run = store.is_empty()
    out = []
    for sport in settings.sports:
        pairs = await collect_sport(settings, client, store, sport)
        if pairs:
            out.append((sport, pairs))
        elif pairs is not None:
            log.info("%s: board fetched, no new alerts", sport)
    return first_run, out


def seed_summary(cycle: list[tuple[str, list[tuple[dict, dict]]]], settings: Settings) -> str:
    total = sum(len(pairs) for _sport, pairs in cycle)
    sports = ", ".join(sport for sport, _pairs in cycle) or ", ".join(settings.sports)
    return (
        f"Now watching {total} {sports} prop offers. "
        "Alerts start on the next new offer or price move."
    )


def mark_pairs(store: SeenStore, pairs: list[tuple[dict, dict]]) -> None:
    for row, _payload in pairs:
        store.mark(offer_id(row), fingerprint(row))


def make_client(settings: Settings) -> KashRockClient:
    return KashRockClient(
        settings.kashrock_base,
        settings.api_key,
        limiter=RateLimiter(settings.rpm),
    )


def run_selftest(settings: Settings) -> int:
    """One live fetch + filter + render cycle. No Discord, throwaway state."""
    if not settings.api_key:
        print("error: KASHROCK_API_KEY is not set", file=sys.stderr)
        return 2
    store = SeenStore(Path(tempfile.mkdtemp()) / "selftest_state.json")
    client = make_client(settings)
    total = 0
    for sport in settings.sports:
        pairs = asyncio.run(collect_sport(settings, client, store, sport))
        count = len(pairs or [])
        total += count
        print(f"{sport}: {count} new alerts")
        for _row, payload in (pairs or [])[:5]:
            print("  " + json.dumps(payload, ensure_ascii=False))
    print(f"selftest ok: {total} alerts across {len(settings.sports)} sport(s)")
    return 0


def run_dry_run(settings: Settings) -> int:
    """Poll loop that prints alerts as JSON lines instead of posting."""
    if not settings.api_key:
        print("error: KASHROCK_API_KEY is not set", file=sys.stderr)
        return 2
    client = make_client(settings)
    store = SeenStore(settings.state_path)

    async def _main() -> None:
        while True:
            first_run, cycle = await poll_cycle(settings, client, store)
            if first_run and cycle:
                print(seed_summary(cycle, settings))
            else:
                for _sport, pairs in cycle:
                    for _row, payload in pairs:
                        print(json.dumps(payload, ensure_ascii=False))
            for _sport, pairs in cycle:
                mark_pairs(store, pairs)
            store.save()
            await asyncio.sleep(settings.interval_minutes * 60)

    asyncio.run(_main())
    return 0


def payloads_of(
    cycle: list[tuple[str, list[tuple[dict, dict]]]]
) -> list[dict[str, Any]]:
    return [payload for _sport, pairs in cycle for _row, payload in pairs]


def pairs_of(
    cycle: list[tuple[str, list[tuple[dict, dict]]]]
) -> list[tuple[dict, dict]]:
    return [pair for _sport, pairs in cycle for pair in pairs]
