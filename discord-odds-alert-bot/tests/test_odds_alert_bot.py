"""Tests for the Discord odds alert bot: filters, rendering, dedupe state,
rate-limit pacing, and the HTTP client. All HTTP is mocked; no live calls."""

from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alerts import fingerprint, offer_id, prop_rows, row_matches, select_new
from config import Settings
from kashrock_client import KashRockClient, KashRockError, RateLimiter
from render import alert_payload
from state import SeenStore, StateFileError

# Row shape verified live against GET /v7/cs2/props?board=all&view=props&format=slim
SAMPLE_ROW = {
    "book_name": "PrizePicks",
    "sportsbook_name": "prizepicks",
    "propId": "kr_prop_30d903dd545c",
    "player_name": "molodoy",
    "player_id": "kr_pl_d397d89c0281",
    "stat_type": "CS2_KILLS_MAPS_1_2",
    "market_type": "kills",
    "market_label": "Kills on Maps 1+2",
    "market_scope": "maps_1_2",
    "line": 32.5,
    "odds": -137,
    "direction": "over",
    "home_team": "FURIA",
    "away_team": "Legacy",
    "canonical_event_name": "FURIA vs Legacy",
    "event_time": "2026-11-11T02:00:00.000Z",
    "decimal_odds": 1.7299,
    "offerId": "kr_prop_30d903dd545c_1_over",
    "canonical_offer_id": "kr_prop_30d903dd545c_1_over",
    "deeplink": "https://example-book.com/projection",
}


def settings(**over) -> Settings:
    base = dict(api_key="kr_test", discord_token="", sports=["cs2"])
    base.update(over)
    return Settings(**base)


class TestFilters:
    def test_empty_filters_match_everything(self):
        assert row_matches(SAMPLE_ROW, settings()) is True

    def test_market_filter_matches_market_type_and_label(self):
        cfg = settings(markets=["kills"])
        assert row_matches(SAMPLE_ROW, cfg) is True
        cfg = settings(markets=["headshots"])
        assert row_matches(SAMPLE_ROW, cfg) is False

    def test_book_filter_uses_book_key(self):
        assert row_matches(SAMPLE_ROW, settings(books=["prizepicks"])) is True
        assert row_matches(SAMPLE_ROW, settings(books=["underdog"])) is False

    def test_player_filter_is_substring(self):
        assert row_matches(SAMPLE_ROW, settings(players=["molo"])) is True
        assert row_matches(SAMPLE_ROW, settings(players=["zywoo"])) is False

    def test_prop_rows_reads_flat_view(self):
        body = {"props": [SAMPLE_ROW], "total": 1}
        assert prop_rows(body) == [SAMPLE_ROW]
        assert prop_rows({"props": None}) == []
        assert prop_rows({}) == []


class TestSelectNew:
    def test_first_poll_alerts_everything(self, tmp_path):
        store = SeenStore(tmp_path / "s.json")
        cfg = settings()
        rows = select_new([SAMPLE_ROW], cfg, store)
        assert len(rows) == 1

    def test_second_poll_same_price_is_quiet(self, tmp_path):
        store = SeenStore(tmp_path / "s.json")
        cfg = settings()
        select_new([SAMPLE_ROW], cfg, store)
        store.mark(offer_id(SAMPLE_ROW), fingerprint(SAMPLE_ROW))
        store.save()
        reloaded = SeenStore(tmp_path / "s.json")
        assert select_new([SAMPLE_ROW], cfg, reloaded) == []

    def test_moved_line_realerts(self, tmp_path):
        store = SeenStore(tmp_path / "s.json")
        cfg = settings()
        select_new([SAMPLE_ROW], cfg, store)
        store.mark(offer_id(SAMPLE_ROW), fingerprint(SAMPLE_ROW))
        moved = dict(SAMPLE_ROW, line=33.5)
        assert len(select_new([moved], cfg, store)) == 1

    def test_filters_apply_before_dedupe(self, tmp_path):
        store = SeenStore(tmp_path / "s.json")
        cfg = settings(markets=["headshots"])
        assert select_new([SAMPLE_ROW], cfg, store) == []


class TestRender:
    def test_payload_fields(self):
        payload = alert_payload(SAMPLE_ROW, "cs2")
        assert payload["player"] == "molodoy"
        assert payload["match"] == "FURIA vs Legacy"
        assert payload["book"] == "PrizePicks"
        assert payload["selection"] == "Over 32.5"
        assert payload["odds_american"] == "-137"
        assert payload["deeplink"] == "https://example-book.com/projection"
        assert payload["event_time_et"].endswith("ET")

    def test_under_direction(self):
        row = dict(SAMPLE_ROW, direction="under")
        assert alert_payload(row, "cs2")["selection"] == "Under 32.5"


