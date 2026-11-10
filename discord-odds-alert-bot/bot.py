"""Discord glue for the KashRock odds alert bot.

Polls GET /v7/{sport}/props on an interval (runner.py does the work), posts
new or repriced offers to a channel as embeds, and serves /odds on demand.

    cp .env.example .env   # fill in KASHROCK_API_KEY and DISCORD_TOKEN
    pip install -r requirements.txt
    python bot.py --selftest     # one live fetch cycle, no Discord needed
    python bot.py --dry-run      # poll loop, prints alerts instead of posting
    python bot.py                # connect and run

Plan note: Sandbox (free) is CS2 props only at 10 requests/minute, fine for
this bot with the default settings. Multi-sport boards and the main
(sportsbook) board need Hobby or above; see README.md for the plan table.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import tasks

from alerts import prop_rows, row_matches
from config import Settings, load_env_file, load_settings
from embeds import build_message
from kashrock_client import KashRockError
from render import alert_payload
from runner import (
    FETCH_ERRORS,
    make_client,
    mark_pairs,
    pairs_of,
    payloads_of,
    poll_cycle,
    run_dry_run,
    run_selftest,
    seed_summary,
)
from state import SeenStore

log = logging.getLogger("odds-alert-bot")


async def post_cycle(
    settings: Settings,
    client,
    store: SeenStore,
    channel: discord.TextChannel,
) -> int:
    """Fetch, post embeds, then mark state. Marks only after delivery so a
    failed send retries the same alerts on the next poll. The first poll on
    an empty state store seeds the baseline with one summary message instead
    of posting the entire board as "new"."""
    first_run, cycle = await poll_cycle(settings, client, store)
    if not cycle:
        return 0
    if first_run:
        await channel.send(seed_summary(cycle, settings))
    else:
        payloads = payloads_of(cycle)
        for embed in build_message(payloads, settings.max_fields_per_message):
            await channel.send(embed=embed)
        log.info("posted %d alerts", len(payloads))
    mark_pairs(store, pairs_of(cycle))
    store.save()
    return sum(len(pairs) for _sport, pairs in cycle)


def build_bot(settings: Settings) -> discord.Client:
    client = discord.Client(intents=discord.Intents.default())
    tree = app_commands.CommandTree(client)
    kr = make_client(settings)
    store = SeenStore(settings.state_path)

    @tree.command(name="odds", description="Show the current esports odds board")
    @app_commands.describe(sport="Sport to check")
    @app_commands.choices(
        sport=[app_commands.Choice(name=s.upper(), value=s) for s in settings.sports]
    )
    async def odds_cmd(interaction: discord.Interaction, sport: str = "") -> None:
        chosen = sport or settings.sports[0]
        await interaction.response.defer()
        try:
            body = await asyncio.to_thread(
                kr.get_props, chosen, board=settings.board, view="props"
            )
        except FETCH_ERRORS as exc:
            await interaction.followup.send(f"KashRock API error: {exc}")
            return
        payloads = [
            alert_payload(row, chosen)
            for row in prop_rows(body)
            if row_matches(row, settings)
        ][:10]
        if not payloads:
            await interaction.followup.send("No props match the current filters.")
            return
        await interaction.followup.send(
            embeds=build_message(payloads, settings.max_fields_per_message)[:10]
        )

    @client.event
    async def on_ready() -> None:
        log.info("logged in as %s", client.user)
        if settings.guild_id:
            guild = discord.Object(id=settings.guild_id)
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
        else:
            await tree.sync()
        log.info("slash commands synced")

    @client.event
    async def setup_hook() -> None:
        if not settings.channel_id:
            log.warning(
                "DISCORD_CHANNEL_ID not set; /odds works but no scheduled posts"
            )
            return

        @tasks.loop(seconds=settings.interval_minutes * 60)
        async def poll() -> None:
            channel = client.get_channel(settings.channel_id)
            if channel is None:
                log.warning(
                    "channel %s not found or not visible", settings.channel_id
                )
                return
            try:
                await post_cycle(settings, kr, store, channel)
            except FETCH_ERRORS as exc:
                log.warning("poll cycle failed: %s", exc)
            except discord.DiscordException as exc:
                log.warning("discord send failed: %s", exc)

        poll.before_loop(client.wait_until_ready)
        poll.start()
        log.info("polling every %.1f minutes", settings.interval_minutes)

    return client


def main() -> int:
    parser = argparse.ArgumentParser(description="Discord odds alerts via KashRock")
    parser.add_argument(
        "--selftest", action="store_true", help="one live fetch cycle, no Discord"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="poll loop, print alerts as JSON"
    )
    parser.add_argument(
        "--config", type=Path, default=None, help="path to JSON config file"
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_env_file()
    settings = load_settings(args.config)

    if args.selftest:
        return run_selftest(settings)
    if args.dry_run:
        return run_dry_run(settings)
    if not settings.discord_token:
        print(
            "error: DISCORD_TOKEN is not set (or pass --selftest/--dry-run)",
            file=sys.stderr,
        )
        return 2

    build_bot(settings).run(settings.discord_token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
