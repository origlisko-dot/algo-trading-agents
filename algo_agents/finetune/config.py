"""Configuration objects for LoRA / QLoRA fine-tuning.

These are plain dataclasses so they can be built and inspected without importing
``peft`` / ``transformers`` (which are optional, heavier deps). ``LoRAConfig``
covers adapter placement; ``QLoRAConfig`` adds the 4/8-bit quantization of the
frozen base model that makes QLoRA memory-cheap. ``TrainingConfig`` holds the
Trainer knobs. Build defaults straight from ``Settings`` via the factories.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from algo_agents.config import Settings, get_settings


def _parse_modules(raw: str) -> list[str]:
    return [m.strip() for m in raw.split(",") if m.strip()]


@dataclass
class LoRAConfig:
    """Low-Rank Adaptation adapter hyper-parameters."""

    r: int = 8
    alpha: int = 16
    dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["query", "value"])
    bias: str = "none"
    task_type: str = "SEQ_CLS"

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> LoRAConfig:
        s = settings or get_settings()
        return cls(
            r=s.lora_r,
            alpha=s.lora_alpha,
            dropout=s.lora_dropout,
            target_modules=_parse_modules(s.lora_target_modules),
        )


@dataclass
class QLoRAConfig:
    """QLoRA = LoRA adapters on top of a quantized (4/8-bit) frozen base model.

    The quantization requires ``bitsandbytes`` and a CUDA GPU at *runtime*; the
    config itself is inert and safe to construct anywhere.
    """

    lora: LoRAConfig = field(default_factory=LoRAConfig)
    bits: int = 4
    double_quant: bool = True
    quant_type: str = "nf4"
    compute_dtype: str = "bfloat16"

    def __post_init__(self) -> None:
        if self.bits not in (4, 8):
            raise ValueError(f"qlora bits must be 4 or 8, got {self.bits}")

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> QLoRAConfig:
        s = settings or get_settings()
        return cls(lora=LoRAConfig.from_settings(s), bits=s.qlora_bits)


@dataclass
class TrainingConfig:
    """Trainer knobs shared by the LoRA and QLoRA paths."""

    base_model: str = "ProsusAI/finbert"
    output_dir: str = "./runs/finetune"
    num_labels: int = 3
    epochs: float = 1.0
    batch_size: int = 8
    learning_rate: float = 2e-4
    max_length: int = 128

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> TrainingConfig:
        s = settings or get_settings()
        return cls(
            base_model=s.finetune_base_model,
            output_dir=s.finetune_output_dir,
            num_labels=s.finetune_num_labels,
            epochs=s.finetune_epochs,
            batch_size=s.finetune_batch_size,
            learning_rate=s.finetune_lr,
            max_length=s.finetune_max_length,
        )
