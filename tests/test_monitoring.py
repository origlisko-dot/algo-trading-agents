"""Tests for champion/challenger monitoring."""
from __future__ import annotations

from datetime import timezone

import pandas as pd

from algo_agents.monitoring.metrics import compare_strategies, signal_drift


def _make_panel(n: int = 100, symbols: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    symbols = symbols or ["AAPL", "MSFT"]
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz=timezone.utc)
    prices = pd.DataFrame({s: 100 + i * 0.1 for i, s in enumerate(symbols, start=0)}, index=idx)
    for s in symbols:
        prices[s] = range(100, 100 + n)
    features = {}
    for s in symbols:
        close = prices[s].astype(float)
        features[s] = pd.DataFrame(
            {
                "open": close,
                "high": close + 1,
                "low": close - 1,
                "close": close,
                "volume": 1_000_000,
                "momentum_10": 0.05,
                "trend": 1.0,
                "rsi_14": 55.0,
                "volatility_20": 0.02,
            },
            index=idx,
        )
    return prices, features


def test_compare_strategies_runs():
    prices, features = _make_panel()
    result = compare_strategies(prices, features, agent_use_llm=False)
    assert result.champion.name == "momentum_sentiment"
    assert result.challenger.name == "agent_strategy"


def test_signal_drift_zero_for_identical():
    idx = pd.date_range("2024-01-01", periods=10, freq="D", tz=timezone.utc)
    w = pd.DataFrame({"AAPL": [0.1] * 10}, index=idx)
    assert signal_drift(w, w) == 0.0
