"""Fetch OHLCV features for OS jobs."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from algo_agents.connectors.market_data.yfinance_data import YFinanceData
from algo_agents.features.technical import compute_features


def fetch_features(symbols: list[str], days: int = 120) -> dict:
    data = YFinanceData()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    features = {}
    for sym in symbols:
        bars = data.get_bars(sym, start, end)
        if not bars.empty:
            features[sym] = compute_features(bars)
    return features
