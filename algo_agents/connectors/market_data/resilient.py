"""Resilient market-data layer: source failover + optional on-disk bar cache."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from algo_agents.connectors.base import (
    ConnectorState,
    ConnectorStatus,
    MarketDataConnector,
)

_log = logging.getLogger(__name__)


class ResilientMarketData(MarketDataConnector):
    """Try each source in order until one returns usable bars.

    Adds a day-granularity on-disk cache so repeated same-day calls
    (paper -> monitor -> portfolio) don't refetch or hit rate limits.
    """

    name = "resilient"

    def __init__(
        self,
        sources: list[MarketDataConnector],
        cache_dir: Path | str | None = None,
    ) -> None:
        self.sources = sources
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.last_source: str | None = None

    def check(self) -> ConnectorStatus:
        statuses = [s.check() for s in self.sources]
        ready = [s for s in statuses if s.ok]
        if ready:
            detail = "; ".join(f"{s.name}={s.state.value}" for s in statuses)
            return ConnectorStatus(self.name, ConnectorState.READY, detail)
        return ConnectorStatus(
            self.name,
            ConnectorState.ERROR,
            "no source ready: " + "; ".join(f"{s.name}={s.state.value}" for s in statuses),
        )

    def _cache_path(self, symbol: str, start: datetime, end: datetime, timeframe: str) -> Path:
        key = f"{symbol.upper()}_{timeframe}_{start:%Y%m%d}_{end:%Y%m%d}.csv"
        return self.cache_dir / key

    def _cache_read(self, path: Path) -> pd.DataFrame | None:
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
        except Exception:
            return None
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "timestamp"
        return df

    def _cache_write(self, path: Path, df: pd.DataFrame) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            df.to_csv(path)
        except Exception as exc:
            _log.debug("bars cache write failed: %s", exc)

    def get_bars(
        self, symbol: str, start: datetime, end: datetime, timeframe: str = "1Day"
    ) -> pd.DataFrame:
        self.last_source = None
        if self.cache_dir is not None:
            path = self._cache_path(symbol, start, end, timeframe)
            if path.exists():
                cached = self._cache_read(path)
                if cached is not None:
                    self.last_source = "cache"
                    return cached

        for source in self.sources:
            try:
                df = source.get_bars(symbol, start, end, timeframe)
            except Exception as exc:
                _log.warning("market-data source %s failed for %s: %s", source.name, symbol, exc)
                continue
            if df is not None and not df.empty:
                self.last_source = source.name
                if self.cache_dir is not None:
                    self._cache_write(self._cache_path(symbol, start, end, timeframe), df)
                return df

        return pd.DataFrame()


def build_market_data_chain(
    settings=None, *, cache: bool = True
) -> ResilientMarketData:
    """Default failover chain: yfinance -> stooq -> finnhub -> polygon (keyed)."""
    from algo_agents.config import get_settings
    from algo_agents.connectors.market_data.finnhub_data import FinnhubData
    from algo_agents.connectors.market_data.polygon_data import PolygonData
    from algo_agents.connectors.market_data.stooq_data import StooqData
    from algo_agents.connectors.market_data.yfinance_data import YFinanceData

    cfg = settings or get_settings()
    sources: list[MarketDataConnector] = [YFinanceData(), StooqData()]
    if cfg.finnhub_api_key:
        sources.append(FinnhubData())
    if cfg.polygon_api_key:
        sources.append(PolygonData())
    cache_dir = Path(cfg.runs_dir) / "cache" / "bars" if cache else None
    return ResilientMarketData(sources, cache_dir=cache_dir)
