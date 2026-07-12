"""Strategy selection and auto-promotion for AGENTIC-OS."""
from __future__ import annotations

from algo_agents.config import Settings
from algo_agents.os.artifacts import read_active_strategy, read_latest_monitor_verdict
from algo_agents.strategy.agent_strategy import AgentStrategy
from algo_agents.strategy.base import Strategy
from algo_agents.strategy.example_strategy import MomentumSentimentStrategy
from algo_agents.strategy.ml_signal_strategy import MLSignalStrategy


def resolve_strategy(
    settings: Settings,
    *,
    name: str | None = None,
    mock: bool = False,
    top_n: int = 5,
) -> Strategy:
    choice = (name or settings.default_strategy).strip().lower()

    if choice == "auto":
        active = read_active_strategy()
        if active and active.get("strategy"):
            choice = str(active["strategy"]).lower()
        else:
            verdict = read_latest_monitor_verdict()
            if verdict and verdict.get("winner"):
                choice = str(verdict["winner"]).lower()
            elif verdict and verdict.get("challenger_wins"):
                choice = "agent"
            else:
                choice = "momentum"

    if choice in ("agent", "llm", "agent_strategy"):
        return AgentStrategy(use_llm=not mock, offline=mock)
    if choice in ("ml", "ml_signal"):
        return MLSignalStrategy(top_n=top_n)
    if choice in ("momentum", "baseline", "champion", "momentum_sentiment"):
        return MomentumSentimentStrategy(top_n=min(top_n, 3))

    return AgentStrategy(use_llm=not mock, offline=mock)
