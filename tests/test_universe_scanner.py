"""Tests for universe scanner + watchlist wiring."""
from __future__ import annotations

from datetime import date

import pandas as pd

from algo_agents.os.jobs import register_all_jobs
from algo_agents.os.jobs.monitor import resolve_monitor_symbols
from algo_agents.os.registry import names
from algo_agents.universe.scanner import (
    load_watchlist,
    rank_universe,
    resolve_paper_symbols,
    score_symbol,
    write_watchlist,
)
from algo_agents.universe.symbols import sample_scan_symbols, scan_seed_for_date


def _frame(momentum: float, trend: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0],
            "momentum_10": [0.0, 0.0, momentum],
            "trend": [0.0, 0.0, trend],
            "rsi_14": [50.0, 50.0, 55.0],
            "volume_zscore": [0.0, 0.0, 1.0],
            "volatility_20": [0.01, 0.01, 0.02],
        }
    )


def test_score_and_rank_universe():
    features = {
        "AAA": _frame(0.05),
        "BBB": _frame(0.20),
        "CCC": _frame(-0.10),
    }
    ranked = rank_universe(features, top_n=2)
    assert len(ranked) == 2
    assert ranked[0]["symbol"] == "BBB"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_watchlist_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    ranked = rank_universe({"AAPL": _frame(0.1), "MSFT": _frame(0.05)}, top_n=2)
    path = write_watchlist(ranked, scanned=2)
    assert path.exists()
    loaded = load_watchlist()
    assert loaded == ["AAPL", "MSFT"] or set(loaded or []) == {"AAPL", "MSFT"}
    get_settings.cache_clear()


def test_resolve_paper_symbols_prefers_watchlist(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.setenv("TRADING_UNIVERSE", "AAPL,MSFT,NVDA")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    write_watchlist(
        [{"symbol": "NVDA", "score": 1.0, "components": {}}],
        scanned=1,
    )
    assert resolve_paper_symbols(settings) == ["NVDA"]
    assert resolve_paper_symbols(settings, explicit=["AAPL"]) == ["AAPL"]
    get_settings.cache_clear()


def test_score_symbol_empty():
    score, components = score_symbol(pd.DataFrame())
    assert score == float("-inf")
    assert components == {}


def test_score_symbol_skips_penny():
    frame = _frame(0.5)
    frame["close"] = [0.5, 0.4, 0.3]
    score, _ = score_symbol(frame)
    assert score == float("-inf")


def test_is_scan_friendly_symbol():
    from algo_agents.universe.symbols import is_scan_friendly_symbol

    assert is_scan_friendly_symbol("AAPL")
    assert not is_scan_friendly_symbol("JUTGF")
    assert is_scan_friendly_symbol("META")

def test_registry_includes_scanner_and_graphify():
    register_all_jobs()
    registered = set(names())
    assert "universe-scan" in registered
    assert "graphify" in registered


def test_resolve_monitor_symbols_prefers_watchlist(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNS_DIR", str(tmp_path))
    monkeypatch.setenv("TRADING_UNIVERSE", "AAPL,MSFT,NVDA,AMZN,GOOGL,META")
    monkeypatch.setenv("MONITOR_MAX_SYMBOLS", "3")
    from algo_agents.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    write_watchlist(
        [
            {"symbol": "NVDA", "score": 1.0, "components": {}},
            {"symbol": "AAPL", "score": 0.9, "components": {}},
            {"symbol": "MSFT", "score": 0.8, "components": {}},
            {"symbol": "AMZN", "score": 0.7, "components": {}},
        ],
        scanned=4,
    )
    assert resolve_monitor_symbols(settings) == ["NVDA", "AAPL", "MSFT"]
    assert resolve_monitor_symbols(settings, explicit=["GOOGL", "META"]) == ["GOOGL", "META"]
    get_settings.cache_clear()


def test_sample_scan_symbols_avoids_alpha_prefix_bias():
    # Alphabetically-first slice would be all "A*" tickers.
    universe = [f"A{i:03d}" for i in range(40)] + [f"Z{i:03d}" for i in range(40)]
    universe += [f"M{i:03d}" for i in range(40)]
    sampled = sample_scan_symbols(universe, 30, seed=20260711)
    assert len(sampled) == 30
    letters = {s[0] for s in sampled}
    assert letters == {"A", "M", "Z"}
    # Same day seed is reproducible.
    assert sample_scan_symbols(universe, 30, seed=20260711) == sampled
    assert sample_scan_symbols(universe, 30, seed=20260712) != sampled


def test_scan_seed_for_date():
    assert scan_seed_for_date(date(2026, 7, 11)) == 20260711


def test_default_trading_universe_is_unrestricted(monkeypatch):
    monkeypatch.delenv("TRADING_UNIVERSE", raising=False)
    from algo_agents.config import Settings, get_settings

    get_settings.cache_clear()
    # Bypass .env so the pydantic field default is what we assert.
    s = Settings(_env_file=None)
    assert s.trading_universe == "*"
    assert s.universe_unrestricted
    get_settings.cache_clear()
