"""Fetch OHLCV features for OS jobs (failover chain + parallel downloads)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from algo_agents.connectors.market_data.resilient import build_market_data_chain
from algo_agents.features.technical import compute_features

_FETCH_WORKERS = 8


def fetch_features(symbols: list[str], days: int = 120) -> dict:
    data = build_market_data_chain()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    features: dict = {}
    with ThreadPoolExecutor(max_workers=max(1, min(_FETCH_WORKERS, len(symbols) or 1))) as pool:
        futures = {sym: pool.submit(data.get_bars, sym, start, end) for sym in symbols}
        for sym, future in futures.items():
            try:
                bars = future.result()
            except Exception:
                continue
            if bars is not None and not bars.empty:
                frame = compute_features(bars)
                if frame is not None and not frame.empty:
                    features[sym] = frame
    return features
