# KashRock Examples

Starter apps for [KashRock](https://www.kashrock.com/agents?utm_source=github&utm_medium=repo&utm_campaign=distribution_2026&utm_content=examples_readme): real-time esports data for applications, models, and AI agents.

Each app calls the live V7 API with your key. There is no sample board in the repo.

[![PyPI](https://img.shields.io/pypi/v/kashrock-mcp)](https://pypi.org/project/kashrock-mcp/)
[![MCP](https://img.shields.io/badge/MCP-0.7.0-111)](https://www.kashrock.com/agents?utm_source=github&utm_medium=repo&utm_campaign=distribution_2026&utm_content=examples_badge)

## Start in under 5 minutes

1. Create a free key at [console](https://www.kashrock.com/console?utm_source=github&utm_medium=repo&utm_campaign=distribution_2026&utm_content=examples_signup). No card.
2. Export it: `export KASHROCK_API_KEY=your_key`
3. Open one starter below, follow its README, and run it.

Agents and coding tools: [Agents](https://www.kashrock.com/agents?utm_source=github&utm_medium=repo&utm_campaign=distribution_2026&utm_content=examples_agents), [SKILL.md](https://www.kashrock.com/SKILL.md), [llms.txt](https://www.kashrock.com/llms.txt). Docs: [Docs](https://www.kashrock.com/docs?utm_source=github&utm_medium=repo&utm_campaign=distribution_2026&utm_content=examples_docs).

## Four starters

| Starter | What you get | Plan | Screenshot |
| --- | --- | --- | --- |
| [CS2 props dashboard](cs2-props-dashboard) | Live CS2 prop board across DFS apps and sportsbooks | Sandbox for props. Lines view needs Hobby. | [screenshot](cs2-props-dashboard/screenshot.jpg) |
| [CS2 live dashboard](cs2-live-dashboard) | Live matches, score, player stats, then a live socket | Hobby for the board. Builder for the socket. | [screenshot](cs2-live-dashboard/screenshot.jpg) |
| [Esports odds monitor](esports-odds-monitor) | Best price per side next to the fair price, and what moved | Hobby | [screenshot](esports-odds-monitor/screenshot.jpg) |
| [AI agent](ai-agent-example) | Connect to the hosted MCP server, list tools, call them | Any plan, including Sandbox | [screenshot](ai-agent-example/screenshot.jpg) |

## More apps

| App | What you get | Plan |
| --- | --- | --- |
| [LoL research dashboard](lol-research-dashboard) | LoL matches, players, teams, grades, quote tapes | Hobby for matches. History tape is Builder and up. Sandbox is CS2 only. |
| [Discord odds bot](discord-odds-alert-bot) | Polls the props board and posts new or repriced offers | Sandbox is enough for one sport on a slow poll. |

Titles on the API: CS2, Valorant, League of Legends, Dota 2, Call of Duty, Rainbow Six, Mobile Legends, Deadlock, Apex Legends, Overwatch. Props, live boards, and grades exist when that title has them. An empty board is an empty board.

Package: [`kashrock-mcp` on PyPI](https://pypi.org/project/kashrock-mcp/).
