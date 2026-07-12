"""AgentStrategy — LangGraph analyst layer implementing the Strategy interface."""
from __future__ import annotations

from typing import Any

import pandas as pd

from algo_agents.agents.graph import analyze_symbol
from algo_agents.config import get_settings
from algo_agents.observability.logging import bind_context, get_logger, new_run_id
from algo_agents.strategy.base import Strategy, StrategyResult

_log = get_logger(__name__)


def _features_summary(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "no features"
    last = frame.iloc[-1]
    parts = []
    for col in ("momentum_10", "trend", "rsi_14", "volatility_20"):
        if col in last and pd.notna(last[col]):
            parts.append(f"{col}={float(last[col]):.4f}")
    return ", ".join(parts) if parts else "features available"


class AgentStrategy(Strategy):
    name = "agent_strategy"

    def __init__(
        self,
        *,
        use_llm: bool | None = None,
        symbols: list[str] | None = None,
        offline: bool = False,
    ) -> None:
        self.use_llm = use_llm
        self.symbols = symbols
        self.offline = offline

    def generate_weights(
        self,
        features: dict[str, pd.DataFrame],
        context: dict[str, Any] | None = None,
    ) -> StrategyResult:
        run_id = (context or {}).get("run_id") or new_run_id()
        bind_context(run_id=run_id, agent_role="agent_strategy")
        ctx = context or {}
        allowed = set(self.symbols) if self.symbols else None
        if allowed is None and not get_settings().universe_unrestricted:
            allowed = set(get_settings().universe)
        target_symbols = list(features.keys())
        if allowed is not None:
            target_symbols = [s for s in target_symbols if s in allowed]
        offline = bool(ctx.get("offline", self.offline))
        weights: dict[str, float] = {}
        rationale: dict[str, str] = {}

        for symbol in target_symbols:
            frame = features.get(symbol)
            if frame is None or frame.empty:
                continue
            summary = _features_summary(frame)
            memory = (ctx.get("memory_context") or {}).get(symbol.upper(), "")
            if memory:
                summary = f"{summary}\nPast memory:\n{memory}"
            state = analyze_symbol(
                symbol,
                summary,
                use_llm=self.use_llm,
                offline=offline,
            )
            weight = float(state.get("final_weight", 0.0))
            if abs(weight) > 1e-9:
                weights[symbol] = weight
                rationale[symbol] = str(state.get("rationale", ""))
            _log.info("agent decision %s weight=%.4f", symbol, weight)

        if not weights:
            return StrategyResult(weights={}, rationale={"_": "no agent convictions"})
        return StrategyResult(weights=weights, rationale=rationale)
