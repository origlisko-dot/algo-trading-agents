"""Readiness checks for the fine-tuning stack (mirrors connector health checks).

Reports each optional dependency as a ``ConnectorStatus`` so the whole
fine-tuning capability can be introspected before any training call — exactly
like ``scripts/check_connections.py`` does for connectors.
"""
from __future__ import annotations

import importlib.util

from algo_agents.connectors.base import ConnectorState, ConnectorStatus


def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def cuda_available() -> bool:
    """True when a CUDA GPU is usable (required for QLoRA quantization)."""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def lora_supported() -> bool:
    """LoRA needs peft + transformers + accelerate; it runs on CPU or GPU."""
    return all(_installed(m) for m in ("peft", "transformers", "accelerate"))


def qlora_supported() -> bool:
    """QLoRA additionally needs bitsandbytes AND a CUDA GPU at runtime."""
    return lora_supported() and _installed("bitsandbytes") and cuda_available()


def finetune_status() -> list[ConnectorStatus]:
    """Per-component readiness for the LoRA / QLoRA stack."""
    report: list[ConnectorStatus] = []

    for module, hint in (
        ("peft", "pip install peft"),
        ("transformers", "pip install transformers torch"),
        ("accelerate", "pip install accelerate"),
        ("datasets", "pip install datasets"),
    ):
        if _installed(module):
            report.append(ConnectorStatus(module, ConnectorState.READY, "importable"))
        else:
            report.append(ConnectorStatus(module, ConnectorState.MISSING_DEPENDENCY, hint))

    # LoRA overall.
    report.append(
        ConnectorStatus(
            "lora",
            ConnectorState.READY if lora_supported() else ConnectorState.MISSING_DEPENDENCY,
            "ready (CPU or GPU)" if lora_supported() else "pip install peft accelerate",
        )
    )

    # bitsandbytes + CUDA gate QLoRA.
    if not _installed("bitsandbytes"):
        report.append(
            ConnectorStatus("bitsandbytes", ConnectorState.MISSING_DEPENDENCY, "pip install bitsandbytes")
        )
    elif not cuda_available():
        report.append(
            ConnectorStatus(
                "bitsandbytes",
                ConnectorState.NOT_RUNNING,
                "installed but no CUDA GPU (4/8-bit QLoRA needs a GPU)",
            )
        )
    else:
        report.append(ConnectorStatus("bitsandbytes", ConnectorState.READY, "4/8-bit ready"))

    report.append(
        ConnectorStatus(
            "qlora",
            ConnectorState.READY if qlora_supported() else ConnectorState.NOT_RUNNING,
            "ready (GPU)" if qlora_supported() else "needs bitsandbytes + CUDA GPU",
        )
    )
    return report
