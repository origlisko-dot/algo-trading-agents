"""Tests for paper P&L tracker."""
from __future__ import annotations

from algo_agents.monitoring.pnl_tracker import load_history, record_snapshot, summarize


def test_pnl_snapshot_and_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    record_snapshot(
        run_id="r1",
        broker="simulated",
        account={"cash": 50000, "equity": 100000, "buying_power": 50000},
        positions=[{"symbol": "AAPL", "qty": 10, "unrealized_pl": 100}],
        strategy="ml",
    )
    record_snapshot(
        run_id="r2",
        broker="simulated",
        account={"cash": 40000, "equity": 105000, "buying_power": 40000},
        positions=[{"symbol": "AAPL", "qty": 10, "unrealized_pl": 500}],
        strategy="ml",
    )
    assert len(load_history()) == 2
    summary = summarize(starting_equity=100000)
    assert summary["latest_equity"] == 105000
    assert abs(summary["total_return"] - 0.05) < 1e-9
    get_settings.cache_clear()
