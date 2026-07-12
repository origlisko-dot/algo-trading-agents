"""Minimal, dependency-light vectorized backtester with realistic costs.

Target weights are applied on the *next* bar (no same-bar look-ahead) and
turnover is charged a per-trade cost. Reported metrics are deliberately
conservative; treat headline returns as plausibility checks, not forecasts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _metrics(returns: pd.Series, equity: pd.Series, periods_per_year: int) -> dict[str, float]:
    n = max(len(returns), 1)
    ann_return = float(equity.iloc[-1] ** (periods_per_year / n) - 1) if equity.iloc[-1] > 0 else -1.0
    ann_vol = float(returns.std() * np.sqrt(periods_per_year))
    sharpe = float(returns.mean() / returns.std() * np.sqrt(periods_per_year)) if returns.std() > 0 else 0.0
    downside = returns[returns < 0].std()
    sortino = float(returns.mean() / downside * np.sqrt(periods_per_year)) if downside and downside > 0 else 0.0
    drawdown = equity / equity.cummax() - 1.0
    max_dd = float(drawdown.min())
    calmar = float(ann_return / abs(max_dd)) if max_dd < 0 else 0.0
    return {
        "ann_return": ann_return,
        "ann_volatility": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": calmar,
    }


def run_backtest(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    cost_bps: float = 5.0,
    periods_per_year: int = 252,
) -> dict[str, object]:
    """Backtest target weights against a price panel.

    prices/weights: index = timestamps, columns = symbols.
    cost_bps: round-trip-ish cost charged on traded notional (turnover).
    """
    asset_returns = prices.pct_change().fillna(0.0)
    applied = weights.shift(1).reindex(prices.index).fillna(0.0)
    turnover = applied.diff().abs().sum(axis=1).fillna(0.0)
    costs = turnover * (cost_bps / 1e4)
    port_returns = (applied * asset_returns).sum(axis=1) - costs
    equity = (1.0 + port_returns).cumprod()
    metrics = _metrics(port_returns, equity, periods_per_year)
    return {"equity": equity, "returns": port_returns, "turnover": turnover, **metrics}
