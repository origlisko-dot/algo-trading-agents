"""Stooq market-data connector: free daily OHLCV, no API key.

Fallback source when yfinance rate-limits. Daily bars only (intraday
timeframes return an empty frame so the failover chain moves on).

Note: Stooq serves a JavaScript proof-of-work challenge to some clients
(datacenter IPs, heavy use). In that case the connector reports
NOT_RUNNING and the failover chain simply skips it.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import requests

from algo_agents.connectors.base import (
    ConnectorState,
    ConnectorStatus,
    MarketDataConnector,
)

_BASE_URL = "https://stooq.com/q/d/l/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def _looks_like_csv(text: str) -> bool:
    return text.lstrip().lower().startswith("date,")


class StooqData(MarketDataConnector):
    name = "stooq"

    def check(self) -> ConnectorStatus:
        try:
            resp = requests.get(
                _BASE_URL,
                params={"s": "aapl.us", "d1": "20240102", "d2": "20240103", "i": "d"},
                headers=_HEADERS,
                timeout=10,
            )
            resp.raise_for_status()
            if not _looks_like_csv(resp.text):
                return ConnectorStatus(
                    self.name,
                    ConnectorState.NOT_RUNNING,
                    "served JS challenge instead of CSV (blocked IP or daily limit)",
                )
            return ConnectorStatus(self.name, ConnectorState.READY, "no key required")
        except Exception as exc:
            return ConnectorStatus(self.name, ConnectorState.ERROR, str(exc))

    def get_bars(
        self, symbol: str, start: datetime, end: datetime, timeframe: str = "1Day"
    ) -> pd.DataFrame:
        if timeframe != "1Day":
            return pd.DataFrame()
        resp = requests.get(
            _BASE_URL,
            params={
                "s": f"{symbol.lower()}.us",
                "d1": start.strftime("%Y%m%d"),
                "d2": end.strftime("%Y%m%d"),
                "i": "d",
            },
            headers=_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        if not _looks_like_csv(resp.text):
            return pd.DataFrame()
        df = pd.read_csv(io.StringIO(resp.text))
        if df.empty or "Date" not in df.columns:
            return pd.DataFrame()
        df = df.rename(columns=str.lower)
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.set_index("date").rename_axis("timestamp")
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        return df.sort_index()
