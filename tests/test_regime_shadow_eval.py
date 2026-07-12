"""Tests for regime, shadow ladder, and eval learning."""
from __future__ import annotations

import pandas as pd

from algo_agents.monitoring.eval_learning import (
    learned_max_weight,
    load_eval_learning,
    record_eval_failure,
    record_eval_success,
    require_mock_on_fail,
)
from algo_agents.monitoring.regime import (
    detect_regime,
    load_regime_sharpe,
    prefer_regime_history_winner,
    record_regime_sharpes,
    regime_history_summary,
    regime_preferred_strategies,
)
from algo_agents.monitoring.shadow import (
    append_shadow_snapshot,
    apply_zero_llm_gate,
    pick_promotion_winner,
    shadow_account_path,
    shadow_leaderboard,
    update_shadow_book,
)


def test_detect_regime_bull(tmp_path=None):
    idx = pd.date_range("2024-01-01", periods=80, freq="B")
    close = pd.Series(range(100, 180), index=idx, dtype=float)
    assert detect_regime(close) in {"bull_low_vol", "bull_high_vol"}


def test_regime_preferences():
    assert regime_preferred_strategies("bear_high_vol")[0] == "agent"


def test_record_regime_sharpes_rolling_mean(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    store = record_regime_sharpes(
        "bull_low_vol",
        {"momentum": 1.0, "agent": 0.5, "ml": 0.8},
    )
    assert store["bull_low_vol"]["momentum"]["samples"] == 1
    assert abs(store["bull_low_vol"]["momentum"]["mean_sharpe"] - 1.0) < 1e-9

    store = record_regime_sharpes(
        "bull_low_vol",
        {"momentum": 2.0, "agent": 0.5, "ml": 0.8},
    )
    assert store["bull_low_vol"]["momentum"]["samples"] == 2
    assert abs(store["bull_low_vol"]["momentum"]["mean_sharpe"] - 1.5) < 1e-9
    assert abs(store["bull_low_vol"]["momentum"]["last_sharpe"] - 2.0) < 1e-9
    reloaded = load_regime_sharpe()
    assert reloaded["bull_low_vol"]["momentum"]["samples"] == 2
    get_settings.cache_clear()


def test_prefer_regime_history_winner_when_enough_samples(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    # ml historically best in this regime; measured soft-winner would be momentum.
    for sharpes in (
        {"momentum": 0.5, "agent": 0.4, "ml": 1.5},
        {"momentum": 0.6, "agent": 0.3, "ml": 1.4},
        {"momentum": 0.7, "agent": 0.2, "ml": 1.6},
    ):
        record_regime_sharpes("bear_high_vol", sharpes)

    winner, reason = prefer_regime_history_winner("bear_high_vol", min_samples=3)
    assert winner == "ml"
    assert "regime_history" in reason
    summary = regime_history_summary("bear_high_vol")
    assert summary["regime"] == "bear_high_vol"
    assert summary["strategies"]["ml"]["samples"] == 3
    get_settings.cache_clear()


def test_prefer_regime_history_thin_returns_none(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    record_regime_sharpes(
        "bull_high_vol",
        {"momentum": 1.0, "agent": 0.9, "ml": 0.8},
    )
    winner, reason = prefer_regime_history_winner("bull_high_vol", min_samples=3)
    assert winner is None
    assert "thin" in reason.lower()
    get_settings.cache_clear()


def test_shadow_and_eval_learning(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    append_shadow_snapshot("ml", run_id="r1", equity=105000, weights={"AAPL": 0.2}, sharpe=0.5)
    board = shadow_leaderboard(starting_equity=100000)
    assert board["ml"]["snapshots"] == 1
    assert abs(board["ml"]["total_return"] - 0.05) < 1e-9

    before = learned_max_weight()
    failed = record_eval_failure(run_id="e1", detail="0/8", passed=0, total=8)
    assert failed["max_weight_per_symbol"] < before
    assert load_eval_learning()["failures"] == 1
    assert require_mock_on_fail() is False
    record_eval_failure(run_id="e1b", detail="0/8", passed=0, total=8)
    third = record_eval_failure(run_id="e1c", detail="0/8", passed=0, total=8)
    assert require_mock_on_fail() is True
    ok = record_eval_success(run_id="e2")
    assert ok["max_weight_per_symbol"] >= third["max_weight_per_symbol"]
    assert require_mock_on_fail() is False
    get_settings.cache_clear()


def test_shadow_book_fills_separate_ledgers(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.setenv("PAPER_STARTING_CASH", "100000")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    prices = {"AAPL": 100.0, "MSFT": 200.0}
    mom = update_shadow_book(
        "momentum",
        weights={"AAPL": 0.2},
        prices=prices,
        run_id="r1",
        sharpe=0.4,
    )
    agent = update_shadow_book(
        "agent",
        weights={"MSFT": 0.2},
        prices=prices,
        run_id="r1",
        sharpe=0.1,
    )
    assert mom["submitted"] >= 1
    assert agent["submitted"] >= 1
    assert shadow_account_path("momentum").exists()
    assert shadow_account_path("agent").exists()
    assert shadow_account_path("momentum") != shadow_account_path("agent")
    board = shadow_leaderboard(starting_equity=100000)
    assert board["momentum"]["snapshots"] == 1
    assert board["agent"]["snapshots"] == 1
    assert board["momentum"]["has_book"] is True
    get_settings.cache_clear()


def test_zero_llm_gate_blocks_agent_on_thin_history(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    # Thin shadow history → gate uses backtest Sharpe.
    board = shadow_leaderboard(starting_equity=100000)
    metrics = {
        "momentum": {"sharpe": 1.2},
        "agent": {"sharpe": 0.8},
        "ml": {"sharpe": 0.5},
    }
    winner, reason = pick_promotion_winner("agent", board=board, backtest_metrics=metrics, min_snapshots=3)
    assert winner == "agent"
    active, gate = apply_zero_llm_gate(
        winner, board=board, backtest_metrics=metrics, min_snapshots=3
    )
    assert active == "momentum"
    assert gate is not None and "zero_llm_gate" in gate
    get_settings.cache_clear()


def test_zero_llm_gate_allows_agent_when_beats_momentum(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    for i in range(3):
        append_shadow_snapshot("momentum", run_id=f"m{i}", equity=100000 + i * 100, weights={})
        append_shadow_snapshot("agent", run_id=f"a{i}", equity=110000 + i * 500, weights={})
        append_shadow_snapshot("ml", run_id=f"l{i}", equity=101000 + i * 50, weights={})
    board = shadow_leaderboard(starting_equity=100000)
    winner, _ = pick_promotion_winner("momentum", board=board, min_snapshots=3)
    assert winner == "agent"
    active, gate = apply_zero_llm_gate(winner, board=board, min_snapshots=3)
    assert active == "agent"
    assert gate is None
    get_settings.cache_clear()
