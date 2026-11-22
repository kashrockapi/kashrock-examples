"""AI agent example: what a coding agent does with the KashRock MCP server.

Connects to the hosted MCP server, discovers its tools (the capability list an
agent sees), calls v7_meta to read the key's plan, calls one data tool, and
validates the output the way PROMPT.md tells an agent to.

Run:

    pip install -r requirements.txt
    cp .env.example .env
    python agent_check.py

Docs: https://www.kashrock.com/docs/mcp  Skill: https://www.kashrock.com/SKILL.md
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.environ.get("KASHROCK_MCP_URL", "https://mcp.kashrock.com/mcp")
ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def body(result) -> dict:
    """Tool results arrive as text content holding JSON."""
    text = "".join(getattr(c, "text", "") for c in result.content)
    return json.loads(text) if text.strip().startswith("{") else {"text": text}


async def run(api_key: str) -> int:
    async with streamablehttp_client(MCP_URL, headers={"x-api-key": api_key}) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(f"1. discovered {len(tools)} tools, e.g. {', '.join(t.name for t in tools[:6])}")

            meta = body(await session.call_tool("v7_meta", {}))
            plan = meta.get("plan")
            print(f"2. v7_meta: plan={plan}, sports={meta.get('sports')}")

            matches = body(await session.call_tool("v7_matches", {"sport": "cs2", "status": "upcoming", "limit": 3}))
            rows = matches.get("matches") or []
            print(f"3. v7_matches: {len(rows)} upcoming CS2 matches")

            problems = []
            if plan in (None, "demo"):
                problems.append("v7_meta did not return a real plan: check the key")
            for m in rows:
                if not str(m.get("kr_match_id", "")).startswith("kr_cs2_"):
                    problems.append(f"unexpected id {m.get('kr_match_id')!r}")
            print("4. validation:", "ok" if not problems else "; ".join(problems))
            return 1 if problems else 0


def main() -> int:
    load_dotenv(ENV_PATH)
    key = os.environ.get("KASHROCK_API_KEY", "").strip()
    if not key:
        print("Set KASHROCK_API_KEY (get a free key at https://www.kashrock.com/console).")
        return 1
    return asyncio.run(run(key))


if __name__ == "__main__":
    sys.exit(main())
