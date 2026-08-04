"""Tiny labeled financial-sentiment dataset for LoRA/QLoRA demos and tests.

Real fine-tuning should swap this for a curated corpus (e.g. Financial
PhraseBank). This built-in set keeps the demo self-contained and offline.
Label ids: 0=negative, 1=neutral, 2=positive.
"""
from __future__ import annotations

from typing import Any

LABELS: list[str] = ["negative", "neutral", "positive"]
LABEL2ID: dict[str, int] = {name: i for i, name in enumerate(LABELS)}
ID2LABEL: dict[int, str] = {i: name for i, name in enumerate(LABELS)}

_EXAMPLES: list[tuple[str, int]] = [
    ("Company beats earnings expectations and raises full-year guidance", 2),
    ("Record data-center revenue driven by strong AI demand", 2),
    ("Shares surge after the board approves a large buyback", 2),
    ("Analysts upgrade the stock to buy on improving margins", 2),
    ("Quarterly profit doubles as new products gain traction", 2),
    ("Firm reports steady revenue in line with prior guidance", 1),
    ("The company maintains its dividend and reaffirms outlook", 1),
    ("Trading was quiet ahead of the scheduled product launch", 1),
    ("Management keeps forecasts unchanged pending market review", 1),
    ("Analysts hold a neutral rating with no change to targets", 1),
    ("Regulators open an antitrust probe into the company", 0),
    ("Shares plunge after the firm slashes its revenue outlook", 0),
    ("The company warns of weak demand and mounting losses", 0),
    ("Recall of a flagship product triggers a sharp selloff", 0),
    ("Credit downgrade raises concerns over rising debt levels", 0),
]


def demo_sentiment_examples() -> list[tuple[str, int]]:
    """Return (text, label_id) pairs for the built-in demo corpus."""
    return list(_EXAMPLES)


def demo_sentiment_dataset() -> dict[str, list[Any]]:
    """Return the demo corpus as column-oriented lists: {"text": [...], "label": [...]}."""
    texts, labels = zip(*_EXAMPLES, strict=True)
    return {"text": list(texts), "label": list(labels)}
