"""Financial Modeling Prep (FMP) market-data connector."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import requests

from algo_agents.config import get_settings
from algo_agents.connectors.base import (
    ConnectorState,
    ConnectorStatus,
    MarketDataConnector,
)

_BASE_URL = "https://financialmodelingprep.com/api/v3"
_INTRADAY = {"1Hour": "1hour", "1Min": "1min", "5Min": "5min", "15Min": "15min"}


class FMPData(MarketDataConnector):
    name = "fmp"

    def __init__(self) -> None:
        self._key = get_settings().fmp_api_key

    def check(self) -> ConnectorStatus:
        if not self._key:
            return ConnectorStatus(
                self.name, ConnectorState.MISSING_CREDENTIALS, "set FMP_API_KEY"
            )
        try:
            resp = requests.get(
                f"{_BASE_URL}/quote-short/AAPL",
                params={"apikey": self._key},
                timeout=10,
            )
            resp.raise_for_status()
            return ConnectorStatus(self.name, ConnectorState.READY, "REST reachable")
        except Exception as exc:
            return ConnectorStatus(self.name, ConnectorState.ERROR, str(exc))

    def get_bars(
        self, symbol: str, start: datetime, end: datetime, timeframe: str = "1Day"
    ) -> pd.DataFrame:
        if not self._key:
            raise RuntimeError("FMP_API_KEY not set")
        symbol = symbol.upper()
        if timeframe == "1Day":
            url = f"{_BASE_URL}/historical-price-full/{symbol}"
            params = {"from": f"{start:%Y-%m-%d}", "to": f"{end:%Y-%m-%d}", "apikey": self._key}
            rows = requests.get(url, params=params, timeout=30).json().get("historical", [])
        else:
            interval = _INTRADAY.get(timeframe, "1hour")
            url = f"{_BASE_URL}/historical-chart/{interval}/{symbol}"
            rows = requests.get(url, params={"apikey": self._key}, timeout=30).json()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["timestamp"] = pd.to_datetime(df["date"], utc=True)
        df = df.set_index("timestamp").sort_index()
        return df[["open", "high", "low", "close", "volume"]]
