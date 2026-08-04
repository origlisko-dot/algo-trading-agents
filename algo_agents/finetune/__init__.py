"""LoRA / QLoRA fine-tuning infrastructure for Hugging Face models.

Adapt the sentiment classifier (or any HF sequence classifier) to your own
labeled data with tiny, swappable LoRA adapters. Everything degrades
gracefully: importing this package never requires peft/transformers, and QLoRA
reports clearly when a CUDA GPU is unavailable. See `scripts/run_finetune_demo.py`.
"""
from __future__ import annotations

from algo_agents.finetune.config import LoRAConfig, QLoRAConfig, TrainingConfig
from algo_agents.finetune.data import (
    ID2LABEL,
    LABEL2ID,
    LABELS,
    demo_sentiment_dataset,
    demo_sentiment_examples,
)
from algo_agents.finetune.status import (
    cuda_available,
    finetune_status,
    lora_supported,
    qlora_supported,
)
from algo_agents.finetune.trainer import LoRAFineTuner, count_parameters

__all__ = [
    "LoRAConfig",
    "QLoRAConfig",
    "TrainingConfig",
    "LoRAFineTuner",
    "count_parameters",
    "finetune_status",
    "lora_supported",
    "qlora_supported",
    "cuda_available",
    "demo_sentiment_examples",
    "demo_sentiment_dataset",
    "LABELS",
    "LABEL2ID",
    "ID2LABEL",
]
