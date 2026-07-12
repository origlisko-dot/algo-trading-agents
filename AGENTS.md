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
- Pure-Python project (Python 3.12 available; requires >=3.10). Dependencies are installed into the system interpreter with `pip install --break-system-packages` (handled by the startup update script), so run everything with plain `python3` — no venv activation needed.
- pip installs console entrypoints (`ruff`, `pytest`, `transformers`, ...) into `~/.local/bin`, which is NOT on PATH. Invoke tools as modules to avoid PATH issues: `python3 -m ruff check .`, `python3 -m pytest tests/ -q`.
- `.env` is optional: `algo_agents.config` (pydantic-settings) already defaults to the values in `.env.example` (simulated broker, paper mode). Only `cp .env.example .env` when you need to add real API keys; every connector degrades gracefully when a key/dependency is missing (`python3 scripts/check_connections.py`).
- KNOWN REPO DEFECT (blocker): the package `algo_agents/os/graphify/` (defines `build_agentic_os_graph` / `export_system_graph`) is absent from the repo because the unanchored `graphify/` rule in `.gitignore` also matches it, so it was never committed. This breaks the whole `algo_agents.os` import chain. Until those source files are restored, these fail with `ModuleNotFoundError: No module named 'algo_agents.os.graphify'`: `scripts/run_agentic_os.py`, `scripts/run_paper_loop.py`, `scripts/run_champion_challenger.py`, and tests `tests/test_agentic_os.py`, `tests/test_graphify.py`, `tests/test_universe_scanner.py`. This is a missing-source issue, not an environment/dependency problem.
- Entrypoints that work independently of `algo_agents.os`: `scripts/run_agent_demo.py <SYM>`, `scripts/run_ml_backtest.py`, `scripts/run_pnl_dashboard.py`, `scripts/run_sentiment_demo.py`, `scripts/check_connections.py`, `scripts/run_agent_evals.py --mock`.
- Working test subset (skips the 3 modules blocked above): `python3 -m pytest tests/ -q --ignore=tests/test_agentic_os.py --ignore=tests/test_graphify.py --ignore=tests/test_universe_scanner.py` (31 passing).
- Network-dependent connectors: yfinance (default market data) and SEC EDGAR need internet; FinBERT (`ProsusAI/finbert`) downloads its model on the first `score()` call. Use `--mock` paths for fully offline runs.
- `ruff check .` currently reports pre-existing F401 (unused-import) errors in a few `tests/*` files — these are repo lint debt, not setup problems.
