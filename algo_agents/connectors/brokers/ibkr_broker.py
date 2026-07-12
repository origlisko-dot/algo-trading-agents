"""Interactive Brokers connector via ib-insync.

Requires a running TWS or IB Gateway. Paper vs live is determined by which
port the gateway listens on (7497/4002 are the common paper ports).
"""
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
    from ib_insync import IB, LimitOrder, MarketOrder, Stock

    _IB_AVAILABLE = True
except ImportError:
    _IB_AVAILABLE = False

_PAPER_PORTS = {7497, 4002}


class IBKRBroker(BrokerConnector):
    name = "ibkr"

    def __init__(self) -> None:
        self._s = get_settings()
        self.is_paper = self._s.ibkr_port in _PAPER_PORTS
        self._ib: Any = None

    def _connect_or_none(self) -> Any:
        if not _IB_AVAILABLE:
            return None
        if self._ib is None or not self._ib.isConnected():
            ib = IB()
            ib.connect(
                self._s.ibkr_host,
                self._s.ibkr_port,
                clientId=self._s.ibkr_client_id,
                timeout=5,
            )
            self._ib = ib
        return self._ib

    def check(self) -> ConnectorStatus:
        if not _IB_AVAILABLE:
            return ConnectorStatus(
                self.name, ConnectorState.MISSING_DEPENDENCY, "pip install ib-insync"
            )
        try:
            ib = self._connect_or_none()
            accounts = ib.managedAccounts()
            mode = "paper" if self.is_paper else "LIVE"
            return ConnectorStatus(
                self.name,
                ConnectorState.READY,
                f"{mode}: connected {self._s.ibkr_host}:{self._s.ibkr_port}, accounts {accounts}",
            )
        except Exception as exc:
            return ConnectorStatus(
                self.name,
                ConnectorState.NOT_RUNNING,
                f"cannot reach TWS/Gateway at {self._s.ibkr_host}:{self._s.ibkr_port} ({exc})",
            )

    def get_account(self) -> dict[str, Any]:
        ib = self._require_ib()
        summary = {row.tag: row.value for row in ib.accountSummary()}
        return {
            "account": ib.managedAccounts(),
            "cash": float(summary.get("TotalCashValue", 0) or 0),
            "equity": float(summary.get("NetLiquidation", 0) or 0),
            "buying_power": float(summary.get("BuyingPower", 0) or 0),
            "paper": self.is_paper,
        }

    def get_positions(self) -> list[dict[str, Any]]:
        ib = self._require_ib()
        return [
            {
                "symbol": pos.contract.symbol,
                "qty": float(pos.position),
                "avg_price": float(pos.avgCost),
            }
            for pos in ib.positions()
        ]

    def submit_order(self, order: OrderRequest) -> dict[str, Any]:
        ib = self._require_ib()
        contract = Stock(order.symbol, "SMART", "USD")
        ib.qualifyContracts(contract)
        action = "BUY" if order.side is OrderSide.BUY else "SELL"
        if order.type is OrderType.LIMIT:
            ib_order = LimitOrder(action, order.qty, order.limit_price)
        else:
            ib_order = MarketOrder(action, order.qty)
        trade = ib.placeOrder(contract, ib_order)
        return {
            "id": str(trade.order.orderId),
            "symbol": order.symbol,
            "qty": float(order.qty),
            "side": action,
            "status": str(trade.orderStatus.status),
        }

    def _require_ib(self) -> Any:
        ib = self._connect_or_none()
        if ib is None:
            raise RuntimeError("IBKR connector not ready; run check() for details.")
        return ib
