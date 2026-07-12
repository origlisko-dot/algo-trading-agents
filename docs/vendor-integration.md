# Vendor Integration: Graphify + Craft Agents

This project vendors two upstream tools as local clones:

| Vendor | Path | Purpose |
|--------|------|---------|
| [Graphify](https://github.com/Graphify-Labs/graphify) | `graphify/` | Knowledge-graph mapping and query for `algo_agents/` |
| [Craft Agents OSS](https://github.com/craft-ai-agents/craft-agents-oss) | `craft-agents-oss/` | Desktop/headless agent UI with MCP sources and skills |

## Graphify

### Installed

- Editable install: `pip install -e graphify` (plus `pip install "graphifyy[mcp]"` for MCP)
- Knowledge graph built at `algo_agents/graphify-out/` (493 nodes, 914 edges)
- Cursor rule: `.cursor/rules/graphify.mdc`
- Project skill: `.agents/skills/algo-trading/SKILL.md`

### Commands

```bash
# Rebuild graph after code changes (AST-only, no API key)
graphify update algo_agents

# Full rebuild
graphify extract algo_agents --code-only
graphify cluster-only algo_agents

# Query
graphify query "How does paper trading connect to risk manager?"
graphify explain "SimulatedBroker"
graphify path "RunContext" "AlpacaBroker"

# MCP launcher (used by Craft workspace)
python scripts/run_graphify_mcp.py
```

### Outputs

```
algo_agents/graphify-out/
├── graph.json          # full graph — query with CLI or MCP
├── GRAPH_REPORT.md     # hubs, god nodes, suggested questions
└── .graphify_analysis.json
```

## Craft Agents OSS

### Prerequisites

1. [Bun](https://bun.sh/) runtime
2. API key: `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, or another supported provider

### Install (from clone)

```powershell
# Install Bun (Windows)
irm https://bun.sh/install.ps1 | iex

cd craft-agents-oss
bun install
```

### Project workspace

A pre-configured workspace lives at `craft-workspace/`:

- **Source: algo-trading-repo** — local filesystem pointing at the repo root
- **Source: graphify-mcp** — stdio MCP via `python scripts/run_graphify_mcp.py`
- **Skill: algo-trading** — paper-first trading rules and verification commands

### Run options

**Desktop app (from source):**

```bash
cd craft-agents-oss
bun run electron:start
```

Import the workspace: point Craft at `craft-workspace/` or copy it to `~/.craft-agent/workspaces/`.

**CLI (self-contained, no prior server):**

```bash
cd craft-agents-oss
ANTHROPIC_API_KEY=sk-... bun run apps/cli/src/index.ts run \
  --workspace-dir ../craft-workspace \
  --source algo-trading-repo \
  --source graphify-mcp \
  "@algo-trading List connector health checks and how to run them"
```

**Headless server:**

```bash
cd craft-agents-oss
CRAFT_SERVER_TOKEN=$(openssl rand -hex 32) bun run packages/server/src/index.ts
```

### Environment

Copy `craft-agents-oss/.env.example` to `craft-agents-oss/.env` for OAuth integrations (Google, Slack, Microsoft). Core repo keys stay in project-root `.env`.

## Git hygiene

Vendored clones and build artifacts are gitignored:

- `graphify/` and `craft-agents-oss/` (upstream clones)
- `algo_agents/graphify-out/` (generated graph)
- `craft-agents-oss/node_modules/`, `craft-workspace/sessions/`

To track vendored versions, note the pinned commits in this doc or a `VENDORS.md` lockfile.

## Quick verification

```bash
# Graphify
graphify query "What is MLSignalStrategy?" --graph algo_agents/graphify-out/graph.json

# Craft CLI (after bun install)
cd craft-agents-oss && bun run apps/cli/src/index.ts run \
  --workspace-dir ../craft-workspace "Summarize the AGENTIC-OS architecture"
```
