"""yfinance market-data connector. No API key; the default data source."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime

import pandas as pd

from algo_agents.connectors.base import (
    ConnectorState,
    ConnectorStatus,
    MarketDataConnector,
)

try:
    import yfinance as yf

    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

_TIMEFRAME_MAP = {"1Day": "1d", "1Hour": "1h", "1Min": "1m", "5Min": "5m", "15Min": "15m"}
_FETCH_TIMEOUT_SEC = 20


class YFinanceData(MarketDataConnector):
    name = "yfinance"

    def check(self) -> ConnectorStatus:
        if not _YF_AVAILABLE:
            return ConnectorStatus(
                self.name, ConnectorState.MISSING_DEPENDENCY, "pip install yfinance"
            )
        return ConnectorStatus(self.name, ConnectorState.READY, "no key required")

    def _download(
        self, symbol: str, start: datetime, end: datetime, interval: str
    ) -> pd.DataFrame:
        return yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )

    def get_bars(
        self, symbol: str, start: datetime, end: datetime, timeframe: str = "1Day"
    ) -> pd.DataFrame:
        if not _YF_AVAILABLE:
            raise RuntimeError("yfinance not installed")
        interval = _TIMEFRAME_MAP.get(timeframe, "1d")
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                df = pool.submit(self._download, symbol, start, end, interval).result(
                    timeout=_FETCH_TIMEOUT_SEC
                )
        except FuturesTimeoutError:
            return pd.DataFrame()
        if df.empty:
            return df
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        df.index = pd.to_datetime(df.index, utc=True)
        df.index.name = "timestamp"
        return df
