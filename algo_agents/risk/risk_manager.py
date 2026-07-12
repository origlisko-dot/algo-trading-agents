"""Hard risk overlay that wraps every strategy decision.

Clips per-symbol weight, caps gross exposure, and acts as a kill-switch when
drawdown breaches the limit. Converts approved target weights into concrete,
broker-ready orders.
"""
from __future__ import annotations

from dataclasses import dataclass

from algo_agents.connectors.base import OrderRequest, OrderSide, OrderType


@dataclass
class RiskLimits:
    max_weight_per_symbol: float = 0.20
    max_gross_exposure: float = 1.0
    max_drawdown_stop: float = 0.20
    min_order_notional: float = 1.0


class RiskManager:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def apply(self, weights: dict[str, float], current_drawdown: float = 0.0) -> dict[str, float]:
        """Return risk-adjusted weights, or all-flat if the kill-switch trips."""
        if current_drawdown <= -abs(self.limits.max_drawdown_stop):
            return {}
        cap = self.limits.max_weight_per_symbol
        clipped = {s: max(-cap, min(cap, w)) for s, w in weights.items()}
        gross = sum(abs(w) for w in clipped.values())
        if gross > self.limits.max_gross_exposure and gross > 0:
            scale = self.limits.max_gross_exposure / gross
            clipped = {s: w * scale for s, w in clipped.items()}
        return clipped

    def to_orders(
        self,
        target_weights: dict[str, float],
        equity: float,
        prices: dict[str, float],
        current_positions: dict[str, float] | None = None,
    ) -> list[OrderRequest]:
        """Translate target weights into delta orders versus current holdings."""
        current_positions = current_positions or {}
        orders: list[OrderRequest] = []
        for symbol, weight in target_weights.items():
            price = prices.get(symbol)
            if not price or price <= 0:
                continue
            target_shares = (weight * equity) / price
            delta = target_shares - current_positions.get(symbol, 0.0)
            if abs(delta) * price < self.limits.min_order_notional:
                continue
            orders.append(
                OrderRequest(
                    symbol=symbol,
                    qty=round(abs(delta), 4),
                    side=OrderSide.BUY if delta > 0 else OrderSide.SELL,
                    type=OrderType.MARKET,
                )
            )
        return orders
