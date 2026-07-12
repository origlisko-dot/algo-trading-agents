"""Baseline long-only strategy: trend filter + momentum, tilted by sentiment.

This is a transparent starting point for the research loop, NOT a proven
edge. Validate it out-of-sample with realistic costs before trusting it.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from algo_agents.strategy.base import Strategy, StrategyResult


class MomentumSentimentStrategy(Strategy):
    name = "momentum_sentiment"

    def __init__(self, top_n: int = 3, sentiment_weight: float = 0.3) -> None:
        self.top_n = top_n
        self.sentiment_weight = sentiment_weight

    def generate_weights(
        self,
        features: dict[str, pd.DataFrame],
        context: dict[str, Any] | None = None,
    ) -> StrategyResult:
        sentiment: dict[str, float] = (context or {}).get("sentiment", {})
        scores: dict[str, float] = {}
        rationale: dict[str, str] = {}

        for symbol, frame in features.items():
            if frame.empty or "momentum_10" not in frame:
                continue
            last = frame.iloc[-1]
            uptrend = float(last.get("trend", 0)) > 0
            momentum = float(last.get("momentum_10", 0) or 0)
            if not uptrend or momentum <= 0:
                continue
            sent = float(sentiment.get(symbol, 0.0))
            scores[symbol] = momentum + self.sentiment_weight * sent
            rationale[symbol] = (
                f"uptrend, momentum_10={momentum:.3f}, sentiment={sent:+.2f}"
            )

        if not scores:
            return StrategyResult(weights={}, rationale={"_": "no qualifying longs"})

        ranked = sorted(scores, key=scores.get, reverse=True)[: self.top_n]
        weight = 1.0 / len(ranked)
        weights = {symbol: weight for symbol in ranked}
        return StrategyResult(weights=weights, rationale={s: rationale[s] for s in ranked})
