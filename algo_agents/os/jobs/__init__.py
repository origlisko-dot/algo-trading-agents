"""Register all AGENTIC-OS jobs."""
from __future__ import annotations

from algo_agents.os.jobs.daily import run_daily
from algo_agents.os.jobs.evals import run_evals_job
from algo_agents.os.jobs.graphify import run_graphify
from algo_agents.os.jobs.health import run_health
from algo_agents.os.jobs.ml_backtest import run_ml_backtest
from algo_agents.os.jobs.monitor import run_monitor
from algo_agents.os.jobs.paper_trade import run_paper_trade
from algo_agents.os.jobs.portfolio import run_portfolio
from algo_agents.os.jobs.universe_scan import run_universe_scan
from algo_agents.os.registry import register


def register_all_jobs() -> None:
    register("health", run_health)
    register("evals", run_evals_job)
    register("universe-scan", run_universe_scan)
    register("paper", run_paper_trade)
    register("monitor", run_monitor)
    register("portfolio", run_portfolio)
    register("ml-backtest", run_ml_backtest)
    register("graphify", run_graphify)
    register("daily", run_daily)
