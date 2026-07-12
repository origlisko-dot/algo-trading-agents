"""Tests for Phase-2 PnL dashboard and FinMem recall helpers."""
from __future__ import annotations

import json

from algo_agents.agents.reflection import build_memory_context
from algo_agents.monitoring.dashboard import build_dashboard_html, write_dashboard
from algo_agents.monitoring.pnl_tracker import record_snapshot
from algo_agents.monitoring.shadow import append_shadow_snapshot


def test_dashboard_builds_html(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    record_snapshot(
        run_id="a",
        broker="simulated",
        account={"cash": 50_000, "equity": 100_000, "buying_power": 50_000},
        positions=[{"symbol": "AAPL", "qty": 1, "unrealized_pl": 10}],
        strategy="ml",
    )
    record_snapshot(
        run_id="b",
        broker="simulated",
        account={"cash": 40_000, "equity": 102_000, "buying_power": 40_000},
        positions=[{"symbol": "AAPL", "qty": 1, "unrealized_pl": 20}],
        strategy="agent",
    )
    append_shadow_snapshot("momentum", run_id="s1", equity=101_000, weights={}, sharpe=0.4)
    run_dir = tmp_path / "run-monitor"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {"monitor": {"signal_drift": 0.1234, "winner": "momentum", "regime": "bull_low_vol"}}
        ),
        encoding="utf-8",
    )
    html = build_dashboard_html(starting_equity=100_000)
    assert "Paper P&amp;L Dashboard" in html
    assert "102000.00" in html or "102,000.00" in html
    assert "Shadow leaderboard" in html
    assert "momentum" in html
    assert "Signal drift" in html
    assert "0.1234" in html
    path = write_dashboard()
    assert path.exists()
    sidecar = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert "shadow" in sidecar
    assert sidecar["monitor"]["signal_drift"] == 0.1234
    get_settings.cache_clear()


def test_build_memory_context_handles_empty(monkeypatch):
    monkeypatch.setattr(
        "algo_agents.agents.reflection.recall_symbol_memories",
        lambda symbol, k=3: "No relevant past trades found.",
    )
    assert build_memory_context(["AAPL"]) == {}
