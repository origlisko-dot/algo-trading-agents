"""Portfolio snapshot and P&L report job."""
from __future__ import annotations

from algo_agents.config import get_settings
from algo_agents.connectors.brokers.factory import broker_status, get_paper_broker
from algo_agents.monitoring.dashboard import write_dashboard
from algo_agents.monitoring.pnl_tracker import load_history, record_snapshot, summarize
from algo_agents.os.artifacts import read_active_strategy
from algo_agents.os.context import JobResult, RunContext


def run_portfolio(ctx: RunContext) -> JobResult:
    settings = ctx.settings
    broker = get_paper_broker()
    status = broker_status(broker)
    if not status.ok:
        return JobResult(name="portfolio", ok=False, detail=f"broker not ready: {status.detail}")

    account = broker.get_account()
    positions = broker.get_positions()
    active = read_active_strategy()
    strategy = (active or {}).get("strategy") or settings.default_strategy

    record_snapshot(
        run_id=ctx.run_id,
        broker=broker.name,
        account=account,
        positions=positions,
        strategy=strategy,
    )

    dash_path = write_dashboard()
    summary = summarize(starting_equity=settings.paper_starting_cash)
    recent = load_history(limit=7)
    return JobResult(
        name="portfolio",
        ok=True,
        detail=(
            f"equity={summary.get('latest_equity', 0):.2f} "
            f"return={summary.get('total_return', 0):+.2%} "
            f"max_dd={summary.get('max_drawdown', 0):.2%} "
            f"dash={dash_path.name}"
        ),
        data={
            "summary": summary,
            "recent": recent,
            "positions": positions,
            "account": account,
            "dashboard": str(dash_path),
        },
    )
