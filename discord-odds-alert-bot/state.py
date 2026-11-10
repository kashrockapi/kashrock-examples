"""Dedupe state: which offers were already alerted, and at what price.

JSON file, atomic writes. Entries older than ``max_age_days`` are pruned on
save so the file stays small; an offer that left the board for longer than
that and returns alerts again, which is correct — it is a fresh offer.
A corrupt state file fails loudly at startup: delete it and restart to
re-alert the current board once.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


class StateFileError(Exception):
    pass


class SeenStore:
    def __init__(self, path: Path, max_age_days: float = 14.0):
        self.path = Path(path)
        self.max_age_days = max_age_days
        self._entries: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateFileError(
                f"state file {self.path} is unreadable: {exc}. "
                "Delete it and restart to rebuild alert state."
            ) from exc
        entries = data.get("seen") if isinstance(data, dict) else None
        if entries is not None and not isinstance(entries, dict):
            raise StateFileError(f"state file {self.path} has an unexpected shape")
        return entries or {}

    def is_empty(self) -> bool:
        return not self._entries

    def is_new(self, offer: str, fingerprint: str) -> bool:
        entry = self._entries.get(offer)
        return entry is None or entry.get("fingerprint") != fingerprint

    def mark(self, offer: str, fingerprint: str) -> None:
        self._entries[offer] = {
            "fingerprint": fingerprint,
            "seen_at": time.time(),
        }

    def save(self) -> None:
        cutoff = time.time() - self.max_age_days * 86400
        self._entries = {
            key: entry
            for key, entry in self._entries.items()
            if float(entry.get("seen_at") or 0) >= cutoff
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps({"seen": self._entries}, indent=1, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)
