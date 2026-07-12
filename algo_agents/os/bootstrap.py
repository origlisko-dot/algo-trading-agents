"""Shared AGENTIC-OS boot sequence."""
from __future__ import annotations

from algo_agents.agents.guardrails import assert_paper_only
from algo_agents.observability import init_tracing, setup_logging
from algo_agents.observability.logging import bind_context


def boot(run_id: str, *, agent_role: str = "agentic_os") -> None:
    setup_logging()
    init_tracing()
    bind_context(run_id=run_id, agent_role=agent_role)


def assert_safe_mode() -> None:
    assert_paper_only()
