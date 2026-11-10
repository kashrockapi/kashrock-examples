"""Alert payloads -> Discord embeds.

Isolated from bot.py so the formatting is one small module. Book display
names come from the API rows themselves; external servers cannot render
KashRock's custom emojis, so text names are correct here.
"""

from __future__ import annotations

from typing import Any

import discord

UTM_LINK = (
    "https://www.kashrock.com/?utm_source=discord"
    "&utm_medium=social&utm_campaign=discord_odds_alert_bot"
)

# Discord embed limits: 25 fields per embed, 6000 chars total per embed.
# max_fields_per_message stays under both with margin.
MAX_FIELDS = 25
MAX_FIELD_NAME = 256
MAX_FIELD_VALUE = 1024


def build_message(payloads: list[dict[str, Any]], max_fields: int = 20) -> list[discord.Embed]:
    """Chunk alert payloads into embeds of at most ``max_fields`` each."""
    embeds: list[discord.Embed] = []
    per = max(1, min(max_fields, MAX_FIELDS))
    for start in range(0, len(payloads), per):
        chunk = payloads[start : start + per]
        embed = discord.Embed(
            title="Esports Odds Alerts",
            description=f"{len(payloads)} new or repriced offers",
            color=discord.Color.blurple(),
        )
        embed.set_author(name="Powered by KashRock", url=UTM_LINK)
        for payload in chunk:
            lines = [
                payload["match"],
                f"**{payload['player']}** - {payload['market']}",
                payload["price"],
                payload["book"],
                payload["event_time_et"],
            ]
            value = "\n".join(line for line in lines if line)
            if payload["deeplink"]:
                value += f"\n[View odds]({payload['deeplink']})"
            embed.add_field(
                name=f"{payload['sport'].upper()} · {payload['player'] or 'Prop'}"[
                    :MAX_FIELD_NAME
                ],
                value=value[:MAX_FIELD_VALUE],
                inline=False,
            )
        embeds.append(embed)
    return embeds
