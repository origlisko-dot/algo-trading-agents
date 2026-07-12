"""AGENTIC-OS kernel: boot, dispatch jobs, persist artifacts."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from algo_agents.config import get_settings
from algo_agents.observability.logging import get_logger
from algo_agents.os.artifacts import write_manifest
from algo_agents.os.bootstrap import assert_safe_mode, boot
from algo_agents.os.context import JobResult, RunContext
from algo_agents.os.jobs import register_all_jobs
from algo_agents.os.registry import names, run_job
from algo_agents.os.scheduler import mark_daily_ran, should_run_daily

_log = get_logger(__name__)


@dataclass
class OSRunReport:
    run_id: str
    job: str
    ok: bool
    detail: str
    result: JobResult
    manifest_path: str = ""
    steps: list[JobResult] = field(default_factory=list)


class AgenticOS:
    """Single entry point for orchestrated trading-agent workflows."""

    def __init__(self) -> None:
        register_all_jobs()

    @staticmethod
    def list_jobs() -> list[str]:
        register_all_jobs()
        return names()

    def run(self, job: str, ctx: RunContext | None = None, *, require_paper: bool = True) -> OSRunReport:
        register_all_jobs()
        context = ctx or RunContext.create()
        boot(context.run_id)

        if require_paper and job in {"daily", "paper"}:
            assert_safe_mode()

        result = run_job(job, context)
        manifest_path = write_manifest(
            context.run_id,
            {
                "job": job,
                "ok": result.ok,
                "detail": result.detail,
                "mock": context.mock,
                "strategy": context.strategy,
                **result.data,
            },
        )

        steps: list[JobResult] = []
        if job == "daily" and isinstance(result.data.get("steps"), list):
            for step in result.data["steps"]:
                if isinstance(step, dict) and "name" in step:
                    steps.append(JobResult(**step))

        return OSRunReport(
            run_id=context.run_id,
            job=job,
            ok=result.ok,
            detail=result.detail,
            result=result,
            manifest_path=str(manifest_path),
            steps=steps,
        )

    def run_scheduler(
        self,
        ctx_factory: Callable[[], RunContext] | None = None,
        *,
        once: bool = False,
    ) -> None:
        """Poll schedule and run daily workflow when due."""
        settings = get_settings()
        factory = ctx_factory or (lambda: RunContext.create())

        while True:
            if should_run_daily(settings):
                _log.info("scheduler triggering daily workflow")
                report = self.run("daily", factory())
                mark_daily_ran(settings)
                _log.info("scheduler daily finished ok=%s detail=%s", report.ok, report.detail)
            if once:
                return
            time.sleep(max(5, settings.agentic_schedule_poll_seconds))
