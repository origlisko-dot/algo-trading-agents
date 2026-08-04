## Learned User Preferences
- Preserve plan artifacts when the user explicitly says not to edit them.
- Prioritize end-to-end verification runs after implementation and report concrete outcomes.
- Return brief execution summaries focused on pass/fail, changed files, and blockers when requested.
- Track sprint/task status explicitly (S1-S6) and close remaining items at completion.
- Prefer Hebrew replies when the user writes in Hebrew or explicitly asks for Hebrew.
- Prefer a full-US trading universe (`TRADING_UNIVERSE=*`) with a capped daily scan (`TRADING_UNIVERSE_MAX`), not a small mega-cap allowlist.
- Prefer real market data over mocks for demos and verification when connectors are available.
- Prefer the simulated paper broker (or other non-Alpaca options) when Alpaca credentials/connectivity fail.

## Learned Workspace Facts
- The AI agents LLMOps plan is implemented through S1-S6, with AGENTIC-OS as the unified orchestrator (`scripts/run_agentic_os.py`, `algo_agents/os/`).
- AGENTIC-OS jobs include health, evals, universe-scan, paper, monitor, portfolio, ml-backtest, graphify, and daily (composite).
- Graphify (`algo_agents/os/graphify/`) exports the live AGENTIC-OS system graph to `runs/graphify/` (`graph.json`, `graph.mmd`, `graph.html`); the vendored Graphify Labs skill lives under `graphify/` for full codebase knowledge graphs.
- Universe scanner writes `runs/daily_watchlist.json`; paper consumes it when present (CLI `--symbols` overrides).
- Verified command baseline in this workspace: `pytest tests/ -q` passed (39/39) including Graphify + universe-scanner tests; `python scripts/run_agent_evals.py --mock` passed (8/8).
- AGENTIC-OS supports scheduler (`schedule` command), 3-way promotion (momentum/agent/ml), and active strategy at `runs/active_strategy.json`.
- Shadow books live at `runs/shadow/{strategy}/account.json`; promotion prefers shadow total return when snapshots are sufficient, else backtest Sharpe. Agent requires beating momentum (zero-LLM gate) before activation.
- Regime Sharpe history persists at `runs/regime_sharpe.json`; with enough samples monitor prefers historical mean Sharpe per regime before other gates.
- Universe scan filters OTC-like 5-letter `*F` tickers and skips empty/penny feature rows; ML scoring skips empty feature frames.
- Ops schedule: `AGENTIC_SCHEDULE_ENABLED=true` @ 21:30 America/New_York mon-fri; run `python scripts/run_agentic_os.py schedule` to poll. Weekend `should_run_daily=False`.
- Verified script baseline: `python scripts/run_agent_demo.py AAPL`, `python scripts/check_connections.py`, `python scripts/run_paper_loop.py --mock --skip-eval`, `python scripts/run_champion_challenger.py`, and `python scripts/run_agentic_os.py job health` all completed successfully in the validated run.
- Runtime default favors graceful degradation: optional integrations (for example Alpaca, Chroma, FinBERT/transformers, LangGraph LLM stack) are non-fatal when unavailable.
- Strategy/agent path includes an offline heuristic mode used for fast tests/backtests and mock paper-loop flows.
- Full LLM graph behavior requires LangChain/LangGraph OpenAI deps plus `OPENAI_API_KEY` or `OPENROUTER_API_KEY` (OpenRouter auto-sets base URL; recommended default `LLM_MODEL=openai/gpt-4o-mini`); otherwise heuristic fallback is used.
- Monitoring includes champion-vs-challenger comparison with signal-drift reporting and symbol-scoped evaluation.
- Fresh environments may require `pip install -r requirements.txt` plus `pip install -e .` before verification scripts pass consistently.
- API keys and runtime config live in project-root `.env` (from `.env.example`); never commit secrets.
- `TRADING_UNIVERSE=*` allows any valid US ticker; universe lists load Finnhub→Polygon→Alpaca and cache at `runs/universe_us.json`, while daily scans are capped by `TRADING_UNIVERSE_MAX`.
- Paper trading can run on the simulated broker (`runs/paper_account.json`) without Alpaca; FMP 403s are optional/non-blocking when yfinance/Finnhub/Polygon work.
- Phase-2 paper ops: `runs/pnl_history.jsonl` + `python scripts/run_pnl_dashboard.py` → `runs/pnl_dashboard.html`; portfolio job refreshes the dashboard; FinMem recall injects Chroma reflections into agent paper context.
- Graphify + AGENTIC OSS expansions may be in sibling trees (`graphify/`, `craft-agents-oss/`); prefer not to conflict with parallel sessions working those areas.
- Monitor backtests must use `agent_use_llm=False` (never LLM-per-bar).

## Cursor Cloud specific instructions
- Dependencies are installed into the **system** Python 3.12 (`/usr/bin/python3`) by the startup update script (`pip install --break-system-packages -r requirements.txt` then `-e .`). There is no `.venv`; just run `python3 ...`. The base image is externally-managed (PEP 668) and lacks `python3.12-venv`, so `--break-system-packages` is intentional.
- Config is optional: every connector degrades gracefully. Copy `.env.example` to `.env` only when wiring keys; scripts run on defaults (simulated broker + yfinance) with no `.env`.
- The AGENTIC-OS runtime graph package lives at `algo_agents/os/graphify/` (`model.py`, `builder.py`, `export.py`). `build_agentic_os_graph(include_live_status)` reads the live job registry + connector roster; `export_system_graph(graph, out_dir)` writes `graph.json` / `graph.mmd` / `graph.html` (Mermaid) under `runs/graphify/`. Note: `builder.py` imports `register_all_jobs` lazily *inside* the function on purpose — `algo_agents.os.jobs` imports the graphify job, so a top-level import there creates a circular import at package init.
- Full flow verified: `python3 -m pytest tests/ -q` (54 passed) and `python3 scripts/run_agentic_os.py daily --mock --skip-eval --symbols AAPL,MSFT,NVDA` (6/6 steps, paper orders filled on the simulated broker, graphify wrote 32 nodes / 52 edges).
- Working entrypoints (verified): `scripts/run_agentic_os.py {list,status,job <name>,daily}`, `scripts/run_paper_loop.py --mock --skip-eval`, `scripts/run_champion_challenger.py`, `scripts/check_connections.py`, `scripts/run_agent_demo.py <SYM>`, `scripts/run_agent_evals.py --mock`, `scripts/run_sentiment_demo.py` (downloads FinBERT on first run), `scripts/run_ml_backtest.py`, `scripts/run_pnl_dashboard.py`. Lint with `ruff check .` (reports pre-existing findings, mostly unused imports in tests).
