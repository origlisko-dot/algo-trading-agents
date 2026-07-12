---
name: Algo Trading Agents
description: US equities ML/agent trading scaffold — connectors, AGENTIC-OS, paper loop, risk overlay
icon: 📈
requiredSources:
  - algo-trading-repo
  - graphify-mcp
globs:
  - algo_agents/**
  - scripts/**
  - tests/**
---

# Algo Trading Agents

You are working in a **paper-first** US equities research scaffold.

## Rules

1. **Paper by default** — `TRADING_PAPER=true`. Do not suggest live trading unless explicitly asked.
2. **Simulated broker fallback** — prefer `PAPER_BROKER=simulated` when Alpaca is unavailable.
3. **Full universe** — `TRADING_UNIVERSE=*` with `TRADING_UNIVERSE_MAX` cap; avoid mega-cap-only allowlists.
4. **Graceful degradation** — optional connectors (Alpaca, Chroma, FinBERT, LangGraph LLM) are non-fatal.
5. **Look-ahead safety** — features and backtests must not leak future data.

## Architecture

```
DATA → FEATURES → DECISION BRAIN → RISK MANAGER → EXECUTION
         ↑              ↓
      MEMORY ← SELF-IMPROVEMENT / MONITORING
```

- **AGENTIC-OS** orchestrator: `scripts/run_agentic_os.py`, `algo_agents/os/`
- **Connectors**: brokers (Alpaca, IBKR), market data (yfinance, Polygon, Finnhub, FMP), news, sentiment, Chroma memory
- **Promotion**: champion/challenger with momentum/agent/ml strategies

## Knowledge graph

Before grepping architecture, query the Graphify graph:

- Read `algo_agents/graphify-out/GRAPH_REPORT.md` for hubs and god nodes
- Use `@graphify-mcp` for path/explain/impact queries
- After code edits: `graphify update algo_agents`

## Verification commands

| Check | Command |
|-------|---------|
| Connectors | `python scripts/check_connections.py` |
| Unit tests | `pytest tests/ -v` |
| Agent evals | `python scripts/run_agent_evals.py --mock` |
| OS health | `python scripts/run_agentic_os.py job health` |
| Paper loop | `python scripts/run_paper_loop.py --mock --skip-eval` |

## Key god nodes (from graph)

- `ConnectorStatus`, `Settings`, `get_settings()`
- `SimulatedBroker`, `AlpacaBroker`, `MLSignalStrategy`
- `RunContext`, `run_paper_trade()`
