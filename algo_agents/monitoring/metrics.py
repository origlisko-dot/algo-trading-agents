"""Production monitoring metrics and champion/challenger comparison."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from algo_agents.backtest.engine import run_backtest
from algo_agents.monitoring.regime import regime_preferred_strategies
from algo_agents.observability.logging import get_logger
from algo_agents.strategy.agent_strategy import AgentStrategy
from algo_agents.strategy.base import Strategy, StrategyResult
from algo_agents.strategy.example_strategy import MomentumSentimentStrategy
from algo_agents.strategy.ml_signal_strategy import MLSignalStrategy

_log = get_logger(__name__)


@dataclass
class StrategyMetrics:
    name: str
    sharpe: float
    max_drawdown: float
    ann_return: float
    ann_volatility: float

    @classmethod
    def from_backtest(cls, name: str, result: dict[str, Any]) -> StrategyMetrics:
        return cls(
            name=name,
            sharpe=float(result.get("sharpe", 0.0)),
            max_drawdown=float(result.get("max_drawdown", 0.0)),
            ann_return=float(result.get("ann_return", 0.0)),
            ann_volatility=float(result.get("ann_volatility", 0.0)),
        )


@dataclass
class ChampionChallengerResult:
    champion: StrategyMetrics
    challenger: StrategyMetrics
    challenger_wins: bool
    reason: str
    signal_drift: float = 0.0


@dataclass
class CompareAllResult:
    strategies: dict[str, StrategyMetrics]
    winner: str
    reason: str
    signal_drift: float = 0.0


def _weights_panel(
    prices: pd.DataFrame,
    strategy: Strategy,
    features: dict[str, pd.DataFrame],
    context: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Build a weight panel by applying strategy at each rebalance date."""
    rows: list[dict[str, float]] = []
    for ts in prices.index:
        sliced = {sym: frame.loc[:ts] for sym, frame in features.items() if ts in frame.index}
        if not sliced:
            continue
        result: StrategyResult = strategy.generate_weights(sliced, context=context)
        row = {sym: 0.0 for sym in prices.columns}
        row.update(result.weights)
        rows.append(row)
    if not rows:
        return pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    weights = pd.DataFrame(rows, index=prices.index[: len(rows)])
    return weights.reindex(prices.index).fillna(0.0)


def compare_strategies(
    prices: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    *,
    context: dict[str, Any] | None = None,
    cost_bps: float = 5.0,
    agent_use_llm: bool = False,
) -> ChampionChallengerResult:
    """Run champion/challenger backtest comparison."""
    symbols = list(prices.columns)
    ctx = {**(context or {}), "offline": not agent_use_llm}
    champion_strat = MomentumSentimentStrategy()
    challenger_strat = AgentStrategy(
        use_llm=agent_use_llm,
        offline=not agent_use_llm,
        symbols=symbols,
    )

    champion_weights = _weights_panel(prices, champion_strat, features, ctx)
    challenger_weights = _weights_panel(prices, challenger_strat, features, ctx)

    champion_bt = run_backtest(prices, champion_weights, cost_bps=cost_bps)
    challenger_bt = run_backtest(prices, challenger_weights, cost_bps=cost_bps)

    champion = StrategyMetrics.from_backtest(champion_strat.name, champion_bt)
    challenger = StrategyMetrics.from_backtest(challenger_strat.name, challenger_bt)

    wins = (
        challenger.sharpe > champion.sharpe
        and challenger.max_drawdown >= champion.max_drawdown
    )
    reason = (
        f"challenger sharpe {challenger.sharpe:.3f} vs champion {champion.sharpe:.3f}; "
        f"dd {challenger.max_drawdown:.3f} vs {champion.max_drawdown:.3f}"
    )
    _log.info("champion/challenger: %s", reason)
    drift = signal_drift(champion_weights, challenger_weights)
    return ChampionChallengerResult(
        champion=champion,
        challenger=challenger,
        challenger_wins=wins,
        reason=reason,
        signal_drift=drift,
    )


def compare_all_strategies(
    prices: pd.DataFrame,
    features: dict[str, pd.DataFrame],
    *,
    context: dict[str, Any] | None = None,
    cost_bps: float = 5.0,
    agent_use_llm: bool = False,
    ml_top_n: int = 3,
    regime: str | None = None,
) -> CompareAllResult:
    """Backtest momentum, agent, and ML; pick best Sharpe (regime-aware tie-break)."""
    symbols = list(prices.columns)
    ctx = {**(context or {}), "offline": not agent_use_llm}
    candidates: dict[str, Strategy] = {
        "momentum": MomentumSentimentStrategy(top_n=min(ml_top_n, 3)),
        "agent": AgentStrategy(use_llm=agent_use_llm, offline=not agent_use_llm, symbols=symbols),
        "ml": MLSignalStrategy(top_n=ml_top_n),
    }

    metrics: dict[str, StrategyMetrics] = {}
    weight_panels: dict[str, pd.DataFrame] = {}
    for key, strategy in candidates.items():
        weights = _weights_panel(prices, strategy, features, ctx)
        bt = run_backtest(prices, weights, cost_bps=cost_bps)
        metrics[key] = StrategyMetrics.from_backtest(strategy.name, bt)
        weight_panels[key] = weights

    # Primary: max Sharpe. Tie-break / soft bias: regime preference order.
    ranked = sorted(metrics.items(), key=lambda item: item[1].sharpe, reverse=True)
    winner = ranked[0][0]
    if regime and len(ranked) > 1:
        top_sharpe = ranked[0][1].sharpe
        prefs = regime_preferred_strategies(regime)  # type: ignore[arg-type]
        near = [k for k, m in ranked if abs(m.sharpe - top_sharpe) < 0.05]
        for pref in prefs:
            if pref in near:
                winner = pref
                break

    best = metrics[winner]
    runner_up = ranked[1][1] if len(ranked) > 1 else best
    reason = (
        f"{winner} sharpe {best.sharpe:.3f} vs runner-up {runner_up.sharpe:.3f}; "
        f"dd {best.max_drawdown:.3f}"
    )
    if regime:
        reason += f"; regime={regime}"
    _log.info("compare_all: %s", reason)

    drift = 0.0
    if "momentum" in weight_panels and winner in weight_panels:
        drift = signal_drift(weight_panels["momentum"], weight_panels[winner])

    return CompareAllResult(
        strategies=metrics,
        winner=winner,
        reason=reason,
        signal_drift=drift,
    )



def signal_drift(
    champion_weights: pd.DataFrame,
    challenger_weights: pd.DataFrame,
) -> float:
    """Mean absolute weight difference as a simple drift metric."""
    aligned = champion_weights.align(challenger_weights, join="inner", axis=0)
    diff = (aligned[0] - aligned[1]).abs()
    return float(diff.mean().mean()) if not diff.empty else 0.0
