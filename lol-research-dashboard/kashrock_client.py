"""Minimal KashRock V7 REST client for the example apps.

Self-contained on purpose: each example carries its own copy so a reader can
copy one folder out of the repo and run it without the rest of KashRock.

Only stdlib + requests. Auth is the x-api-key header; the key comes from
KASHROCK_API_KEY and is never logged or printed.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import requests

DEFAULT_BASE_URL = "https://kashrock.up.railway.app"


class KashRockError(Exception):
    """A KashRock API error carrying the status, code and plain-English message."""

    def __init__(self, status: int, code: str, message: str, retry_after: Optional[float] = None):
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.retry_after = retry_after


def _error_fields(resp: requests.Response) -> tuple[str, str]:
    """Pull (code, message) out of a V7 error body.

    Every /v7 error body is {"error": {"code", "message", ...}}. If the body is
    not that shape (a proxy page, an empty reply), the status and the first
    bytes of the body still tell the caller what happened; nothing is hidden.
    """
    try:
        body = resp.json()
    except ValueError:
        snippet = resp.text[:200].strip() or resp.reason or "empty body"
        return "http_error", f"HTTP {resp.status_code}: {snippet}"
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return str(err.get("code") or "http_error"), str(err.get("message") or resp.reason or "")
    if isinstance(body, dict) and body.get("detail"):
        # Some routes answer FastAPI-style {"detail": ..., "reason": ...}
        # (for example a 504 request_timeout while a tape builds).
        reason = body.get("reason")
        detail = str(body["detail"])
        return str(reason or "http_error"), f"{detail} ({reason})" if reason else detail
    return "http_error", str(body)[:200] if body else (resp.reason or "")


class KashRockClient:
    def __init__(self, api_key: str, base_url: Optional[str] = None, timeout: float = 30.0):
        if not api_key:
            raise KashRockError(0, "missing_key", "Set KASHROCK_API_KEY to a key from your KashRock console.")
        self.base_url = (base_url or os.environ.get("KASHROCK_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": api_key, "accept": "application/json"})

    @classmethod
    def from_env(cls) -> "KashRockClient":
        return cls(api_key=os.environ.get("KASHROCK_API_KEY", "").strip())

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> Dict[str, Any]:
        """GET a /v7 path. Returns the decoded JSON body, raises KashRockError.

        ``timeout`` overrides the client default for endpoints that build
        their answer on demand (history tapes can take a minute on a cold
        match; the API also answers available:false + retry_after_seconds
        while a tape warms).
        """
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.get(url, params=params, timeout=timeout or self.timeout)
        except requests.RequestException as exc:
            raise KashRockError(0, "network_error", f"Could not reach {self.base_url}: {exc}") from exc

        if resp.status_code >= 400:
            code, message = _error_fields(resp)
            retry_after = None
            if resp.status_code == 429:
                header = resp.headers.get("Retry-After")
                if header and header.replace(".", "", 1).isdigit():
                    retry_after = float(header)
            raise KashRockError(resp.status_code, code, message or f"HTTP {resp.status_code}", retry_after)
        return resp.json()

    def get_with_retry(self, path: str, params: Optional[Dict[str, Any]] = None, attempts: int = 3) -> Dict[str, Any]:
        """GET with a small bounded retry that honors the API's Retry-After on 429."""
        for i in range(attempts):
            try:
                return self.get(path, params)
            except KashRockError as exc:
                if exc.status == 429 and i < attempts - 1:
                    time.sleep(min(exc.retry_after or 5.0, 30.0))
                    continue
                raise
        raise AssertionError("unreachable")
