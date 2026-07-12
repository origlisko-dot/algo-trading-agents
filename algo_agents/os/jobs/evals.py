"""Agent eval gate job with failure-learning feedback."""
from __future__ import annotations

from algo_agents.evals.runner import mock_runner, run_evals
from algo_agents.monitoring.eval_learning import (
    record_eval_failure,
    record_eval_success,
    require_mock_on_fail,
)
from algo_agents.os.context import JobResult, RunContext


def run_evals_job(ctx: RunContext) -> JobResult:
    if ctx.skip_eval:
        return JobResult(name="evals", ok=True, detail="skipped")

    force_mock = ctx.mock or require_mock_on_fail()
    runner = mock_runner
    if not force_mock:
        try:
            from algo_agents.agents.graph import run_single_symbol_eval

            runner = run_single_symbol_eval
        except Exception as exc:
            return JobResult(name="evals", ok=False, detail=f"LLM runner unavailable: {exc}")

    summary = run_evals(runner)
    ok = summary.passed == summary.total
    learning: dict = {}
    if ok:
        learning = record_eval_success(run_id=ctx.run_id)
    else:
        learning = record_eval_failure(
            run_id=ctx.run_id,
            detail=f"{summary.passed}/{summary.total}",
            passed=summary.passed,
            total=summary.total,
        )
    detail = f"{summary.passed}/{summary.total} scenarios passed"
    if force_mock and not ctx.mock:
        detail += " | require_mock_on_fail"
    if not ok:
        detail += f" | tightened max_weight={learning.get('max_weight_per_symbol')}"
    return JobResult(
        name="evals",
        ok=ok,
        detail=detail,
        data={
            "passed": summary.passed,
            "total": summary.total,
            "pass_rate": summary.pass_rate,
            "learning": learning,
            "forced_mock": force_mock and not ctx.mock,
        },
    )
