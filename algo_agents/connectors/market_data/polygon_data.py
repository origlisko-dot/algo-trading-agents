"""Polygon.io market-data connector (REST aggregates)."""
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

_BASE_URL = "https://api.polygon.io"
_TIMEFRAME_MAP = {
    "1Day": (1, "day"),
    "1Hour": (1, "hour"),
    "1Min": (1, "minute"),
    "5Min": (5, "minute"),
    "15Min": (15, "minute"),
}


class PolygonData(MarketDataConnector):
    name = "polygon"

    def __init__(self) -> None:
        self._key = get_settings().polygon_api_key

    def check(self) -> ConnectorStatus:
        if not self._key:
            return ConnectorStatus(
                self.name, ConnectorState.MISSING_CREDENTIALS, "set POLYGON_API_KEY"
            )
        try:
            resp = requests.get(
                f"{_BASE_URL}/v3/reference/tickers",
                params={"limit": 1, "apiKey": self._key},
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
            raise RuntimeError("POLYGON_API_KEY not set")
        mult, span = _TIMEFRAME_MAP.get(timeframe, (1, "day"))
        url = (
            f"{_BASE_URL}/v2/aggs/ticker/{symbol.upper()}/range/{mult}/{span}/"
            f"{start:%Y-%m-%d}/{end:%Y-%m-%d}"
        )
        resp = requests.get(
            url, params={"adjusted": "true", "sort": "asc", "apiKey": self._key}, timeout=30
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return pd.DataFrame()
        df = pd.DataFrame(results).rename(
            columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
        )
        df["timestamp"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        return df.set_index("timestamp")[["open", "high", "low", "close", "volume"]]
