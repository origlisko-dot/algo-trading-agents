# algo-trading-agents

> Project soul & continuity for other devices/sessions: **[SOUL.md](SOUL.md)**

A research scaffold for building ML / agent-based trading systems for **US
equities**, with first-class **connectors to everything**: brokers, market
data, news, Hugging Face sentiment models, and a vector-store memory.

> [!WARNING]
> **Read this first.** Academic research across 8 countries finds that
> **70%–97% of day traders lose money**, and under ~1% are consistently
> profitable. ~70% of *retail algo* traders also lose. This repo is an
> engineering scaffold, **not** a money machine and **not** financial advice.
> The goal is a small, well-managed statistical edge — proven out-of-sample on
> **paper trading** — before any real capital. Default mode is paper. Keep it
> that way until you have evidence.

## Architecture

```
DATA  ->  FEATURES  ->  DECISION BRAIN  ->  RISK MANAGER  ->  EXECUTION
prices    technical +   ML signal + RL      position sizing    broker API
news      fundamentals  alloc + LLM agents   stops / limits     (paper->live)
alt-data  sentiment     (debate + memory)    kill-switch
  ^                          |                                     |
  |                          v                                     v
  +-------  MEMORY  +  SELF-IMPROVEMENT LOOP  <----  MONITORING (P&L, drift)
            reflection · vector DB · RL fine-tune · evolutionary search
```

Three paradigms, layered (not competing): supervised ML for signals, RL for
allocation/timing, and LLM agents for the research/reasoning layer — all
wrapped in a hard risk overlay. See the in-chat research brief for the full
rationale and the references (TradingAgents, FinMem, FinRL-X, Qlib).

## AGENTIC-OS + Graphify

**AGENTIC-OS** (`algo_agents/os/`, `scripts/run_agentic_os.py`) is the unified
orchestrator for paper-first workflows:

| Command | What it does |
|---------|----------------|
| `python scripts/run_agentic_os.py list` | Registered jobs |
| `python scripts/run_agentic_os.py status` | Active strategy, schedule, watchlist, PnL |
| `python scripts/run_agentic_os.py daily --mock --skip-eval` | Full daily pipeline |
| `python scripts/run_agentic_os.py job <name>` | Single job |
| `python scripts/run_agentic_os.py schedule --once` | Scheduler poll |

**Daily pipeline:** health → eval gate → **universe-scan** → paper → monitor →
portfolio/PnL → **graphify**.

- **Universe scanner (I1):** ranks candidates (momentum / trend / RSI / volume),
  writes `runs/daily_watchlist.json`. Paper consumes the watchlist when present
  (CLI `--symbols` still wins).
- **Graphify:** materializes the live AGENTIC-OS topology (jobs, connectors,
  strategies, artifacts, data flows) as inspectable artifacts under
  `runs/graphify/` — `graph.json`, `graph.mmd` (Mermaid), `graph.html`.
  Deterministic and local (no LLM). The vendored Graphify Labs skill at
  `graphify/` remains available for full codebase knowledge graphs; AGENTIC-OS
  Graphify is the runtime OS map.

```bash
python scripts/run_agentic_os.py job graphify
python scripts/run_agentic_os.py job universe-scan --symbols AAPL,MSFT,NVDA --top-n 3
python scripts/run_agentic_os.py daily --mock --skip-eval --symbols AAPL,MSFT,NVDA
```

Default paper broker is **simulated** (`PAPER_BROKER=simulated`). Prefer
`TRADING_UNIVERSE=*` with `TRADING_UNIVERSE_MAX` for a capped full-US scan.

## Vendor tools (Graphify Labs + Craft Agents)

Cloned upstream repos and project integration configs. Full setup:
[docs/vendor-integration.md](docs/vendor-integration.md).

| Tool | Path | Quick use |
|------|------|-----------|
| Graphify (codebase KG) | `graphify/` | `graphify query "..."` on `algo_agents/graphify-out/` |
| Craft Agents (agent UI) | `craft-agents-oss/` | `bun install && bun run electron:start` |

- **Code knowledge graph:** `algo_agents/graphify-out/GRAPH_REPORT.md` (493 nodes, AST-only build)
- **Craft workspace:** `craft-workspace/` — repo source, Graphify MCP, `@algo-trading` skill
- **MCP launcher:** `python scripts/run_graphify_mcp.py`
- **Cursor rule:** `.cursor/rules/graphify.mdc` (installed)

```bash
pip install -e graphify
pip install "graphifyy[mcp]"
graphify extract algo_agents --code-only && graphify cluster-only algo_agents
```

