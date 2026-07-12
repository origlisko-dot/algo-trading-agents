"""Tests for AGENTIC-OS kernel, scheduler, and promotion."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from algo_agents.os import AgenticOS, RunContext
from algo_agents.os.artifacts import read_active_strategy, write_active_strategy
from algo_agents.os.jobs import register_all_jobs
from algo_agents.os.registry import names, run_job
from algo_agents.os.routing.strategy_router import resolve_strategy
from algo_agents.os.scheduler import is_scheduled_now, parse_weekdays, should_run_daily


def test_job_registry_contains_core_jobs():
    register_all_jobs()
    registered = set(names())
    assert {
        "health",
        "evals",
        "universe-scan",
        "paper",
        "monitor",
        "portfolio",
        "ml-backtest",
        "graphify",
        "daily",
    }.issubset(registered)


def test_health_job():
    register_all_jobs()
    ctx = RunContext.create()
    result = run_job("health", ctx)
    assert result.name == "health"
    assert result.ok
    assert result.data["ready"] >= 1


def test_evals_job_mock():
    register_all_jobs()
    ctx = RunContext.create(mock=True)
    result = run_job("evals", ctx)
    assert result.ok
    assert result.data["passed"] == result.data["total"]


def test_strategy_router_auto_uses_active(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    write_active_strategy("ml", reason="test")
    settings = get_settings()
    assert resolve_strategy(settings, name="auto").name == "ml_signal"
    get_settings.cache_clear()


def test_strategy_router_names():
    from algo_agents.config import get_settings

    settings = get_settings()
    assert resolve_strategy(settings, name="momentum").name == "momentum_sentiment"
    assert resolve_strategy(settings, name="ml").name == "ml_signal"
    assert resolve_strategy(settings, name="agent", mock=True).name == "agent_strategy"


def test_kernel_list_jobs():
    os_kernel = AgenticOS()
    jobs = os_kernel.list_jobs()
    assert "daily" in jobs


def test_parse_weekdays():
    assert parse_weekdays("mon-fri") == {0, 1, 2, 3, 4}


def test_scheduler_should_run_once(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.setenv("AGENTIC_SCHEDULE_ENABLED", "true")
    monkeypatch.setenv("AGENTIC_SCHEDULE_HOUR", "10")
    monkeypatch.setenv("AGENTIC_SCHEDULE_MINUTE", "0")
    monkeypatch.setenv("AGENTIC_SCHEDULE_TZ", "UTC")
    monkeypatch.setenv("AGENTIC_SCHEDULE_WEEKDAYS", "mon-fri")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    now = datetime(2026, 7, 13, 10, 0, tzinfo=ZoneInfo("UTC"))
    assert is_scheduled_now(settings, now)
    assert should_run_daily(settings, now)
    get_settings.cache_clear()
