---
name: Algo Trading Agents
description: US equities ML/agent trading scaffold — connectors, AGENTIC-OS, paper loop, risk overlay
icon: 📈
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

## Knowledge graph

This project has a Graphify knowledge graph at `algo_agents/graphify-out/`.

- For architecture questions, run `graphify query "<question>"` or read `GRAPH_REPORT.md`
- After code edits: `graphify update algo_agents`
- Cursor rule at `.cursor/rules/graphify.mdc` is already installed

## Verification commands

```bash
python scripts/check_connections.py
pytest tests/ -v
python scripts/run_agent_evals.py --mock
python scripts/run_agentic_os.py job health
```
