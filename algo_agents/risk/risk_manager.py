"""Hard risk overlay that wraps every strategy decision.

Clips per-symbol weight, targets per-position volatility, caps book-level
volatility (correlation-aware when a correlation matrix is supplied), caps
gross exposure, and acts as a kill-switch when drawdown breaches the limit.
Converts approved target weights into concrete, broker-ready orders.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from algo_agents.connectors.base import OrderRequest, OrderSide, OrderType


@dataclass
class RiskLimits:
    max_weight_per_symbol: float = 0.20
    max_gross_exposure: float = 1.0
    max_drawdown_stop: float = 0.20
    min_order_notional: float = 1.0
    # Daily per-position volatility target (features report daily std).
    # High-vol names are scaled down toward this; low-vol names are never levered up.
    vol_target: float = 0.015
    # Daily book-level volatility cap (sqrt(w' Sigma w)).
    max_portfolio_vol: float = 0.04


class RiskManager:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def apply(
        self,
        weights: dict[str, float],
        current_drawdown: float = 0.0,
        vols: dict[str, float] | None = None,
        corr: pd.DataFrame | None = None,
    ) -> dict[str, float]:
        """Return risk-adjusted weights, or all-flat if the kill-switch trips."""
        if current_drawdown <= -abs(self.limits.max_drawdown_stop):
            return {}

        adjusted = dict(weights)

        if vols:
            adjusted = {
                s: w * self._vol_scale(vols.get(s))
                for s, w in adjusted.items()
            }

        cap = self.limits.max_weight_per_symbol
        adjusted = {s: max(-cap, min(cap, w)) for s, w in adjusted.items()}

        adjusted = self._apply_book_vol_cap(adjusted, vols, corr)

        gross = sum(abs(w) for w in adjusted.values())
        if gross > self.limits.max_gross_exposure and gross > 0:
            scale = self.limits.max_gross_exposure / gross
            adjusted = {s: w * scale for s, w in adjusted.items()}
        return adjusted

    def _vol_scale(self, vol: float | None) -> float:
        """Scale factor toward the per-position vol target (never > 1)."""
        if vol is None or vol <= 0 or not math.isfinite(vol):
            return 1.0
        return min(1.0, self.limits.vol_target / vol)

    def _apply_book_vol_cap(
        self,
        weights: dict[str, float],
        vols: dict[str, float] | None,
        corr: pd.DataFrame | None,
    ) -> dict[str, float]:
        if not vols or not weights:
            return weights
        sigmas = {s: vols.get(s) for s in weights}
        if any(v is None or v <= 0 or not math.isfinite(v) for v in sigmas.values()):
            return weights

        if corr is not None and set(weights) <= set(corr.index):
            cov = self._covariance(sigmas, corr, weights)
            w_vec = np.array([weights[s] for s in weights])
            book_vol = math.sqrt(max(0.0, float(w_vec @ cov.to_numpy() @ w_vec)))
        else:
            book_vol = math.sqrt(sum((w * sigmas[s]) ** 2 for s, w in weights.items()))

        if book_vol <= self.limits.max_portfolio_vol or book_vol == 0:
            return weights
        scale = self.limits.max_portfolio_vol / book_vol
        return {s: w * scale for s, w in weights.items()}

    @staticmethod
    def _covariance(
        sigmas: dict[str, float], corr: pd.DataFrame, weights: dict[str, float]
    ) -> pd.DataFrame:
        symbols = list(weights)
        c = corr.loc[symbols, symbols].to_numpy()
        d = pd.Series({s: sigmas[s] for s in symbols})
        return pd.DataFrame(c, index=symbols, columns=symbols).mul(d, axis=0).mul(d, axis=1)

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
