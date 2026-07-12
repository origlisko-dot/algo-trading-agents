"""ML signal OOS backtest job."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd

from algo_agents.backtest.engine import run_backtest
from algo_agents.connectors.market_data.yfinance_data import YFinanceData
from algo_agents.features.technical import compute_features
from algo_agents.os.context import JobResult, RunContext
from algo_agents.strategy.ml_signal_strategy import MLSignalStrategy
from algo_agents.universe.symbols import resolve_trading_symbols


def run_ml_backtest(ctx: RunContext) -> JobResult:
    settings = ctx.settings
    if ctx.symbols:
        symbols = ctx.symbols
    else:
        symbols = resolve_trading_symbols(settings)[: min(20, settings.trading_universe_max)]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=ctx.ml_days)
    data = YFinanceData()
    features: dict = {}
    prices: dict = {}
    for symbol in symbols:
        bars = data.get_bars(symbol, start, end)
        if bars.empty:
            continue
        feat = compute_features(bars)
        features[symbol] = feat
        prices[symbol] = feat["close"]

    if len(features) < 3:
        return JobResult(name="ml_backtest", ok=False, detail="need >=3 symbols with data")

    price_df = pd.DataFrame(prices).dropna(how="all")
    strategy = MLSignalStrategy(top_n=ctx.top_n)
    weights_df, latest = strategy.generate_oos_weights(features)
    if weights_df.empty:
        return JobResult(name="ml_backtest", ok=False, detail="empty OOS weight panel")

    weights_df = weights_df.reindex(columns=price_df.columns, fill_value=0.0)
    bt = run_backtest(price_df, weights_df)
    metrics = {k: float(bt[k]) for k in ("ann_return", "ann_volatility", "sharpe", "sortino", "max_drawdown", "calmar")}
    return JobResult(
        name="ml_backtest",
        ok=True,
        detail=f"sharpe={metrics['sharpe']:.3f} ann_return={metrics['ann_return']:.2%}",
        data={"metrics": metrics, "latest_weights": latest.weights, "symbols": list(features)},
    )
