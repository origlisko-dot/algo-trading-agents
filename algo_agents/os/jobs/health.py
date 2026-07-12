"""Connector health job."""
from __future__ import annotations

from algo_agents.connectors import check_all
from algo_agents.os.context import JobResult, RunContext


def run_health(ctx: RunContext) -> JobResult:
    report = check_all()
    ready = sum(1 for statuses in report.values() for s in statuses if s.ok)
    total = sum(len(statuses) for statuses in report.values())
    flat = {f"{cat}/{s.name}": s.state.value for cat, statuses in report.items() for s in statuses}
    return JobResult(
        name="health",
        ok=ready > 0,
        detail=f"{ready}/{total} connectors READY",
        data={"report": flat, "ready": ready, "total": total},
    )
