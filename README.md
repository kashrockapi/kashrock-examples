# KashRock Examples

Working developer examples for the [KashRock](https://www.kashrock.com) esports data API. Each example is a small, runnable app that talks to the public V7 REST API with a normal API key. No sample data: every row comes from the live API.

| Example | What it builds | Plans |
| --- | --- | --- |
| [cs2-props-dashboard](cs2-props-dashboard) | Player props research app: live CS2 prop board across DFS apps and sportsbooks, plus consensus lines | Free Sandbox works; lines view needs Hobby+ |
| [cs2-live-dashboard](cs2-live-dashboard) | CS2 live dashboard: live matches, score and player stats, then live WebSocket pushes | Hobby+ for the board; Builder+ for the WebSocket |
| [esports-odds-monitor](esports-odds-monitor) | Odds monitor: best price per side across books next to the fair price, and what moved | Hobby+ |
| [ai-agent-example](ai-agent-example) | AI agent example: connect to the hosted MCP server, discover tools, call them, check the output | Any plan, including Sandbox |
| [lol-research-dashboard](lol-research-dashboard) | Flask web app: LoL matches, players, teams, graded results, quote tapes | Sandbox browses; deeper history needs Hobby+ |
| [discord-odds-alert-bot](discord-odds-alert-bot) | Discord bot that polls the props board and posts new or repriced offers | Sandbox fine for one sport on a slow poll |

Get a free API key at <https://www.kashrock.com/console>. Full docs: <https://www.kashrock.com/docs>.

These examples were previously maintained inside the main KashRock repository. If you are looking at this repo, this is the public home for them.
