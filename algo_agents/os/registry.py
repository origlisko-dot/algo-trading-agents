"""Job registry for AGENTIC-OS."""
from __future__ import annotations

from collections.abc import Callable

from algo_agents.os.context import JobResult, RunContext

JobFn = Callable[[RunContext], JobResult]

_REGISTRY: dict[str, JobFn] = {}


def register(name: str, fn: JobFn) -> None:
    _REGISTRY[name] = fn


def get(name: str) -> JobFn:
    if name not in _REGISTRY:
        raise KeyError(f"Unknown job: {name}")
    return _REGISTRY[name]


def names() -> list[str]:
    return sorted(_REGISTRY)


def run_job(name: str, ctx: RunContext) -> JobResult:
    return get(name)(ctx)
