"""Settings for the Discord odds alert bot.

Values come from the environment first; an optional JSON file
(``bot.config.json`` next to bot.py, or the path in ``BOT_CONFIG``) supplies
defaults for anything the environment does not set. Environment always wins.

Nothing here is a secret except the two tokens, which live in .env only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = "https://kashrock.up.railway.app"

# The nine titles /v7/meta advertises on the live API.
ALL_SPORTS = ["apex", "cod", "cs2", "deadlock", "dota2", "lol", "mlbb", "r6", "valorant"]


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def _csv(value: str) -> list[str]:
    return [part.strip().lower() for part in value.split(",") if part.strip()]


def _load_file(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"error: cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: {path} must contain a JSON object")
    return data


def _pick(env_name: str, cfg: dict, cfg_key: str, default: str = "") -> str:
    env = os.environ.get(env_name, "").strip()
    if env:
        return env
    value = cfg.get(cfg_key, "")
    if isinstance(value, (list, tuple)):
        value = ",".join(str(v) for v in value)
    value = str(value).strip() if value is not None else ""
    return value or default


@dataclass
class Settings:
    kashrock_base: str = DEFAULT_BASE
    api_key: str = ""
    discord_token: str = ""
    channel_id: int = 0
    guild_id: int = 0
    sports: list[str] = field(default_factory=lambda: ["cs2"])
    board: str = "all"
    markets: list[str] = field(default_factory=list)
    books: list[str] = field(default_factory=list)
    players: list[str] = field(default_factory=list)
    interval_minutes: float = 5.0
    rpm: int = 10
    state_path: Path = HERE / "odds_alert_state.json"
    max_fields_per_message: int = 20

    @property
    def needs_discord(self) -> bool:
        return bool(self.discord_token)


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or Path(_env("BOT_CONFIG", str(HERE / "bot.config.json")))
    cfg = _load_file(path)

    sports_raw = _pick("KASHROCK_SPORT", cfg, "sports", "cs2")
    sports = [s.strip().lower() for s in sports_raw.split(",") if s.strip()]
    for sport in sports:
        if sport not in ALL_SPORTS:
            raise SystemExit(
                f"error: unknown sport {sport!r}; valid: {', '.join(ALL_SPORTS)}"
            )

    board = _pick("KASHROCK_BOARD", cfg, "board", "all").lower()
    if board not in ("dfs", "main", "all"):
        raise SystemExit("error: KASHROCK_BOARD must be dfs, main, or all")

    interval = float(_pick("POLL_INTERVAL_MINUTES", cfg, "interval_minutes", "5") or 5)
    if interval <= 0:
        raise SystemExit("error: POLL_INTERVAL_MINUTES must be positive")

    rpm_raw = _pick("KASHROCK_RPM", cfg, "rpm", "10")
    try:
        rpm = int(rpm_raw)
    except ValueError as exc:
        raise SystemExit("error: KASHROCK_RPM must be an integer") from exc
    if rpm <= 0:
        raise SystemExit("error: KASHROCK_RPM must be positive")

    state = Path(_pick("STATE_FILE", cfg, "state_file", str(HERE / "odds_alert_state.json")))

    def _int_env(name: str, cfg_key: str, default: int) -> int:
        raw = _pick(name, cfg, cfg_key, str(default))
        try:
            return int(raw)
        except ValueError as exc:
            raise SystemExit(f"error: {name} must be an integer") from exc

    return Settings(
        kashrock_base=_pick("KASHROCK_BASE", cfg, "base", DEFAULT_BASE).rstrip("/"),
        api_key=_pick("KASHROCK_API_KEY", cfg, "api_key"),
        discord_token=_pick("DISCORD_TOKEN", cfg, "discord_token")
        or _pick("DISCORD_BOT_TOKEN", cfg, "discord_bot_token"),
        channel_id=_int_env("DISCORD_CHANNEL_ID", "channel_id", 0),
        guild_id=_int_env("DISCORD_GUILD_ID", "guild_id", 0),
        sports=sports,
        board=board,
        markets=_csv(_pick("KASHROCK_MARKETS", cfg, "markets")),
        books=_csv(_pick("KASHROCK_BOOKS", cfg, "books")),
        players=_csv(_pick("KASHROCK_PLAYERS", cfg, "players")),
        interval_minutes=interval,
        rpm=rpm,
        state_path=state,
        max_fields_per_message=_int_env("MAX_ALERTS_PER_MESSAGE", "max_fields_per_message", 20),
    )


def load_env_file(path: Path = HERE / ".env") -> None:
    """Minimal .env loader (same pattern as bots/discord/bot.py): only fills
    variables that are not already set, so real environment always wins."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value
