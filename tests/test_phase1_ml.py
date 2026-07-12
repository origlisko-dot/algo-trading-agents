"""Tests for Chroma metadata sanitization, universe cache, ML signal."""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
import pytest

from algo_agents.connectors.memory.vector_store import _sanitize_metadata
from algo_agents.strategy.ml_signal_strategy import MLSignalStrategy
from algo_agents.universe.symbols import _load_cache, _save_cache, resolve_trading_symbols


def test_sanitize_metadata_drops_none_and_stringifies():
    meta = _sanitize_metadata({"a": 1, "b": None, "c": 0.5, "d": True, "e": {"x": 1}})
    assert meta == {"a": 1, "c": 0.5, "d": True, "e": "{'x': 1}"}


def test_universe_cache_roundtrip(tmp_path):
    path = tmp_path / "universe.json"
    _save_cache(path, ["AAPL", "MSFT"], "finnhub")
    loaded = _load_cache(path, max_age_hours=24)
    assert loaded == ["AAPL", "MSFT"]


def test_universe_cache_expires(tmp_path):
    path = tmp_path / "universe.json"
    path.write_text(json.dumps({"ts": time.time() - 7200, "symbols": ["AAPL"]}), encoding="utf-8")
    assert _load_cache(path, max_age_hours=1) is None


def test_resolve_unrestricted_uses_cache(monkeypatch, tmp_path):
    cache = tmp_path / "u.json"
    _save_cache(cache, ["AAPL", "MSFT", "NVDA"], "test")
    monkeypatch.setenv("TRADING_UNIVERSE", "ALL US STOCK")
    monkeypatch.setenv("UNIVERSE_CACHE_PATH", str(cache))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    symbols = resolve_trading_symbols(get_settings())
    get_settings.cache_clear()
    assert symbols == ["AAPL", "MSFT", "NVDA"]


def _synthetic_features(n: int = 120) -> dict[str, pd.DataFrame]:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    out: dict[str, pd.DataFrame] = {}
    rng = np.random.default_rng(42)
    for sym, drift in [("AAPL", 0.001), ("MSFT", 0.0005), ("NVDA", 0.002)]:
        close = 100 * np.cumprod(1 + drift + rng.normal(0, 0.01, n))
        df = pd.DataFrame(
            {
                "close": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "volume": rng.integers(1_000_000, 2_000_000, n),
                "return_1d": pd.Series(close).pct_change(),
                "momentum_10": pd.Series(close).pct_change(10),
                "volatility_20": pd.Series(close).pct_change().rolling(20).std(),
                "rsi_14": 50 + rng.normal(0, 5, n),
                "volume_zscore": rng.normal(0, 1, n),
                "trend": 1.0,
            },
            index=idx,
        )
        out[sym] = df.fillna(0.0)
    return out


def test_ml_signal_strategy_trains_and_returns_weights():
    strategy = MLSignalStrategy(top_n=2, train_frac=0.7)
    features = _synthetic_features()
    assert strategy.fit(features)
    result = strategy.generate_weights(features)
    assert result.weights
    assert abs(sum(result.weights.values()) - 1.0) < 1e-6
