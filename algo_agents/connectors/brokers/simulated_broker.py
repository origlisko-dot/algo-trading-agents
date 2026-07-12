"""Local paper broker — no external account required.

Persists a virtual portfolio to disk and fills market orders at yfinance prices.
Default replacement when Alpaca/IBKR are unavailable.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from algo_agents.config import get_settings
from algo_agents.connectors.base import (
    BrokerConnector,
    ConnectorState,
    ConnectorStatus,
    OrderRequest,
    OrderSide,
)
from algo_agents.connectors.market_data.yfinance_data import YFinanceData
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)


class SimulatedBroker(BrokerConnector):
    name = "simulated"
    is_paper = True

    def __init__(
        self,
        *,
        state_path: str | Path | None = None,
        name: str | None = None,
        mark_prices: dict[str, float] | None = None,
        starting_cash: float | None = None,
    ) -> None:
        self._settings = get_settings()
        self._path = Path(state_path) if state_path else Path(self._settings.paper_state_path)
        self._data = YFinanceData()
        self._state: dict[str, Any] | None = None
        self._mark_prices = dict(mark_prices or {})
        self._starting_cash = (
            float(starting_cash)
            if starting_cash is not None
            else float(self._settings.paper_starting_cash)
        )
        if name:
            self.name = name

    def set_mark_prices(self, prices: dict[str, float]) -> None:
        """Prefer these marks for fills/equity (avoids extra yfinance round-trips)."""
        self._mark_prices = {str(k).upper(): float(v) for k, v in prices.items()}

    def _load(self) -> dict[str, Any]:
        if self._state is not None:
            return self._state
        if self._path.exists():
            with self._path.open(encoding="utf-8") as f:
                self._state = json.load(f)
                return self._state
        self._state = {
            "cash": self._starting_cash,
            "positions": {},
            "orders": [],
        }
        self._save()
        return self._state

    def _save(self) -> None:
        if self._state is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)

    def check(self) -> ConnectorStatus:
        state = self._load()
        return ConnectorStatus(
            self.name,
            ConnectorState.READY,
            f"local paper @ {self._path} cash={state['cash']:.2f}",
        )

    def _last_price(self, symbol: str) -> float:
        key = symbol.upper()
        if key in self._mark_prices:
            return float(self._mark_prices[key])
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=5)
        bars = self._data.get_bars(symbol, start, end)
        if bars.empty:
            raise RuntimeError(f"No price for {symbol}")
        return float(bars["close"].iloc[-1])

    def _mark_equity(self, state: dict[str, Any]) -> float:
        equity = float(state["cash"])
        for symbol, pos in state.get("positions", {}).items():
            qty = float(pos.get("qty", 0))
            if abs(qty) < 1e-9:
                continue
            try:
                equity += qty * self._last_price(symbol)
            except Exception:
                equity += qty * float(pos.get("avg_price", 0))
        return equity

    def get_account(self) -> dict[str, Any]:
        state = self._load()
        equity = self._mark_equity(state)
        return {
            "account_number": "SIM-PAPER",
            "cash": float(state["cash"]),
            "equity": equity,
            "buying_power": float(state["cash"]),
            "paper": True,
        }

    def get_positions(self) -> list[dict[str, Any]]:
        state = self._load()
        out: list[dict[str, Any]] = []
        for symbol, pos in state.get("positions", {}).items():
            qty = float(pos.get("qty", 0))
            if abs(qty) < 1e-9:
                continue
            avg = float(pos.get("avg_price", 0))
            try:
                price = self._last_price(symbol)
                mv = qty * price
            except Exception:
                price = avg
                mv = qty * avg
            out.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "avg_price": avg,
                    "market_value": mv,
                    "unrealized_pl": mv - qty * avg,
                }
            )
        return out

    def submit_order(self, order: OrderRequest) -> dict[str, Any]:
        state = self._load()
        price = order.limit_price if order.limit_price else self._last_price(order.symbol)
        notional = order.qty * price
        positions: dict[str, Any] = state.setdefault("positions", {})
        pos = positions.setdefault(order.symbol, {"qty": 0.0, "avg_price": 0.0})
        cur_qty = float(pos["qty"])

        if order.side is OrderSide.BUY:
            if notional > float(state["cash"]) + 1e-6:
                raise RuntimeError(f"Insufficient cash for {order.symbol}")
            new_qty = cur_qty + order.qty
            if new_qty > 0:
                pos["avg_price"] = (
                    (cur_qty * float(pos["avg_price"]) + notional) / new_qty
                    if cur_qty > 0
                    else price
                )
            pos["qty"] = new_qty
            state["cash"] = float(state["cash"]) - notional
        else:
            if order.qty > cur_qty + 1e-6:
                raise RuntimeError(f"Insufficient shares to sell {order.symbol}")
            pos["qty"] = cur_qty - order.qty
            state["cash"] = float(state["cash"]) + notional
            if pos["qty"] <= 1e-9:
                positions.pop(order.symbol, None)

        order_id = order.client_order_id or str(uuid.uuid4())[:8]
        record = {
            "id": order_id,
            "symbol": order.symbol,
            "qty": float(order.qty),
            "side": order.side.value,
            "fill_price": price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        state.setdefault("orders", []).append(record)
        self._save()
        _log.info("sim fill %s %s %s @ %.2f", order.symbol, order.side.value, order.qty, price)
        return {"id": order_id, "symbol": order.symbol, "qty": order.qty, "side": order.side.value, "status": "filled"}
