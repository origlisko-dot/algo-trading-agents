"""Demonstrate the LoRA / QLoRA fine-tuning infrastructure end-to-end.

Run from the project root:
    python scripts/run_finetune_demo.py                 # LoRA on the demo model
    python scripts/run_finetune_demo.py --qlora         # attempt QLoRA (needs a CUDA GPU)
    python scripts/run_finetune_demo.py --base ProsusAI/finbert

By default it uses a tiny model so a full fine-tune runs in seconds on CPU. It
trains LoRA adapters on a built-in financial-sentiment corpus, saves the
adapter, reloads it, and scores fresh headlines.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from rich.console import Console
from rich.table import Table

from algo_agents.finetune import (
    ID2LABEL,
    LoRAConfig,
    LoRAFineTuner,
    QLoRAConfig,
    TrainingConfig,
    demo_sentiment_examples,
    finetune_status,
    lora_supported,
)

_DEFAULT_MODEL = "hf-internal-testing/tiny-random-BertForSequenceClassification"
_EVAL_HEADLINES = [
    "Company crushes earnings and lifts guidance for the year",
    "Regulators launch a probe as shares tumble on weak demand",
    "Board reaffirms the outlook with no change to targets",
]


def _print_status(console: Console) -> None:
    table = Table(title="fine-tuning stack readiness")
    table.add_column("component")
    table.add_column("state")
    table.add_column("detail")
    for status in finetune_status():
        color = {"READY": "green", "NOT_RUNNING": "yellow"}.get(status.state.value, "red")
        table.add_row(status.name, f"[{color}]{status.state.value}[/]", status.detail)
    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="LoRA / QLoRA fine-tuning demo")
    parser.add_argument("--base", default=_DEFAULT_MODEL, help="base HF model id")
    parser.add_argument("--qlora", action="store_true", help="use 4-bit QLoRA (requires CUDA GPU)")
    parser.add_argument("--epochs", type=float, default=3.0)
    args = parser.parse_args()

    console = Console()
    _print_status(console)

    if not lora_supported():
        console.print("\n[red]LoRA stack unavailable.[/] Install: pip install peft accelerate transformers torch")
        return

    training = TrainingConfig(
        base_model=args.base,
        output_dir="./runs/finetune",
        num_labels=3,
        epochs=args.epochs,
        batch_size=8,
        learning_rate=5e-3,
    )
    if args.qlora:
        tuner = LoRAFineTuner(training=training, qlora=QLoRAConfig())
    else:
        tuner = LoRAFineTuner(training=training, lora=LoRAConfig())

    console.print(f"\n[cyan]Fine-tuning[/] mode=[bold]{tuner.mode}[/] base=[bold]{args.base}[/]\n")
    try:
        metrics = tuner.train(demo_sentiment_examples())
    except RuntimeError as exc:
        console.print(f"[yellow]{tuner.mode} unavailable:[/] {exc}")
        console.print("Falling back to plain LoRA is recommended on CPU-only hosts.")
        return

    table = Table(title=f"{metrics['mode']} training result")
    table.add_column("metric")
    table.add_column("value")
    table.add_row("base_model", str(metrics["base_model"]))
    table.add_row("train_loss", f"{metrics['train_loss']:.4f}")
    table.add_row("trainable_params", f"{metrics['trainable_params']:,}")
    table.add_row("all_params", f"{metrics['all_params']:,}")
    table.add_row("trainable_pct", f"{metrics['trainable_pct']}%")
    table.add_row("adapter_dir", str(metrics["adapter_dir"]))
    console.print(table)

    _score_with_adapter(console, metrics["adapter_dir"], training.base_model)


def _score_with_adapter(console: Console, adapter_dir: str, base_model: str) -> None:
    """Reload the saved adapter on top of the base model and classify headlines."""
    import torch
    from peft import PeftModel
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    console.print("\n[cyan]Reloading saved adapter and scoring fresh headlines...[/]\n")
    tokenizer = AutoTokenizer.from_pretrained(adapter_dir)
    base = AutoModelForSequenceClassification.from_pretrained(
        base_model, num_labels=3, ignore_mismatched_sizes=True
    )
    model = PeftModel.from_pretrained(base, adapter_dir)
    model.eval()

    enc = tokenizer(_EVAL_HEADLINES, truncation=True, padding=True, return_tensors="pt")
    with torch.no_grad():
        logits = model(**enc).logits
    preds = logits.argmax(dim=-1).tolist()
    for headline, pred in zip(_EVAL_HEADLINES, preds):
        label = ID2LABEL.get(int(pred), str(pred))
        color = {"positive": "green", "negative": "red"}.get(label, "yellow")
        console.print(f"[{color}]{label:<9}[/] | {headline}")


if __name__ == "__main__":
    main()