class TestSeenStore:
    def test_persistence_roundtrip(self, tmp_path):
        path = tmp_path / "state.json"
        store = SeenStore(path)
        store.mark("offer_1", "32.5|-137")
        store.save()
        again = SeenStore(path)
        assert again.is_new("offer_1", "32.5|-137") is False
        assert again.is_new("offer_1", "33.5|-137") is True
        assert again.is_new("offer_2", "32.5|-137") is True

    def test_corrupt_file_fails_loudly(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(StateFileError):
            SeenStore(path)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.slept = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds


class TestRateLimiter:
    def test_paces_requests_to_rpm(self):
        clock = FakeClock()
        limiter = RateLimiter(60, sleep=clock.sleep, monotonic=clock.monotonic)
        limiter.acquire()
        limiter.acquire()
        limiter.acquire()
        # 60 rpm = one request per second; third acquire waits ~1s twice.
        assert clock.slept == pytest.approx([1.0, 1.0])

    def test_sandbox_rpm_is_one_per_six_seconds(self):
        clock = FakeClock()
        limiter = RateLimiter(10, sleep=clock.sleep, monotonic=clock.monotonic)
        limiter.acquire()
        limiter.acquire()
        assert clock.slept == pytest.approx([6.0])


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestClient:
    def test_get_props_builds_v7_url_and_params(self):
        seen = {}

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["key"] = request.headers.get("X-api-key")
            return FakeResponse({"props": [], "total": 0})

        client = KashRockClient(
            "https://kashrock.up.railway.app",
            "kr_test",
            limiter=RateLimiter(1000),
            opener=opener,
        )
        body = client.get_props("cs2", board="all", view="props")
        assert body["total"] == 0
        assert seen["url"].startswith(
            "https://kashrock.up.railway.app/v7/cs2/props?"
        )
        for param in ("board=all", "view=props", "format=slim"):
            assert param in seen["url"]
        assert seen["key"] == "kr_test"

    def test_http_error_becomes_kashrock_error(self):
        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"detail":"no"}')
            )

        client = KashRockClient(
            "https://kashrock.up.railway.app",
            "kr_test",
            limiter=RateLimiter(1000),
            opener=opener,
        )
        with pytest.raises(KashRockError) as excinfo:
            client.get_props("lol")
        assert excinfo.value.status == 403

    def test_limiter_runs_before_request(self):
        clock = FakeClock()
        calls = []

        def opener(request, timeout):
            calls.append(clock.now)
            return FakeResponse({})

        client = KashRockClient(
            "https://example.com",
            "kr_test",
            limiter=RateLimiter(60, sleep=clock.sleep, monotonic=clock.monotonic),
            opener=opener,
        )
        client.get_props("cs2")
        client.get_props("cs2")
        assert calls == [0.0, pytest.approx(1.0)]


class TestPollCycle:
    @pytest.mark.asyncio
    async def test_first_run_flag_and_empty_board(self, tmp_path):
        import runner

        class StubClient:
            def get_props(self, sport, **kwargs):
                return {"props": [SAMPLE_ROW]}

        cfg = settings()
        store = SeenStore(tmp_path / "s.json")
        first_run, cycle = await runner.poll_cycle(cfg, StubClient(), store)
        assert first_run is True
        assert len(cycle) == 1
        assert len(cycle[0][1]) == 1
        # State is not mutated by the poll itself.
        assert store.is_empty()

    @pytest.mark.asyncio
    async def test_second_run_not_first(self, tmp_path):
        import runner

        class StubClient:
            def get_props(self, sport, **kwargs):
                return {"props": [SAMPLE_ROW]}

        cfg = settings()
        store = SeenStore(tmp_path / "s.json")
        _first, cycle = await runner.poll_cycle(cfg, StubClient(), store)
        runner.mark_pairs(store, runner.pairs_of(cycle))
        store.save()
        store2 = SeenStore(tmp_path / "s.json")
        first_run, cycle2 = await runner.poll_cycle(cfg, StubClient(), store2)
        assert first_run is False
        assert cycle2 == []

    @pytest.mark.asyncio
    async def test_fetch_error_skips_sport_not_crash(self, tmp_path, caplog):
        import logging

        import runner

        class BadClient:
            def get_props(self, sport, **kwargs):
                raise KashRockError(500, "boom")

        cfg = settings(sports=["cs2", "dota2"])
        store = SeenStore(tmp_path / "s.json")
        with caplog.at_level(logging.WARNING):
            first_run, cycle = await runner.poll_cycle(cfg, BadClient(), store)
        assert cycle == []
        assert "props fetch failed" in caplog.text
