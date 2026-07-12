"""Phase 1 ML signal: logistic regression on technical features."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from algo_agents.strategy.base import Strategy, StrategyResult

FEATURE_COLS = (
    "return_1d",
    "momentum_10",
    "volatility_20",
    "rsi_14",
    "volume_zscore",
    "trend",
)


class MLSignalStrategy(Strategy):
    """Cross-sectional classifier: predict next-day up-move, go long top names."""

    name = "ml_signal"

    def __init__(self, top_n: int = 5, train_frac: float = 0.7) -> None:
        self.top_n = top_n
        self.train_frac = train_frac
        self._coef: np.ndarray | None = None
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None

    def _build_panel(self, features: dict[str, pd.DataFrame]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for symbol, frame in features.items():
            if frame.empty:
                continue
            usable = frame.dropna(subset=list(FEATURE_COLS) + ["close"])
            if len(usable) < 30:
                continue
            part = usable.copy()
            part["symbol"] = symbol
            part["label"] = (part["close"].shift(-1) > part["close"]).astype(float)
            rows.append(part)
        if not rows:
            return pd.DataFrame()
        return pd.concat(rows, axis=0).dropna(subset=list(FEATURE_COLS) + ["label"])

    def fit(self, features: dict[str, pd.DataFrame]) -> bool:
        panel = self._build_panel(features)
        if panel.empty:
            return False
        split_idx = int(len(panel) * self.train_frac)
        train = panel.iloc[:split_idx]
        if train.empty:
            return False
        x = train[list(FEATURE_COLS)].to_numpy(dtype=float)
        y = train["label"].to_numpy(dtype=float)
        self._mean = x.mean(axis=0)
        self._std = x.std(axis=0)
        self._std[self._std == 0] = 1.0
        x_norm = (x - self._mean) / self._std
        x_bias = np.c_[np.ones(len(x_norm)), x_norm]
        try:
            self._coef = np.linalg.lstsq(x_bias, y, rcond=None)[0]
        except np.linalg.LinAlgError:
            return False
        return True

    def _score_latest(self, features: dict[str, pd.DataFrame]) -> dict[str, float]:
        if self._coef is None or self._mean is None or self._std is None:
            return {}
        scores: dict[str, float] = {}
        for symbol, frame in features.items():
            if frame.empty:
                continue
            usable = frame.dropna(subset=list(FEATURE_COLS))
            if usable.empty:
                continue
            row = usable.iloc[-1]
            x = row[list(FEATURE_COLS)].to_numpy(dtype=float)
            x_norm = (x - self._mean) / self._std
            prob = float(np.dot(np.r_[1.0, x_norm], self._coef))
            scores[symbol] = prob
        return scores

    def generate_weights(
        self,
        features: dict[str, pd.DataFrame],
        context: dict[str, Any] | None = None,
    ) -> StrategyResult:
        if self._coef is None and not self.fit(features):
            return StrategyResult(weights={}, rationale={"_": "ML model not trained"})

        scores = self._score_latest(features)
        if not scores:
            return StrategyResult(weights={}, rationale={"_": "no scored symbols"})

        ranked = sorted(scores, key=scores.get, reverse=True)[: self.top_n]
        positive = [s for s in ranked if scores[s] > 0.5]
        if not positive:
            return StrategyResult(
                weights={},
                rationale={"_": "no symbols above 0.5 probability threshold"},
            )
        weight = 1.0 / len(positive)
        weights = {symbol: weight for symbol in positive}
        rationale = {
            s: f"ml_prob={scores[s]:.3f} rank={ranked.index(s) + 1}" for s in positive
        }
        return StrategyResult(weights=weights, rationale=rationale)

    def generate_oos_weights(
        self, features: dict[str, pd.DataFrame]
    ) -> tuple[pd.DataFrame, StrategyResult]:
        """Train in-sample, return daily weight panel for the OOS tail + latest decision."""
        panel = self._build_panel(features)
        if panel.empty:
            return pd.DataFrame(), StrategyResult(weights={}, rationale={"_": "empty panel"})

        split_idx = int(len(panel) * self.train_frac)
        train = panel.iloc[:split_idx]
        test = panel.iloc[split_idx:]
        if train.empty or test.empty:
            return pd.DataFrame(), StrategyResult(weights={}, rationale={"_": "insufficient OOS rows"})

        x_train = train[list(FEATURE_COLS)].to_numpy(dtype=float)
        y_train = train["label"].to_numpy(dtype=float)
        self._mean = x_train.mean(axis=0)
        self._std = x_train.std(axis=0)
        self._std[self._std == 0] = 1.0
        x_train_norm = (x_train - self._mean) / self._std
        x_bias = np.c_[np.ones(len(x_train_norm)), x_train_norm]
        self._coef = np.linalg.lstsq(x_bias, y_train, rcond=None)[0]

        weight_rows: list[dict[str, float]] = []
        index: list[Any] = []
        for ts, group in test.groupby(level=0):
            day_scores = {}
            for _, row in group.iterrows():
                x = row[list(FEATURE_COLS)].to_numpy(dtype=float)
                x_norm = (x - self._mean) / self._std
                day_scores[str(row["symbol"])] = float(np.dot(np.r_[1.0, x_norm], self._coef))
            ranked = sorted(day_scores, key=day_scores.get, reverse=True)[: self.top_n]
            picks = [s for s in ranked if day_scores[s] > 0.5]
            row_weights = {s: 0.0 for s in features}
            if picks:
                w = 1.0 / len(picks)
                for s in picks:
                    row_weights[s] = w
            weight_rows.append(row_weights)
            index.append(ts)

        weights_df = pd.DataFrame(weight_rows, index=pd.Index(index)).sort_index()
        latest = self.generate_weights(features)
        return weights_df, latest
