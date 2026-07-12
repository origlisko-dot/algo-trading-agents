"""Finnhub market-data connector (REST candles)."""
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

_BASE_URL = "https://finnhub.io/api/v1"
_RESOLUTION_MAP = {"1Day": "D", "1Hour": "60", "1Min": "1", "5Min": "5", "15Min": "15"}


class FinnhubData(MarketDataConnector):
    name = "finnhub"

    def __init__(self) -> None:
        self._key = get_settings().finnhub_api_key

    def check(self) -> ConnectorStatus:
        if not self._key:
            return ConnectorStatus(
                self.name, ConnectorState.MISSING_CREDENTIALS, "set FINNHUB_API_KEY"
            )
        try:
            resp = requests.get(
                f"{_BASE_URL}/quote",
                params={"symbol": "AAPL", "token": self._key},
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
            raise RuntimeError("FINNHUB_API_KEY not set")
        resolution = _RESOLUTION_MAP.get(timeframe, "D")
        resp = requests.get(
            f"{_BASE_URL}/stock/candle",
            params={
                "symbol": symbol.upper(),
                "resolution": resolution,
                "from": int(start.timestamp()),
                "to": int(end.timestamp()),
                "token": self._key,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("s") != "ok":
            return pd.DataFrame()
        df = pd.DataFrame(
            {
                "open": data["o"],
                "high": data["h"],
                "low": data["l"],
                "close": data["c"],
                "volume": data["v"],
            }
        )
        df["timestamp"] = pd.to_datetime(data["t"], unit="s", utc=True)
        return df.set_index("timestamp")
