"""Hugging Face financial-sentiment connector (FinBERT by default).

Turns raw news/filing text into a signed sentiment score in [-1, 1] that the
feature layer aggregates per ticker per day. Runs locally; CPU is sufficient
for FinBERT. Swap FINBERT_MODEL in .env for FinGPT or any HF text-classifier.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

from algo_agents.config import get_settings
from algo_agents.connectors.base import (
    ConnectorState,
    ConnectorStatus,
    SentimentConnector,
)

try:
    from transformers import pipeline

    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False

_SIGN = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}
_MODEL_LOAD_TIMEOUT_SEC = 15


class HFSentiment(SentimentConnector):
    name = "hf_sentiment"

    def __init__(self) -> None:
        self._model_name = get_settings().finbert_model
        self._pipe: Any = None
        self._load_failed = False

    def _pipe_or_none(self) -> Any:
        if not _TRANSFORMERS_AVAILABLE or self._load_failed:
            return None
        if self._pipe is None:
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    self._pipe = pool.submit(
                        pipeline, "sentiment-analysis", model=self._model_name
                    ).result(timeout=_MODEL_LOAD_TIMEOUT_SEC)
            except FuturesTimeoutError:
                self._load_failed = True
                return None
            except Exception:
                self._load_failed = True
                return None
        return self._pipe

    def check(self) -> ConnectorStatus:
        if not _TRANSFORMERS_AVAILABLE:
            return ConnectorStatus(
                self.name,
                ConnectorState.MISSING_DEPENDENCY,
                "pip install transformers torch",
            )
        if self._load_failed:
            return ConnectorStatus(
                self.name,
                ConnectorState.ERROR,
                f"model '{self._model_name}' failed to load",
            )
        return ConnectorStatus(
            self.name,
            ConnectorState.READY,
            f"model '{self._model_name}' loads on first score() call",
        )

    def score(self, texts: list[str]) -> list[dict[str, Any]]:
        pipe = self._pipe_or_none()
        if pipe is None:
            raise RuntimeError("transformers model unavailable")
        if not texts:
            return []
        results = pipe(texts, truncation=True)
        scored: list[dict[str, Any]] = []
        for res in results:
            label = res["label"].lower()
            score = float(res["score"])
            scored.append(
                {"label": label, "score": score, "signed": _SIGN.get(label, 0.0) * score}
            )
        return scored
