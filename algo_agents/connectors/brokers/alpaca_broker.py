"""Alpaca broker connector (US equities). Defaults to paper trading."""
from __future__ import annotations

from typing import Any

from algo_agents.config import get_settings
from algo_agents.connectors.base import (
    BrokerConnector,
    ConnectorState,
    ConnectorStatus,
    OrderRequest,
    OrderSide,
    OrderType,
)

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide as AlpacaSide
    from alpaca.trading.enums import TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest

    _ALPACA_AVAILABLE = True
except ImportError:
    _ALPACA_AVAILABLE = False


class AlpacaBroker(BrokerConnector):
    name = "alpaca"

    def __init__(self) -> None:
        self._settings = get_settings()
        self.is_paper = self._settings.trading_paper
        self._client: Any = None

    def _client_or_none(self) -> Any:
        if not _ALPACA_AVAILABLE:
            return None
        if self._client is None:
            s = self._settings
            if not (s.alpaca_api_key and s.alpaca_secret_key):
                return None
            self._client = TradingClient(
                s.alpaca_api_key, s.alpaca_secret_key, paper=s.trading_paper
            )
        return self._client

    def check(self) -> ConnectorStatus:
        if not _ALPACA_AVAILABLE:
            return ConnectorStatus(
                self.name, ConnectorState.MISSING_DEPENDENCY, "pip install alpaca-py"
            )
        s = self._settings
        if not (s.alpaca_api_key and s.alpaca_secret_key):
            return ConnectorStatus(
                self.name,
                ConnectorState.MISSING_CREDENTIALS,
                "set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env",
            )
        try:
            acct = self._client_or_none().get_account()
            mode = "paper" if self.is_paper else "LIVE"
            return ConnectorStatus(
                self.name,
                ConnectorState.READY,
                f"{mode}: acct {acct.account_number}, equity {acct.equity}",
            )
        except Exception as exc:
            return ConnectorStatus(self.name, ConnectorState.ERROR, str(exc))

    def get_account(self) -> dict[str, Any]:
        client = self._require_client()
        a = client.get_account()
        return {
            "account_number": a.account_number,
            "cash": float(a.cash),
            "equity": float(a.equity),
            "buying_power": float(a.buying_power),
            "paper": self.is_paper,
        }

    def get_positions(self) -> list[dict[str, Any]]:
        client = self._require_client()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_price": float(p.avg_entry_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
            }
            for p in client.get_all_positions()
        ]

    def submit_order(self, order: OrderRequest) -> dict[str, Any]:
        client = self._require_client()
        side = AlpacaSide.BUY if order.side is OrderSide.BUY else AlpacaSide.SELL
        tif = TimeInForce.DAY if order.time_in_force.lower() == "day" else TimeInForce.GTC
        if order.type is OrderType.LIMIT:
            request = LimitOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=side,
                time_in_force=tif,
                limit_price=order.limit_price,
                client_order_id=order.client_order_id,
            )
        else:
            request = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=side,
                time_in_force=tif,
                client_order_id=order.client_order_id,
            )
        resp = client.submit_order(order_data=request)
        return {
            "id": str(resp.id),
            "symbol": resp.symbol,
            "qty": float(resp.qty or 0),
            "side": str(resp.side),
            "status": str(resp.status),
        }

    def _require_client(self) -> Any:
        client = self._client_or_none()
        if client is None:
            raise RuntimeError(
                "Alpaca connector is not ready; run check() to see why."
            )
        return client
