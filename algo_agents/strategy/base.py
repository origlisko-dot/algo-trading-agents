"""Weight-centric strategy contract.

Every strategy outputs a target weight per symbol (long > 0, short < 0). The
same interface is used in backtest and live, so research results stay
consistent with deployment (the FinRL-X principle).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class StrategyResult:
    weights: dict[str, float]
    rationale: dict[str, str] = field(default_factory=dict)

    def gross_exposure(self) -> float:
        return sum(abs(w) for w in self.weights.values())


class Strategy(ABC):
    name: str = "strategy"

    @abstractmethod
    def generate_weights(
        self,
        features: dict[str, pd.DataFrame],
        context: dict[str, Any] | None = None,
    ) -> StrategyResult:
        """Map per-symbol feature frames to target portfolio weights."""
