"""AGENTIC-OS — unified orchestrator for trading agent workflows."""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.table import Table

from algo_agents.config import get_settings
from algo_agents.os import AgenticOS, RunContext
from algo_agents.os.artifacts import read_active_strategy
from algo_agents.os.scheduler import is_scheduled_now, should_run_daily
from algo_agents.universe.scanner import load_watchlist

console = Console()

_JOB_CHOICES = [
    "health",
    "evals",
    "universe-scan",
    "paper",
    "monitor",
    "portfolio",
    "ml-backtest",
    "graphify",
]


def _parse_symbols(raw: str) -> list[str] | None:
    if not raw.strip():
        return None
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def _build_ctx(args) -> RunContext:
    return RunContext.create(
        mock=getattr(args, "mock", False),
        skip_eval=getattr(args, "skip_eval", False),
        strategy=getattr(args, "strategy", None),
        symbols=_parse_symbols(getattr(args, "symbols", "")),
        top_n=getattr(args, "top_n", 5),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="AGENTIC-OS orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List registered jobs")

    sub.add_parser("status", help="Show active strategy, schedule, PnL, watchlist")
    daily = sub.add_parser("daily", help="Run full daily workflow")
    daily.add_argument("--mock", action="store_true")
    daily.add_argument("--skip-eval", action="store_true")
    daily.add_argument("--strategy", default=None)
    daily.add_argument("--symbols", default="")
    daily.add_argument("--top-n", type=int, default=5)

    sched = sub.add_parser("schedule", help="Run scheduler loop (daily at configured time)")
    sched.add_argument("--mock", action="store_true")
    sched.add_argument("--skip-eval", action="store_true")
    sched.add_argument("--strategy", default=None)
    sched.add_argument("--symbols", default="")
    sched.add_argument("--once", action="store_true", help="Single poll iteration (for tests)")

    job = sub.add_parser("job", help="Run a single job")
    job.add_argument("name", choices=_JOB_CHOICES)
    job.add_argument("--mock", action="store_true")
    job.add_argument("--skip-eval", action="store_true")
    job.add_argument("--strategy", default=None)
    job.add_argument("--symbols", default="")
    job.add_argument("--top-n", type=int, default=5)

    args = parser.parse_args()
    os_kernel = AgenticOS()
    settings = get_settings()

    if args.command == "list":
        table = Table(title="AGENTIC-OS jobs", header_style="bold cyan")
        table.add_column("job")
        for name in os_kernel.list_jobs():
            table.add_row(name)
        console.print(table)
        sys.exit(0)

    if args.command == "status":
        from algo_agents.monitoring.pnl_tracker import summarize

        active = read_active_strategy()
        pnl = summarize()
        watch = load_watchlist()
        console.print(f"default_strategy={settings.default_strategy}")
        console.print(
            f"schedule_enabled={settings.agentic_schedule_enabled} "
            f"@ {settings.agentic_schedule_hour:02d}:{settings.agentic_schedule_minute:02d} "
            f"{settings.agentic_schedule_tz} ({settings.agentic_schedule_weekdays})"
        )
        console.print(
            f"scheduled_now={is_scheduled_now(settings)} should_run_daily={should_run_daily(settings)}"
        )
        if active:
            console.print(f"active_strategy={active.get('strategy')} reason={active.get('reason')}")
        else:
            console.print("active_strategy=(none yet)")
        if watch:
            console.print(f"watchlist={','.join(watch[:10])}" + ("…" if len(watch) > 10 else ""))
        else:
            console.print("watchlist=(none)")
        if pnl.get("snapshots"):
            console.print(
                f"pnl equity={pnl.get('latest_equity', 0):.2f} "
                f"return={pnl.get('total_return', 0):+.2%} "
                f"max_dd={pnl.get('max_drawdown', 0):.2%} "
                f"snapshots={pnl.get('snapshots')}"
            )
        else:
            console.print("pnl=(no snapshots yet)")
        sys.exit(0)

    if args.command == "schedule":
        console.rule("AGENTIC-OS · scheduler")
        factory = lambda: _build_ctx(args)
        os_kernel.run_scheduler(factory, once=args.once)
        sys.exit(0)

    ctx = _build_ctx(args)
    job_name = "daily" if args.command == "daily" else args.name
    console.rule(f"AGENTIC-OS · {job_name} · run={ctx.run_id}")

    report = os_kernel.run(job_name, ctx, require_paper=job_name in {"daily", "paper"})
    style = "green" if report.ok else "red"
    console.print(f"[{style}]{report.job}[/]: {report.detail}")
    console.print(f"manifest -> {report.manifest_path}")

    if report.steps:
        table = Table(title="Steps", header_style="bold")
        table.add_column("job")
        table.add_column("ok")
        table.add_column("detail")
        for step in report.steps:
            ok_style = "green" if step.ok else "red"
            table.add_row(step.name, f"[{ok_style}]{step.ok}[/]", step.detail)
        console.print(table)

    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
