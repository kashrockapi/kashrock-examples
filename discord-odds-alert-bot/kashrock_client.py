"""KashRock API client with a token-bucket rate limiter.

Only real V7 routes are called. Verified against openapi.public.json:

    GET /v7/{sport}/props   board=dfs|main|all, view=props, market=,
                            player=, book=, format=slim, limit=, offset=

Plan limits (db/auth_db.py PLANS, pricing v2): Sandbox 10 req/min (CS2
props only), Hobby 30, Builder 100, Pro 250, Quant 500. Set KASHROCK_RPM
to your plan's requests-per-minute; the default of 10 stays inside Sandbox.
HTTP errors surface as KashRockError; transport errors propagate to the
caller, which logs and skips the poll.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


class RateLimiter:
    """Token bucket: at most ``rpm`` acquisitions per 60-second window.

    ``sleep`` and ``monotonic`` are injectable so tests can drive a fake
    clock instead of waiting on real time.
    """

    def __init__(self, rpm: int, sleep=None, monotonic=None):
        import time

        self.interval = 60.0 / max(1, int(rpm))
        self._sleep = sleep or time.sleep
        self._monotonic = monotonic or time.monotonic
        self._next_at = 0.0

    def acquire(self) -> None:
        now = self._monotonic()
        wait = self._next_at - now
        if wait > 0:
            self._sleep(wait)
            now = self._monotonic()
        self._next_at = max(now, self._next_at) + self.interval


class KashRockError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(f"KashRock API {status}: {detail}")
        self.status = status
        self.detail = detail


class KashRockClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        limiter: Optional[RateLimiter] = None,
        opener=urllib.request.urlopen,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.limiter = limiter or RateLimiter(10)
        self._open = opener

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None and v != ""}
        )
        url = f"{self.base_url}{path}?{query}"
        request = urllib.request.Request(url, headers={"x-api-key": self.api_key})
        self.limiter.acquire()
        try:
            with self._open(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            raise KashRockError(exc.code, body) from exc

    def get_props(
        self,
        sport: str,
        board: str = "all",
        view: str = "props",
        market: Optional[str] = None,
        player: Optional[str] = None,
        book: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """GET /v7/{sport}/props — flat prop rows (view=props, format=slim)."""
        return self._get(
            f"/v7/{sport}/props",
            {
                "board": board,
                "view": view,
                "format": "slim",
                "market": market,
                "player": player,
                "book": book,
                "limit": limit,
                "offset": offset or None,
            },
        )
