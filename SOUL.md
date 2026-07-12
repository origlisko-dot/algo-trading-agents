# SOUL.md — algo-trading-agents

Identity, doctrine, and journey for this project. Read this first when continuing on another device or in a new agent session.

> **Not financial advice.** Paper-first. Prove edge out-of-sample before any real capital.

---

## Who we are

A **paper-first US equities** research scaffold: connectors → features → decision brain (momentum / ML / LLM agents) → risk → simulated (or broker) execution → memory + promotion loop.

**AGENTIC-OS** (`algo_agents/os/`, `scripts/run_agentic_os.py`) is the unified daily orchestrator.

**Doctrine**

1. Paper before live. Default `TRADING_PAPER=true`, `PAPER_BROKER=simulated`.
2. Full US universe intent: `TRADING_UNIVERSE=*` + capped scan `TRADING_UNIVERSE_MAX`.
3. Real market data when connectors work; graceful degradation when they don’t.
4. Prefer simulated broker over broken Alpaca/IBKR.
5. Promotion must beat free baselines (shadow PnL + zero-LLM / momentum gate).
6. Monitor/backtest panels stay **offline** (`agent_use_llm=False`) — never LLM-per-bar.
7. Secrets live only in `.env` (never commit). Hebrew OK when the user writes Hebrew.

---

## What we built (journey)

### Core platform (S1–S6 / LLMOps)

- Connectors: brokers (simulated / Alpaca / IBKR), yfinance / Finnhub / Polygon / FMP, news, FinBERT, Chroma.
- Features, backtest, risk manager, strategies: momentum, agent (LangGraph + heuristic fallback), ML (`MLSignalStrategy`).
- Evals with golden scenarios + guardrails.
- Config via `.env` / `.env.example`.

### AGENTIC-OS

Jobs: `health` → `evals` → `universe-scan` → `paper` → `monitor` → `portfolio` → `graphify` (+ `ml-backtest`, composite `daily`).

| Artifact | Path |
|----------|------|
| Active strategy | `runs/active_strategy.json` |
| Watchlist | `runs/daily_watchlist.json` |
| Paper book | `runs/paper_account.json` |
| PnL history | `runs/pnl_history.jsonl` |
| Dashboard | `runs/pnl_dashboard.html` |
| Shadow books | `runs/shadow/{momentum,agent,ml}/` |
| Regime Sharpe | `runs/regime_sharpe.json` |
| Eval learning | `runs/eval_learning.json` |
| OS Graphify | `runs/graphify/` |
| Scheduler state | `runs/scheduler_state.json` |

CLI:

```bash
python scripts/run_agentic_os.py list
python scripts/run_agentic_os.py status
python scripts/run_agentic_os.py daily --skip-eval
python scripts/run_agentic_os.py schedule
python scripts/run_pnl_dashboard.py --open
```

Schedule (ops): `AGENTIC_SCHEDULE_ENABLED=true` @ **21:30 America/New_York**, mon–fri.

### Ideation I1–I7 (status)

| ID | Idea | Status |
|----|------|--------|
| I1 | Universe scanner → daily watchlist | Done |
| I2 | FinMem closed loop (Chroma recall in paper) | Done |
| I3 | Regime-aware promotion + `regime_sharpe.json` | Done |
| I4 | PnL dashboard (+ shadow board / drift) | Done |
| I5 | Shadow ladder (per-strategy simulated books) | Done |
| I6 | Eval-failure learning (`max_weight`, `require_mock_on_fail`) | Done |
| I7 | Zero-LLM gate (agent must beat momentum) | Done |

### Hardening (ops lessons)

- ML scoring skips empty/`dropna` frames (OTC crash fix).
- Universe scan: date-seeded stratified sample; filter 5-letter `*F` OTC-like; skip penny/empty feature rows; cache v3.
- Dashboard must **not** import `algo_agents.os` (circular import with portfolio).
- IBKR/Alpaca optional; health can be ~8/11 READY and still run.

### Vendor / tooling tracks

- **Graphify Labs:** local KG under `algo_agents/graphify-out/` (gitignored build); Cursor rule `.cursor/rules/graphify.mdc`; MCP launcher `scripts/run_graphify_mcp.py`.
- **AGENTIC-OS Graphify:** live OS map job (in daily).
- **Craft Agents:** workspace `craft-workspace/`; upstream clone `craft-agents-oss/` (gitignored deps); Bun for install/run. Guide: `docs/vendor-integration.md`.
- Project skill: `.agents/skills/algo-trading/SKILL.md`.

---

## How decisions are promoted

1. Monitor compares momentum / agent / ml (offline backtests).
2. Records shadow fills into separate simulated ledgers.
3. If regime history is thick enough → prefer historical mean Sharpe for that regime.
4. Else prefer shadow total return when history exists; else backtest Sharpe.
5. **I7:** `agent` becomes active only if it beats **momentum** on the chosen metric.
6. Writes `runs/active_strategy.json`; paper with `DEFAULT_STRATEGY=auto` follows it.

---

## Preferences for future agents

- Prefer Hebrew replies when the user writes Hebrew.
- End-to-end verification > claims; report pass/fail, files, blockers.
- Do not commit `.env`, `runs/`, `chroma_db/`, `node_modules/`, or vendored huge clones unless asked.
- Do not fight parallel Graphify/Craft sessions on ignored vendor trees.
- Continue paper discipline (30–90 day evidence) before live.
- First-class ops commands: `daily`, `status`, `schedule`, dashboard.

---

## Bootstrapping another device

```bash
git clone <this-repo>
cd algo-trading-agents
pip install -r requirements.txt && pip install -e .
cp .env.example .env   # fill keys locally — never copy secrets into git
python scripts/run_agentic_os.py job health
python scripts/run_agentic_os.py daily --skip-eval --symbols AAPL,MSFT,NVDA
python scripts/run_agentic_os.py status
```

Optional: Bun + `craft-agents-oss` / Graphify Labs per `docs/vendor-integration.md`.

Tests: `pytest tests/ -q`

---

## Explicitly out of scope (for now)

- Live trading / Phase-5 capital.
- Full FinRL / evolutionary RL as production path.
- Desktop GUI beyond Craft (optional vendor UI).
- Blind trust of LLM signals without shadow + zero-LLM gates.

---

## Soul in one line

**Prove a small statistical edge on paper, with an agentic OS that scans, trades, remembers, and only promotes what beats free baselines — then sync the craft, not the secrets, across devices.**