## Project layout

```
algo_agents/
  config.py                # env/.env settings (all keys optional)
  os/                      # AGENTIC-OS kernel, jobs, Graphify, scheduler
  universe/                # US ticker resolution + cross-section scanner
  connectors/
    base.py                # ABCs + ConnectorStatus + OrderRequest
    brokers/               # alpaca, ibkr, simulated
    market_data/           # yfinance (no key), polygon, finnhub, fmp
    news/                  # newsapi, edgar
    sentiment/             # hf_sentiment (FinBERT/FinGPT via transformers)
    memory/                # chroma vector store
  features/technical.py    # look-ahead-safe technical features
  strategy/                # weight-centric strategy interface + baseline
  risk/risk_manager.py     # clipping, exposure caps, kill-switch, sizing
  backtest/engine.py       # cost-aware vectorized backtest + metrics
  monitoring/              # champion/challenger + pnl_tracker
scripts/
  check_connections.py     # health-check every connector
  run_agentic_os.py        # AGENTIC-OS CLI
  run_sentiment_demo.py    # FinBERT demo (Hugging Face)
```

## Quickstart

```bash
# 1. (recommended) virtual env
python -m venv .venv
. .venv/Scripts/Activate.ps1     # Windows PowerShell
# source .venv/bin/activate      # macOS/Linux

# 2. install
pip install -r requirements.txt
pip install -e .

# 3. configure (every key is optional; copy and fill what you have)
cp .env.example .env

# 4. verify all connectors
python scripts/check_connections.py

# 5. see Hugging Face FinBERT score live headlines
python scripts/run_sentiment_demo.py

# 6. AGENTIC-OS smoke
python scripts/run_agentic_os.py list
python scripts/run_agentic_os.py job graphify
```

`check_connections.py` reports each integration as `READY`,
`MISSING_CREDENTIALS`, `MISSING_DEPENDENCY`, `NOT_RUNNING`, or `ERROR` — the
stack runs in degraded mode without crashing, so you can wire keys one at a
time.

## Connectors

| Category    | Connector            | Needs                                  |
|-------------|----------------------|----------------------------------------|
| Broker      | Simulated (default)  | nothing (local `runs/paper_account.json`) |
| Broker      | Alpaca (paper/live)  | `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` |
| Broker      | Interactive Brokers  | `ib-insync` + running TWS/Gateway      |
| Market data | yfinance             | nothing (default source)               |
| Market data | Polygon              | `POLYGON_API_KEY`                      |
| Market data | Finnhub              | `FINNHUB_API_KEY`                      |
| Market data | FMP                  | `FMP_API_KEY`                          |
| News        | NewsAPI              | `NEWSAPI_KEY`                          |
| News        | SEC EDGAR            | `EDGAR_USER_AGENT` (name + email)      |
| Sentiment   | Hugging Face FinBERT | `transformers` + `torch` (CPU ok)      |
| Memory      | Chroma               | `chromadb`                             |

## Roadmap (paper-first)

0. **Infra** — clean, look-ahead-safe data pipeline + cost-aware backtester.
1. **Signal** — one ML model on technical + sentiment features; prove edge OOS.
2. **Risk + execution** — overlay + paper broker, 30–90 days stable.
3. **Agents** — analyst/debate layer + FinMem-style memory over the signal.
4. **Self-improvement** — reflection + champion/challenger, then RL/evolution.
5. **Live (tiny)** — small capital, close monitoring, scale only on evidence.

### Phase 2 ops (current)

```bash
python scripts/run_agentic_os.py daily --skip-eval
python scripts/run_pnl_dashboard.py --open   # writes runs/pnl_dashboard.html
python scripts/run_agentic_os.py status
```

Paper P&amp;L history: `runs/pnl_history.jsonl`. Active strategy: `runs/active_strategy.json`.
Shadow ladder (I5): each of momentum/agent/ml keeps a separate simulated book under
`runs/shadow/{strategy}/account.json`; promotion prefers shadow total return once
history is thick enough (`SHADOW_MIN_SNAPSHOTS`), else backtest Sharpe.
Zero-LLM gate (I7): `agent` is promoted only if it beats momentum on that same metric;
otherwise momentum or ml stays active (reason recorded in monitor JobResult / active metrics).
FinMem closed loop: paper job recalls Chroma reflections into agent feature context.

## Disclaimer

For research and education only. Not investment advice. Trading involves risk
of loss. You are responsible for compliance (PDT/margin rules, taxes) and for
anything this code does with a live account.
