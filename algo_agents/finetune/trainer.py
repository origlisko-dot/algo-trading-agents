"""LoRA / QLoRA fine-tuning for Hugging Face sequence classifiers (e.g. FinBERT).

The trainer freezes the base model and trains only small LoRA adapters. In QLoRA
mode the base model is additionally loaded in 4/8-bit (bitsandbytes) — which
requires a CUDA GPU; on CPU-only hosts QLoRA raises a clear, early error while
plain LoRA still runs. Heavy deps are imported lazily so importing this module
never fails when peft/transformers are absent.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from algo_agents.finetune.config import LoRAConfig, QLoRAConfig, TrainingConfig
from algo_agents.finetune.status import cuda_available
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)


def count_parameters(model: Any) -> tuple[int, int]:
    """Return (trainable_params, all_params)."""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


class _TokenizedDataset:
    """Minimal map-style dataset of pre-tokenized, uniformly-padded examples."""

    def __init__(self, encodings: dict[str, Any], labels: list[int]) -> None:
        import torch

        self._encodings = encodings
        self._labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self) -> int:
        return len(self._labels)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = {k: v[idx] for k, v in self._encodings.items()}
        item["labels"] = self._labels[idx]
        return item


class LoRAFineTuner:
    """Fine-tune a sequence classifier with LoRA (or QLoRA when a GPU is present)."""

    def __init__(
        self,
        training: TrainingConfig | None = None,
        lora: LoRAConfig | None = None,
        qlora: QLoRAConfig | None = None,
    ) -> None:
        self.training = training or TrainingConfig()
        self.qlora = qlora
        # In QLoRA mode the adapter config lives inside the QLoRAConfig.
        self.lora = qlora.lora if qlora is not None else (lora or LoRAConfig())

    @property
    def is_qlora(self) -> bool:
        return self.qlora is not None

    @property
    def mode(self) -> str:
        return "qlora" if self.is_qlora else "lora"

    def build_peft_config(self) -> Any:
        from peft import LoraConfig, TaskType

        task = getattr(TaskType, self.lora.task_type, TaskType.SEQ_CLS)
        return LoraConfig(
            task_type=task,
            r=self.lora.r,
            lora_alpha=self.lora.alpha,
            lora_dropout=self.lora.dropout,
            target_modules=self.lora.target_modules,
            bias=self.lora.bias,
        )

    def build_quantization_config(self) -> Any | None:
        """Return a BitsAndBytesConfig for QLoRA, or None for plain LoRA.

        Raises early with an actionable message when QLoRA is requested but the
        runtime cannot support it (missing bitsandbytes or no CUDA GPU).
        """
        if not self.is_qlora:
            return None

        import importlib.util

        if importlib.util.find_spec("bitsandbytes") is None:
            raise RuntimeError("QLoRA requires bitsandbytes: pip install bitsandbytes")
        if not cuda_available():
            raise RuntimeError(
                "QLoRA requires a CUDA GPU for 4/8-bit quantization; none is available. "
                "Use plain LoRA (qlora=None) on CPU."
            )

        import torch
        from transformers import BitsAndBytesConfig

        assert self.qlora is not None
        compute_dtype = getattr(torch, self.qlora.compute_dtype, torch.float16)
        if self.qlora.bits == 4:
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type=self.qlora.quant_type,
                bnb_4bit_use_double_quant=self.qlora.double_quant,
                bnb_4bit_compute_dtype=compute_dtype,
            )
        return BitsAndBytesConfig(load_in_8bit=True)

    def load_tokenizer(self) -> Any:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(self.training.base_model)

    def load_model(self) -> Any:
        """Load the base classifier, quantize for QLoRA, and attach LoRA adapters."""
        from peft import get_peft_model, prepare_model_for_kbit_training
        from transformers import AutoModelForSequenceClassification

        quant_config = self.build_quantization_config()
        kwargs: dict[str, Any] = {
            "num_labels": self.training.num_labels,
            "ignore_mismatched_sizes": True,
        }
        if quant_config is not None:
            kwargs["quantization_config"] = quant_config

        model = AutoModelForSequenceClassification.from_pretrained(
            self.training.base_model, **kwargs
        )
        if quant_config is not None:
            model = prepare_model_for_kbit_training(model)

        model = get_peft_model(model, self.build_peft_config())
        return model

    def train(self, examples: list[tuple[str, int]], *, output_dir: str | None = None) -> dict[str, Any]:
        """Run LoRA/QLoRA training on (text, label) pairs; save the adapter; return metrics."""
        from transformers import Trainer, TrainingArguments, default_data_collator

        out_dir = Path(output_dir or self.training.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        tokenizer = self.load_tokenizer()
        model = self.load_model()
        trainable, total = count_parameters(model)
        _log.info(
            "finetune mode=%s base=%s trainable=%d/%d (%.2f%%)",
            self.mode,
            self.training.base_model,
            trainable,
            total,
            100.0 * trainable / max(total, 1),
        )

        texts = [t for t, _ in examples]
        labels = [int(y) for _, y in examples]
        encodings = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=self.training.max_length,
            return_tensors="pt",
        )
        dataset = _TokenizedDataset(dict(encodings), labels)

        args = TrainingArguments(
            output_dir=str(out_dir),
            num_train_epochs=self.training.epochs,
            per_device_train_batch_size=self.training.batch_size,
            learning_rate=self.training.learning_rate,
            logging_steps=1,
            save_strategy="no",
            report_to=[],
        )
        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=dataset,
            data_collator=default_data_collator,
        )
        result = trainer.train()

        adapter_dir = out_dir / "adapter"
        model.save_pretrained(str(adapter_dir))
        tokenizer.save_pretrained(str(adapter_dir))

        return {
            "mode": self.mode,
            "base_model": self.training.base_model,
            "train_loss": float(getattr(result, "training_loss", 0.0) or 0.0),
            "trainable_params": trainable,
            "all_params": total,
            "trainable_pct": round(100.0 * trainable / max(total, 1), 4),
            "adapter_dir": str(adapter_dir),
            "num_examples": len(examples),
        }
