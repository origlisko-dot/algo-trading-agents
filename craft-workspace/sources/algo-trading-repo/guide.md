# Algo Trading Repo

This source points at the parent `algo-trading-agents` repository.

## Scope

- `algo_agents/` — connectors, strategy, risk, backtest, AGENTIC-OS
- `scripts/` — verification and paper-trading entrypoints
- `tests/` — pytest suite
- `runs/` — runtime artifacts (paper account, watchlists, active strategy)
- `docs/` — project documentation

## Guidelines

- Default to **paper trading** (`TRADING_PAPER=true`); never suggest live trading without explicit user request.
- Prefer the **simulated paper broker** when Alpaca credentials are missing.
- Use `TRADING_UNIVERSE=*` with `TRADING_UNIVERSE_MAX` for daily scans — not a mega-cap allowlist.
- Run `python scripts/check_connections.py` before assuming a connector is available.
- For architecture questions, prefer the Graphify knowledge graph (`algo_agents/graphify-out/`) over blind grepping.
- Verified baselines: `pytest tests/ -v`, `python scripts/run_agent_evals.py --mock`, `python scripts/run_agentic_os.py job health`.

## Key entrypoints

| Task | Command |
|------|---------|
| Connector health | `python scripts/check_connections.py` |
| Agent demo | `python scripts/run_agent_demo.py AAPL` |
| Paper loop (mock) | `python scripts/run_paper_loop.py --mock --skip-eval` |
| AGENTIC-OS health | `python scripts/run_agentic_os.py job health` |
| Champion/challenger | `python scripts/run_champion_challenger.py` |
