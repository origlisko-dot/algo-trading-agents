"""Composite daily workflow for AGENTIC-OS."""
from __future__ import annotations

from algo_agents.os.context import JobResult, RunContext
from algo_agents.os.jobs.evals import run_evals_job
from algo_agents.os.jobs.graphify import run_graphify
from algo_agents.os.jobs.health import run_health
from algo_agents.os.jobs.monitor import run_monitor
from algo_agents.os.jobs.paper_trade import run_paper_trade
from algo_agents.os.jobs.portfolio import run_portfolio
from algo_agents.os.jobs.universe_scan import run_universe_scan


def run_daily(ctx: RunContext) -> JobResult:
    steps: list[JobResult] = []

    health = run_health(ctx)
    steps.append(health)
    if not health.ok:
        return JobResult(
            name="daily",
            ok=False,
            detail=f"health failed: {health.detail}",
            data={"steps": [s.__dict__ for s in steps]},
        )

    if ctx.settings.eval_gate_enabled and not ctx.skip_eval:
        evals = run_evals_job(ctx)
        steps.append(evals)
        if not evals.ok:
            return JobResult(
                name="daily",
                ok=False,
                detail=f"eval gate failed: {evals.detail}",
                data={"steps": [s.__dict__ for s in steps]},
            )

    scan = run_universe_scan(ctx)
    steps.append(scan)
    if not scan.ok:
        return JobResult(
            name="daily",
            ok=False,
            detail=f"universe-scan failed: {scan.detail}",
            data={"steps": [s.__dict__ for s in steps]},
        )

    paper = run_paper_trade(ctx)
    steps.append(paper)
    if not paper.ok:
        return JobResult(
            name="daily",
            ok=False,
            detail=f"paper failed: {paper.detail}",
            data={"steps": [s.__dict__ for s in steps]},
        )

    monitor_data: dict | None = None
    if ctx.settings.monitor_after_paper:
        monitor = run_monitor(ctx)
        steps.append(monitor)
        monitor_data = monitor.data

    portfolio = run_portfolio(ctx)
    steps.append(portfolio)

    graphify = run_graphify(ctx)
    steps.append(graphify)

    return JobResult(
        name="daily",
        ok=True,
        detail=f"completed {len(steps)} steps | {portfolio.detail}",
        data={
            "steps": [s.__dict__ for s in steps],
            "universe_scan": scan.data,
            "paper": paper.data,
            "monitor": monitor_data,
            "portfolio": portfolio.data,
            "graphify": graphify.data,
        },
    )
