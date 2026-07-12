"""Tests for AgentStrategy with heuristic (no LLM) path."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from algo_agents.strategy.agent_strategy import AgentStrategy


def _sample_features(symbol: str = "AAPL") -> dict[str, pd.DataFrame]:
    idx = pd.date_range("2024-01-01", periods=60, freq="D", tz=timezone.utc)
    close = pd.Series(range(100, 160), index=idx, dtype=float)
    df = pd.DataFrame(
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
    return {symbol: df}


def test_agent_strategy_heuristic(monkeypatch):
    monkeypatch.setenv("TRADING_UNIVERSE", "AAPL")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    strategy = AgentStrategy(use_llm=False, offline=True, symbols=["AAPL"])
    result = strategy.generate_weights(_sample_features(), context={"run_id": "test"})
    get_settings.cache_clear()
    assert isinstance(result.weights, dict)
    assert "AAPL" in result.rationale or "_" in result.rationale


def test_agent_strategy_empty_features():
    strategy = AgentStrategy(use_llm=False, symbols=["AAPL"])
    result = strategy.generate_weights({})
    assert result.weights == {}
