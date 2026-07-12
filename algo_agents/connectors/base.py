"""Connector contracts shared by every external integration.

A connector never raises on construction. Missing SDKs or credentials are
reported through `check()` as a `ConnectorStatus`, so the whole stack can be
introspected (see `scripts/check_connections.py`) before any live call.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import pandas as pd


class ConnectorState(str, Enum):
    READY = "READY"
    MISSING_CREDENTIALS = "MISSING_CREDENTIALS"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    NOT_RUNNING = "NOT_RUNNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class ConnectorStatus:
    name: str
    state: ConnectorState
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.state is ConnectorState.READY


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class OrderRequest:
    symbol: str
    qty: float
    side: OrderSide
    type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    take_profit: float | None = None
    time_in_force: str = "day"
    client_order_id: str | None = None


class BaseConnector(ABC):
    name: str = "base"

    @abstractmethod
    def check(self) -> ConnectorStatus:
        """Report readiness without performing any trading side effects."""


class MarketDataConnector(BaseConnector):
    @abstractmethod
    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        """Return OHLCV bars indexed by timestamp (tz-aware, UTC)."""


class NewsConnector(BaseConnector):
    @abstractmethod
    def get_news(self, symbol: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Return news items: [{ 'datetime', 'headline', 'summary', 'url' }]."""


class SentimentConnector(BaseConnector):
    @abstractmethod
    def score(self, texts: list[str]) -> list[dict[str, Any]]:
        """Return [{ 'label', 'score', 'signed' }] aligned with `texts`."""


class BrokerConnector(BaseConnector):
    is_paper: bool = True

    @abstractmethod
    def get_account(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def submit_order(self, order: OrderRequest) -> dict[str, Any]:
        ...


class MemoryStore(BaseConnector):
    @abstractmethod
    def add(self, text: str, metadata: dict[str, Any]) -> None:
        ...

    @abstractmethod
    def query(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        ...
