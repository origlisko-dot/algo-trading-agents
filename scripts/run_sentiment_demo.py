"""Demonstrate the Hugging Face FinBERT sentiment connector end-to-end.

Run from the project root:  python scripts/run_sentiment_demo.py
First run downloads the model (~400MB); afterwards it is cached and offline.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console

from algo_agents.connectors.sentiment import HFSentiment

_HEADLINES = [
    "Apple beats earnings expectations and raises full-year guidance",
    "Regulators open an antitrust probe into the company's app store",
    "Analysts maintain a neutral rating ahead of the product launch",
    "NVIDIA reports record data-center revenue on strong AI demand",
]


def main() -> None:
    console = Console()
    connector = HFSentiment()
    status = connector.check()
    console.print(f"[cyan]{status.name}[/]: {status.state.value} — {status.detail}\n")
    if not status.ok:
        console.print("Install NLP deps first:  pip install transformers torch")
        return

    console.print("Loading FinBERT and scoring sample headlines...\n")
    for headline, result in zip(_HEADLINES, connector.score(_HEADLINES)):
        color = {"positive": "green", "negative": "red"}.get(result["label"], "yellow")
        console.print(
            f"[{color}]{result['label']:<9}[/] "
            f"signed={result['signed']:+.3f}  conf={result['score']:.2f}  | {headline}"
        )


if __name__ == "__main__":
    main()
